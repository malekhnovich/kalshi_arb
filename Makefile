.PHONY: push tmux help test-quick test-full test-suite-quick test-suite-full optimize-quick optimize-full tsa dryrun dryrun-debug dryrun-test dryrun-test-debug kill-python kill-dryrun kill-all

# Git commands
gcp:
	git add .
	git commit -m "Auto-commit from Makefile"
	git push

# Session management
tmux:
	@tmux has-session -t arbitrage 2>/dev/null || \
	tmux new-session -d -s arbitrage \; split-window -h \; split-window -v \; select-pane -t 0 \; split-window -v \; select-layout tiled
	@tmux attach-session -t arbitrage

# Process management - Kill running processes
kill-python:
	@echo "Killing all Python processes..."
	@pkill -f "uv run python.*run_trader\|python.*run_backtest\|python.*dryrun" || echo "No Python trading processes running"
	@sleep 1
	@echo "✓ Done"

kill-dryrun:
	@echo "Killing dry-run processes..."
	@pkill -f "python.*run_trader" || echo "No dryrun processes running"
	@sleep 1
	@echo "✓ Done"

kill-all:
	@echo "Killing ALL Python processes in this directory..."
	@pkill -f "python" || echo "No Python processes running"
	@sleep 1
	@echo "✓ Done (use with caution!)"

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
	@echo "Log file: logs/dryrun_$(shell date +%Y%m%d_%H%M%S).log"
	@uv run python run_trader.py | tee logs/dryrun_$(shell date +%Y%m%d_%H%M%S).log

dryrun-debug:
	@echo "Starting dry-run trading with debug output..."
	@echo "Log file: logs/dryrun_debug_$(shell date +%Y%m%d_%H%M%S).log"
	@uv run python run_trader.py --debug | tee logs/dryrun_debug_$(shell date +%Y%m%d_%H%M%S).log

# TEST CONFIG: Bare minimum filters for workflow validation
# Uses config_test.py instead of config.py
# This is a SEPARATE configuration to test end-to-end flow
dryrun-test:
	@echo "Starting TEST CONFIG dry-run (bare minimum filters)..."
	@echo "Using: config_test.py (SEPARATE TEST CONFIG)"
	@echo "Price Monitor: Binance (default) - Override with PRICE_MONITOR_SOURCE=coingecko"
	@echo "Log file: logs/dryrun_test_$(shell date +%Y%m%d_%H%M%S).log"
	@uv run python run_trader.py --config config_test 2>&1 | tee logs/dryrun_test_$(shell date +%Y%m%d_%H%M%S).log

dryrun-test-debug:
	@echo "Starting TEST CONFIG dry-run with debug output (bare minimum filters)..."
	@echo "Using: config_test.py (SEPARATE TEST CONFIG)"
	@echo "Price Monitor: Binance (default) - Override with PRICE_MONITOR_SOURCE=coingecko"
	@echo "Log file: logs/dryrun_test_debug_$(shell date +%Y%m%d_%H%M%S).log"
	@uv run python run_trader.py --config config_test --debug 2>&1 | tee logs/dryrun_test_debug_$(shell date +%Y%m%d_%H%M%S).log

# Check for trades in dry-run logs
check-trades:
	@echo "=== CHECKING FOR EXECUTED TRADES ===" && \
	if [ -f "$$(ls -t logs/dryrun*.log 2>/dev/null | head -1)" ]; then \
		LATEST=$$(ls -t logs/dryrun*.log 2>/dev/null | head -1); \
		echo "Latest log: $$LATEST" && \
		echo "" && \
		TRADE_COUNT=$$(grep -c "TRADE ENTERED\|TRADE CLOSED" "$$LATEST" 2>/dev/null || echo "0"); \
		if [ "$$TRADE_COUNT" -eq 0 ]; then \
			echo "❌ No trades found yet in latest log"; \
		else \
			echo "✅ Found $$TRADE_COUNT trade events" && \
			echo "" && \
			echo "=== TRADE ENTRIES ===" && \
			grep "TRADE ENTERED" "$$LATEST" || echo "No entries yet" && \
			echo "" && \
			echo "=== TRADE CLOSURES ===" && \
			grep "TRADE CLOSED" "$$LATEST" || echo "No closures yet" && \
			echo "" && \
			echo "=== WIN/LOSS SUMMARY ===" && \
			WINS=$$(grep -c "WIN" "$$LATEST" 2>/dev/null || echo "0"); \
			LOSSES=$$(grep -c "LOSS" "$$LATEST" 2>/dev/null || echo "0"); \
			echo "Wins: $$WINS | Losses: $$LOSSES"; \
		fi; \
	else \
		echo "❌ No dry-run logs found. Start a dry-run first with 'make dryrun' or 'make dryrun-debug'"; \
	fi

