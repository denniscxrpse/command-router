#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("CommandRouter", "REPL")

import threading
import tomllib
from http.server import HTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import json5

from cmd_router.lib.control import ControlResult
from cmd_router.lib.control.api import *
from cmd_router.lib.grammar.loader import *
from cmd_router.sdk import Fixtures
from cmd_router.suggestions import *
from cmd_router.suite import *
from cmd_router.utils import LazyServer, Status, flags, log, paths, stat, uctx

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
        addr = uctx.CMD_ROUTER_DEFAULT_ADDRESS
        server = HTTPServer((addr, uctx.CMD_ROUTER_DEFAULT_PORT), Lazy)
        log.info("lazy grammar server listening on %s", addr)
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
    def initialize(self, as_router: bool = True) -> Status:
        """The main entry point for the router."""
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

        suggestions_server: HTTPServer | None = None
        if flags.no_suggestions_server:
            log.info("suggestions server completely disabled; not binding")
        else:
            # Bind even when `suggestions_server` is off, so disabled use stays
            # visible instead of a dropped connection: the handler logs at
            # error level, ignores POST bodies (204), and answers GET with an
            # empty JSON list (200), while returning SuggestionServerDisabled.
            try:
                sgs_addr = lazy_suggest_srv_ctx.address
                sgs_port = lazy_suggest_srv_ctx.port
                suggestions_server = HTTPServer((sgs_addr, sgs_port), LazySuggestionsServer)
                log.debug("initializing thread of lazy suggestions server")
                _sgs_thread = threading.Thread(
                    target=suggestions_server.serve_forever,
                    kwargs={"poll_interval": 0.2},
                    name="lazy-suggestions-server",
                    daemon=True,
                )
                _sgs_thread.start()
                log.info("lazy suggestions server listening on %s:%d", sgs_addr, suggestions_server.server_port)
            except OSError as exception:
                log.error("could not start lazy suggestions server: %s", exception)
                suggestions_server = None

        ultima: Status

        # Technically, a lazy initialization is possible, but it's not worth the complexity.
        if ctrl_init and flags.test_suite:
            log.warning("test-suite enabled, giving up control to our suite")
            try:
                ultima = self._test_suite_loop()
                log.info("test-suite loop exited with status %s", ultima)
                return ultima
            finally:
                if suggestions_server is not None:
                    suggestions_server.shutdown()
                    suggestions_server.server_close()

        log.info("ready (%d commands grammar(s))", len(self._grammars))

        # The `ultima` shouldn't be instantiated when the router is embedded.
        # Values must be instantiated only when the router either successfully
        # exited or crashed.
        # We instantiate `ultima` here to avoid Python complaints.
        ultima = stat.Success()
        try:
            ...
        except KeyboardInterrupt:
            log.critical("router interrupted")
            ultima = stat.Interrupted()
        finally:
            # Embedded use keeps the daemon server alive beyond `initialize`
            # so clients can POST/GET after ready (it dies with the process).
            # Only the test-suite path above shuts its server down eagerly.
            ...
        return ultima

    @property
    def main(self) -> Status:
        """(Alias) The main entry point for the router."""
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
        """Run the Textual REPL until it exits with a status.

        The router owns this loop because the control API only knows how to
        initialize and execute a command surface; it does not know whether
        the surrounding application wants an interactive session. Command
        failures are represented by ``ControlResult`` (unknown -> suggestions)
        and therefore do not end the session. Failures in the loop itself are
        converted to a status so a bad app crash cannot escape router startup.
        """
        try:
            initialized = self.control.deeper_context.initialized
        except Exception as exception:
            log.critical("cannot inspect test state before starting the loop: %s", exception)
            return stat.Abort()

        if not initialized:
            log.error("cannot start test loop; control is not initialized")
            return stat.ControlNotInitializedError()

        log.info("test loop has started")
        app = REPL(handle=self._handle_command)
        try:
            ultima: Status | None = app.run()  # blocks this thread, like input() did
        except KeyboardInterrupt:
            log.warning("test loop interrupted")
            return stat.Interrupted()
        except Exception as exception:  # app-level crash
            log.error("repl crashed: %r", exception)
            return stat.Abort()
        if ultima is None:
            log.error("repl exited without a status")
            return stat.ImpossibleControlState()
        log.info("repl exited with status %s", ultima)
        return ultima

    def _handle_command(self, command: str) -> Outcome:
        """Execute one REPL line: exit-status, suggestions, or keep-going.

        Returns ``Status`` to exit the REPL, ``list[str]`` of suggestions for
        an unknown command, or ``None`` for a known command (keep listening).
        Mirrors the old ``input()`` loop body minus the blocking read.
        """
        if not isinstance(command, str):
            log.error("test loop received non-string input (%s)", type(command).__name__)
            return stat.TokenizeUnsupportedTypeError()

        command_marker = command.strip().casefold()
        quitters: tuple[str, ...] = ("q", "quit", "e", "exit")
        for name in quitters:  # o(n)
            quitters += (f"{Fixtures.cmd_prefix}{name}",)
        if command_marker in quitters:
            log.info("test loop requested to stop")
            return stat.Success()
        if not command_marker:
            log.warning("test loop received empty input! is it a typo on an error?")
            return None

        try:
            result = self.execute(command)
        except KeyboardInterrupt:
            log.warning("test loop interrupted during commands execution")
            return stat.Interrupted()
        except Exception as exception:
            log.critical("test loop failed while executing a commands: %s", exception)
            return stat.Abort()

        if not isinstance(result, ControlResult):
            log.critical("test execution returned an invalid result")
            return stat.Abort()

        was_not_initialized = stat.ControlNotInitializedError()
        if result.code.code == was_not_initialized.code:
            log.critical("test became uninitialized while the loop was running")
            return was_not_initialized

        if result.ok:
            if result.kind != "input" and result.value is not None:
                log.info("test result: %r", result.value)
            if result.command == "help" and isinstance(result.value, dict):
                log.info(
                    "commands: '%s'\n  prefix: '%s'\n  target: '%s'\n suggestions: '%s'",
                    result.value.get("commands", None),
                    result.value.get("prefix", None),
                    result.value.get("target", None),
                    result.value.get("suggestions", None),
                )
            return None

        final_result = result.suggestions
        return [] if final_result is None else final_result
