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

The control API imports `fixtures/__init__.py` and looks for one `Fixtures` class derived from
`cmd_router.sdk.FixturesSDK`. The class owns the state, actions, and command settings together. The control layer
constructs it once, then uses the instance as both the holder and setup while compiling grammars.

A minimal fixture looks like this:

```python
from typing import Any

from cmd_router.sdk import FixturesSDK


class Fixtures(FixturesSDK):
    def __init__(self) -> None:
        super().__init__()
        self.cmd_prefix = "/"
        self.command_action = {"say": self.logic.say}

    def say(self, **arguments: Any) -> dict[str, Any]:
        return self._record("say", arguments)
```

The older two-class `context_holder` and `SetupFixtures` contract remains supported for existing fixtures.

`FixturesSetup` owns the command prefix, built-in-help policy, action mapping, and argument overrides for one control
surface.

Importing the fixture should define classes only. Put setup-time state in the fixture constructor and keep command
work in action methods. The initialized objects remain available through
`control.deeper_level.fixture_logic` and `control.deeper_level.fixture_setup`.
