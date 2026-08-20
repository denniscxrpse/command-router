# justfile
# You may use `uv run just`, or use the `just` package provided by your distribution.
# Read the *justfile* documentation if you really do not know what to do:
# - https://just.systems/man/en/introduction.html
# - https://just.systems/man/en/packages.html
# Last edit: 20/Aug/2026

# Initialize the project. Use `PREFIX` to specify `.bat`, `.fish`, etcetera.
init PREFIX="":
    #!/usr/bin/env bash
    if [ -d ".venv" ]; then echo "Virtual environment already exists!"; exit 1; fi
    uv venv
    source .venv/bin/activate{{ PREFIX }}
    uv sync

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
lint:
    uv run ruff check .
    uv run pyrefly check .
