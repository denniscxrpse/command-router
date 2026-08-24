# command-router — Brigadier-ish roadmap (personal project)

Goal: build something conceptually similar to Mojang’s Brigadier (Minecraft’s command dispatcher):
a command tree, typed arguments, good parse errors, and suggestions/autocomplete.

Also: make it runnable as a small standalone process that another app can talk to (local socket or similar).

Non-goals (for now): PyPI polish, long-term API stability promises, docs, perfect CI.

Rule: only add complexity when a real command grammar demands it.

---

## Phase 0 — Keep the project runnable

**Goal:** a tight iteration loop.

- [x] One command to run tests.
- [x] One command to run a demo (REPL or “send one line, print result”).
- [x] Ruff/formatting stays “good enough” (don’t bikeshed).

**Exit condition:** you can change engine code and validate it in under a minute.

---

## Phase 1 — Fixtures: the Minecraft-ish spec (ground truth)

**Goal:** write down exactly what you want, before refining APIs.

Pick 4–6 real-ish grammars that force the mechanics you care about:

- `say <message...>` (greedy tail)
- `tell <target> <message...>` (typed arg + greedy tail)
- `gamemode (survival|creative|adventure|spectator) [<target>]` (choice + optional)
- `advancement (grant|revoke) <target> ('*' | only <advancement> [<criterion>])` (nesting + sentinel + optional)
- one numeric command: `tp <x> <y> <z>`
- one “debug” command: `debug (on|off)`

For each fixture, write:

- input string
- expected tokenization (including quotes)
- expected match: handler name + parsed args
- expected failure: error kind + where it failed + what would have worked next

**Exit condition:** you can directly turn the table into parametrized tests.

---

## Phase 2 — Tokenization

**Goal:** raw string → list of tokens, including quoted segments.

- [x] Wrap `shlex.split()` and convert failures into a friendly error (don’t leak a cryptic `ValueError`).
- [x] Tests: empty, whitespace-only, quoted strings, escaped quotes, unterminated quotes.

**Exit condition:** tokenizer is fully tested and independent of the dispatcher.

---

## Phase 3 — Command tree + dispatcher (the core)

**Goal:** register commands into a tree and parse input against it.

Brigadier-like concepts to implement (names are yours):

- [x] `CommandDispatcher` with a root node
- [x] node types:
    - [x] literal node (matches exact token)
    - [x] argument node (uses an `ArgumentType` to parse)
- [x] attach a “command”/handler to nodes that represent complete commands
- [x] parse output:
    - success: handler + `CommandContext` (parsed args, original input, maybe cursor)
    - failure: best error (position + expectations)

Don’t add a builder API yet; hand-build the tree until it’s correct.

**Exit condition:** all Phase 1 fixtures pass by constructing a tree directly.

---

## Phase 4 — Argument types (minimum set, but clean)

**Goal:** typed argument parsing like Brigadier’s `ArgumentType`.

- [x] `ArgumentType[T]` protocol (or base class):
    - `parse(reader) -> T | error` (you can use a simple token reader abstraction)
    - optional `suggest(reader) -> list[str]`
- [x] built-ins required by fixtures:
    - [x] `word` / `string` (single token)
    - [x] `int`
    - [x] `greedy` (consume remaining tokens)

Structural invariant:

- [x] forbid children after `greedy` at definition time (fail fast).

**Exit condition:** greedy commands work, and invalid grammars crash at registration/build time, not mid-parse.

---

## Phase 5 — Good errors (actionable failures)

**Goal:** failures that explain themselves.

- [x] Track token index / cursor as you parse.
- [x] Produce a consistent error object:
    - where it failed
    - “expected next” (literal candidates and/or argument types)
    - maybe: partial parsed args (for debugging)

**Exit condition:** failing fixtures produce predictable, testable errors. The
control API also emits a compact ``{"data": ..., "err": ...}`` response to
stderr for every execution result.

---

## Phase 6 — Suggestions / autocomplete

**Goal:** “Minecraft-y” feel: partial input yields helpful completions.

- [ ] `get_suggestions(input, cursor)` returning a list of suggestion strings (later you can add ranges/weights).
- [ ] literal suggestions (based on current node)
- [ ] argument suggestions via `ArgumentType.suggest` when available

**Exit condition:** e.g. `ga<TAB>` → `gamemode`, `gamemode <TAB>` → mode names.

---

## Phase 7 — Builder API (ergonomics, after correctness)

**Goal:** pleasant registration, Brigadier-inspired.

You want to be able to express things like:

- `literal("say").then(argument("message", greedy_string())).executes(handler)`
- choices and optionals without writing a novel

Hard rule: the builder can’t introduce new matching behavior; it’s just a nicer way to build the same tree.

**Exit condition:** fixtures are expressed via the builder and still pass.

---

## Phase 8 — Redirect / repetition (only with one real motivating grammar)

**Goal:** support graph-like trees (redirect/fork) if/when a real command needs it.

- [ ] choose one motivating grammar (e.g. an `execute`-style modifier chain)
- [ ] implement redirect/fork mechanics
- [ ] add a guard so malformed grammars can’t loop forever

**Exit condition:** that one repeating grammar works and termination is well-defined.

---

## Phase 9 — Run it as a service (local socket / stdio)

**Goal:** another application can drive this engine over an IPC-style transport.

- [ ] pick transport (s):
    - [ ] unix domain socket (best “internal socket” default on Linux/macOS)
    - [ ] optional: TCP localhost
    - [ ] optional: stdio mode (subprocess pipes)
- [ ] define a tiny protocol (start with JSON lines):
    - request: `{id, input, cursor?}`
    - response: `{id, ok, result|error, suggestions?}`
- [ ] keep logs on stderr; keep protocol clean on the transport

**Exit condition:** a tiny external client can connect, send a command, and get a structured response.

---

## Phase 10 — Integration demos

**Goal:** prove the “another app summons this” story end-to-end.

- [ ] a minimal client script that connects and sends requests
- [ ] server mode that loads a demo command tree and serves requests

**Exit condition:** two terminals (server + client) feel solid and boring.

---

## Packaging note

Don’t optimize for PyPI. If you ever want that, create a new TODO dedicated to “publishable library mode”.
