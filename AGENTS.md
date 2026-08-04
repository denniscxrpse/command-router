# Command Router Contributor Guidance

## Project direction

This is a personal, Brigadier-inspired command router. Keep the implementation small and fixture-driven. Correct
parsing, useful errors, and a readable outer API matter more than packaging polish or speculative abstractions.

Do not build the fluent builder, service layer, or other later roadmap phases early. Hand-built trees are intentional
until the matching behavior is proven.

## Repository organization

- Keep filenames lowercase and snake_case; use PascalCase for public classes and private, underscored implementation
  classes where that improves the public surface.
- Add a Python `__init__.py` only when a package needs a deliberate public façade. Do not add package initializers
  everywhere by habit.
- Prefer using the existing files and skeletons under `cmd_router/lib` before creating new implementation files there.
- Planning stubs may describe a future control/runtime layer; leave it alone while the package is being organized unless
  the user explicitly asks to implement that layer.
- Preserve unrelated working-tree changes. Inspect before editing and keep changes narrowly scoped to the request.

## Public API and imports

The command package exposes concise namespaces. Example from
`cmd_router.lib.command`:

```python
from cmd_router.lib.command import CmdError, CmdNode, CmdParse, CmdType
```

Use the namespace façade at outer call sites:

- `CmdError` for error codes and argument errors
- `CmdType` for argument types
- `CmdParse` for contexts, parse errors, results, and tokenization
- `CmdNode` for the dispatcher and command-tree nodes

Keep implementation modules separate underneath the façade. Add aliases in the package initializer when a public name
would otherwise expose an internal or overly verbose implementation name.

Use `__all__` deliberately in modules. The project favors clean, explicit import surfaces and may use
`from cmd_router.module import *` when the imported module defines a trustworthy `__all__`. Do not replace that pattern
with conventional imports merely for style, and do not use wildcards from third-party or uncontrolled modules.

Preserve the existing Clear BSD license header in new Python files.

## Error handling and safety

- Expected user/input failures should return an error code or a structured result, rather than escaping as exceptions.
  Reuse the centralized error values in `cmd_router.utils.context` and expose them through `CmdError`.
- Convert exceptions from dependencies at the narrow boundary where they can occur. Do not use broad `try` blocks as
  ordinary control flow.
- Keep invalid input, unsupported types, duplicate nodes, and malformed tree definitions from producing confusing
  downstream failures. Validate close to the boundary and make the resulting error actionable.
- Log useful error information through the project logger when the surrounding workflow calls for it, while keeping
  returned errors testable.
- Preserve structured parse information: handler, original input, parsed arguments, token position, expected next items,
  and the furthest failure.

## Code style

- Prefer readable implementations to clever compression. Public behavior should be easy to discover and use from the
  namespace façade.
- Keep docstrings informative, direct, and short enough to scan. Explain the contract and important edge cases; avoid
  documenting obvious syntax.
- `__init__` methods are for necessary object initialization, not a mandatory pattern for every module or class.
- Black may be run for formatting, but do not spend effort on cosmetic churn. Ruff and Pyrefly are the practical quality
  checks.
- Follow the existing private-class plus public-alias pattern, `Final` values, centralized context objects, and
  module-level singleton conventions where they fit the design.

## Tests and verification

Tests should exercise the public namespace and describe both successful and failing behavior. Prefer parametrized,
fixture-driven cases for command grammars, including tokenization, parsed arguments, handler identity, error kinds,
positions, and expectations.

Useful checks:

```text
uv run pytest -q
uv run ruff check .
uv run pyrefly check .
uv run python main.py --lazy # You may use `curl` via HTTP to test this. 
```

Run focused tests while iterating, then run the complete suite before handing off a change. Do not modify or delete user
files just to make checks pass.
