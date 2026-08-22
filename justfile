# justfile
# You may use `uv run just`, or use the `just` package provided by your distribution.
# Read the *justfile* documentation if you really do not know what to do:
# - https://just.systems/man/en/introduction.html
# - https://just.systems/man/en/packages.html
# Last edit: 21/Aug/2026

# Initialize the project. This will only work if you have `just` in your ENV already.
init:
    #!/usr/bin/env bash
    if [ -d ".venv" ]; then echo "Virtual environment already exists!"; exit 1; fi
    uv sync
    @echo "Run: `source .venv/bin/activate` if needed."

# Run with sane defaults. Use `FLASG` to specify a flag, use `--help` for details.
run FLAGS="":
    uv run python main.py {{ FLAGS }}

# Run with `--lazy` flag.
lazy:
    just run --lazy

# Run with `--control` flag.
control:
    just run --control

# Pytest everything
test:
    uv run pytest -q

# Check all lints
lint PATH="./cmd_router/":
    # Note: Avoid checking stub files. It will raise a lot (and I mean A LOT) of errors.
    uv run ruff check {{ PATH }}
    uv run pyrefly check {{ PATH }}

# Automatically generate stub files.
stub:
    # ==> Running stubgen...
    uv run stubgen ./cmd_router/ -o ./stubs/
    # ==> Running black...
    uv run black --pyi ./stubs/** --quiet
    # done
