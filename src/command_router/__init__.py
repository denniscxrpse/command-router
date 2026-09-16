#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("start", "init_flags")

import json
import shutil
import sys
import threading
import tomllib
from http.server import HTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from uuid import uuid4

import json5

from command_router.lib.control import ControlInitialization, ControlResult
from command_router.lib.control.api import *
from command_router.lib.grammar.loader import *
from command_router.sdk import Fixtures
from command_router.suggestions import *
from command_router.suite import *
from command_router.utils import (
    LazyServer,
    Status,
    default_fixtures_dir,
    describe_flags,
    flag_names,
    flags,
    init_flags,
    log,
    normalize_bare_options,
    paths,
    stat,
    uctx,
)

_Dict = dict[str, Any]


def _check_genesis_dir(path: Path) -> str | None:
    """Return an error message when *path* cannot serve as a fixture directory."""
    if not path.exists():
        return f"genesis given, but directory {path} does not exist"
    if not (path / "__init__.py").exists():
        return "genesis given, but the existing directory does not contain its `__init__.py` file"
    return None


class __Router:
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
        # The packaged templates live somewhere read-only once installed, so
        # fall back to a working-directory cache when no repo checkout exists.
        http_dir = paths.FIXTURES_HTTP if paths.FIXTURES.is_dir() else Path.cwd() / ".command-router" / "http"
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

    @property
    def genesis_source(self) -> Path | None:
        """Return the validated genesis directory, or None when unset or invalid.

        A genesis directory must exist and contain a ``__init__.py`` file so
        the fixture loader can treat it as a package. String values are
        coerced for callers that bypass ``init_flags``. Failures are logged
        as critical diagnostics; callers decide whether that aborts startup,
        so grammar discovery and control initialization share one check.
        """
        if flags.genesis is None:
            return None
        genesis = flags.genesis if isinstance(flags.genesis, Path) else Path(flags.genesis)
        if (message := _check_genesis_dir(genesis)) is not None:
            log.critical("%s", message)
            return None
        return genesis

    def control_init(self) -> bool:
        """Load fixture behavior and compile the active command surface."""
        log.info("initializing control")

        r: ControlInitialization

        if flags.genesis is None:
            fixture = default_fixtures_dir()
        else:
            genesis = self.genesis_source
            if genesis is None:
                return False
            log.info("genesis given, fixtures will be loaded from %s", genesis)
            fixture = genesis
        r = self.control.initialize(
            self.grammars,
            fixture=fixture,
            keep_help=not flags.no_help,
        )

        if not r.ok:
            log.error("control initialization failed (%s): %s", r.code, r.message)
            return False
        log.info("control ready (%d grammar(s))", r.command_count)
        return True


_router = __Router()


