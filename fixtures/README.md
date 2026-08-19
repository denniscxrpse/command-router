# Fixture reference

The files in this directory are the command router's fixture inputs. Grammar files (`json`/`.json5` and `.toml`)
describe command syntax; `__init__.py` supplies the Python state and actions used by the control layer.

## Grammar notation

Define the command first, followed by its grammar in cmd-notation format. The engine supports:

- `word` — required literal.
- `(a|b|c)` — choice between alternatives.
- `[item]` — optional token or group, such as `[args...]`.
- `<name:type>` — required, typed argument.
- `<name>` — required `word` argument.
- `<name...>` — greedy terminal argument that captures the remaining input.
- `<name:type=default>` — argument with an alternate omitted value.
- `'char'` or `"literal"` — literal containing punctuation or whitespace.

See the individual grammar files for complete examples of choices, nesting, optional arguments, and greedy values.

## Python fixture contract

The control API imports `fixtures/__init__.py` and looks for two definitions:

1. `context_holder`, a class derived from
   `cmd_router.api.FixturesContextHolder`.
2. `SetupFixtures`, a class derived from
   `cmd_router.api.FixturesSetup`.

Initialization then proceeds as follows:

1. `context_holder()` creates one state holder. Its `__init__` should call `super().__init__()` before setting an
   application-specific state.
2. The control layer assigns that holder to `SetupFixtures.logic`.
3. `SetupFixtures()` calls `super().__init__()` and assigns its settings, such as `self.cmd_prefix` and
   `self.command_action`.
4. Grammar compilation reads the setup object, and the holder's bound methods execute commands.

A minimal fixture looks like this:

```python
from typing import Any

from cmd_router.api import FixturesContextHolder, FixturesSetup


class Context(FixturesContextHolder):
    def say(self, **arguments: Any) -> dict[str, Any]:
        return self._record("say", arguments)


context_holder = Context


class SetupFixtures(FixturesSetup):
    def __init__(self) -> None:
        super().__init__()
        self.cmd_prefix = "/"
        self.command_action = {"say": self.logic.say}
```

`FixturesSetup` owns the command prefix, built-in-help policy, action mapping, and argument overrides for one control
surface.

Importing the fixture should define classes and aliases only. Put setup-time state in the holder or setup constructors
and keep command work in action methods. The initialized objects remain available through
`control.deeper_level.fixture_logic` and `control.deeper_level.fixture_setup`.
