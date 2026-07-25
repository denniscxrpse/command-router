# command-router — Build Roadmap

A phase-by-phase scope, in build order. Each phase has a goal, concrete
recommendations, and an exit condition — don't move to the next phase until
the exit condition is true. The two mistakes most likely to derail this
project are: building the fluent builder before the matcher is correct, and
designing ellipsis before you have a single concrete repeating grammar to
test it against. Both are called out below where they'd normally happen.

---

## Phase 0 — Environment & project skeleton

**Goal:** a project that runs, lints, and tests, containing nothing yet.

- [x] Python **3.14**. Newer than 3.12, and specifically the self-referential
  `CommandNode` type hints (`children: dict[str, "CommandNode"]`) benefit
  from PEP 649's deferred annotation evaluation, on by default in 3.14 — no
  `from __future__ import annotations`, no quoted forward refs.
- [x] `uv init --lib command-router` — use `--lib`, not the bare app template.
  Even though this starts as a personal project, a `src/command_router/`
  layout with a real package name avoids import-shadowing bugs later if you
  ever `pip install -e .` it into something else (e.g. testing against a
  throwaway Godot client).
- [x] `uv add --dev pytest ruff` at minimum. Add `ty` or `pyrefly` per the note
  above — either is fine, just know which tradeoff you picked.
- [x] `ruff.toml` (or `[tool.ruff]` in `pyproject.toml`): start with
  `select = ["E", "F", "I", "UP", "B"]` (pyflakes, isort, pyupgrade,
  bugbear). Don't reach for the stricter rulesets (docstrings, complexity)
  yet — the code's shape will change too much before Phase 6 for style
  rules to be worth enforcing.
- [x] `pyproject.toml`: `requires-python = ">=3.14"`.

**Exit condition:** `uv run pytest` runs (even with zero tests), `uv run ruff check .` is clean.

---

## Phase 1 — Fixture-first spec (no engine code yet)

**Goal:** a written-down, unambiguous ground truth to build against, before
any tree/matcher code exists.

- [ ] Pick 4–5 concrete grammars and write them, by hand, as a table: input →
  expected tokens → expected match result. Suggested set, since each
  exercises a different mechanic:
  - [ ] `gamemode (survival|creative|adventure|spectator) [<target>]` — choice + optional
  - [ ] `tell <target> <message>` — required arg + terminal greedy arg
  - [ ] `advancement (grant|revoke) <targets> only <advancement> [<criterion>]` — nesting + optional
  - [ ] `say <message>` — single greedy arg, no branching at all
- [ ] Put this in `tests/fixtures/grammars.md` or similar. It's documentation
  *and* the source you'll transcribe into `pytest.mark.parametrize` in
  Phase 3.

**Exit condition:** you can describe all 4–5 grammars without opening an editor to "figure out" how they should behave — if you can't, the ambiguity belongs here, not in code.

---

## Phase 2 — Tokenizer

**Goal:** raw string → list of tokens, correctly, including quoted strings.

- [ ] Wrap `shlex.split()`. Don't reimplement it.
- [ ] Test explicitly: empty string, whitespace-only string, unterminated
  quote (should raise a clear error, not a cryptic `ValueError` from deep
  inside `shlex`), and a message with an embedded quote character.

**Exit condition:** tokenizer has its own test file, fully green, decoupled from anything tree-related.

---

## Phase 3 — Core tree engine

**Goal:** the actual matcher. This is the phase that matters most —
everything after this is either testing it or building on top of it.

- [ ] `CommandNode`: `literal_children: dict[str, CommandNode]`,
  `argument_child: tuple[str, ArgumentType, CommandNode] | None`,
  `executor: Callable | None`.
- [ ] `ParseResult` dataclass (`ok`, `value`, `error`) instead of exceptions for
  per-candidate parse attempts — build this now, not retrofitted later,
  since the matcher's control flow depends on it from the first line.
- [ ] Matching order: literal children first (exact match), then the argument
  child (attempt `.parse()`, use the `ParseResult`, backtrack on failure).
- [ ] Write this directly against the Phase 1 fixtures as parametrized pytest
  cases. Do **not** build the fluent builder (Phase 6) yet, even though
  hand-constructing trees with nested dicts is tedious — that tedium is
  useful pressure, and building ergonomics before correctness means
  redesigning the builder every time the engine's shape changes underneath
  it.

**Exit condition:** all Phase 1 fixtures pass, constructed via raw `CommandNode` objects, no builder syntax sugar anywhere yet.

