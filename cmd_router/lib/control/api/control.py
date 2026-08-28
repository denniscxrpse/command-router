#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Initialize and execute one command-control surface.

``Control`` coordinates three independent concerns:

* ``FixturesSetup`` owns the active command prefix, help policy, action
* ``_GrammarSource`` values are compiled into a fresh command dispatcher.
  mapping, and argument overrides.
* Execution validates input, preserves structured parse information, applies
  runtime argument overrides, and returns ``ControlResult`` instead of leaking
  expected command failures.

When no fixture is supplied, ``Control`` creates an isolated default
``FixturesSetup`` so direct programmatic use remains useful.  When a fixture
is supplied, its ``context_holder`` class is instantiated first, and its
``SetupFixtures`` class is then constructed with that holder bound to
``FixturesSetup.logic``.  The resulting setup replaces only this control's
active configuration.

Fixture modules should therefore expose the following contract:

.. code-block:: python

    context_holder = MyContextHolder

    class SetupFixtures(FixturesSetup):
        def __init__(self):
            super().__init__()
            self.command_action = {"say": self.logic.say}

The loader stores the module, holder, and setup in ``DeeperLevelContext``
before grammar compilation.  A missing or invalid fixture contract is returned
as ``ControlInitialization`` with ``ControlFixtureError``; grammar and action
validation failures use the corresponding structured initialization path.
"""

__all__ = ("Control",)

import asyncio
import inspect
from asyncio import Lock
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any, Self

from cmd_router.lib.commands import CmdError, CmdParse
from cmd_router.lib.control.compiler import _compile_grammars, _GrammarSource, _GrammarSyntaxError
from cmd_router.lib.control.fixture import _load_fixture_module
from cmd_router.utils.cli import *
from cmd_router.utils.context import error
from cmd_router.utils.logger import *

from .context import *
from .fixtures import *
from .result import *

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
        setup: FixturesSetup | None = None,
        deeper: DeeperLevelContext | None = None,
    ) -> None:
        """Create a control surface backed by *setup* or isolated defaults.

        ``setup`` is used only when *deeper* is omitted.  Supplying an existing
        ``deeper`` context preserves that context and its active setup, which
        is useful when a caller wants to share inspection state deliberately.
        """
        self.deeper_level: DeeperLevelContext = deeper if deeper is not None else DeeperLevelContext(setup)
        self._async_lock: Lock = asyncio.Lock()
        self._stderr_locked: bool = False
        log.debug(
            "created (setup=%s, deeper=%s)",
            type(self.deeper_level.setup).__name__,
            deeper is not None,
        )

    @property
    def context(self) -> FixturesSetup:
        """Return the active fixture setup through the short context alias."""
        return self.deeper_level.setup

    @property
    def deeper(self) -> DeeperLevelContext:
        """Return the deeper control state."""
        return self.deeper_level

    def initialize(
        self,
        grammars: _GrammarSource | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization:
        """Initialize an optional fixture, apply overrides, and compile grammars.

        Fixture construction happens before grammar compilation so actions can
        be derived from the newly created holder.  If *keep_help* is supplied,
        it replaces the active setup's help policy for this control.  Omitting
        it preserves the setup's configured value.
        """
        log.info("initialization started")
        log.debug(
            "initialization options (grammars=%s, fixture=%r, keep_help=%r)",
            type(grammars).__name__ if grammars is not None else "stored",
            fixture,
            keep_help,
        )
        if fixture is not None:
            fixture_result = self._initialize_fixture(fixture)
            if not fixture_result.ok:
                log.warning("fixture setup failed; grammar compilation was skipped")
                self.deeper_level.last_initialization = fixture_result
                return fixture_result

        if keep_help is not None:
            if not isinstance(keep_help, bool):
                return self._initialization_error("keep_help must be a boolean")
            self.deeper_level.lazy_init_help = keep_help

        selected = self.deeper_level.grammars if grammars is None else grammars
        result = self.configure(selected)
        self.deeper_level.last_initialization = result
        log.debug("initialization finished (ok=%s, code=%s)", result.ok, result.code)
        return result

    def configure(self, grammars: _GrammarSource) -> ControlInitialization:
        """Compile *grammars* using the active ``FixturesSetup`` configuration."""
        if not isinstance(grammars, Mapping):
            return self._initialization_error("grammars must be a mapping of command names to syntax")

        normalized = dict(grammars)
        log.info("compiling %d grammar entr%s", len(normalized), "y" if len(normalized) == 1 else "ies")
        log.debug(
            "compiler settings (prefix=%r, keep_help=%s, actions=%s)",
            self.deeper_level.cmd_prefix,
            self.deeper_level.lazy_init_help,
            tuple(self.deeper_level.command_action),
        )
        try:
            dispatcher = _compile_grammars(
                normalized,
                lambda: self.deeper_level.command_action,
                self.deeper_level.lazy_init_help,
                self.deeper_level.cmd_prefix,
            )
        except (AttributeError, TypeError, ValueError, _GrammarSyntaxError) as exception:
            return self._initialization_error(str(exception), exception)

        self.deeper_level.grammars = normalized
        self.deeper_level.dispatcher = dispatcher
        self.deeper_level.initialized = True
        result = ControlInitialization(True, error.Succeed, command_count=len(normalized))
        self.deeper_level.last_initialization = result
        log.info(
            "compilation completed (%d grammar entr%s)",
            len(normalized),
            "y" if len(normalized) == 1 else "ies",
        )
        return result

    def _initialize_fixture(self, fixture: ModuleType | str | Path) -> ControlInitialization:
        """Load and initialize a ``context_holder``/``SetupFixtures`` fixture.

        The holder is created first.  Its instance is then injected into the
        setup class's ``logic`` class attribute before the setup constructor is
        called, which lets a setup subclass build action mappings from bound
        holder methods in its own ``__init__``.  The active control state is
        changed only after both objects have been created successfully.

        The old ``setup``/``FixtureGrammarLogic`` hook pair is intentionally no
        longer used: those hooks depended on mutable ``uctx`` settings that
        were removed from the API.  The returned initialization error names the
        new contract when a legacy or incomplete module is supplied.
        """
        log.info("loading fixture")
        log.debug("fixture source=%r", fixture)
        if not self._stderr_locked:
            log_handler.lock_stderr()
            self._stderr_locked = True

        try:
            module = _load_fixture_module(fixture, id(self))
            log.debug("fixture module loaded (%s)", module.__name__)
            holder_factory = getattr(module, "context_holder", None)
            setup_factory = getattr(module, "SetupFixtures", None)
            if not isinstance(holder_factory, type) or not issubclass(holder_factory, FixturesContextHolder):
                raise TypeError("fixture must define context_holder as a FixturesContextHolder child class")
            if not isinstance(setup_factory, type) or not issubclass(setup_factory, FixturesSetup):
                raise TypeError("fixture must define SetupFixtures as a FixturesSetup child class")

            logic = holder_factory()
            log.debug("fixture context holder created (%s)", type(logic).__name__)
            setup_factory.logic = logic
            setup = setup_factory()
            log.debug("fixture setup created (%s)", type(setup).__name__)
            self.deeper_level.attach_fixture(module, logic, setup)
        except Exception as exception:
            return self._initialization_error("fixture initialization failed", exception, error.ControlFixtureError)

        log.info("fixture ready (%s)", module.__name__)
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
        detail = f": {result.exception}" if result.exception is not None else ""
        log.error("initialization failed (%s)%s", message, detail)
        return result

    def close(self) -> None:
        """Release the fixture stderr wrapper."""
        if self._stderr_locked:
            log_handler.unlock_stderr()
            self._stderr_locked = False
            log.debug("released fixture stderr wrapper")

    def __enter__(self) -> Self:
        """Return this control surface to a context manager."""
        return self

    def __exit__(self, *_arguments: Any) -> None:
        """Close resources when leaving a context manager."""
        self.close()

    def execute(self, command: Any) -> ControlResult:
        """Execute one command synchronously."""
        log.debug("execute requested (input_type=%s)", type(command).__name__)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            log.debug("no running event loop; bridging through execute_async")
            return asyncio.run(self.execute_async(command))
        log.debug("running inside an event loop; using synchronous action path")
        return self._execute_sync(command)

    dispatch = execute

    async def execute_async(self, command: Any) -> ControlResult:
        """Execute one command while serializing async actions."""
        log.debug("async execution waiting for action lock")
        async with self._async_lock:
            log.debug("async action lock acquired")
            prepared = self._prepare(command)
            if isinstance(prepared, ControlResult):
                return self._remember(prepared)

            arguments = self._controlled_arguments(prepared.command, prepared.context.args)
            invocation_context = replace(prepared.context, args=arguments)
            log.debug(
                "invoking %r asynchronously with %d argument%s",
                prepared.command,
                len(arguments),
                "" if len(arguments) == 1 else "s",
            )
            try:
                value = prepared.handler(**arguments)
                if inspect.isawaitable(value):
                    log.debug("awaiting action result for %r", prepared.command)
                    value = await value
            except Exception as exception:
                return self._remember(
                    ControlResult(
                        ok=False,
                        code=error.ControlActionError,
                        kind=ControlResultKinds.ACTION_ERROR,
                        input=command,
                        command=prepared.command,
                        parse_result=prepared.parsed,
                        context=invocation_context,
                        handler=prepared.handler,
                        message="command action failed",
                        exception=f"{type(exception).__name__}: {exception}",
                    )
                )

            return self._remember(
                ControlResult(
                    ok=True,
                    code=error.Succeed,
                    kind=ControlResultKinds.COMMAND,
                    input=command,
                    command=prepared.command,
                    value=value,
                    parse_result=prepared.parsed,
                    context=invocation_context,
                    handler=prepared.handler,
                )
            )

    async_dispatch = execute_async
    aexecute = execute_async

    def _execute_sync(self, command: Any) -> ControlResult:
        """Execute a prepared command in a synchronous context."""
        log.debug("entering synchronous action path")
        prepared = self._prepare(command)
        if isinstance(prepared, ControlResult):
            return self._remember(prepared)

        arguments = self._controlled_arguments(prepared.command, prepared.context.args)
        invocation_context = replace(prepared.context, args=arguments)
        log.debug(
            "invoking %r synchronously with %d argument%s",
            prepared.command,
            len(arguments),
            "" if len(arguments) == 1 else "s",
        )
        try:
            value = prepared.handler(**arguments)
            if inspect.isawaitable(value):
                log.debug("synchronous action returned an awaitable for %r", prepared.command)
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
                            ok=False,
                            code=error.ControlActionError,
                            kind=ControlResultKinds.ACTION_ERROR,
                            input=command,
                            command=prepared.command,
                            parse_result=prepared.parsed,
                            context=invocation_context,
                            handler=prepared.handler,
                            message="async action requires execute_async",
                        )
                    )
        except Exception as exception:
            return self._remember(
                ControlResult(
                    ok=False,
                    code=error.ControlActionError,
                    kind=ControlResultKinds.ACTION_ERROR,
                    input=command,
                    command=prepared.command,
                    parse_result=prepared.parsed,
                    context=invocation_context,
                    handler=prepared.handler,
                    message="command action failed",
                    exception=f"{type(exception).__name__}: {exception}",
                )
            )

        return self._remember(
            ControlResult(
                ok=True,
                code=error.Succeed,
                kind=ControlResultKinds.COMMAND,
                input=command,
                command=prepared.command,
                value=value,
                parse_result=prepared.parsed,
                context=invocation_context,
                handler=prepared.handler,
            )
        )

    def _prepare(self, command: Any) -> ControlResult | _Invocation:
        """Validate input and parse it into an invocation."""
        if not self.deeper_level.initialized:
            log.debug("rejected command because the control surface is not initialized")
            return ControlResult(
                ok=False,
                code=error.ControlNotInitializedError,
                kind=ControlResultKinds.NOT_INITIALIZED,
                input=command,
                message="control has not been initialized",
            )
        if not isinstance(command, str):
            log.debug("rejected non-string command input (%s)", type(command).__name__)
            return ControlResult(
                ok=False,
                code=CmdError.TokenizeUnsupportedTypeError,
                kind=ControlResultKinds.INVALID_INPUT,
                input=command,
                message="command input must be a string",
            )

        prefix = self.deeper_level.cmd_prefix
        if not isinstance(prefix, str):
            log.debug("active command prefix has invalid type (%s)", type(prefix).__name__)
            return ControlResult(
                ok=False,
                code=error.ControlGrammarError,
                kind=ControlResultKinds.INVALID_CONTEXT,
                input=command,
                message="cmd_prefix must be a string",
            )
        if prefix and not command.startswith(prefix):
            log.debug("treating input as ordinary text; prefix %r was not present", prefix)
            return ControlResult(True, error.Succeed, ControlResultKinds.INPUT, command, value=command)

        command_text = command[len(prefix) :] if prefix else command
        if not command_text.strip():
            log.warning("logic or user error? command prefix was supplied without a command. this shouldn't be fatal.")
            return ControlResult(
                ok=False,
                code=error.Abort,
                kind=ControlResultKinds.INVALID_INPUT,
                input=command,
                message="command prefix must be followed by a command",
            )

        log.debug("parsing command text %r", command_text)
        parsed = self.deeper_level.dispatcher.parse(command_text)
        if not parsed.ok or parsed.context is None or parsed.handler is None:
            parse_error = parsed.error
            code = error.Abort if parse_error is None or parse_error.code is None else parse_error.code
            log.debug(
                "parser returned no invocation (kind=%s, token=%s)",
                None if parse_error is None else parse_error.kind,
                None if parse_error is None else parse_error.token_index,
            )
            return ControlResult(
                ok=False,
                code=code,
                kind=ControlResultKinds.PARSE_ERROR if parse_error is None else parse_error.kind,
                input=command,
                command=command_text.split(maxsplit=1)[0],
                parse_result=parsed,
                error=parse_error,
                message="command did not match the grammar" if parse_error is None else parse_error.message,
            )

        command_name = parsed.context.tokens[0]
        log.debug("command %r matched with parsed arguments %r", command_name, parsed.context.args)
        return _Invocation(command_name, parsed, parsed.context, parsed.handler)

    def _controlled_arguments(self, command: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Apply configured argument overrides to parsed arguments."""
        values = dict(arguments)
        controls = self.deeper_level.command_args_ctrl
        command_controls = controls.get(command)
        applied = False
        if isinstance(command_controls, Mapping):
            values.update(command_controls)
            applied = bool(command_controls)

        for name, value in controls.items():
            if name in values and not isinstance(value, Mapping):
                values[name] = value
                applied = True
        if applied:
            log.debug("applied argument overrides for %r; final names=%s", command, tuple(values))
        return values

    def _remember(self, result: ControlResult) -> ControlResult:
        """Store and return the latest control result."""
        self.deeper_level.last_result = result

        if result.ok:
            if result.kind == "input":
                log.debug("ordinary input passed through unchanged")
            else:
                log.info("command %r completed successfully", result.command)
        elif result.kind in {"not_initialized", "invalid_input"}:
            log.warning("command was not executed (%s): %s", result.kind, result.message)
        else:
            detail = f"; {result.exception}" if result.exception is not None else ""
            log.error("command failed (%s): %s%s", result.kind, result.message, detail)

        log.debug("result=%s code=%s", result.kind, result.code)
        log.stderr(result.to_response() if not flags.json_out else result.to_json())

        return result
