#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Tokenize and parse the compact grammar notation used by control fixtures.

This module is the syntax-only front end for the control grammar compiler.  It turns one grammar string into a small
immutable, private syntax tree made from the term records below.  It does not build dispatcher nodes, resolve argument
types, validate action functions, or parse user-entered command text.  Those responsibilities belong to
``cmd_router.lib.control.compiler`` and the command dispatcher respectively.

The supported notation is intentionally small:

``literal``
    A required literal token.  Whitespace separates ordinary tokens.
``(a|b|c)``
    A choice.  Each side of ``|`` is a sequence and may contain nested terms.
``[term]``
    An optional term or group.  The body may itself contain choices and sequences.
``<name>``
    A required ``word`` argument.
``<name:type>``
    A required argument whose type name is retained for the compiler.
``<name...>``
    A greedy-string argument.  The trailing ellipsis is translated to the ``greedy_string`` type name.
``<name:type=default>``
    An argument declaration with an alternate omitted value.  The parser stores defaults as text except that a source
    type spelled ``int`` or ``integer`` is converted to an ``int`` immediately.
``'literal'`` or ``"literal"``
    A quoted literal.  Quotes are removed with ``ast.literal_eval``, so Python string escapes are accepted, and
    punctuation or whitespace inside the literal is not interpreted as grammar structure.

Only the parser recognizes syntax.  The compiler currently accepts the type names ``word``, ``string``,
``int``/``integer``, and ``greedy``/``greedy_string``.  Unknown type names are preserved in an ``_ArgumentTerm`` and
rejected later by the compiler.  Likewise, this parser does not enforce dispatcher-specific rules such as the
requirement that a greedy argument be terminal.

Parsing is performed in two passes.  ``_scan`` walks the source character by character and emits tokens for
structural markers, quoted literals, argument declarations, and unquoted literals.  ``_GrammarParser`` then consumes
those tokens with a recursive-descent parser.  Parentheses and brackets pass their closing marker down to the
sequence parser, while ``|`` terminates the current sequence and is consumed by the alternatives' parser.  The
top-level result is wrapped in a one-element tuple containing ``_ChoiceTerm``.  This may look unusual for a source
that is not visibly a choice, but it gives the compiler a uniform representation: the whole expression can be
expanded by the same choice/sequence machinery used for nested groups.

The parser intentionally preserves structure rather than eagerly producing paths.
A source such as ``(survival|creative) [<target>]`` becomes a choice whose alternatives contain literal terms,
followed by an optional term whose body is another choice.  The compiler later turns that structure into four
possible paths.  Dataclass terms are frozen and slotted, so they can be passed around safely as parser output
without exposing the mutable parser state.

Errors are raised as ``_GrammarSyntaxError``, a ``ValueError`` subclass used by the control API as a
grammar-initialization failure.  The scanner reports unterminated quotes and argument declarations and rejects
quoted values that are not strings.  The parser reports unexpected closing markers, incomplete groups,
missing names/types, empty literals, and trailing tokens.  It does not attach source offsets to these errors;
structured token positions are produced later when the compiled dispatcher parses an actual command.  Empty source,
empty alternatives, and empty groups are syntactically representable because the recursive sequence parser can return
an empty tuple; the compiler decides what those empty paths mean in a command tree.

