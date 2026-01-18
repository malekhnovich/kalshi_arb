# Claude Development Guide

Guidelines for working with this project in Claude Code.

## Python Command Execution

**IMPORTANT: All Python commands must be run through `uv` to ensure proper dependency resolution.**

### ✓ Correct
```bash
# Use uv run for all Python commands
uv run python script.py
uv run python -c "import module; ..."
uv run python -m pytest tests/
```

### ✗ Incorrect
```bash
# Do NOT use plain python
python script.py        # Wrong - bypasses dependency management
python3 script.py       # Wrong - may use system Python
```

## Why uv?

This project uses **`uv`** for dependency management instead of pip/venv:
- Faster dependency resolution
- Deterministic builds (reproducible across systems)
- Better isolation from system Python
- Defined in `pyproject.toml`

## Common Commands

### Testing & Development
```bash
uv run python run_backtest_real.py --symbol BTCUSDT --days 2
uv run python test_all_strategies.py --quick
uv run python analyze_strategy_results.py
```

### Using Make
```bash
# Make targets automatically use uv (already configured)
make test-quick
make test-suite-quick
make stats
```

### Bash Operations
```bash
# For non-Python bash commands, use normal bash
grep -r "pattern" src/
git status
ls -la logs/
```

## Project Structure

- `pyproject.toml` - Project metadata and dependencies
- `strategies.py` - Strategy configuration
- `run_backtest_real.py` - Main backtest entry point
- `test_all_strategies.py` - Strategy permutation testing
- `analyze_strategy_results.py` - Statistical analysis

## Useful Makefile Commands

```bash
make help                 # Show all available commands
make test-quick          # Run 2-day backtest
make test-suite-quick    # Test 5 strategies (32 perms)
make stats               # Analyze latest backtest
make analyze-permutations # Analyze all strategy combinations
```

## Debugging

If a Python command fails:
1. Check that `uv run` is being used (not plain `python`)
2. Verify environment variables are set correctly
3. Check `pyproject.toml` for required dependencies
4. Use `make help` to see verified working commands

## Note for Claude

When executing Python commands:
- Always prefix with `uv run`
- When using Bash tool, remember that plain `python` won't work
- Use `uv run python -c "..."` for inline Python
- Prefer Makefile targets when available (they handle uv automatically)
