# Cmd-notation reference (summary)

Define the command first, followed by its grammar in cmd-notation format. Place examples above the commands they
demonstrate.

The engine expects grammar definitions to use the following notation:

- `word` — required literal.
- `(a|b|c)` — choice between alternatives.
- `[item]` — optional token or group, such as `[args...]`.
- `<name:type>` — required, typed argument.
- `<name>` — required, untyped argument; its value is echoed as-is.
- `<name...>` — greedy terminal argument; it captures everything that follows.
- `<name:type=default>` — argument with a default value.
- `'char'` — literal branch containing exactly one character.
- `'*'` — built-in literal branch that selects all choices as a sentinel for a deeper branch.

This is a summary. You may read the documentation for individual commands to learn more about their grammar and usage.

## Fixture logic

When control is enabled, the router imports this module and calls only two hooks:

1. `FixtureGrammarLogic()` to create the fixture's state.
2. `setup()` to assign the command prefix and action mapping.

Keep state and setup-time work in `FixtureGrammarLogic.__init__`. Importing this
file should only define the hooks and classes; command scripts should run from
their action methods. The initialized logic object is available through the
control layer's `deeper_level.fixture_logic` attribute.
