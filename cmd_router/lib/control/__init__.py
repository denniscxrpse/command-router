#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Control and execution helpers for an embedded command router.

The command tree remains the source of matching behavior.  This module only
connects loaded grammar definitions and the small configuration object in
``cmd_router.utils.context`` to that tree.  It exposes two levels of API:

``Control.execute`` returns a small structured result suitable for a process
boundary, while ``Control.deeper_level`` exposes the live dispatcher and
fixture object to Python callers that need more control.
"""

from __future__ import annotations

__all__ = (
    "Control",
    "ControlInitialization",
    "ControlResult",
    "DeeperLevelContext",
    "control",
    "deeper_level",
    "execute",
    "execute_async",
    "initialize",
)

import ast
import asyncio
import importlib
import importlib.util
import inspect
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from cmd_router.lib.command import CmdError, CmdNode, CmdParse, CmdType
from cmd_router.utils.context import ctx, error
from cmd_router.utils.logger import log_handler

_Action = Callable[..., Any]
_GrammarSource = Mapping[str, str]


class _GrammarSyntaxError(ValueError):
    """Raised when the compact fixture grammar cannot be expanded."""


@dataclass(frozen=True, slots=True)
class _LiteralTerm:
    value: str


@dataclass(frozen=True, slots=True)
class _ArgumentTerm:
    name: str
    type_name: str
    default: Any = None
    has_default: bool = False


@dataclass(frozen=True, slots=True)
class _ChoiceTerm:
    alternatives: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True, slots=True)
class _OptionalTerm:
    body: _ChoiceTerm


class _GrammarParser:
    """Parse the deliberately small notation used by the fixture files."""

    def __init__(self, source: str) -> None:
        self._tokens = self._scan(source)
        self._position = 0

    def parse(self) -> tuple[Any, ...]:
        alternatives = self._parse_alternatives(None)
        if self._position != len(self._tokens):
            token = self._tokens[self._position]
            raise _GrammarSyntaxError(f"unexpected grammar token {token!r}")
        return (_ChoiceTerm(alternatives),)

    def _parse_alternatives(self, closing: str | None) -> tuple[tuple[Any, ...], ...]:
        alternatives = [self._parse_sequence(closing)]
        while self._peek() == "|":
            self._position += 1
            alternatives.append(self._parse_sequence(closing))
        return tuple(alternatives)

    def _parse_sequence(self, closing: str | None) -> tuple[Any, ...]:
        terms: list[Any] = []
        while self._position < len(self._tokens):
            token = self._peek()
            if token == "|" or token == closing:
                break
            if token in (")", "]"):
                raise _GrammarSyntaxError(f"unexpected closing token {token!r}")
            terms.append(self._parse_term())
        return tuple(terms)

    def _parse_term(self) -> Any:
        token = self._take()
        if token == "(":
            alternatives = self._parse_alternatives(")")
            self._expect(")")
            return _ChoiceTerm(alternatives)
        if token == "[":
            alternatives = self._parse_alternatives("]")
            self._expect("]")
            return _OptionalTerm(_ChoiceTerm(alternatives))
        if token.startswith("<"):
            return self._parse_argument(token)
        if not token:
            raise _GrammarSyntaxError("grammar literals cannot be empty")
        return _LiteralTerm(token)

    @staticmethod
    def _scan(source: str) -> tuple[str, ...]:
        tokens: list[str] = []
        position = 0
        while position < len(source):
            if source[position].isspace():
                position += 1
                continue

            character = source[position]
            if character in "()[]|":
                tokens.append(character)
                position += 1
                continue

            if character in ("'", '"'):
                quote = character
                start = position
                position += 1
                escaped = False
                while position < len(source):
                    current = source[position]
                    position += 1
                    if escaped:
                        escaped = False
                        continue
                    if current == "\\":
                        escaped = True
                        continue
                    if current == quote:
                        break
                else:
                    raise _GrammarSyntaxError("unterminated quoted grammar literal")

                raw = source[start:position]
                try:
                    literal = ast.literal_eval(raw)
                except (SyntaxError, ValueError) as exception:
                    raise _GrammarSyntaxError(f"invalid quoted grammar literal: {raw!r}") from exception
                if not isinstance(literal, str):
                    raise _GrammarSyntaxError("quoted grammar literals must contain text")
                tokens.append(literal)
                continue

            if character == "<":
                end = source.find(">", position + 1)
                if end < 0:
                    raise _GrammarSyntaxError("unterminated argument declaration")
                tokens.append(source[position : end + 1])
                position = end + 1
                continue

            start = position
            while position < len(source) and not source[position].isspace() and source[position] not in "()[]|":
                position += 1
            tokens.append(source[start:position])

        return tuple(tokens)

    def _parse_argument(self, token: str) -> _ArgumentTerm:
        if not token.endswith(">"):
            raise _GrammarSyntaxError(f"invalid argument declaration {token!r}")
        body = token[1:-1].strip()
        if not body:
            raise _GrammarSyntaxError("argument name cannot be empty")

        default: Any = None
        has_default = "=" in body
        if has_default:
            body, default_text = body.split("=", 1)
            default = default_text

        if body.endswith("..."):
            name = body[:-3].strip()
            type_name = "greedy_string"
        elif ":" in body:
            name, type_name = (part.strip() for part in body.split(":", 1))
        else:
            name, type_name = body.strip(), "word"

        if not name:
            raise _GrammarSyntaxError("argument name cannot be empty")
        if not type_name:
            raise _GrammarSyntaxError(f"argument {name!r} has no type")
        if has_default and type_name in {"int", "integer"}:
            try:
                default = int(default)
            except (TypeError, ValueError) as exception:
                raise _GrammarSyntaxError(f"default for {name!r} must be an integer") from exception
        return _ArgumentTerm(name, type_name.casefold(), default, has_default)

    def _peek(self) -> str | None:
        if self._position == len(self._tokens):
            return None
        return self._tokens[self._position]

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise _GrammarSyntaxError("grammar ended before a complete expression")
        self._position += 1
        return token

    def _expect(self, expected: str) -> None:
        actual = self._take()
        if actual != expected:
            raise _GrammarSyntaxError(f"expected {expected!r}, got {actual!r}")


def _expand(term: Any) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Expand choices and optionals into terminal paths and defaults."""
    if isinstance(term, _LiteralTerm) or isinstance(term, _ArgumentTerm):
        if isinstance(term, _ArgumentTerm) and term.has_default:
            return [((term,), {}), ((), {term.name: term.default})]
        return [((term,), {})]

    if isinstance(term, _ChoiceTerm):
        paths: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        for alternative in term.alternatives:
            paths.extend(_expand_sequence(alternative))
        return paths

    if isinstance(term, _OptionalTerm):
        return [((), {}), *_expand(term.body)]

    raise _GrammarSyntaxError(f"unsupported grammar term: {term!r}")


