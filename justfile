# justfile
# You may use `uv run just`, or use the `just` package provided by your distribution.

# Test everything
test:
    uv run pytest -q

# Run with sane the defaults
run:
    uv run python main.py

# Run with specific flag
run-w FLAG:
    uv run python main.py {{ FLAG }}

# Run with --lazy/-L
run-l:
    uv run python main.py -L

# Check all lints
lint:
    uv run ruff check .
    uv run pyrefly check .

# Lint with an specific tool
lints TOOL:
    uv run {{ TOOL }} check .