class __CommandRouter:
    _was_i_initialized = False
    """Literal variable to track whether the router was initialized using ``__init__``."""

    def __init__(self) -> None:
        self._grammars = _router.grammars
        self._info = _router.info
        self.control = _router.control
        self._was_i_initialized = True
        log.info("router instance was initialized. use `initialize` to actually start the router")

    @property
    def initialize(self) -> Status:
        """The main entry point for the router."""
        if not self._was_i_initialized:
            return stat.ImpossibleControlState()
        log.debug(
            "flags (lazy=%s, test_suite=%s, no_help=%s, ignore=%s, genesis=%s)",
            flags.lazy,
            flags.test_suite,
            flags.no_help,
            flags.ignore,
            flags.genesis,
        )

        # Informational and scaffolding flags short-circuit before anything
        # boots: verbose help is read-only, and init only writes files.
        if flags.verbose_help is not None:
            return self._verbose_help(flags.verbose_help)
        if flags.init is not None:
            return self._scaffold(flags.init)

        # Get every single file in fixtures/*
        if flags.lazy:
            log.info("lazy grammar loading enabled")
            _router.lazy_init()
            ctrl_init = _router.control_init()
            if ctrl_init and flags.test_suite:
                c = self._test_suite_loop()
                return c
            log.info("initialization completed")

        genesis = flags.genesis
        if genesis is None:
            grammar_source = default_fixtures_dir()
        else:
            grammar_source = Path(genesis)
        try:
            files = [path for path in grammar_source.iterdir() if path.is_file()]
        except OSError as exception:
            log.critical("cannot list grammar source %s: %s", grammar_source, exception)
            return stat.Abort()
        log.debug("discovered %d fixture file(s) in %s", len(files), grammar_source)
        result = _router.grammar_init(files)
        if isinstance(result, Status):
            log.error("grammar initialization failed (%s); continuing with loaded data", result)

        # The test-suite loop doesn't need to be initialized for embedded use.
        ctrl_init = _router.control_init()

        log.debug("normalized grammars=%r; info=%r", self._grammars, self._info)

        suggestions_server: HTTPServer | None = None
        if flags.no_suggestions_server:
            log.info("suggestions server completely disabled; not binding")
        elif flags.serve:
            log.info("serve mode owns the stderr transport; suggestions server not binding")
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

        if ctrl_init and flags.serve:
            if not flags.json_out:
                log.debug("serve mode implies JSON responses")
                flags.json_out = True
            log.info("serve mode enabled; entering stdin loop")
            try:
                ultima = self._serve_loop()
                log.info("serve loop exited with status %s", ultima)
                return ultima
            finally:
                if suggestions_server is not None:
                    suggestions_server.shutdown()
                    suggestions_server.server_close()

        if not ctrl_init and flags.genesis is not None:
            log.critical("router cannot start without an initialized control surface")
            return stat.Abort()
        return stat.Success()

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

    def _serve_loop(self) -> Status:
        """Feed dirty stdin lines to the control surface; answers flow to stderr.

        There is no input schema: every line is fed whole to ``execute``,
        the same path the test suite uses, so empty lines, plain text, and
        broken commands are all accepted eagerly. The control layer prints
        exactly one JSON response line per execution on ``stderr`` itself,
        which keeps framing strictly one-to-one with no printing done here.
        The loop only writes when that emission could not have happened: an
        execution failure, or an action value that JSON cannot serialize
        (re-serialized here as a watchdog, since the control layer swallows
        that emission failure internally). EOF ends the loop with ``Success``.
        """
        log.info("serve loop started; reading commands from stdin")
        try:
            for line in sys.stdin:
                text = line.rstrip("\n")
                try:
                    result = self.execute(text)
                except Exception as exception:
                    log.error("serve loop failed to execute %r: %s", text, exception)
                    self._serve_fallback(text, str(exception))
                    continue
                try:
                    result.to_json()
                except (TypeError, ValueError) as exception:
                    log.error("serve loop could not serialize the answer to %r: %s", text, exception)
                    self._serve_fallback(text, f"unserializable result: {exception}")
        except KeyboardInterrupt:
            log.warning("serve loop interrupted")
            return stat.Interrupted()
        log.info("serve loop reached EOF")
        return stat.Success()

    @staticmethod
    def _serve_fallback(text: str, message: str) -> None:
        """Print one JSON error line on ``stderr`` to preserve 1:1 framing.

        Only used when the control layer could not emit its own response
        line, so a pipe consumer waiting on the next line never hangs.
        """
        print(
            json.dumps(
                {
                    "ok": False,
                    "input": text,
                    "value": None,
                    "suggestions": [],
                    "error": {"message": message},
                    "message": message,
                }
            ),
            file=sys.stderr,
            flush=True,
        )

    def _verbose_help(self, name: str) -> Status:
        """Print flag documentation; a full dump asks first on terminals.

        Dumping every flag behind a bare `--verbose-help` prints the whole
        environment, so interactive use confirms first. Piped input cannot
        answer, so it dumps directly instead of hanging.
        """
        if name == "all" and sys.stdin.isatty():
            try:
                answer = input(f"Print documentation for {len(flag_names())} flags? [y/N] ")
            except EOFError:
                answer = ""
            if answer.strip().casefold() not in ("y", "yes"):
                print("cancelled.", flush=True)
                return stat.Success()
        try:
            text = describe_flags(name)
        except ValueError as exception:
            print(exception, flush=True)
            return stat.Abort()
        print(text, flush=True)
        return stat.Success()

    def _scaffold(self, dest: Path | None) -> Status:
        """Copy the bundled fixture templates to *dest* and explain `--genesis`.

        A missing destination is treated as a name for a new directory under
        the working directory (`None` means `./fixtures`); an existing
        directory is used as-is, but a non-empty one is refused rather than
        merged into. The copied tree is validated with the same rules the
        fixture loader enforces, so the printed next step is guaranteed to
        work.
        """
        target = Path("fixtures") if dest is None else Path(dest)
        try:
            if target.exists():
                if not target.is_dir():
                    log.critical("init destination %s exists and is not a directory", target)
                    return stat.Abort()
                if any(target.iterdir()):
                    log.critical("init destination %s is not empty; refusing to overwrite", target)
                    return stat.Abort()
            else:
                target.mkdir(parents=True)
        except OSError as exception:
            log.critical("cannot prepare init destination %s: %s", target, exception)
            return stat.Abort()
        try:
            with resources.as_file(resources.files("command_router") / "_example" / "fixtures") as source:
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
        except OSError as exception:
            log.critical("cannot copy fixture templates to %s: %s", target, exception)
            return stat.Abort()
        if (message := _check_genesis_dir(target)) is not None:
            log.critical("%s", message)
            return stat.Abort()
        print(f"Done. Run the program with 'cmd-router --genesis {target}'.", flush=True)
        return stat.Success()

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
        quitters: tuple[str, ...] = ("q", "quit", "e", "exit", "!q", "!quit")
        quitters += tuple(f"{Fixtures.cmd_prefix}{name}" for name in ("q", "quit", "e", "exit"))
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


def start(entry: tuple[str, ...] | None = None) -> Status:
    """Start the command router and return its process exit status name.

    When *entry* is given, it is parsed as CLI arguments first, so importers
    can initialize the flag environment without touching ``sys.argv``::

        start(("--serve", "--quiet"))

    An absent *entry* parses ``sys.argv`` instead. Bare `--init` and
    `--verbose-help` occurrences are expanded to explicit values before
    parsing, since stock click cannot express an option that is valid
    both bare and valued. Invalid entries raise ``SystemExit`` exactly
    like the command line does.
    """

    if entry is not None:
        init_flags(normalize_bare_options(list(entry)), standalone_mode=False)
    else:
        init_flags(normalize_bare_options(sys.argv[1:]), standalone_mode=False)

    log.info("starting command router")
    ultima: Status
    try:
        ultima = __CommandRouter().main
    except KeyboardInterrupt:
        log.warning("interrupted; shutting down")
        return stat.Interrupted()
    except Exception as exception:
        log.debug("unrecoverable startup exception was raised")
        log.critical(str(exception))
        return stat.Abort()
    log.info("command router exited with code %s (%s)", ultima.code, ultima.name)
    log.info("contract message (if any): %s", ultima.message)
    return ultima
