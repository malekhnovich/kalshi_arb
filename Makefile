.PHONY: push tmux help test-quick test-full test-suite-quick test-suite-full optimize-quick optimize-full tsa

# Git commands
push:
	git add .
	git commit -m "Auto-commit from Makefile"
	git push

# Session management
tmux:
	@tmux has-session -t arbitrage 2>/dev/null || \
	tmux new-session -d -s arbitrage \; split-window -h \; split-window -v \; select-pane -t 0 \; split-window -v \; select-layout tiled
	@tmux attach-session -t arbitrage

# Quick backtest (2 days)
test-quick:
	python run_backtest_real.py --symbol BTCUSDT --days 2

# Full backtest (7 days)
test-full:
	uv run python run_backtest_real.py --symbol BTCUSDT --days 7

# Quick strategy permutation test (first 5 strategies, 2 days)
test-suite-quick:
	uv run python test_all_strategies.py --quick --limit-strategies 5

# Full strategy permutation test (all 10 strategies, 7 days)
# Warning: This takes 15-20+ hours
test-suite-full:
	uv run python test_all_strategies.py --days 7

# Quick parameter optimization (fewer combinations, 2 days)
optimize-quick:
	uv run python optimize_parameters.py --quick

# Full parameter optimization (all combinations, 7 days)
optimize-full:
	uv run python optimize_parameters.py --days 7

# Legacy alias
tsa:
	$(MAKE) test-suite-quick

# Help/info
help:
	@echo "=== ARBITRAGE BACKTEST COMMANDS ==="
	@echo ""
	@echo "Quick Tests (2 days):"
	@echo "  make test-quick           - Single backtest with all strategies"
	@echo "  make test-suite-quick     - Test 5 strategies (32 permutations)"
	@echo "  make optimize-quick       - Test parameter combinations (16 tests)"
	@echo ""
	@echo "Full Tests (7 days):"
	@echo "  make test-full            - Single backtest with all strategies"
	@echo "  make test-suite-full      - Test all 10 strategies (1024 permutations)"
	@echo "  make optimize-full        - Test parameter combinations (256 tests)"
	@echo ""
	@echo "Other:"
	@echo "  make push                 - Git add, commit, and push"
	@echo "  make tmux                 - Start tmux session"
	@echo ""