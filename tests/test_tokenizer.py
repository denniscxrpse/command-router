from typing import cast

import pytest

from cmd_router.lib.commands import CmdError, CmdParse


@pytest.mark.parametrize(
    "command",
    ["", " \t\n  "],
)
def test_tokenize_empty_input(command: str) -> None:
    assert CmdParse.Tokenize(command) == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('say "hello world"', ["say", "hello world"]),
        (r'say "She said \"hello\""', ["say", 'She said "hello"']),
    ],
)
def test_tokenize_quoted_strings(command: str, expected: list[str]) -> None:
    assert CmdParse.Tokenize(command) == expected


def test_tokenize_unterminated_quote_returns_invalid_error() -> None:
    assert CmdParse.Tokenize('say "hello') == CmdError.TokenizeInvalidError


def test_tokenize_unsupported_type_returns_friendly_error() -> None:
    assert CmdParse.Tokenize(cast(str, 42)) == CmdError.TokenizeUnsupportedTypeError