---

## Phase 4 — ArgumentType interface + minimal built-ins

**Goal:** typed argument parsing, plus the one structural invariant that
prevents a whole class of bugs.

- [ ] `ArgumentType` protocol: `parse(token: str) -> ParseResult`.
- [ ] Implement: a plain string type, an integer type, and the **greedy
  string** type.
- [ ] The greedy type is the one to build carefully: enforce, at tree
  *construction* time (in `CommandNode.then()`), that a node whose argument
  type is greedy cannot have children. Raise `GrammarDefinitionError`
  immediately if someone tries — this is what makes the `/tell`-style
  ambiguity from earlier structurally impossible instead of merely
  discouraged.

**Exit condition:** a test that tries to add a child after a greedy node raises at build time, not at parse time.

---

## Phase 5 — Optional & choice, as tests, not new code

**Goal:** confirm the design decisions from Phase 3 actually hold.

- [ ] Optional: a node with `executor` set *and* a further child — both are
  reachable. Test `/gamemode survival` and `/gamemode survival Steve` both
  succeed.
- [ ] Choice: sibling literal children. Test `/advancement grant …` and
  `/advancement revoke …` both resolve correctly, and `/advancement steal …`
  fails cleanly.
- [ ] If you find yourself writing new matcher logic in this phase rather than
  just tests, that's a signal Phase 3's node model needs revisiting before
  you go further — don't patch around it here.

**Exit condition:** all fixtures pass with zero changes to `CommandNode` or the matcher itself.

---

## Phase 6 — Fluent builder API

**Goal:** make constructing trees pleasant, now that the tree shape is stable.

- [ ] `literal("advancement").then(literal("grant").then(argument("targets", EntitySelector())...)).executes(handler)`
- [ ] This is a construction-time convenience layer over Phase 3's `CommandNode`
  — it should not introduce any new matching behavior. If it does, that
  logic belongs in Phase 3, not here.

**Exit condition:** every Phase 1 fixture can be expressed as a builder chain, and produces the identical tree to the hand-built Phase 3 version.

---

## Phase 7 — Error reporting

**Goal:** failures a human can act on.

- [ ] Track token position through the matcher; report "unknown argument at
  position N", not a bare exception with no context.
- [ ] This is where the `ParseResult`-over-exceptions choice from Phase 3 pays
  off directly — errors are data you format, not tracebacks you catch.

**Exit condition:** a deliberately malformed command produces a one-line, position-aware error message, for every fixture grammar.

---

## Phase 8 — Transport & subprocess integration

**Goal:** the router actually talks to something outside itself.

- [ ] `--transport {stdio,tcp}`, default `stdio`.
- [ ] stdout carries protocol responses **only** — configure `logging` to
  target stderr, default level `warning` (i.e. quiet unless something's
  actually wrong).
- [ ] `--log-level` as its own independent flag, orthogonal to `--transport`.
- [ ] Build a minimal throwaway client (even a 15-line C# console app, doesn't
  need to touch Godot yet) to validate a real round trip over stdio before
  wiring it into the actual game project.

**Exit condition:** a command sent from an external process gets a correct response, over the real transport, not just in-process pytest calls.

---

## Phase 9 — Ellipsis / repetition (only once you have a real case)

**Goal:** repeating grammars — deliberately last.

- [ ] Don't start this until you have one concrete repeating grammar you
  actually want, e.g. a toy `execute`-style modifier chain. Designing the
  mechanism in the abstract, with nothing to test it against, is exactly
  the trap you were already in a few turns ago.
- [ ] Likely shape: a `redirect` pointer on a node, aiming back at an ancestor,
  turning the tree into a graph with a cycle. Add a recursion or
  visited-node guard so a malformed grammar can't hang the matcher.

**Exit condition:** your one concrete repeating grammar passes, and you can explain in one sentence why the cycle doesn't infinite-loop.

---

## Phase 10 — Packaging & polish

**Goal:** a project someone else (including future you) could pick up.

- [ ] Fill in `pyproject.toml` metadata properly; `uv build` to confirm it
  packages cleanly.
- [ ] README with the grammar notation you settled on, since by now it may
  have drifted from the Minecraft wiki's version in small ways.
- [ ] *Now* turn on Ruff's stricter rulesets (docstrings, complexity) — the
  code's shape is stable enough for style enforcement to be worth the
  churn.

**Exit condition:** a fresh `uv sync && uv run pytest` from a clean clone passes with no manual setup steps.
