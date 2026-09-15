from typing import Any

from _typeshed import Incomplete

from command_router.sdk import FixturesSDK

__all__ = ["Fixtures"]

class Fixtures(FixturesSDK):
    cmd_prefix: str
    lazy_init_help: bool
    command_action: Incomplete
    builder_dispatcher: Incomplete
    builder_redirect_dispatcher: Incomplete
    suggestions_set_current_size: int
    def __init__(self, logic: Any = None) -> None: ...
    def foo(self, **arguments: Any) -> dict[str, Any]: ...
    def bar(self, **arguments: Any) -> dict[str, Any]: ...
