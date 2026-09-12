#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("CommandRouter", "REPL")

import json
import pprint
import random
import threading
import tomllib
from collections.abc import Callable
from http.server import HTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import json5
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Key, Resize
from textual.widgets import Footer, Input, RichLog, Static

from cmd_router.lib.control import ControlResult
from cmd_router.lib.control.api import *
from cmd_router.lib.grammar.loader import *
from cmd_router.sdk import Fixtures
from cmd_router.suggestions import *
from cmd_router.utils import LazyServer, Status, flags, log, log_handler, paths, stat, uctx

_Dict = dict[str, Any]
# Status -> exit the app (run() returns it); list[str] -> unknown command
# (suggestions for the next input); None -> known command, keep listening.
_Outcome = Status | list[str] | None


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


class REPL(App[Status]):
    """Interactive test-suite surface with a command line and two output windows.

    handle(command) is called for every submitted line:
        Status     -> the app exits, run() returns it
        list[str]  -> unknown command; these are the suggestions for the next input
        None       -> known command; keep going
    """

    MIN_WIDTH = 96
    MIN_HEIGHT = 24
    LOG_LIMIT = 15

    CSS = """
    Screen {
        background: $surface;
        color: $text;
    }

    #command-input {
        margin: 1 2 0 2;
    }

    #status {
        height: 1;
        margin: 1 2 0 2;
        text-style: bold;
    }

    #status.status-ok {
        color: $success;
    }

    #status.status-error {
        color: $error;
    }

    #status.status-info {
        color: $text-muted;
    }

    #sugg {
        height: 2;
        margin: 0 2;
        color: $text-muted;
        overflow-x: hidden;
    }

    #context {
        height: 2;
        margin: 0 2 1 2;
        color: $accent;
        text-style: bold;
    }

    #output-windows {
        width: 100%;
        height: 1fr;
        min-height: 8;
        padding: 0 2;
    }

    .window {
        width: 1fr;
        height: 100%;
        min-width: 0;
        border: round $primary;
        padding: 0 1;
    }

    #result-window {
        margin-right: 1;
    }

    .window-title {
        height: 2;
        padding: 0 1;
        color: $accent;
        text-style: bold;
    }

    .window-content {
        width: 100%;
        height: 1fr;
        min-width: 0;
    }

    #size-warning {
        layer: warning;
        display: none;
        position: absolute;
        width: 100%;
        height: 100%;
        padding: 2 4;
        background: $surface;
        color: $warning;
        content-align: center middle;
        text-align: center;
        text-style: bold;
    }

    #size-warning.visible {
        display: block;
    }
    """

    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, handle: Callable[[str], _Outcome], context: Any | None = None) -> None:
        super().__init__()
        self._handle = handle
        self._control_context = context if context is not None else self._context_from_handle(handle)
        self._pending: list[str] | None = None
        self._too_small = False
        self._mounted = False
        self._result_rendered = False
        self._rendered_result: ControlResult | None = None
        self._rendered_json_mode: bool | None = None
        self._rendered_logs: tuple[tuple[int, str], ...] = ()

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._command_placeholder(), id="command-input")
        # NOTE: these are textual Static widgets (the status/suggestion lines),
        # not cmd_router Status codes.
        yield Static("ready", id="status", markup=False, classes="status-info")
        yield Static("", id="sugg", markup=False)
        yield Static(self._context_summary(), id="context", markup=False)
        yield Horizontal(
            Container(
                Static(
                    f"COMMAND RESULT · {'JSON' if flags.json_out else 'PYTHON DICT'}",
                    id="result-title",
                    classes="window-title",
                    markup=False,
                ),
                RichLog(
                    id="result-window-content",
                    classes="window-content",
                    min_width=1,
                    wrap=True,
                    markup=False,
                ),
                id="result-window",
                classes="window",
            ),
            Container(
                Static("LATEST 15 LOG MESSAGES", id="logs-title", classes="window-title", markup=False),
                RichLog(
                    id="logs-window-content",
                    classes="window-content",
                    min_width=1,
                    wrap=True,
                    markup=False,
                ),
                id="logs-window",
                classes="window",
            ),
            id="output-windows",
        )
        yield Static("", id="size-warning", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Start the small refresh loop used by the result and log windows."""
        self._mounted = True
        self.set_interval(0.25, self._refresh_views)
        self._refresh_views()
        self._update_size_state(self.size.width, self.size.height)

    def on_unmount(self) -> None:
        """Stop refreshing views after Textual releases the terminal."""
        self._mounted = False

    def on_resize(self, event: Resize) -> None:
        """Gate command input until both output windows have room to render."""
        if self._mounted:
            self._update_size_state(event.size.width, event.size.height)

    def on_key(self, event: Key) -> None:
        """Block keyboard interaction while the terminal is below its minimum size."""
        if self._too_small:
            event.stop()
            return
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self._complete_input()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._pending is None:
            return
        self._update_suggestion_line(self._pending, event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._too_small:
            event.stop()
            return
        value = event.value
        event.input.value = ""  # clears the line; the Changed event then shows suggestions
        try:
            outcome = self._handle(value)  # <- your router, your rules
        except Exception as exception:  # app-level boundary for a command handler
            log.error("test suite command handler failed: %s", exception)
            self._refresh_views()
            self.exit(stat.Abort())
            return
        self._refresh_views()
        if outcome is None:  # known command, keep listening
            self._pending = None
            self._set_status("OK · command completed", "status-ok")
            self.query_one("#sugg", Static).update("")
        elif isinstance(outcome, list):  # unknown -> suggestions on the next input
            self._pending = outcome
            self._set_status("UNKNOWN · choose a suggestion or try again", "status-error")
            self.query_one("#sugg", Static).update("suggestions: " + (", ".join(outcome) or "(none)"))
        elif isinstance(outcome, Status):  # Status -> this is what run() returns
            self.exit(outcome)
        else:  # defensive: a bad handle return must not hang the UI
            log.error("repl handle returned an invalid outcome (%s)", type(outcome).__name__)
            self.exit(stat.Abort())

    def _refresh_views(self) -> None:
        """Refresh both panels from the latest control state and logger history."""
        if not self._mounted:
            return
        self.query_one("#context", Static).update(self._context_summary())
        self._refresh_result_window()
        self._refresh_log_window()

    def _complete_input(self) -> None:
        """Complete the current input fragment with its first matching suggestion."""
        input_widget = self.query_one("#command-input", Input)
        cursor = max(0, min(input_widget.cursor_position, len(input_widget.value)))
        before = input_widget.value[:cursor]
        after = input_widget.value[cursor:]
        suggestions = self._suggestions_for_input(before)
        if not suggestions:
            return

        matching = self._matching_suggestions(suggestions, before)
        if not matching:
            return
        suggestion = matching[0]
        prefix = getattr(self._control_context, "cmd_prefix", "")
        start = self._completion_start(before, prefix if isinstance(prefix, str) else "")
        completed_before = before[:start] + suggestion
        input_widget.value = completed_before + after
        input_widget.cursor_position = len(completed_before)
        self._pending = suggestions
        self._update_suggestion_line(suggestions, input_widget.value)
        self._set_status(f"TAB · completed with {suggestion}", "status-info")

    def _suggestions_for_input(self, command_text: str) -> list[str]:
        """Get current suggestions, using the server path when it is enabled."""
        if self._suggestions_server_available():
            suggestions, compute_error = LazySuggestionsServer._compute_suggestions(command_text)
            if compute_error is None:
                return [] if suggestions is None else suggestions
            log.debug("test suite could not compute server suggestions (%s); using local parsing", compute_error)

        local = self._local_suggestions(command_text)
        if local is not None:
            return local[:1]
        pending = self._matching_suggestions(self._pending or (), command_text)
        return pending[:1]

    def _local_suggestions(self, command_text: str) -> list[str] | None:
        """Compute one-shot suggestions from the active context without a server."""
        context = self._control_context
        dispatcher = getattr(context, "dispatcher", None)
        if dispatcher is None:
            return None

        text = command_text.strip()
        prefix = getattr(context, "cmd_prefix", "")
        if isinstance(prefix, str) and prefix and text.startswith(prefix):
            text = text[len(prefix) :]
        try:
            parsed = dispatcher.parse(text)
        except Exception as exception:
            log.debug("test suite could not compute local suggestions: %s", exception)
            return None
        if parsed.ok or parsed.error is None:
            return []
        return LazySuggestionsServer._immediate_suggestions(parsed.error)

    def _suggestions_server_available(self) -> bool:
        """Return whether the independent suggestions channel is enabled."""
        return bool(flags.suggestions_server and not flags.no_suggestions_server)

    def _update_suggestion_line(self, suggestions: list[str] | tuple[str, ...], value: str) -> None:
        """Show suggestions matching the fragment currently being edited."""
        hits = self._matching_suggestions(suggestions, value)
        self.query_one("#sugg", Static).update("suggestions: " + (", ".join(hits) or "(none)"))

    def _matching_suggestions(self, suggestions: list[str] | tuple[str, ...], value: str) -> list[str]:
        """Filter suggestions by the current command token, ignoring its prefix."""
        prefix = getattr(self._control_context, "cmd_prefix", "")
        text = value
        if isinstance(prefix, str) and prefix and text.startswith(prefix):
            text = text[len(prefix) :]
        fragment = "" if not text or text.endswith((" ", "\t")) else text.rsplit(maxsplit=1)[-1]
        return [suggestion for suggestion in suggestions if suggestion.startswith(fragment)]

    @staticmethod
    def _completion_start(value: str, prefix: str = "") -> int:
        """Return the start offset of the token at the cursor.

        A command prefix belongs to the input syntax but not to the token
        returned by the suggestion algorithm, so a root-command completion
        starts immediately after that prefix.
        """
        start = max(value.rfind(" "), value.rfind("\t")) + 1
        if start == 0 and prefix and value.startswith(prefix):
            return len(prefix)
        return start

    def _refresh_result_window(self) -> None:
        """Render the latest compact control result in the selected output format."""
        result = self._latest_result()
        json_mode = bool(flags.json_out)
        if self._result_rendered and result is self._rendered_result and json_mode == self._rendered_json_mode:
            return

        title = self.query_one("#result-title", Static)
        title.update(f"COMMAND RESULT · {'JSON' if json_mode else 'PYTHON DICT'}")
        window = self.query_one("#result-window-content", RichLog)
        window.clear()
        if result is None:
            window.write("No command has been executed yet.")
        else:
            try:
                payload = result.to_response()
                if json_mode:
                    content = json.dumps(payload, indent=2, ensure_ascii=False, default=repr)
                else:
                    content = pprint.pformat(payload, sort_dicts=False, width=72)
            except (TypeError, ValueError, RecursionError) as exception:
                content = json.dumps(
                    {"render_error": str(exception), "result": repr(result)},
                    indent=2,
                    ensure_ascii=False,
                )
            window.write(content)

        self._rendered_result = result
        self._rendered_json_mode = json_mode
        self._result_rendered = True

    def _refresh_log_window(self) -> None:
        """Render the most recent ordinary log messages in the log panel."""
        messages = log_handler.recent_entries(self.LOG_LIMIT)
        if messages == self._rendered_logs:
            return

        window = self.query_one("#logs-window-content", RichLog)
        window.clear()
        if messages:
            for level, message in messages:
                # LoggerHandler intentionally keeps this palette private; the
                # REPL mirrors it so the panel uses the same level colors.
                color = log_handler._colors.get(level, "#291f1c")
                window.write(Text(message, style=color))
        else:
            window.write("No log messages yet.")
        self.query_one("#logs-title", Static).update(f"LATEST {self.LOG_LIMIT} LOG MESSAGES")
        self._rendered_logs = messages

    def _latest_result(self) -> ControlResult | None:
        """Read the latest result from the live control context, when present."""
        result = getattr(self._control_context, "last_result", None)
        return result if isinstance(result, ControlResult) else None

    def _update_size_state(self, width: int, height: int) -> None:
        """Show the resize gate and disable input when the panels cannot fit."""
        self._too_small = width < self.MIN_WIDTH or height < self.MIN_HEIGHT
        if not self._mounted:
            return

        input_widget = self.query_one("#command-input", Input)
        warning = self.query_one("#size-warning", Static)
        input_widget.disabled = self._too_small
        if self._too_small:
            warning.update(
                "Terminal window is too small to render the test suite.\n\n"
                f"Current size: {width}×{height}. Make the window bigger to continue "
                f"(minimum {self.MIN_WIDTH}×{self.MIN_HEIGHT})."
            )
            warning.add_class("visible")
        else:
            warning.remove_class("visible")

    def _set_status(self, message: str, status_class: str) -> None:
        """Update the plain-text status line and its color class."""
        status = self.query_one("#status", Static)
        for class_name in ("status-ok", "status-error", "status-info"):
            status.remove_class(class_name)
        status.add_class(status_class)
        status.update(message)

    def _context_summary(self) -> str:
        """Return a compact SDK/control summary for the test-suite header."""
        context = self._control_context
        setup = getattr(context, "setup", None) or Fixtures
        prefix = getattr(context, "cmd_prefix", getattr(Fixtures, "cmd_prefix", "/"))
        grammars = getattr(context, "grammars", {})
        command_count = len(grammars) if isinstance(grammars, dict) else 0
        return (
            f"COMMAND ROUTER TEST SUITE  ·  SDK {type(setup).__name__}  ·  "
            f"prefix={prefix!r}  ·  grammar commands={command_count}  ·  "
            f"help={'on' if self._help_enabled() else 'off'}"
        )

    def _command_placeholder(self) -> str:
        """Build an example command from the current SDK/control settings."""
        context = self._control_context
        prefix = getattr(context, "cmd_prefix", getattr(Fixtures, "cmd_prefix", "/"))
        names: tuple[str, ...] = ()
        for source in (
            getattr(context, "grammars", None),
            getattr(context, "command_action", None),
            getattr(Fixtures, "command_action", None),
        ):
            if isinstance(source, dict):
                names = tuple(name for name in source if isinstance(name, str) and name.casefold() != "help" and name)
                if names:
                    break
        command = random.choice(names) if names else "command"
        return f"{prefix}help {command}" if self._help_enabled() else f"{prefix}{command}"

    def _help_enabled(self) -> bool:
        """Return whether the active surface exposes a help command."""
        context = self._control_context
        if bool(getattr(context, "lazy_init_help", getattr(Fixtures, "lazy_init_help", True))):
            return True
        grammars = getattr(context, "grammars", None)
        return isinstance(grammars, dict) and any(
            isinstance(name, str) and name.casefold() == "help" for name in grammars
        )

    @staticmethod
    def _context_from_handle(handle: Callable[[str], _Outcome]) -> Any | None:
        """Find a router-owned live context for the default bound handler."""
        owner = getattr(handle, "__self__", None)
        control = getattr(owner, "control", None)
        return getattr(control, "deeper_context", None)

    def action_quit(self) -> None:  # ty: ignore[invalid-method-override]
        # ctrl+q would otherwise exit(None); your contract forbids None
        self.exit(stat.Abort())


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
        # TODO: Once this is implemented, remove the `Success()` contract.
        #       This WILL break the test suite, so you might as well test at runtime.
        #       Or maybe just try the C# example? Up to you.
        try:
            ...
        except KeyboardInterrupt:
            log.critical("router interrupted")
            ultima = stat.Interrupted()
        finally:
            # Embedded use keeps the daemon server alive beyond `initialize`
            # so clients can POST/GET after ready (it dies with the process).
            # Only the test-suite path above shuts its server down eagerly.
            pass
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

        log.info("test loop started (type 'exit'/'e' or 'quit'/'q' to stop)")
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

    def _handle_command(self, command: str) -> _Outcome:
        """Execute one REPL line: exit-status, suggestions, or keep-going.

        Returns ``Status`` to exit the REPL, ``list[str]`` of suggestions for
        an unknown command, or ``None`` for a known command (keep listening).
        Mirrors the old ``input()`` loop body minus the blocking read.
        """
        if not isinstance(command, str):
            log.error("test loop received non-string input (%s)", type(command).__name__)
            return stat.TokenizeUnsupportedTypeError()

        command_marker = command.strip().casefold()
        if command_marker in ("exit", "e", "quit", "q", "!q", "!quit"):
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
        if result.code.name == was_not_initialized.name:
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
