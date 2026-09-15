from collections.abc import Callable, Mapping
from typing import Any

from command_router.lib.commands.dispatcher import CommandDispatcher

__all__ = ["build_grammar", "build_redirect_grammar"]

_Action = Callable[..., Any]

def build_grammar(actions: Mapping[str, _Action]) -> CommandDispatcher: ...
def build_redirect_grammar(actions: Mapping[str, _Action]) -> CommandDispatcher: ...
