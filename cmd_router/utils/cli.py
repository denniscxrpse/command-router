__all__ = (
    "flags",
    "init_flags",
)

from dataclasses import dataclass
from typing import Final, final

import click

from cmd_router.utils.types import LogicalDataPath


@final
@dataclass
class EnvFlags:
    lazy: bool = False
    """
    - True: Ignores any fixture and read the given logical data at runtime. 
    - False: Reads grammars.toml as soon as possible. Ignoring any given logical data.
    """

    logical_engine: str = ""
    """
    The logical-engine tells the engine to initialize the commands later, following a specific format.
    We should only support TOML and JSON/JSONC. This will only work if the program is initialized with `--lazy`;
    else, read a file as early as posible.
    
    Unless given directly from the command line, this value will be changed automatically based on the file extension 
    and other factors.
    """

    logical_data_path: LogicalDataPath = ""
    """
    The local file, remote URL or direct string to the logical data.
    
    This is ignored if `--lazy` is set to False.
    """


flags: Final[EnvFlags] = EnvFlags()
"""Single module-level instance, access the internal configuration flags. Not to be confused with DotEnv."""


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
def init_flags(**kwargs) -> None:
    for key, value in kwargs.items():
        if hasattr(flags, key):
            setattr(flags, key, value)
