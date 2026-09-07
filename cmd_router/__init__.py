#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("CommandRouter",)

import tomllib
from http.server import HTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import json5
from icecream import ic

from cmd_router.lib.control import ControlResult
from cmd_router.lib.control.api import *
from cmd_router.lib.grammar.loader import *
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.lazy_server import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import Status, stat

_Dict = dict[str, Any]


class _CmdRouter:
    grammars: _Dict = {}
    info: _Dict = {}
    control = Api.Control

    def normalize(self, *t: _Dict) -> None:
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

        # noinspection bad-argument-type
        # Define the small HTTP protocol used to receive a grammar.
        class Lazy(LazyServer):
            # noinspection pep8-naming
            def do_POST(self) -> None:
                self.post(self.__class__.__name__)

                # Detect whether the body is a JSON5 or TOML object.
                suffix: str | None = None
                for candidate, parser in ((".json5", json5.loads), (".toml", tomllib.loads)):
                    try:
                        parsed = parser(self.text)
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
                            if candidate.is_file() and candidate.read_bytes() == self.payload:
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
                    if isinstance(result, int) or isinstance(result, Status):
                        self._invalid("HTTP grammar has an invalid schema.")
                        return

                    # noinspection not-iterable
                    router.normalize(*result)
                    log.stderr(0)
                    log.debug("reused grammar normalized (%d commands(s))", len(result[0]))
                    state["success"] = True
                    self._reply(204)
                    return

                # Save unseen grammars under a unique filename.
                target = http_dir / f"grammar-{uuid4().hex}{suffix}"
                try:
                    http_dir.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(self.payload)
                    result = load_grammars(target)
                except OSError as exception:
                    log.error("could not persist lazy grammar %s: %s", target, exception)
                    self._invalid("Could not save the HTTP grammar.")
                    return

                # Remove files that fail schema validation.
                if isinstance(result, int) or isinstance(result, Status):
                    target.unlink(missing_ok=True)
                    self._invalid("HTTP grammar has an invalid schema.")
                    return

                # Store the grammar and signal that initialization is complete.
                # noinspection not-iterable
                router.normalize(*result)
                log.stderr(0)
                log.info("saved and loaded lazy grammar %s", target.name)
                log.debug("saved grammar normalized (%d commands(s))", len(result[0]))
                state["success"] = True
                self._reply(204)

        # noinspection bad-argument-type
        # Bind an ephemeral localhost port and announce it to the client.
        server = HTTPServer(("127.0.0.1", 0), Lazy)
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

    def grammar_init(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | Status:
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
            if isinstance(result, Status):
                if result.name == stat.UnsupportedGrammarFormatError().name:
                    log.debug("skipped unsupported grammar file %s", file)
                    continue
                log.error("grammar file %s failed with code %s", file, result)
                return result
            # noinspection not-iterable
            self.normalize(*result)

        log.info("grammar loading completed (%d commands(s))", len(self.grammars))
        return self.grammars, self.info

    def control_init(self) -> bool:
        """Load fixture behavior and compile the active commands surface."""
        log.info("initializing control")
        result = self.control.initialize(
            self.grammars,
            fixture=paths.FIXTURES,
            keep_help=not flags.no_help,
        )
        if not result.ok:
            log.error("control initialization failed (%s): %s", result.code, result.message)
            return False
        log.info("control ready (%d grammar(s))", result.command_count)
        return True


_cmd_router = _CmdRouter()


class CommandRouter:
    _was_i_initialized = False
    """Literal variable to track whether the router was initialized using ``__init__``."""

    def __init__(self) -> None:
        self._grammars = _cmd_router.grammars
        self._info = _cmd_router.info
        self.control = _cmd_router.control
        self._was_i_initialized = True
        log.info("router instance was initialized. use `initialize` to actually start the router")

    @property
    def initialize(self) -> Status:
        if not self._was_i_initialized:
            return stat.ImpossibleControlState()
        log.debug(
            "flags (lazy=%s, test_suite=%s, no_help=%s, ignore=%s)",
            flags.lazy,
            flags.test_suite,
            flags.no_help,
            flags.ignore,
        )

        # Get every single file in fixtures/*
        if flags.lazy:
            log.info("lazy grammar loading enabled")
            _cmd_router.lazy_init()
            ctrl_init = _cmd_router.control_init()
            if ctrl_init and flags.test_suite:
                c = self._test_suite_loop()
                return c
            log.info("initialization completed")

        files = [path for path in paths.FIXTURES.iterdir() if path.is_file()]
        log.debug("discovered %d fixture file(s) in %s", len(files), paths.FIXTURES)
        result = _cmd_router.grammar_init(files)
        if isinstance(result, Status):
            log.error("grammar initialization failed (%s); continuing with loaded data", result)

        # The test-suite loop doesn't need to be initialized for embedded use.
        ctrl_init = _cmd_router.control_init()

        log.debug("normalized grammars=%r; info=%r", self._grammars, self._info)

        # Technically, a lazy initialization is possible, but it's not worth the complexity.
        if ctrl_init and flags.test_suite:
            c = self._test_suite_loop()
            log.info("test-suite loop exited with status %s", c)
            return c

        log.info("ready (%d commands grammar(s))", len(self._grammars))

        # The `ultima` shouldn't be instantiated when the router is embedded.
        # Values must be instantiated only when the router either successfully
        # exited or crashed.
        # We instantiate `ultima` here to avoid Python complaints.
        ultima: Status = stat.Success()
        # TODO: Once this is implemented, remove the `Success()` contract.
        #       This WILL break the test suite, so you might as well test at runtime.
        #       Or maybe just try the C# example? Up to you.
        try:
            ...
        except KeyboardInterrupt:
            log.critical("router interrupted")
            ultima = stat.Interrupted()
        return ultima

    @property
    def main(self) -> Status:
        return self.initialize

    def execute(self, command: Any) -> ControlResult:
        """Execute through the configured control surface."""
        return self.control.execute(command)

    async def execute_async(self, command: Any) -> ControlResult:
        """Async counterpart to :meth:`execute`."""
        return await self.control.execute_async(command)

    @property
    def deeper_level(self) -> Any:
        """Expose the live Python control state for embedded callers."""
        return self.control.deeper_context

    def _test_suite_loop(self) -> Status:
        """Run the fixture-backed commands interface until it is closed.

        The router owns this loop because the control API only knows how to
        initialize and execute a command surface; it does not know whether
        the surrounding application wants an interactive session.  Command
        failures are yet represented by ``ControlResult`` and therefore
        do not end the session.  Failures in the loop itself are converted to
        the status ``name`` so a bad input stream or an unexpected control
        exception cannot escape from router startup.
        """
        try:
            initialized = self.control.deeper_context.initialized
        except Exception as exception:
            log.critical("router.control: cannot inspect control state before starting the loop: %s", exception)
            return stat.Abort()

        if not initialized:
            log.error("router.control: cannot start control loop; control is not initialized")
            return stat.ControlNotInitializedError()

        log.info("control loop started (type 'exit'/'e' or 'quit'/'q' to stop)")

        while True:
            try:
                command = input("cmd-router> ")
            except EOFError:
                log.info("control loop reached end of input")
                return stat.Success()
            except KeyboardInterrupt:
                log.warning("control loop interrupted")
                return stat.Interrupted()
            except Exception as exception:
                log.critical("control loop could not read input: %s", exception)
                return stat.Abort()

            if not isinstance(command, str):
                log.error("control loop received non-string input (%s)", type(command).__name__)
                return stat.TokenizeUnsupportedTypeError()

            command_marker = command.strip().casefold()
            if command_marker in ["exit", "e", "quit", "q"]:
                log.info("control loop requested to stop")
                return stat.Success()
            if not command_marker:
                log.warning("control loop received empty input! is it a typo on an error?")
                continue

            try:
                result = self.execute(command)

                if not isinstance(result, ControlResult):
                    log.critical("control execution returned an invalid result")
                    return stat.Abort()

                was_not_initialized = stat.ControlNotInitializedError()
                if result.code.name == was_not_initialized.name:
                    log.critical("control became uninitialized while the loop was running")
                    return was_not_initialized

                if result.ok and result.kind != "input" and result.value is not None:
                    log.info("control result: %r", result.value)

                ic(Api.Surface.readable_stderr())
                if result.command == "help":
                    log.info(
                        "commands: '%s'\n  prefix: '%s'\n  target: '%s'\n suggestions: '%s'",
                        result.value.get("commands", None),
                        result.value.get("prefix", None),
                        result.value.get("target", None),
                        result.value.get("suggestions", None),
                    )
            except KeyboardInterrupt:
                log.warning("control loop interrupted during commands execution")
                return stat.Interrupted()
            except Exception as exception:
                log.critical("control loop failed while executing a commands: %s", exception)
                return stat.Abort()

        return stat.ImpossibleControlState()