check-trades-all:
	@echo "=== CHECKING ALL DRY-RUN LOGS ===" && \
	if ls logs/dryrun*.log 1> /dev/null 2>&1; then \
		echo "Found $$(ls logs/dryrun*.log 2>/dev/null | wc -l) log files" && \
		echo "" && \
		for log in $$(ls -t logs/dryrun*.log); do \
			TRADE_COUNT=$$(grep -c "TRADE ENTERED\|TRADE CLOSED" "$$log" 2>/dev/null || echo "0"); \
			WINS=$$(grep -c "WIN" "$$log" 2>/dev/null || echo "0"); \
			LOSSES=$$(grep -c "LOSS" "$$log" 2>/dev/null || echo "0"); \
			echo "$$log: Trades=$$TRADE_COUNT | Wins=$$WINS | Losses=$$LOSSES"; \
		done; \
	else \
		echo "❌ No dry-run logs found"; \
	fi

check-wins:
	@echo "=== WINNING TRADES ===" && \
	if [ -f "$$(ls -t logs/dryrun*.log 2>/dev/null | head -1)" ]; then \
		LATEST=$$(ls -t logs/dryrun*.log 2>/dev/null | head -1); \
		grep -A 5 "TRADE CLOSED - WIN" "$$LATEST" 2>/dev/null || echo "No winning trades found"; \
	else \
		echo "❌ No dry-run logs found"; \
	fi

check-losses:
	@echo "=== LOSING TRADES ===" && \
	if [ -f "$$(ls -t logs/dryrun*.log 2>/dev/null | head -1)" ]; then \
		LATEST=$$(ls -t logs/dryrun*.log 2>/dev/null | head -1); \
		grep -A 5 "TRADE CLOSED - LOSS" "$$LATEST" 2>/dev/null || echo "No losing trades found"; \
	else \
		echo "❌ No dry-run logs found"; \
	fi

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
	@echo "  make dryrun-test          - TEST CONFIG (bare minimum filters for testing)"
	@echo "  make dryrun-test-debug    - TEST CONFIG with debug output"
	@echo "  make check-trades         - Check if trades were executed (latest log)"
	@echo "  make check-trades-all     - Show all trades across all logs"
	@echo "  make check-wins           - Show only winning trades"
	@echo "  make check-losses         - Show only losing trades"
	@echo ""
	@echo "Price Monitor Selection:"
	@echo "  Default: CoinGecko (free, no API key required)"
	@echo "  Override: PRICE_MONITOR_SOURCE=binance make dryrun-test-debug"
	@echo ""
	@echo "Pre-Live Deployment:"
	@echo "  make checklist            - Show quick 7-step live readiness checklist"
	@echo "  make checklist-full       - Show comprehensive pre-live validation checklist"
	@echo ""
	@echo "Process Management:"
	@echo "  make kill-dryrun          - Kill dry-run processes"
	@echo "  make kill-python          - Kill all trading-related Python processes"
	@echo "  make kill-all             - Kill ALL Python processes (use with caution!)"
	@echo ""
	@echo "Other:"
	@echo "  make push                 - Git add, commit, and push"
	@echo "  make tmux                 - Start tmux session"
	@echo ""