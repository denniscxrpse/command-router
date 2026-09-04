from typing import cast

import pytest

from cmd_router.lib.commands import CmdParse
from cmd_router.utils.status import stat


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
    result = CmdParse.Tokenize('say "hello')
    assert isinstance(result, type(stat.TokenizeInvalidError()))
    assert result.name == stat.TokenizeInvalidError().name


def test_tokenize_unsupported_type_returns_friendly_error() -> None:
    result = CmdParse.Tokenize(cast(str, 42))
    assert isinstance(result, type(stat.TokenizeUnsupportedTypeError()))
    assert result.name == stat.TokenizeUnsupportedTypeError().name
