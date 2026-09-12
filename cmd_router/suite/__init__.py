#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ["REPL", "Outcome"]

import json
import pprint
import random
from collections.abc import Callable
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Key, Resize
from textual.widgets import Footer, Input, RichLog, Static

from cmd_router.lib.control import ControlResult
from cmd_router.sdk import Fixtures
from cmd_router.suggestions import *
from cmd_router.utils import Status, flags, log, log_handler, stat

from .css import style

Outcome = Status | list[str] | None
"""
``Status`` -> exit the app (``run()`` returns it); ``list[str]`` -> unknown command
(suggestions for the next input); ``None`` -> known command, keep listening.
"""


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

    CSS = style

    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, handle: Callable[[str], Outcome], context: Any | None = None) -> None:
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
    def _context_from_handle(handle: Callable[[str], Outcome]) -> Any | None:
        """Find a router-owned live context for the default bound handler."""
        owner = getattr(handle, "__self__", None)
        control = getattr(owner, "control", None)
        return getattr(control, "deeper_context", None)

    def action_quit(self) -> None:  # ty: ignore[invalid-method-override]
        # ctrl+q would otherwise exit(None); your contract forbids None
        self.exit(stat.Abort())
