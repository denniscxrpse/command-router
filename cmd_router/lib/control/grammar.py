#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Parse the compact grammar syntax used by control fixtures."""

import ast
from dataclasses import dataclass
from typing import Any


class _GrammarSyntaxError(ValueError):
    """Report an invalid control grammar expression."""


@dataclass(frozen=True, slots=True)
class _LiteralTerm:
    """Represent one literal grammar term."""

    value: str


@dataclass(frozen=True, slots=True)
class _ArgumentTerm:
    """Represent one argument grammar term."""

    name: str
    type_name: str
    default: Any = None
    has_default: bool = False


@dataclass(frozen=True, slots=True)
class _ChoiceTerm:
    """Represent alternatives in a grammar expression."""

    alternatives: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True, slots=True)
class _OptionalTerm:
    """Represent an optional grammar expression."""

    body: _ChoiceTerm


class _GrammarParser:
    """Parse the small grammar notation accepted by control."""

    def __init__(self, source: str) -> None:
        """Create a parser for *source*."""
        self._tokens = self._scan(source)
        self._position = 0

    def parse(self) -> tuple[Any, ...]:
        """Return the parsed grammar expression."""
        alternatives = self._parse_alternatives(None)
        if self._position != len(self._tokens):
            token = self._tokens[self._position]
            raise _GrammarSyntaxError(f"unexpected grammar token {token!r}")
        return (_ChoiceTerm(alternatives),)

    def _parse_alternatives(self, closing: str | None) -> tuple[tuple[Any, ...], ...]:
        """Parse alternatives up to *closing*."""
        alternatives = [self._parse_sequence(closing)]
        while self._peek() == "|":
            self._position += 1
            alternatives.append(self._parse_sequence(closing))
        return tuple(alternatives)

    def _parse_sequence(self, closing: str | None) -> tuple[Any, ...]:
        """Parse a sequence up to *closing* or an alternative marker."""
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
        """Parse one literal, argument, choice, or optional term."""
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
        """Tokenize a grammar source string."""
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
        """Parse one argument declaration."""
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
        """Return the next token without consuming it."""
        if self._position == len(self._tokens):
            return None
        return self._tokens[self._position]

    def _take(self) -> str:
        """Consume and return the next token."""
        token = self._peek()
        if token is None:
            raise _GrammarSyntaxError("grammar ended before a complete expression")
        self._position += 1
        return token

    def _expect(self, expected: str) -> None:
        """Consume *expected* or raise a syntax error."""
        actual = self._take()
        if actual != expected:
            raise _GrammarSyntaxError(f"expected {expected!r}, got {actual!r}")
