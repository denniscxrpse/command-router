# Command Router Contributor Guidance

## Project direction

This is a personal, Brigadier-inspired command router. Keep the implementation small and fixture-driven. Correct
parsing, useful errors, and a readable outer API matter more than packaging polish or speculative abstractions.

Hand-built trees are the proven core. The fluent builder (Phase 7) is done as ergonomics only: builders delegate to
`CommandNode.add_child` / `set_command` and must parse exactly like hand-built trees. Do not introduce new matching
behavior through the builder, the SDK, or later roadmap phases.

The current surfaces are:

- `cmd_router.lib.commands` for parsing primitives and the tree.
- `cmd_router.sdk` for fixture authoring and tree building (`FixturesSDK`, `literal` / `argument` /
  `build_dispatcher`).
- `cmd_router.lib.control` for fixture-backed initialization and execution (`Control`, `ControlResult`).
- `cmd_router.suite` for the interactive Textual test-suite REPL.
- `cmd_router.suggestions` for ranked prefix-first / fuzzy-fallback suggestions and the lazy server.
- `cmd_router` (`CommandRouter`) as the thin runtime orchestrator over grammar loading, control, and servers.

Do not implement `todo.md` phases out of order. Implement functionality in the order the user describes, or in the
order that best fits the existing design.

## Repository organization

Top-level layout:

- `cmd_router/__init__.py`: thin `CommandRouter` / `_CmdRouter` orchestrator only.
- `cmd_router/lib/commands`: tokenizer, argument types, dispatcher nodes, parse contexts.
- `cmd_router/lib/control`: compiler, fixture loader, grammar helpers, and `api/` (`control`, `result`, `context`,
  `fixtures_sdk`).
- `cmd_router/lib/grammar`: file-backed TOML / JSON5 loading and parsing.
- `cmd_router/sdk`: user façade (`FixturesSDK`, default `Fixtures`) plus `backend/` peers (`builder`, `holder`,
  `settings`, `setup`, `loader`).
- `cmd_router/suggestions`: `algo.py` matching logic, `context.py` endpoint state, package root for
  `LazySuggestionsServer`.
- `cmd_router/suite`: Textual REPL (`REPL`, `Outcome`) and its CSS.
- `cmd_router/utils`: `flags` / `init_flags`, `log`, `stat` / `Status`, `uctx` / `paths`, lazy-server base.
- `fixtures/`: reference inputs. `__init__.py` holds behavior and settings, `grammars.py` holds the advanced
  Python-built tree (`builder_dispatcher`), `*.toml` / `*.json5` hold file-backed grammars.
- `tests/`, `stubs/`, `main.py`, `justfile`, `ruff.toml`, `pyproject.toml`.

Rules:

- Keep filenames lowercase and snake_case; use PascalCase for public classes and private, underscored implementation
  classes where that improves the public surface.
- Add a Python `__init__.py` only when a package needs a deliberate public façade. Do not add package initializers
  everywhere by habit.
- Prefer using the existing files and skeletons under `cmd_router/lib`, `cmd_router/sdk`, `cmd_router/suite`,
  `cmd_router/suggestions`, and `cmd_router/utils` before creating new implementation files there.
- Planning stubs may describe a future control/runtime layer; leave it alone while the package is being organized unless
  the user explicitly asks to implement that layer.
- Preserve unrelated working-tree changes. Inspect with `git status` / `git diff` before editing and keep changes
  narrowly scoped to the request.

## Type stubs

- Keep the current implementation-module `.pyi` stubs untouched.
- Do not create or update stub files for future implementation changes unless the user explicitly requests it.
- Keep stubs in their dedicated root and avoid mirroring the implementation tree when a flat layout is valid. If a type
  checker requires import-compatible package resolution, retain only the minimal `stubs/cmd_router/...`
  hierarchy needed for that resolution; do not add extra duplicate directories or initializers.
- Regenerate only when asked, with the project command (`just stub`, which runs `stubgen` plus `black --pyi` plus
  `ruff --fix`). Do not hand-format stubs outside that flow.

## Public API and imports

The command package exposes concise namespaces. Example from
`cmd_router.lib.commands`:

```python
from cmd_router.lib.commands import CmdError, CmdNode, CmdParse, CmdType
```

Use the namespace façades at outer call sites:

- `CmdError` for error codes and argument errors
- `CmdType` for argument types
- `CmdParse` for contexts, parse errors, results, and tokenization
- `CmdNode` for the dispatcher and command-tree nodes

Use the surrounding façades the same way:

- `from cmd_router.sdk import FixturesSDK, Fixtures, literal, argument, build_dispatcher` for fixture authoring and
  Python-built trees. `cmd_router.sdk.backend` mirrors `control.deeper` for advanced integration only.
- `from cmd_router.lib.control import ControlType as Control, ControlResult, ControlInitialization` for isolated
  command surfaces. Pass a `FixturesSDK` subclass or instance directly to `Control.initialize` when no fixture module
  file is needed.
- `from cmd_router.suite import REPL, Outcome` for the test-suite UI. `Outcome` is `Status | list[str] | None`:
  `Status` exits, `list[str]` reports unknown-command suggestions, `None` keeps listening.
