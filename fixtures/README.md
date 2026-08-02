# Cmd-notation reference

Define the command first, followed by its grammar in cmd-notation format. Place
examples above the commands they demonstrate.

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