def _expand_sequence(sequence: tuple[Any, ...]) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    paths: list[tuple[tuple[Any, ...], dict[str, Any]]] = [((), {})]
    for term in sequence:
        next_paths: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        for prefix, prefix_defaults in paths:
            for suffix, suffix_defaults in _expand(term):
                defaults = dict(prefix_defaults)
                defaults.update(suffix_defaults)
                next_paths.append((prefix + suffix, defaults))
        paths = next_paths
    return paths


def _argument_type(type_name: str) -> Any:
    types = {
        "word": CmdType.Word,
        "string": CmdType.String,
        "int": CmdType.Int,
        "integer": CmdType.Int,
        "greedy": CmdType.GreedyString,
        "greedy_string": CmdType.GreedyString,
    }
    selected = types.get(type_name)
    if selected is None:
        raise _GrammarSyntaxError(f"unsupported argument type {type_name!r}")
    return selected()


def _find_child(parent: Any, term: Any) -> Any | None:
    for child in parent.children:
        if isinstance(term, _LiteralTerm) and isinstance(child, CmdNode.Literal):
            if child.name == term.value:
                return child
        elif isinstance(term, _ArgumentTerm) and isinstance(child, CmdNode.Argument):
            if child.name == term.name and child.argument_type.name == _argument_type(term.type_name).name:
                return child
    return None


def _make_action_handler(
    command_name: str,
    action_provider: Callable[[], Mapping[str, Any]],
    defaults: Mapping[str, Any],
) -> _Action:
    default_values = dict(defaults)

    def handler(**arguments: Any) -> Any:
        values = dict(default_values)
        values.update(arguments)
        action = action_provider().get(command_name)
        if action is not None and not callable(action):
            raise TypeError(f"action for {command_name!r} must be callable")
        if action is None:
            return None
        return action(**values)

    return handler


