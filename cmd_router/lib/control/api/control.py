#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""The class-based control API."""

import asyncio
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any, Self

from cmd_router.lib.command import CmdError, CmdParse
from cmd_router.utils.context import ctx, error
from cmd_router.utils.logger import log_handler

from ..compiler import _compile_grammars, _GrammarSource, _GrammarSyntaxError
from ..fixture import _load_fixture_module
from .context import _DeeperLevelContext
from .result import ControlInitialization, ControlResult

__all__ = ("Control",)

_Action = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class _Invocation:
    """Hold the parsed data needed to run one command."""

    command: str
    parsed: CmdParse.Result
    context: CmdParse.Context
    handler: _Action


class Control:
    """Initialize, execute, and inspect one control surface."""

    def __init__(
        self,
        *,
        command_context: Any = ctx,
        deeper: _DeeperLevelContext | None = None,
    ) -> None:
        """Create a control surface backed by *command_context*."""
        self.context = command_context
        self.deeper_level = deeper if deeper is not None else _DeeperLevelContext(command_context)
        self._async_lock = asyncio.Lock()
        self._stderr_locked = False

    @property
    def deeper(self) -> _DeeperLevelContext:
        """Return the deeper control state."""
        return self.deeper_level

    def initialize(
        self,
        grammars: _GrammarSource | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization:
        """Configure grammars and optionally initialize a fixture."""
        if fixture is not None:
            fixture_result = self._initialize_fixture(fixture)
            if not fixture_result.ok:
                self.deeper_level.last_initialization = fixture_result
                return fixture_result

        if keep_help is not None:
            if not isinstance(keep_help, bool):
                return self._initialization_error("keep_help must be a boolean")
            self.context.control_no_help_keeps_help = keep_help

        selected = self.deeper_level.grammars if grammars is None else grammars
        result = self.configure(selected)
        self.deeper_level.last_initialization = result
        return result

    def configure(self, grammars: _GrammarSource) -> ControlInitialization:
        """Compile grammars into the current dispatcher."""
        if not isinstance(grammars, Mapping):
            return self._initialization_error("grammars must be a mapping of command names to syntax")

        normalized = dict(grammars)
        try:
            dispatcher = _compile_grammars(
                normalized,
                lambda: self.context.command_action,
                self.context.control_no_help_keeps_help,
                self.context.cmd_prefix,
            )
        except (AttributeError, TypeError, ValueError, _GrammarSyntaxError) as exception:
            return self._initialization_error(str(exception), exception)

        self.deeper_level.grammars = normalized
        self.deeper_level.dispatcher = dispatcher
        self.deeper_level.initialized = True
        result = ControlInitialization(True, error.Succeed, command_count=len(normalized))
        self.deeper_level.last_initialization = result
        return result

    def _initialize_fixture(self, fixture: ModuleType | str | Path) -> ControlInitialization:
        """Load a fixture and run its declared setup hooks."""
        if not self._stderr_locked:
            log_handler.lock_stderr()
            self._stderr_locked = True

        try:
            module = _load_fixture_module(fixture, id(self))
            setup = getattr(module, "setup", None)
            logic_factory = getattr(module, "FixtureGrammarLogic", None)
            if logic_factory is None:
                logic_factory = getattr(module, "_FixG", None)
            if not callable(setup) or not callable(logic_factory):
                raise TypeError("fixture must define callable setup and FixtureGrammarLogic objects")

            logic = logic_factory()
            self.deeper_level.fixture_module = module
            self.deeper_level.fixture_logic = logic
            setup()
        except Exception as exception:
            return self._initialization_error("fixture initialization failed", exception, error.ControlFixtureError)

        return ControlInitialization(True, error.Succeed, "fixture initialized")

    def _initialization_error(
        self,
        message: str,
        exception: Exception | None = None,
        code: int = error.ControlGrammarError,
    ) -> ControlInitialization:
        """Create and remember an initialization failure."""
        result = ControlInitialization(
            False,
            code,
            message,
            exception=None if exception is None else f"{type(exception).__name__}: {exception}",
        )
        self.deeper_level.last_initialization = result
        return result

    def close(self) -> None:
        """Release the fixture stderr wrapper."""
        if self._stderr_locked:
            log_handler.unlock_stderr()
            self._stderr_locked = False

    def __enter__(self) -> Self:
        """Return this control surface to a context manager."""
        return self

    def __exit__(self, *_arguments: Any) -> None:
        """Close resources when leaving a context manager."""
        self.close()

    def execute(self, command: Any) -> ControlResult:
        """Execute one command synchronously."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.execute_async(command))
        return self._execute_sync(command)

    dispatch = execute

    async def execute_async(self, command: Any) -> ControlResult:
        """Execute one command while serializing async actions."""
        async with self._async_lock:
            prepared = self._prepare(command)
            if isinstance(prepared, ControlResult):
                return self._remember(prepared)

            arguments = self._controlled_arguments(prepared.command, prepared.context.args)
            invocation_context = replace(prepared.context, args=arguments)
            try:
                value = prepared.handler(**arguments)
                if inspect.isawaitable(value):
                    value = await value
            except Exception as exception:
                return self._remember(
                    ControlResult(
                        False,
                        error.ControlActionError,
                        "action_error",
                        command,
                        prepared.command,
                        parse_result=prepared.parsed,
                        context=invocation_context,
                        handler=prepared.handler,
                        message="command action failed",
                        exception=f"{type(exception).__name__}: {exception}",
                    )
                )

            return self._remember(
                ControlResult(
                    True,
                    error.Succeed,
                    "command",
                    command,
                    prepared.command,
                    value,
                    prepared.parsed,
                    invocation_context,
                    prepared.handler,
                )
            )

    async_dispatch = execute_async
    aexecute = execute_async

    def _execute_sync(self, command: Any) -> ControlResult:
        """Execute a prepared command in a synchronous context."""
        prepared = self._prepare(command)
        if isinstance(prepared, ControlResult):
            return self._remember(prepared)

        arguments = self._controlled_arguments(prepared.command, prepared.context.args)
        invocation_context = replace(prepared.context, args=arguments)
        try:
            value = prepared.handler(**arguments)
            if inspect.isawaitable(value):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    value = asyncio.run(value)
                else:
                    close = getattr(value, "close", None)
                    if callable(close):
                        close()
                    return self._remember(
                        ControlResult(
                            False,
                            error.ControlActionError,
                            "action_error",
                            command,
                            prepared.command,
                            parse_result=prepared.parsed,
                            context=invocation_context,
                            handler=prepared.handler,
                            message="async action requires execute_async",
                        )
                    )
        except Exception as exception:
            return self._remember(
                ControlResult(
                    False,
                    error.ControlActionError,
                    "action_error",
                    command,
                    prepared.command,
                    parse_result=prepared.parsed,
                    context=invocation_context,
                    handler=prepared.handler,
                    message="command action failed",
                    exception=f"{type(exception).__name__}: {exception}",
                )
            )

        return self._remember(
            ControlResult(
                True,
                error.Succeed,
                "command",
                command,
                prepared.command,
                value,
                prepared.parsed,
                invocation_context,
                prepared.handler,
            )
        )

    def _prepare(self, command: Any) -> ControlResult | _Invocation:
        """Validate input and parse it into an invocation."""
        if not self.deeper_level.initialized:
            return ControlResult(
                False,
                error.ControlNotInitializedError,
                "not_initialized",
                command,
                message="control has not been initialized",
            )
        if not isinstance(command, str):
            return ControlResult(
                False,
                CmdError.TokenizeUnsupportedTypeError,
                "invalid_input",
                command,
                message="command input must be a string",
            )

        prefix = self.context.cmd_prefix
        if not isinstance(prefix, str):
            return ControlResult(
                False,
                error.ControlGrammarError,
                "invalid_context",
                command,
                message="cmd_prefix must be a string",
            )
        if prefix and not command.startswith(prefix):
            return ControlResult(True, error.Succeed, "input", command, value=command)

        command_text = command[len(prefix) :] if prefix else command
        if not command_text.strip():
            return ControlResult(
                False,
                error.Abort,
                "invalid_input",
                command,
                message="command prefix must be followed by a command",
            )

        parsed = self.deeper_level.dispatcher.parse(command_text)
        if not parsed.ok or parsed.context is None or parsed.handler is None:
            parse_error = parsed.error
            code = error.Abort if parse_error is None or parse_error.code is None else parse_error.code
            return ControlResult(
                False,
                code,
                "parse_error" if parse_error is None else parse_error.kind,
                command,
                command_text.split(maxsplit=1)[0],
                parse_result=parsed,
                error=parse_error,
                message="command did not match the grammar" if parse_error is None else parse_error.message,
            )

        command_name = parsed.context.tokens[0]
        return _Invocation(command_name, parsed, parsed.context, parsed.handler)

    def _controlled_arguments(self, command: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Apply configured argument overrides to parsed arguments."""
        values = dict(arguments)
        controls = self.deeper_level.command_args_ctrl
        command_controls = controls.get(command)
        if isinstance(command_controls, Mapping):
            values.update(command_controls)

        for name, value in controls.items():
            if name in values and not isinstance(value, Mapping):
                values[name] = value
        return values

    def _remember(self, result: ControlResult) -> ControlResult:
        """Store and return the latest control result."""
        self.deeper_level.last_result = result
        return result