All names in this module are private implementation details.  Use the control
API for normal grammar configuration and keep grammar examples in fixture
files or public configuration documentation.
"""

import ast
from dataclasses import dataclass
from typing import Any

from cmd_router.utils.logger import log


class _GrammarSyntaxError(ValueError):
    """Report a grammar-source error before command-tree compilation.

    This exception distinguishes malformed grammar notation from failures that happen later while building or
    executing a command tree.  It subclasses ``ValueError`` so callers that do not know the private parser type can
    still handle it with ordinary value-validation logic.  The parser does not add a character offset; its messages
    describe the offending token or declaration instead.
    """

    ...


@dataclass(frozen=True, slots=True)
class _LiteralTerm:
    """Represent one exact literal after grammar tokenization.

    ``value`` contains the unquoted value.  Structural punctuation is never stored here when it was used as grammar
    syntax, while punctuation inside a quoted literal is preserved.  Matching the value against runtime command
    tokens is the dispatcher's responsibility.
    """

    value: str


@dataclass(frozen=True, slots=True)
class _ArgumentTerm:
    """Represent one typed or greedy argument declaration.

    ``name`` is passed to the eventual action as a keyword.  ``type_name`` is case-folded by the parser but is not
    otherwise canonicalized; the compiler resolves aliases such as ``integer`` and ``greedy_string``.  ``default``
    holds the value for the alternate path in which this argument is omitted, and ``has_default`` is separate from
    the value, so an explicit default such as an empty string or ``None``-like text can be distinguished from no
    default at all.
    """

    name: str
    type_name: str
    default: Any = None
    has_default: bool = False


@dataclass(frozen=True, slots=True)
class _ChoiceTerm:
    """Represent one or more alternative sequences.

    Each element of ``alternatives`` is a tuple of terms to be traversed in order.  A choice may be top-level,
    parenthesized, or the body of an optional term.  The parser retains alternatives as sequences rather than
    flattening them, so nesting remains visible to the compiler's expansion step.
    """

    alternatives: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True, slots=True)
class _OptionalTerm:
    """Represent a grammar expression that may contribute no terms.

    ``body`` is always a ``_ChoiceTerm`` so an optional single term, sequence, or nested choice can use one uniform
    representation.  The parser records optionality here but does not duplicate paths; the compiler adds the empty
    branch during expansion.
    """

    body: _ChoiceTerm


class _GrammarParser:
    """Parse one compact grammar string with a recursive-descent parser.

    The parser owns a tuple of scanner tokens and a cursor into that tuple.  A call to ``parse`` consumes one
    complete expression and returns the private term representation used by the compiler.  Parsing methods stop at the
    structural marker owned by their caller, which is how nested parentheses, brackets, and alternatives are handled
    without a separate token-reader abstraction.

    This class is intentionally single-use.  Its cursor is advanced as terms are consumed; constructing a new parser
    is the supported way to parse a new source string or retry after an error.
    """

    def __init__(self, source: str) -> None:
        """Scan *source* and create a parser positioned at its first token.

        Scanning is eager, so malformed quoting or an unterminated argument declaration fails before recursive
        parsing begins.  The resulting tokens are immutable for the lifetime of this parser, and the cursor is
        initialized to zero.
        """
        log.debug("scanning source %r", source)
        self._tokens = self._scan(source)
        self._position = 0
        log.debug("scanner produced %d token(s)", len(self._tokens))

    def parse(self) -> tuple[Any, ...]:
        """Parse and return the complete grammar expression.

        The top-level expression is represented as a one-element tuple whose item is a ``_ChoiceTerm``.  The wrapper
        gives the compiler the same shape for a plain sequence and for a source containing ``|``.  Parsing succeeds
        only when the alternative parser consumes every token; a token left behind is reported as an unexpected
        grammar token rather than being silently ignored.

        :return: The private syntax-tree sequence consumed by the compiler.
        :raises _GrammarSyntaxError: If the source is incomplete, it contains a mismatched structure or has trailing
        tokens.
        """
        alternatives = self._parse_alternatives(None)
        if self._position != len(self._tokens):
            token = self._tokens[self._position]
            raise _GrammarSyntaxError(f"unexpected grammar token {token!r}")
        log.debug("parsed %d top-level alternative(s)", len(alternatives))
        return (_ChoiceTerm(alternatives),)

    def _parse_alternatives(self, closing: str | None) -> tuple[tuple[Any, ...], ...]:
        """Parse one or more sequences separated by ``|``.

        Parsing stops before *closing* when this method is handling a nested group, or at end-of-input for the top
        level.  The separator is consumed here, while each sequence parser leaves its closing marker untouched
        for the caller to consume.  Because an empty sequence is valid to this syntax layer, leading, trailing,
        or repeated ``|`` markers produce empty alternatives that the compiler may later expand into empty paths.
        """
        alternatives = [self._parse_sequence(closing)]
        while self._peek() == "|":
            self._position += 1
            alternatives.append(self._parse_sequence(closing))
        return tuple(alternatives)

    def _parse_sequence(self, closing: str | None) -> tuple[Any, ...]:
        """Parse consecutive terms until a boundary owned by the caller.

        A sequence ends before ``|`` or the supplied *closing* marker.  A closing marker of the wrong kind is an
        error rather than a literal, which prevents a malformed group from being accepted as a different grammar.
        Returning an empty tuple is intentional and represents an empty source, branch, or group at the syntax level.
        """
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
        """Consume and parse one term from the current token.

        Parentheses recursively parse a ``_ChoiceTerm`` and require ``)``; brackets do the same while wrapping the
        result in ``_OptionalTerm``. Tokens beginning with ``<`` are argument declarations.  Everything else is an
        exact literal, except that an empty token is rejected so a quoted empty string cannot become an unusable
        command node.
        """
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
        """Tokenize a *source* without applying runtime command tokenization.

        Outside quotes, whitespace is discarded and ``()[]|`` are emitted as individual structural tokens.  A quoted
        span is consumed as one token, decoded with ``ast.literal_eval``, and required to evaluate to
        a string.  An argument declaration consumes from ``<`` through the first following ``>``; its internal text
        is left for ``_parse_argument``.  All other characters are collected into one unquoted literal until
        whitespace or a structural marker appears.

        This scanner is for grammar definitions, not command invocations.  At execution time the dispatcher uses the
        project's command tokenizer, so quoting in a user's command is interpreted independently of quoting
        in this source string.

        :raises _GrammarSyntaxError: For an unterminated quote, an unterminated argument declaration, an invalid
        Python-style quoted literal, or a quoted value that is not text.
        """
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

    @staticmethod
    def _parse_argument(token: str) -> _ArgumentTerm:
        """Decode one ``<...>`` token into an ``_ArgumentTerm``.

        The body is trimmed and then split at the first ``=`` when a default is present.  A trailing ``...`` takes
        precedence as the shorthand for ``greedy_string``; otherwise the first ``:`` separates the name from
        the type, and an omitted type defaults to ``word``.  Type names are case-folded for the compiler.  Defaults
        remain text except for source type spellings ``int`` and ``integer``, which are converted and report
        a syntax error when the value is not a valid integer.

        The parser validates that the declaration has a name and, when a type separator is present, a type name.  It
        deliberately does not validate the type against the compiler's supported-type map or enforce semantic
        rules such as unique argument names and terminal greedy placement.

        :raises _GrammarSyntaxError: If the token is not closed, has an empty name/type, or has an invalid integer
        default.
        """
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
        """Return the current token without moving the parser cursor.

        ``None`` is the end-of-input sentinel.  It is distinct from an empty parsed sequence because no token is
        available to consume in that state.
        """
        if self._position == len(self._tokens):
            return None
        return self._tokens[self._position]

    def _take(self) -> str:
        """Consume and return the current token.

        Attempting to consume past the scanner output is treated as an incomplete grammar expression and reported
        through the parser's syntax exception rather than an indexing failure.
        """
        token = self._peek()
        if token is None:
            raise _GrammarSyntaxError("grammar ended before a complete expression")
        self._position += 1
        return token

    def _expect(self, expected: str) -> None:
        """Consume exactly *expected* at the current cursor position.

        The actual token is consumed before it is compared, so callers use this helper only after a nested parser has
        stopped at the closing boundary it expects.  ``_take`` reports End-of-input; a different closing
        marker receives a message containing both expected and actual tokens.
        """
        actual = self._take()
        if actual != expected:
            raise _GrammarSyntaxError(f"expected {expected!r}, got {actual!r}")
