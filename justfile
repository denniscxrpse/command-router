# justfile
# You may use `uv run just`, or use the `just` package provided by your distribution.
# Read the *justfile* documentation if you really do not know what to do:
# - https://just.systems/man/en/introduction.html
# - https://just.systems/man/en/packages.html
# Last edit: 22/Aug/2026

# Initialize the project. This will only work if you have `just` in your ENV already.
init:
    #!/usr/bin/env bash
    if [ -d ".venv" ]; then echo "Virtual environment already exists!"; exit 1; fi
    uv sync
    @echo "Run: `source .venv/bin/activate` if needed."

# Run with sane defaults. Use `what` to specify a flag, use `--help` for details.
run what="":
    uv run python main.py {{ what }}

# Run with `--lazy` flag.
lazy:
    just run --lazy

# Run with `--control` flag.
control:
    just run --control

# Pytest everything
test:
    uv run pytest -q

# Check all lints. Use `path` to lint someting else.
lint path="./cmd_router/ ./fixtures/":
    ###> Avoid checking stub files, linters will go crazy on them.
    uv run ruff check {{ path }}
    uv run pyrefly check {{ path }}

# Auto fix all (and only) ruff lints.
autofix path="./cmd_router/ ./fixtures/":
    uv run ruff check {{ path }} --fix

# Format the code. Use `what` to inject extra flags into the `black` formatter.
format what="./cmd_router/**":
    uv run ruff check --select I --fix {{ what }}
    uv run black {{ what }}

# Automatically generate stub files.
stub:
    ###> Running stubgen...
    uv run stubgen ./cmd_router/ -o ./stubs/ --include-private
    ###> Running black...
    uv run black --pyi "./stubs/**"
    ###> done
