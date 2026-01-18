.PHONY: push tmux help test-quick test-full test-suite-quick test-suite-full optimize-quick optimize-full tsa dryrun dryrun-debug

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

# Quick backtest (2 days) - with baseline strategy config
test-quick:
	STRATEGY_VOLATILITY_FILTER=false \
	STRATEGY_PULLBACK_ENTRY=false \
	STRATEGY_MOMENTUM_ACCELERATION=false \
	STRATEGY_TIME_FILTER=false \
	STRATEGY_MULTIFRAME_CONFIRMATION=false \
	uv run python run_backtest_real.py --symbol BTCUSDT --days 2

# Baseline backtest (all filters off)
test-baseline:
	STRATEGY_VOLATILITY_FILTER=false \
	STRATEGY_PULLBACK_ENTRY=false \
	STRATEGY_MOMENTUM_ACCELERATION=false \
	STRATEGY_TIME_FILTER=false \
	STRATEGY_MULTIFRAME_CONFIRMATION=false \
	STRATEGY_TIGHT_SPREAD_FILTER=false \
	STRATEGY_CORRELATION_CHECK=false \
	STRATEGY_TREND_CONFIRMATION=false \
	STRATEGY_DYNAMIC_NEUTRAL_RANGE=false \
	STRATEGY_IMPROVED_CONFIDENCE=false \
	uv run python run_backtest_real.py --symbol BTCUSDT --days 7

# Full features backtest (all filters on)
test-full-features:
	uv run python run_backtest_real.py --symbol BTCUSDT --days 7

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

# Multi-symbol backtest (test across BTC, ETH, SOL)
multi-quick:
	uv run python test_multi_symbol.py --quick

multi-full:
	uv run python test_multi_symbol.py --full

# Statistical testing and analysis commands
stats:
	uv run python analyze_strategy_results.py

analyze-latest:
	uv run python analyze_strategy_results.py

analyze-permutations:
	uv run python analyze_permutations.py

diagnose:
	uv run python diagnose_filters.py

kelly:
	uv run python position_sizing.py

# Live trading (dry-run mode for testing)
dryrun:
	@echo "Starting dry-run trading (simulated, no real money)..."
	@uv run python run_trader.py

dryrun-debug:
	@echo "Starting dry-run trading with debug output..."
	@uv run python run_trader.py --debug

# Pre-live checklists
checklist:
	@cat LIVE_READY_CHECKLIST.md

checklist-full:
	@cat PRE_LIVE_CHECKLIST.md

# Help/info
help:
	@echo "=== ARBITRAGE BACKTEST COMMANDS ==="
	@echo ""
	@echo "Quick Tests (2 days):"
	@echo "  make test-quick           - Backtest with moderate filters (5 disabled)"
	@echo "  make test-baseline        - Backtest with ALL filters disabled"
	@echo "  make test-suite-quick     - Test 5 strategies (32 permutations)"
	@echo "  make optimize-quick       - Test parameters (16 combinations)"
	@echo "  make multi-quick          - Test BTC/ETH/SOL (3 symbols)"
	@echo ""
	@echo "Full Tests (7 days):"
	@echo "  make test-full            - Single backtest (BTCUSDT, all strategies)"
	@echo "  make test-suite-full      - Test all 10 strategies (1024 perms)"
	@echo "  make optimize-full        - Test all parameters (256 combinations)"
	@echo "  make multi-full           - Test BTC/ETH/SOL (3 symbols)"
	@echo ""
	@echo "Analysis & Tools:"
	@echo "  make diagnose             - Show which filters are enabled/disabled"
	@echo "  make stats                - Statistical analysis of latest backtest"
	@echo "  make analyze-latest       - Same as stats"
	@echo "  make analyze-permutations - Analyze strategy permutation results"
	@echo "  make kelly                - Kelly criterion position sizing"
	@echo ""
	@echo "Live Trading (Dry-Run):"
	@echo "  make dryrun               - Run dry-run trading simulator (no real money)"
	@echo "  make dryrun-debug         - Run dry-run with debug output"
	@echo ""
	@echo "Pre-Live Deployment:"
	@echo "  make checklist            - Show quick 7-step live readiness checklist"
	@echo "  make checklist-full       - Show comprehensive pre-live validation checklist"
	@echo ""
	@echo "Other:"
	@echo "  make push                 - Git add, commit, and push"
	@echo "  make tmux                 - Start tmux session"
	@echo ""