def _compile_grammars(
    grammars: _GrammarSource,
    action_provider: Callable[[], Mapping[str, Any]],
    keep_help: bool,
    command_prefix: str,
) -> CmdNode.Dispatcher:
    dispatcher = CmdNode.Dispatcher()
    actions = action_provider()

    for command_name, syntax in grammars.items():
        if not isinstance(command_name, str) or not command_name:
            raise _GrammarSyntaxError("command names must be non-empty strings")
        if not isinstance(syntax, str):
            raise _GrammarSyntaxError(f"grammar for {command_name!r} must be a string")
        if command_name == "help" and keep_help:
            continue

        action = actions.get(command_name)
        if action is not None and not callable(action):
            raise _GrammarSyntaxError(f"action for {command_name!r} must be callable")

        expression = _GrammarParser(syntax).parse()
        paths = _expand_sequence(expression)
        root = CmdNode.Literal(command_name)
        for terms, defaults in paths:
            current = root
            for term in terms:
                child = _find_child(current, term)
                if child is None:
                    if isinstance(term, _LiteralTerm):
                        child = CmdNode.Literal(term.value)
                    else:
                        child = CmdNode.Argument(term.name, _argument_type(term.type_name))
                    current.add_child(child)
                current = child
            current.set_command(_make_action_handler(command_name, action_provider, defaults))
        dispatcher.register(root)

    if keep_help:
        command_names = tuple(name for name in grammars if name != "help")

        def help_action(**_arguments: Any) -> dict[str, Any]:
            return {"commands": command_names, "prefix": command_prefix}

        dispatcher.register(CmdNode.Literal("help", command=help_action))

    return dispatcher


@dataclass(frozen=True, slots=True)
class ControlResult:
    """Structured output from one control request."""

    ok: bool
    code: int
    kind: str
    input: Any
    command: str | None = None
    value: Any = None
    parse_result: CmdParse.Result | None = None
    context: CmdParse.Context | None = None
    handler: _Action | None = None
    error: CmdParse.Error | None = None
    message: str = ""
    exception: str | None = None

    @property
    def success(self) -> bool:
        """Readable alias for :attr:`ok`."""
        return self.ok

    @property
    def parsed_args(self) -> dict[str, Any]:
        """Return parsed and controlled arguments without exposing internals."""
        if self.context is None:
            return {}
        return dict(self.context.args)

    @property
    def result(self) -> Any:
        """Return the action value for callers that prefer a short name."""
        return self.value

    def __bool__(self) -> bool:
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        """Return the transport-friendly representation of this result."""
        data: dict[str, Any] = {
            "ok": self.ok,
            "code": int(self.code),
            "kind": self.kind,
            "input": self.input,
            "command": self.command,
            "value": self.value,
        }
        if self.context is not None:
            data["parsed_args"] = dict(self.context.args)
        if self.error is not None:
            data["error"] = {
                "kind": self.error.kind,
                "token_index": self.error.token_index,
                "expected": self.error.expected,
                "message": self.error.message,
                "partial_args": dict(self.error.partial_args),
                "code": None if self.error.code is None else int(self.error.code),
            }
        if self.message:
            data["message"] = self.message
        if self.exception is not None:
            data["exception"] = self.exception
        return data

    as_dict = to_dict


@dataclass(frozen=True, slots=True)
class ControlInitialization:
    """Result returned after grammar and optional fixture initialization."""

    ok: bool
    code: int
    message: str = ""
    command_count: int = 0
    exception: str | None = None

    def __bool__(self) -> bool:
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ok": self.ok,
            "code": int(self.code),
            "message": self.message,
            "command_count": self.command_count,
        }
        if self.exception is not None:
            data["exception"] = self.exception
        return data

    as_dict = to_dict


@dataclass(frozen=True, slots=True)
class _Invocation:
    command: str
    parsed: CmdParse.Result
    context: CmdParse.Context
    handler: _Action


