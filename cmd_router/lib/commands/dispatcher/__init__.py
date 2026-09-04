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
    "tokenize",
    "cmd_dispatcher",
)

import shlex
from collections.abc import Callable
from typing import Any, Final

from cmd_router.lib.commands.context import *
from cmd_router.lib.commands.dispatcher.nodes import *
from cmd_router.lib.commands.typing import ArgumentParseError
from cmd_router.utils.logger import log
from cmd_router.utils.status import *

_Handler = Callable[..., Any]


def tokenize(command: str) -> list[str] | Status:
    """Return shell-like tokens from *commands*.

    Empty and whitespace-only input produce an empty list. Quoting and
    backslash escaping follow `shlex.split`. Unsupported input types and
    malformed commands strings return the corresponding tokenizer error code.
    """

    log.debug("received input of type %s", type(command).__name__)
    if not isinstance(command, str):
        log.warning("cannot tokenize non-string input (%s)", type(command).__name__)
        return stat.TokenizeUnsupportedTypeError()
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError as exception:
        log.error("malformed commands input: %s", exception)
        return stat.TokenizeInvalidError()
    log.debug("produced %d token(s): %r", len(tokens), tokens)
    return tokens


class CommandDispatcher:
    """Parse tokenized input against a hand-built command tree."""

    def __init__(self, root: RootNode | None = None) -> None:
        self.root = root if root is not None else RootNode()
        log.debug("created with root containing %d child node(s)", len(self.root.children))

    def register(self, node: CommandNode) -> CommandNode:
        """Register a top-level node and return it."""
        log.debug("registering root node %r (%s)", node.name, node.kind)
        return self.root.add_child(node)

    def parse(self, command: str) -> ParseResult:
        """Parse *command* and return its handler/context or the best error."""
        log.debug("tokenizing input %r", command)
        tokens = tokenize(command)

        if isinstance(tokens, Status):
            log.error("tokenization failed with code %s", tokens.name)
            failure = ParseError(
                kind=ParseErrorKinds.TOKENIZATION,
                token_index=0,
                expected=self._expected(self.root),
                message=f"could not tokenize command ({tokens})",
                code=tokens,
            )
            return ParseResult(error=failure)

        token_values = tuple(tokens)
        log.debug("received %d token(s): %r", len(token_values), token_values)
        result = self._walk(self.root, token_values, 0, {}, command)
        if isinstance(result, ParseResult):
            log.debug("parse matched at token %d", result.context.cursor if result.context else -1)
            return result
        log.error(
            "parse failed (%s) at token %d; expected=%s",
            result.kind,
            result.token_index,
            result.expected,
        )
        return ParseResult(error=result)

    def dispatch(self, command: str) -> ParseResult:
        """Alias for `parse` for callers thinking in dispatcher terms."""
        return self.parse(command)

    def _walk(
        self,
        node: CommandNode,
        tokens: tuple[str, ...],
        index: int,
        args: dict[str, Any],
        original_input: str,
    ) -> ParseResult | ParseError:
        log.debug(
            "visiting node %r at token %d/%d with args=%r",
            node.label or "<root>",
            index,
            len(tokens),
            args,
        )
        if index == len(tokens):
            if node.command is not None:
                log.debug("terminal handler found at %r", node.label or "<root>")
                return ParseResult(
                    handler=node.command,
                    context=CommandContext(
                        input=original_input,
                        args=dict(args),
                        cursor=index,
                        tokens=tokens,
                    ),
                )
            log.debug("input ended before a command was complete at %r", node.label or "<root>")
            return self._incomplete(node, index, args)

        literal_children = [child for child in node.children if isinstance(child, LiteralNode)]
        argument_children = [child for child in node.children if isinstance(child, ArgumentNode)]
        failures: list[ParseError] = []

        for child in literal_children:
            if child.name != tokens[index]:
                continue
            log.debug("trying literal %r at token %d", child.name, index)
            result = self._walk(child, tokens, index + 1, args, original_input)
            if isinstance(result, ParseResult):
                return result
            failures.append(result)

        for child in argument_children:
            value = " ".join(tokens[index:]) if child.greedy else tokens[index]
            parsed = child.argument_type.parse(value)  # ty: ignore[unresolved-attribute]
            if isinstance(parsed, ArgumentParseError):
                log.debug("argument %r rejected value %r: %s", child.label, value, parsed.message)
                failures.append(
                    ParseError(
                        kind=ParseErrorKinds.INVALID_ARGUMENT,
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
            log.debug("argument %r accepted value %r", child.label, parsed)
            result = self._walk(child, tokens, next_index, next_args, original_input)
            if isinstance(result, ParseResult):
                return result
            failures.append(result)

        if failures:
            log.debug("selecting the best of %d branch failure(s)", len(failures))
            return self._best_error(failures)
        log.debug("no child matched token %r at index %d", tokens[index], index)
        return ParseError(
            kind=ParseErrorKinds.UNEXPECTED_TOKEN,
            token_index=index,
            expected=self._expected(node),
            message=f"unexpected token: {tokens[index]!r}",
            partial_args=dict(args),
        )

    def _incomplete(self, node: CommandNode, index: int, args: dict[str, Any]) -> ParseError:
        expected = self._expected(node)
        message = "incomplete command" if not expected else f"expected one of: {', '.join(expected)}"
        log.debug("incomplete command at token %d; expected=%s", index, expected)
        return ParseError(
            kind=ParseErrorKinds.UNEXPECTED_COMMAND,
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
            log.debug("best error is the only failure at token %d", furthest)
            return candidates[0]

        first = candidates[0]
        expected = tuple(dict.fromkeys(item for candidate in candidates for item in candidate.expected))
        partial_args = max(candidates, key=lambda candidate: len(candidate.partial_args)).partial_args
        log.debug("merged %d furthest failures at token %d", len(candidates), furthest)
        return ParseError(
            kind=first.kind,
            token_index=first.token_index,
            expected=expected,
            message=first.message,
            partial_args=dict(partial_args),
            code=first.code,
        )


cmd_dispatcher: Final[CommandDispatcher] = CommandDispatcher()