- `from cmd_router.suggestions import LazySuggestionsServer, lazy_suggest_srv_ctx` for completion infrastructure.
- `from cmd_router.utils import flags, init_flags, log, stat, Status, uctx, paths` for CLI state, diagnostics, error
  values, shared context, and well-known paths.

Fixture contract, preferred first:

```python
from cmd_router.sdk import FixturesSDK


class Fixtures(FixturesSDK):
    def __init__(self, logic=None):
        super().__init__(logic=logic)
        self.cmd_prefix = "/"
        self.command_action = {"say": self.logic.say}
```

The legacy two-class `context_holder` plus `SetupFixtures` contract remains supported for compatibility. New fixtures
use the single-class form. File-backed grammars stay in TOML / JSON5; `fixtures/grammars.py` plus the fixture's
`builder_dispatcher` is the advanced Python form for trees that need handlers at build time, computed branches, helper
functions, or argument types the data formats avoid.

Keep implementation modules separate underneath the façade. Add aliases in the package initializer when a public name
would otherwise expose an internal or overly verbose implementation name.

Use `__all__` deliberately in modules. The project favors clean, explicit import surfaces and may use
`from cmd_router.module import *` when the imported module defines a trustworthy `__all__`. Do not replace that pattern
with conventional imports merely for style, and do not use wildcards from third-party or uncontrolled modules. Use
`TYPE_CHECKING` imports to break cycles (for example `ParseError` inside `cmd_router.suggestions`).

Preserve the existing Clear BSD license header in new Python files:

```python
#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.
```

## Error handling and safety

- Expected user/input failures should return an error code or a structured result, rather than escaping as exceptions.
  Reuse the centralized error values in `cmd_router.utils.status` and expose them through `CmdError` / `stat`.
- Control failures use structured results: `ControlResult` for execution and `ControlInitialization` (including
  `ControlFixtureError`) for fixture, grammar, and action validation. `FixtureInitializationError` covers fixture
  lifecycle-flag disagreements.
- Convert exceptions from dependencies at the narrow boundary where they can occur. Do not use broad `try` blocks as
  ordinary control flow.
- Keep invalid input, unsupported types, duplicate nodes, and malformed tree definitions from producing confusing
  downstream failures. Validate close to the boundary and make the resulting error actionable. Builder `then` /
  `executes` must fail fast exactly like `add_child` / `set_command`.
- Log useful error information through the project logger when the surrounding workflow calls for it, while keeping
  returned errors testable.
- Preserve structured parse information: handler, original input, parsed arguments, token position, expected next items,
  and the furthest failure. `ParseError` carries the failing token, `expected`, and ranked `suggestions`
  (prefix-first, rapidfuzz fallback, `<...>` hints preserved).
- Keep response contracts fixed with null defaults, and keep disabled servers visible (for example suggestions
  `GET -> 200 []`) instead of dropping the connection.

## Logging

- Use `log.debug`, `log.info`, `log.warning`, `log.error`, and `log.critical` for engine diagnostics; these methods
  write to stdout and should describe the stage, decision, and outcome when that context is useful.
- Use `log.raw` only for controlled progress/status fragments such as `"grammar: "` followed by `"OK"` or
  `"FAILURE"`. Do not pass arbitrary user input to `raw`, because it is intentionally unescaped.
- Treat `warning` as an expected but noteworthy condition, `error` as a recoverable formatting/configuration or
  operation failure, and `critical` as a failure after which execution cannot safely continue. Do not label a failure
  `critical` when the caller receives a structured recovery result.
- Never use `log.stderr` or `log.stderr_async` for diagnostics. Those writers are reserved for listener/protocol data
  explicitly consumed from stderr.

## Code style

- Prefer readable implementations to clever compression. Public behavior should be easy to discover and use from the
  namespace façade.
- Keep docstrings informative, direct, and short enough to scan. Explain the contract and important edge cases; avoid
  documenting obvious syntax.
- `__init__` methods are for necessary object initialization, not a mandatory pattern for every module or class.
- Black may be run for formatting, but do not spend effort on cosmetic churn. Ruff and Ty are the practical quality
  checks. Line length is 120; config lives in `ruff.toml` (`E`, `F`, `I`, `UP`, `B`; ignoring only `F403`, `F405`,
  `E402`, `E702`) and `pyproject.toml` (`requires-python = ">=3.14"`). Prefer the `justfile` wrappers: `just lint`,
  `just autofix`, `just format`.
- Do not add `from __future__ import annotations`. The project targets Python 3.14+, so annotations are evaluated
  normally; import referenced types before they are used and use `typing.Self` for recursive type references.
- Never use quoted type annotations. Do not write stringized unions or forward references in quotes. Ruff rule `UP037`
  is always enabled and must never be ignored, silenced with `noqa`, or worked around.

  ```python
  # Wrong: quoted annotation needing UP037.
  def then(self, *children: "NodeBuilder | CommandNode") -> Self:  # noqa: UP037
      ...

  # Right: direct annotation with real imports.
  def then(self, *children: NodeBuilder | CommandNode) -> Self:
      ...
  ```

  The same rule applies to `build_dispatcher` roots, `X | Y` unions, `X | None` optionals, and return positions. If a
  name is only available under `TYPE_CHECKING`, restructure the import instead of quoting the annotation.