class _DeeperLevelContext:
    """Live Python-facing control state.

    The object intentionally exposes the dispatcher and fixture instance for
    embedded Python users.  Process-boundary callers should use
    :class:`ControlResult` instead of inspecting this state.
    """

    def __init__(self, command_context: Any = ctx) -> None:
        self.context = command_context
        self.dispatcher = CmdNode.Dispatcher()
        self.grammars: dict[str, str] = {}
        self.fixture_module: ModuleType | None = None
        self.fixture_logic: Any = None
        self.initialized = False
        self.last_result: ControlResult | None = None
        self.last_initialization: ControlInitialization | None = None

    @property
    def command_args_ctrl(self) -> dict[str, Any]:
        """Return the argument override map owned by the shared context."""
        return self.context.command_args_ctrl

    @command_args_ctrl.setter
    def command_args_ctrl(self, value: dict[str, Any]) -> None:
        if not isinstance(value, dict):
            raise TypeError("command_args_ctrl must be a dictionary")
        self.context.command_args_ctrl = value

    @property
    def command_action(self) -> dict[str, _Action]:
        return self.context.command_action

    @command_action.setter
    def command_action(self, value: dict[str, _Action]) -> None:
        if not isinstance(value, dict):
            raise TypeError("command_action must be a dictionary")
        self.context.command_action = value

    def set_command_args(self, command: str, **arguments: Any) -> None:
        """Set runtime argument overrides for one command."""
        if not isinstance(command, str) or not command:
            raise ValueError("command must be a non-empty string")
        overrides = self.command_args_ctrl.setdefault(command, {})
        if not isinstance(overrides, dict):
            raise TypeError(f"argument overrides for {command!r} must be a dictionary")
        overrides.update(arguments)

    def clear_command_args(self, command: str | None = None) -> None:
        """Clear one command's overrides, or all overrides when omitted."""
        if command is None:
            self.command_args_ctrl.clear()
        else:
            self.command_args_ctrl.pop(command, None)


DeeperLevelContext: Final[type[_DeeperLevelContext]] = _DeeperLevelContext


class Control:
    """Initialize, execute, and inspect one command-router control surface."""

    def __init__(
        self,
        *,
        command_context: Any = ctx,
        deeper: _DeeperLevelContext | None = None,
    ) -> None:
        self.context = command_context
        self.deeper_level = deeper if deeper is not None else _DeeperLevelContext(command_context)
        self._async_lock = asyncio.Lock()
        self._stderr_locked = False

    @property
    def deeper(self) -> _DeeperLevelContext:
        """Short alias for :attr:`deeper_level`."""
        return self.deeper_level

    def initialize(
        self,
        grammars: _GrammarSource | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization:
        """Configure the dispatcher and optionally initialize fixture logic.

        When *fixture* is provided, only its ``FixtureGrammarLogic`` (or
        ``_FixG``) callable and its ``setup`` callable are invoked.  Other
        module-level names are deliberately ignored.
        """
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
        """Compile grammar strings into the existing hand-built dispatcher."""
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
        result = ControlInitialization(
            False,
            code,
            message,
            exception=None if exception is None else f"{type(exception).__name__}: {exception}",
        )
        self.deeper_level.last_initialization = result
        return result

    def close(self) -> None:
        """Release the stderr wrapper installed for fixture execution."""
        if self._stderr_locked:
            log_handler.unlock_stderr()
            self._stderr_locked = False

    def __enter__(self) -> Control:
        return self

    def __exit__(self, *_arguments: Any) -> None:
        self.close()

    def execute(self, command: Any) -> ControlResult:
        """Execute one command synchronously and return a structured result."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.execute_async(command))
        return self._execute_sync(command)

    dispatch = execute

    async def execute_async(self, command: Any) -> ControlResult:
        """Execute one command while serializing async handlers."""
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
        self.deeper_level.last_result = result
        return result


def _load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType:
    if isinstance(source, ModuleType):
        return source

    if isinstance(source, Path):
        candidate = source
    elif isinstance(source, str):
        candidate = Path(source)
        if not candidate.exists() and not source.endswith(".py"):
            return importlib.import_module(source)
    else:
        raise TypeError("fixture must be a module, module name, or path")

    if candidate.is_dir():
        candidate = candidate / "__init__.py"
    if not candidate.is_file():
        raise FileNotFoundError(f"fixture module does not exist: {candidate}")

    module_name = f"_cmd_router_fixture_{identifier}"
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load fixture module: {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


control: Final[Control] = Control()
deeper_level: Final[_DeeperLevelContext] = control.deeper_level


def initialize(
    grammars: _GrammarSource | None = None,
    *,
    fixture: ModuleType | str | Path | None = None,
    keep_help: bool | None = None,
) -> ControlInitialization:
    """Initialize the module-level control surface."""
    return control.initialize(grammars, fixture=fixture, keep_help=keep_help)


def execute(command: Any) -> ControlResult:
    """Execute through the module-level control surface."""
    return control.execute(command)


async def execute_async(command: Any) -> ControlResult:
    """Async counterpart to :func:`execute`."""
    return await control.execute_async(command)
