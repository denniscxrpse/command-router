#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "CommandRouter",
    "Control",
    "ControlInitialization",
    "ControlResult",
)

import tomllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import json5
from icecream import ic

from cmd_router.api import Control, ControlInitialization, ControlResult, listener
from cmd_router.lib.grammar.loader import *
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *

_Dict = dict[str, Any]


class _CmdRouter:
    grammars: _Dict = {}
    info: _Dict = {}
    control = Control()

    def normalize(self, t: tuple[_Dict, _Dict]) -> None:
        grammars, info = t
        self.grammars.update(grammars)
        self.info.update(info)
        log.debug(
            "normalized grammar batch (commands=%d, info_keys=%s, totals=%d)",
            len(grammars),
            tuple(info),
            len(self.grammars),
        )

    def lazy_init(self) -> None:
        """Load the first valid grammar received through the local HTTP endpoint."""

        log.info("starting lazy grammar server")
        # Keep HTTP grammars in a persistent cache between application runs.
        http_dir = paths.FIXTURES_HTTP
        # Stop serving requests after one grammar loads successfully.
        state = {"success": False}
        # Let the request handler update this router instance.
        router = self

        # Define the small HTTP protocol used to receive a grammar.
        class _Handler(BaseHTTPRequestHandler):
            def _reply(self, status: int, body: bytes = b"") -> None:
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _invalid(self, message: str) -> None:
                log.warning("lazy request rejected: %s", message)
                log.error("rejecting malformed lazy request; waiting for another request")
                log.stderr(1)
                self._reply(400, b"1\n")

            # noinspection pep8-naming
            def do_POST(self) -> None:
                log.debug("lazy server received POST request for %s", self.path)
                # Read and validate the request body length.
                try:
                    content_length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    self._invalid("Invalid HTTP content length.")
                    return

                if content_length < 0:
                    self._invalid("HTTP request has no content.")
                    return

                # Decode the grammar as UTF-8 text.
                payload = self.rfile.read(content_length)
                log.debug("lazy request body read (%d byte(s))", len(payload))
                try:
                    text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    self._invalid("HTTP grammar is not valid UTF-8.")
                    return

                # Detect whether the body is a JSON5 or TOML object.
                suffix: str | None = None
                for candidate, parser in ((".json5", json5.loads), (".toml", tomllib.loads)):
                    try:
                        parsed = parser(text)
                    except ValueError, tomllib.TOMLDecodeError:
                        continue
                    if isinstance(parsed, dict):
                        suffix = candidate
                        break

                if suffix is None:
                    self._invalid("HTTP body is not valid JSON5 or TOML.")
                    return
                log.debug("lazy request recognized as %s", suffix)

                # Reuse an identical grammar already saved by an earlier run.
                existing: Path | None = None
                try:
                    for candidate in http_dir.glob(f"grammar-*{suffix}"):
                        try:
                            if candidate.is_file() and candidate.read_bytes() == payload:
                                existing = candidate
                                break
                        except OSError:
                            continue
                except OSError:
                    # Handle the request as new when the cache cannot be scanned.
                    log.warning("could not scan the persisted lazy grammar cache")
                    log.error("continuing with this request as a new grammar")

                if existing is not None:
                    # Load the cached grammar into this router instance.
                    log.info("reusing persisted lazy grammar %s", existing.name)
                    result = load_grammars(existing)
                    if isinstance(result, int):
                        self._invalid("HTTP grammar has an invalid schema.")
                        return

                    router.normalize(result)
                    log.stderr(0)
                    log.debug("reused grammar normalized (%d command(s))", len(result[0]))
                    state["success"] = True
                    self._reply(204)
                    return

                # Save unseen grammars under a unique filename.
                target = http_dir / f"grammar-{uuid4().hex}{suffix}"
                try:
                    http_dir.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                    result = load_grammars(target)
                except OSError as exception:
                    log.error("could not persist lazy grammar %s: %s", target, exception)
                    self._invalid("Could not save the HTTP grammar.")
                    return

                # Remove files that fail schema validation.
                if isinstance(result, int):
                    target.unlink(missing_ok=True)
                    self._invalid("HTTP grammar has an invalid schema.")
                    return

                # Store the grammar and signal that initialization is complete.
                router.normalize(result)
                log.stderr(0)
                log.info("saved and loaded lazy grammar %s", target.name)
                log.debug("saved grammar normalized (%d command(s))", len(result[0]))
                state["success"] = True
                self._reply(204)

            # pyrefly: ignore [bad-override]
            def log_message(self, *_args: Any) -> None:
                # The lazy protocol reserves stderr for the port and errors.
                return

        # Bind an ephemeral localhost port and announce it to the client.
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        log.info("lazy grammar server listening on localhost")
        log.stderr(server.server_port)
        try:
            # Process requests until a valid grammar is accepted.
            while not state["success"]:
                server.handle_request()
        finally:
            # Always release the listening socket.
            server.server_close()
            log.info("lazy grammar server stopped")
            log.raw("lazy grammar server: ", end="")
            log.raw("OK" if state["success"] else "FAILURE")

    def grammar_init(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | int:
        files = f if isinstance(f, list) else [f]
        log.info("loading %d grammar file(s)", len(files))

        # Keep bare filenames fast while also accepting full file or directory paths.
        ignored_names: set[str] = set()
        ignored_paths: set[Path] = set()
        for value in flags.ignore:
            candidate = Path(value).expanduser()
            if not candidate.is_absolute() and len(candidate.parts) == 1 and not candidate.is_dir():
                ignored_names.add(candidate.name)
                continue
            try:
                ignored_paths.add(candidate.resolve())
            except OSError, RuntimeError:
                ignored_paths.add(candidate.absolute())

        # Load grammars unless their name or path was explicitly ignored.
        for file in files:
            if file.name in ignored_names:
                log.debug("ignoring grammar file by name: %s", file.name)
                continue
            if ignored_paths:
                try:
                    file_path = file.resolve()
                except OSError, RuntimeError:
                    file_path = file.absolute()
                if any(file_path == ignored or ignored in file_path.parents for ignored in ignored_paths):
                    log.debug("ignoring grammar file by path: %s", file)
                    continue
            log.debug("loading grammar file %s", file)
            result = load_grammars(file)
            if isinstance(result, int):
                if result == error.UnsupportedGrammarFormatError:
                    log.debug("skipped unsupported grammar file %s", file)
                    continue
                log.error("grammar file %s failed with code %s", file, result)
                return result
            self.normalize(result)

        log.info("grammar loading completed (%d command(s))", len(self.grammars))
        return self.grammars, self.info

    def control_init(self) -> bool:
        """Load fixture behavior only when the control flag requests it."""
        if not flags.control:
            log.debug("control initialization disabled")
            return False
        log.info("initializing control")
        result = self.control.initialize(
            self.grammars,
            fixture=paths.FIXTURES,
            keep_help=not flags.control_no_help,
        )
        if not result.ok:
            log.error("control initialization failed (%s): %s", result.code, result.message)
            return False
        log.info("control ready (%d grammar(s))", result.command_count)
        return True


_cmd_router = _CmdRouter()


class CommandRouter:
    def __init__(self) -> None:
        log.info("initialization started")
        self._grammars = _cmd_router.grammars
        self._info = _cmd_router.info
        self.control = _cmd_router.control
        log.debug(
            "flags (lazy=%s, control=%s, control_no_help=%s, ignore=%s)",
            flags.lazy,
            flags.control,
            flags.control_no_help,
            flags.ignore,
        )

        # Get every single file in fixtures/*
        if flags.lazy:
            log.info("lazy grammar loading enabled")
            _cmd_router.lazy_init()
            ctrl_init = _cmd_router.control_init()
            if ctrl_init:
                self._control_loop()
            log.info("initialization completed")
            return

        files = [path for path in paths.FIXTURES.iterdir() if path.is_file()]
        log.debug("discovered %d fixture file(s) in %s", len(files), paths.FIXTURES)
        result = _cmd_router.grammar_init(files)
        if isinstance(result, int):
            log.error("grammar initialization failed (%s); continuing with loaded data", result)

        # The control loop doesn't necessarily need to be initialized immediately.
        ctrl_init = _cmd_router.control_init()

        log.debug("normalized grammars=%r; info=%r", self._grammars, self._info)

        # Technically, a lazy initialization is possible, but it's not worth the complexity.
        # Note: If `flags.control` is somehow false and `ctrl_init` is true, the loop will run anyway.
        #       This is intentional, since `_control_init` owns the rights to this initialization.
        if ctrl_init:
            c = self._control_loop()
            log.info("control loop exited with status %s", c)
            return

        log.info("ready (%d command grammar(s))", len(self._grammars))

    def execute(self, command: Any) -> ControlResult:
        """Execute through the configured control surface."""
        return self.control.execute(command)

    async def execute_async(self, command: Any) -> ControlResult:
        """Async counterpart to :meth:`execute`."""
        return await self.control.execute_async(command)

    @property
    def deeper_level(self) -> Any:
        """Expose the live Python control state for embedded callers."""
        return self.control.deeper_level

    def _control_loop(self) -> int:
        """Run the fixture-backed command interface until it is closed.

        The router owns this loop because the control API only knows how to
        initialize and execute a command surface; it does not know whether
        the surrounding application wants an interactive session.  Command
        failures are yet represented by ``ControlResult`` and therefore
        do not end the session.  Failures in the loop itself are converted to
        an integer status, so a bad input stream or an unexpected control
        exception cannot escape from router startup.
        """
        try:
            initialized = self.control.deeper_level.initialized
        except Exception as exception:
            log.error("router.control: cannot inspect control state before starting the loop: %s", exception)
            return error.Abort

        if not initialized:
            log.error("router.control: cannot start control loop; control is not initialized")
            return int(error.ControlNotInitializedError)

        log.info("control loop started (type 'exit'/'e' or 'quit'/'q' to stop)")
        while True:
            try:
                command = input("cmd-router> ")
            except EOFError:
                log.info("control loop reached end of input")
                return error.Succeed
            except KeyboardInterrupt:
                log.warning("control loop interrupted")
                return error.Interrupted
            except Exception as exception:
                log.error("control loop could not read input: %s", exception)
                return error.Abort

            if not isinstance(command, str):
                log.error("control loop received non-string input (%s)", type(command).__name__)
                return error.TokenizeUnsupportedTypeError

            command_marker = command.strip().casefold()
            if command_marker in ["exit", "e", "quit", "q"]:
                log.info("control loop requested to stop")
                return error.Succeed
            if not command_marker:
                log.warning("control loop received empty input! is it a typo on an error?")
                continue

            try:
                result = self.execute(command)

                if not isinstance(result, ControlResult):
                    log.error("control execution returned an invalid result")
                    return error.Abort

                if result.code == error.ControlNotInitializedError:
                    log.error("control became uninitialized while the loop was running")
                    return error.ControlNotInitializedError

                if result.ok and result.kind != "input" and result.value is not None:
                    log.info("control result: %r", result.value)

                ic(listener())
                if result.command == "help":
                    log.info(
                        "commands: '%s'\n  prefix: '%s'\n  target: '%s'",
                        result.value.get("commands", None),
                        result.value.get("prefix", None),
                        result.value.get("target", None),
                    )
            except KeyboardInterrupt:
                log.warning("control loop interrupted during command execution")
                return error.Interrupted
            except Exception as exception:
                log.error("control loop failed while executing a command: %s", exception)
                return error.Abort