- Follow the existing private-class plus public-alias pattern, `Final` values, centralized context objects, and
  module-level singleton conventions where they fit the design. Examples: `Fixtures: Final[FixturesSDK] =
  FixturesSDK()`, `CmdError: Final[type[Status]]`, `uctx` / `paths` / `flags` singletons, `ContextHolder` / `Setup` /
  `Err` legacy aliases on `FixturesSDK`.
- Use `typing.Final` for constants, default instances, and alias targets; use `@final` / `Final` where the codebase
  already seals namespaces and fixture classes.
- Do not try to implement how the `todo.md` file directly represents the project roadmap. Instead, implement the given
  functionality in the order it is either described by the user, or it is instead expected to be the best.

## Tests and verification

Tests should exercise the public namespace and describe both successful and failing behavior. Prefer parametrized,
fixture-driven cases for command grammars, including tokenization, parsed arguments, handler identity, error kinds,
positions, and expectations.

Current coverage pattern:

- `test_tokenizer.py`, `test_dispatcher.py`, `test_errors.py` for engine behavior.
- `test_control.py`, `test_command_router.py` for control and runtime orchestration.
- `test_api.py`, `test_builder.py` for SDK façade and builder-versus-hand-built parity.
- `test_suggestions.py`, `test_suggestions_budget.py`, `test_suggestions_server.py`, `test_edge_cases.py` for ranking,
  budgets, server lifecycle, and boundaries.
- `test_cli.py` for `init_flags` / `EnvFlags` behavior. Configure `flags.ignore` through the public CLI option with
  `CliRunner`, not by assigning the set directly; it normalizes to `frozenset`.

Useful checks:

```text
uv run pytest -q
uv run ruff check .
uv run ty check .
uv run python main.py --lazy # You may use `curl` via HTTP to test this.
```

The `justfile` equivalents are preferred while iterating: `just pytest`, `just lint [path]`, `just test [extra]`,
`just run [what]`, `just lazy`. `just lint` intentionally skips `stubs/`.

Run focused tests while iterating, then run the complete suite before handing off a change. Do not modify or delete user
files just to make checks pass.

## Commits

Follow this repository's commit format exactly. Do not invent another format, omit parts, or reword the trailer. Every
commit in `git log` uses this shape, and reviews expect it.

Shape:

```text
<type>: <short subject>

- <area>: <what changed, using backticked paths and symbols>.
  <Optional wrapped continuation lines, indented two spaces.>

- <next area>: <next change group.>

Signed-off-by: name <email>
```

Rules in detail:

- The first line is, all lowercase types`<type>: <subject>`, colon, single space, then a short imperative subject
  starting lowercase with no trailing period. Observed types are `feat`, `refactor`, `chore`, `bump`, and `docs`. Use
  the narrowest fitting type: `feat` for user-visible behavior, `refactor` for behavior-preserving restructuring and
  renames, `chore` for maintenance and internal cleanup, `bump` for stub/import/typo-only updates, `docs` for
  documentation-only updates.
- Good subjects: `feat: add lazy suggestions server with standalone lifecycle`, `refactor: moved REPL to
  cmd_router.suite`, `chore: rename err module to status and migrate status call sites`. Bad subjects: `Feat: ...`,
  `feat:Add ...`, `feat: Added ...`, `feat: add ... .`
- Leave one blank line after the subject, then a bullet list. Each bullet starts with `- ` and names the affected area
  first (`api:`, `control:`, `fixtures:`, `suggestions:`, `stubs/tests:`, `cleanup:`, and similar). Keep one bullet
  group per area so a reader can scan what moved.
- Wrap body lines to stay readable (the history wraps near 72-80 columns), indent continuation lines two spaces, and
  leave a blank line between bullet groups. Use backticks for paths, modules, symbols, flags, and status codes, for
  example `` `cmd_router/suggestions/` ``, `` `build_dispatcher` ``, `` `flags.no_suggestions_server` ``.
- Always end with exactly `Signed-off-by: name <email>` as its own trailing block, preceded by a
  blank line. Never omit it, change the name or email, or substitute another trailer.
- Tiny maintenance commits may be subject plus trailer only, with no body. Example:

  ```text
  bump: update stubs and typos

  Signed-off-by: name <email>
  ```

- Larger commits must explain each area. Example skeleton derived from the history:

  ```text
  feat: add Textual test-suite REPL and simplify fixture SDK

  - Add an interactive Textual test-suite interface with ...

  - Replace the public cmd_router.api namespace with cmd_router.sdk and ...

  - Update control initialization, fixture loading, backend imports, ...

  Signed-off-by: name <email>
  ```

- Keep each commit narrowly scoped and preserve unrelated working-tree changes. Inspect `git status`, `git diff`, and
  recent `git log --oneline -10` before committing. Only commit, amend, push, or open pull requests when explicitly
  requested.
- It is essential to not commit unless explicitly requested.
