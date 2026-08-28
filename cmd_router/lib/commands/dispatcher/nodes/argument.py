#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from collections.abc import Callable
from typing import Any

from cmd_router.lib.commands.typing import *

from .command import *
from .kinds import *

_Handler = Callable[..., Any]


class ArgumentNode(CommandNode):
    """A node that converts the next token using an argument type."""

    kind = NodeKind.ARGUMENT

    def __init__(
        self,
        name: str,
        argument_type: ArgumentType[Any] | None = None,
        *,
        command: _Handler | None = None,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("argument name must be a non-empty string")
        selected_type = argument_type if argument_type is not None else arg_type

        if isinstance(selected_type, type):
            selected_type = selected_type()
        elif not callable(getattr(selected_type, "parse", None)) and callable(selected_type):
            selected_type = selected_type()

        if not callable(getattr(selected_type, "parse", None)):
            raise TypeError("argument_type must provide a callable parse method")
        self.argument_type = selected_type
        super().__init__(name, command=command)

    @property
    def greedy(self) -> bool:
        return bool(getattr(self.argument_type, "greedy", False))

    @property
    def label(self) -> str:
        type_name = getattr(self.argument_type, "name", "argument")
        if self.greedy:
            return f"<{self.name}...>"
        if type_name == "word":
            return f"<{self.name}>"
        return f"<{self.name}:{type_name}>"
