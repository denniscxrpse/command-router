#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Hand-built command tree nodes and the command dispatcher."""

__all__ = (
    "ArgumentNode",
    "CommandNode",
    "LiteralNode",
    "RootNode",
    "CommandDispatcher",
    "cmd_dispatcher",
)

from collections.abc import Callable
from typing import Any, Final

from cmd_router.lib.command.context import *
from cmd_router.lib.command.dispatcher.nodes import *
from cmd_router.lib.command.typing import *
from cmd_router.lib.tokenizer import *

_Handler = Callable[..., Any]


class CommandDispatcher:
    """Parse tokenized input against a hand-built command tree."""

    def __init__(self, root: RootNode | None = None) -> None:
        self.root = root if root is not None else RootNode()

    def register(self, node: CommandNode) -> CommandNode:
        """Register a top-level node and return it."""
        return self.root.add_child(node)

    def parse(self, command: str) -> ParseResult:
        """Parse *command* and return its handler/context or the best error."""
        tokens = tokenize(command)
        if isinstance(tokens, int):
            failure = ParseError(
                kind="tokenization",
                token_index=0,
                expected=self._expected(self.root),
                message=f"could not tokenize command ({tokens})",
                code=tokens,
            )
            return ParseResult(error=failure)

        token_values = tuple(tokens)
        result = self._walk(self.root, token_values, 0, {}, command)
        if isinstance(result, ParseResult):
            return result
        return ParseResult(error=result)

    def dispatch(self, command: str) -> ParseResult:
        """Alias for :meth:`parse` for callers thinking in dispatcher terms."""
        return self.parse(command)

    def _walk(
        self,
        node: CommandNode,
        tokens: tuple[str, ...],
        index: int,
        args: dict[str, Any],
        original_input: str,
    ) -> ParseResult | ParseError:
        if index == len(tokens):
            if node.command is not None:
                return ParseResult(
                    handler=node.command,
                    context=CommandContext(
                        input=original_input,
                        args=dict(args),
                        cursor=index,
                        tokens=tokens,
                    ),
                )
            return self._incomplete(node, index, args)

        literal_children = [child for child in node.children if isinstance(child, LiteralNode)]
        argument_children = [child for child in node.children if isinstance(child, ArgumentNode)]
        failures: list[ParseError] = []

        for child in literal_children:
            if child.name != tokens[index]:
                continue
            result = self._walk(child, tokens, index + 1, args, original_input)
            if isinstance(result, ParseResult):
                return result
            failures.append(result)

        for child in argument_children:
            value = " ".join(tokens[index:]) if child.greedy else tokens[index]
            parsed = child.argument_type.parse(value)
            if isinstance(parsed, ArgumentParseError):
                failures.append(
                    ParseError(
                        kind="invalid_argument",
                        token_index=index,
                        expected=(child.label,),
                        message=parsed.message,
                        partial_args=dict(args),
                    )
                )
                continue

            next_args = dict(args)
            next_args[child.name] = parsed
            next_index = len(tokens) if child.greedy else index + 1
            result = self._walk(child, tokens, next_index, next_args, original_input)
            if isinstance(result, ParseResult):
                return result
            failures.append(result)

        if failures:
            return self._best_error(failures)
        return ParseError(
            kind="unexpected_token",
            token_index=index,
            expected=self._expected(node),
            message=f"unexpected token: {tokens[index]!r}",
            partial_args=dict(args),
        )

    def _incomplete(self, node: CommandNode, index: int, args: dict[str, Any]) -> ParseError:
        expected = self._expected(node)
        message = "incomplete command" if not expected else f"expected one of: {', '.join(expected)}"
        return ParseError(
            kind="incomplete_command",
            token_index=index,
            expected=expected,
            message=message,
            partial_args=dict(args),
        )

    @staticmethod
    def _expected(node: CommandNode) -> tuple[str, ...]:
        return tuple(child.label for child in node.children)

    @staticmethod
    def _best_error(errors: list[ParseError]) -> ParseError:
        furthest = max(error.token_index for error in errors)
        candidates = [error for error in errors if error.token_index == furthest]
        if len(candidates) == 1:
            return candidates[0]

        first = candidates[0]
        expected = tuple(dict.fromkeys(item for candidate in candidates for item in candidate.expected))
        partial_args = max(candidates, key=lambda candidate: len(candidate.partial_args)).partial_args
        return ParseError(
            kind=first.kind,
            token_index=first.token_index,
            expected=expected,
            message=first.message,
            partial_args=dict(partial_args),
            code=first.code,
        )


cmd_dispatcher: Final[CommandDispatcher] = CommandDispatcher()
