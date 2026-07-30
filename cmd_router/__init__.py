__all__ = ("CommandRouter",)

from icecream import ic

from cmd_router.lib.utils.const import *
from cmd_router.utils.cli import *
from cmd_router.utils.grammar_loader import *
from cmd_router.utils.logger import *
from cmd_router.utils.types import DictMapping, LogicalDataPath


class CommandRouter:
    _info: DictMapping
    _grammars: DictMapping

    def __init__(self) -> None:
        if flags.lazy:
            self._lazy_init()
            return
        self._init_grammar(paths.GRAMMARS)
        ic(self._info, self._grammars)

    def _lazy_init(self) -> None:
        raise NotImplementedError

    def _init_grammar(self, ldp: LogicalDataPath) -> DictMapping:
        d = load_grammars(ldp)
        if isinstance(d, dict):
            d = d.get("cmd-router", {})
            self._info = {key: value for key, value in d.items() if key != "grammar"}
            self._grammars = d["grammar"]
            return d
        log.critical(f"Expected a valid mapping/dictionary, got {type(d).__name__}")
        return {}
