# Binance.US ↔ Kalshi Temporal Arbitrage Detection System

A multi-agent system that detects price inefficiencies between cryptocurrency spot markets (Binance.US) and prediction markets (Kalshi). The system identifies temporal lag—when spot momentum confirms a direction but prediction market odds remain mispriced.

## Core Concept

When Binance shows strong directional momentum (≥70% up candles) but Kalshi prediction markets still price an outcome near 50/50, this indicates the prediction market hasn't caught up to spot price discovery—creating an exploitable arbitrage window.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                              │
│                   (Lifecycle & Health Management)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Event Bus                                │
│                   (Async Pub/Sub Communication)                  │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌──────────────────────┐
│ PriceMonitor  │  │  KalshiMonitor  │  │  ArbitrageDetector   │
│   Agent       │  │     Agent       │  │       Agent          │
│               │  │                 │  │                      │
│ Uses WebSocket│  │ Uses WebSocket  │  │ Uses Strike-Price    │
│ (fallback REST)│  │ (fallback REST) │  │ & Probability logic  │
└───────────────┘  └─────────────────┘  └──────────────────────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  SignalAggregator    │
                   │       Agent          │
                   │                      │
                   │ Logs & deduplicates  │
                   │ signals to JSON      │
                   └──────────────────────┘
```

## Installation

### Requirements

- Python 3.13+
- uv (recommended) or pip

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd arbitrage

# Install dependencies with uv
uv sync

# Or with pip
pip install -r requirements.txt
```

## Usage

Monitor real-time prices and detect arbitrage opportunities:

```bash
# Standard run (uses WebSockets by default)
python run_agents.py

# With debug logging
python run_agents.py --debug
```

### Run Trading System (Dry-Run or Live)

The trading agent executes simulated trades (dry-run) or actual trades (live) based on signals.

```bash
# Recommended for testing (saves output to log file)
python run_trader.py | tee logs/dryrun_$(date +%Y%m%d_%H%M%S).log

# Live trading (requires following all safety gates)
python run_trader.py --live
```

### Run Backtesting with Real Kalshi Data

Test the strategy on historical data using real Kalshi market data:

```bash
# Default: BTC, last 7 days
python run_backtest_real.py --symbol BTCUSDT --days 7

# Quick 2-day test
python run_backtest_real.py --symbol BTCUSDT --days 2

# Specify exact dates
python run_backtest_real.py --symbol BTCUSDT --start 2026-01-01 --end 2026-01-14
```

### Strategy Permutation Testing

Test all combinations of strategies to find the optimal configuration:

```bash
# Quick test with 5 strategies (32 permutations, ~2 min)
python test_all_strategies.py --quick --limit-strategies 5

# Full test with all 10 strategies (1024 permutations, ~30-60 min)
python test_all_strategies.py --quick

# Verbose mode to see backtest progress
python test_all_strategies.py --quick --limit-strategies 5 --verbose

# 7-day backtest for each permutation (more thorough, slower)
python test_all_strategies.py --full --limit-strategies 5
```

Results are saved as `STRATEGY_RESULTS_YYYYMMDD_HHMMSS.md` with rankings and analysis.

### Strategy Configuration

Enable/disable individual strategies via environment variables:

```bash
# Test specific strategy combination
STRATEGY_VOLATILITY_FILTER=true \
STRATEGY_PULLBACK_ENTRY=true \
STRATEGY_TIGHT_SPREAD_FILTER=false \
python run_backtest_real.py --symbol BTCUSDT --days 2
```

### MCP Server (Claude Integration)

Run the Model Context Protocol server for Claude integration:

```bash
python binance_mcp_server.py
```

Available tools:
#### 1. Analyze Momentum
Calculate % of recent candles closing higher (Hybrid volume-weighted).

#### 2. Statistical Confirmation
Calculate the theoretical probability of settlement using recent price volatility.

#### 3. Detect Lag
Identify when spot momentum is strong but Kalshi odds remain neutral, provided the spot price is within the strike distance threshold (default 0.5%).

#### 4. Execution
Execute trades in dry-run or live mode with realistic simulation (fees, slippage).

## Configuration

Configuration is managed in `config.py` and `strategies.py` with environment variable overrides.

### Core Configuration (`config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_URL` | `https://api.binance.us/api/v3` | Binance.US API endpoint |
| `KALSHI_API_URL` | `https://api.elections.kalshi.com/trade-api/v2` | Kalshi API endpoint |
| `BINANCE_WS_ENABLED` | `true` | Enable real-time Binance price stream |
| `KALSHI_WS_ENABLED` | `true` | Enable real-time Kalshi odds stream |
| `STRIKE_DISTANCE_THRESHOLD_PCT` | `0.5` | Max % distance to strike for signal |
| `MOMENTUM_WINDOW` | `20` | Minutes to analyze for momentum (reduced from 60) |
| `CONFIDENCE_THRESHOLD` | `70` | Minimum confidence % for signals |
| `MIN_ODDS_SPREAD` | `10.0` | Minimum spread (cents) for opportunity |

### Strategy Configuration (`strategies.py`)

Enable/disable individual improvement strategies:

| Variable | Default | Purpose |
|----------|---------|---------|
| `STRATEGY_MOMENTUM_ACCELERATION` | `true` | Skip signals when momentum is decelerating |
| `STRATEGY_TREND_CONFIRMATION` | `true` | Confirm with higher highs/lows (+5 confidence) |
| `STRATEGY_DYNAMIC_NEUTRAL_RANGE` | `true` | Adjust neutral range by spread size |
| `STRATEGY_IMPROVED_CONFIDENCE` | `true` | Enhanced confidence formula with bonuses |
| `STRATEGY_VOLATILITY_FILTER` | `true` | Skip high volatility periods |
| `STRATEGY_PULLBACK_ENTRY` | `true` | Wait for pullback before entering |
| `STRATEGY_TIGHT_SPREAD_FILTER` | `true` | Minimum 15c spread (vs 10c baseline) |
| `STRATEGY_CORRELATION_CHECK` | `true` | Don't trade same symbol twice |
| `STRATEGY_TIME_FILTER` | `true` | Only trade 2pm-10pm UTC |
| `STRATEGY_MULTIFRAME_CONFIRMATION` | `true` | Confirm on both 1m and 5m timeframes |

**Strategy Thresholds:**

| Variable | Default | Description |
|----------|---------|-------------|
| `STRATEGY_VOLATILITY_THRESHOLD` | `0.015` | Max volatility (1.5% stdev) |
| `STRATEGY_PULLBACK_THRESHOLD` | `0.3` | Min pullback 0.3% |
| `STRATEGY_MIN_SPREAD_CENTS` | `15.0` | Minimum spread in cents |
| `STRATEGY_TRADING_HOURS_START` | `14` | Trading start (2pm UTC) |
| `STRATEGY_TRADING_HOURS_END` | `22` | Trading end (10pm UTC) |

### Symbols Monitored

- **Binance.US**: BTCUSDT, ETHUSDT, SOLUSDT
- **Kalshi**: KXBTC (Bitcoin), KXETH (Ethereum)

## Project Structure

### Core Files

```
arbitrage/
├── config.py                 # Configuration with env var support
├── strategies.py             # Strategy toggles & configuration
├── events.py                 # Event types & async event bus
└── cache.py                  # Caching layer for API data
```

### Agents (`agents/`)

```
agents/
├── __init__.py               # Package exports
├── base.py                   # BaseAgent with retry/circuit breaker
├── price_monitor.py          # Binance price monitoring with momentum
├── kalshi_monitor.py         # Kalshi odds monitoring
├── arbitrage_detector.py     # Arbitrage detection with 10 strategies
├── signal_aggregator.py      # Logging & statistics
├── backtester.py             # Historical replay & P&L
├── kalshi_historical.py      # Real Kalshi data fetching
├── trader.py                 # Trade execution (dry-run/live)
├── binance_websocket.py      # Binance WebSocket streaming
└── kalshi_websocket.py       # Kalshi WebSocket streaming
```

### Entry Points

```
├── run_agents.py             # Live monitoring entry point
├── run_trader.py             # Trading system entry point
├── run_backtest.py           # Simulated backtest entry point
├── run_backtest_real.py      # Real data backtest entry point
├── binance_mcp_server.py     # MCP server for Claude
└── main.py                   # Standalone analyzer CLI
```

### Testing & Analysis

```
├── test_all_strategies.py    # Permutation testing (all 1024 combinations)
├── test_strategies.py        # Quick preset strategy tests
├── compare_strategies.py     # Analysis tool for results
├── quick_backtest.py         # Fast backtest using cache
└── diagnose.py              # Diagnostic utility
```

### Documentation & Config

```
├── README.md                 # This file
├── CHANGELOG.md              # Version history
├── STRATEGIES.md             # Strategy documentation
├── TESTING_GUIDE.md          # How to test strategies
├── TROUBLESHOOTING.md        # Common issues & solutions
├── EXAMPLE_STRATEGY_RESULTS.md # Example report output
├── pyproject.toml            # Project metadata
├── .mcp.json                 # Claude MCP configuration
└── logs/                     # Results & cache
    ├── backtest_real_*.json  # Backtest results
    ├── cache.db             # Cached API data
    └── signals_*.json       # Signal logs
```

## File Purposes

### Core Configuration & Events

- **`config.py`**: Central configuration file. Manages all settings with environment variable overrides. Includes API URLs, polling intervals, trading limits, backtesting parameters, and realistic simulation settings.

- **`strategies.py`**: Strategy configuration system. Defines 10 independent improvement strategies that can be toggled on/off via environment variables. Each strategy has adjustable thresholds for fine-tuning.

- **`events.py`**: Event system. Defines all event types (PRICE_UPDATE, KALSHI_ODDS, ARBITRAGE_SIGNAL, ALERT) and the async event bus for pub/sub communication between agents.

- **`cache.py`**: Caching layer. Stores historical Binance klines and Kalshi trades in SQLite to avoid repeated API calls. Makes backtesting fast after initial data load.

### Price & Market Data Agents

- **`agents/price_monitor.py`**: Monitors Binance prices. Calculates hybrid volume-weighted momentum (70% volume + 30% candle count). Detects trend confirmation (higher highs/lows).

- **`agents/kalshi_monitor.py`**: Monitors Kalshi prediction markets. Fetches current odds for crypto markets. Supports both WebSocket (real-time) and REST polling (fallback).

- **`agents/binance_websocket.py`**: Real-time Binance data via WebSocket. Provides sub-second price updates for ultra-low latency.

- **`agents/kalshi_websocket.py`**: Real-time Kalshi data via WebSocket. Streams odds changes with automatic reconnection and fallback to polling.

### Signal Generation

- **`agents/arbitrage_detector.py`**: Core arbitrage detection logic. Implements 10 improvement strategies:
  1. Momentum acceleration filter
  2. Trend confirmation bonus
  3. Dynamic neutral range
  4. Improved confidence formula
  5. Volatility filter
  6. Pullback entry
  7. Tight spread filter
  8. Correlation check
  9. Time filter
  10. Multi-timeframe confirmation

- **`agents/signal_aggregator.py`**: Aggregates signals into daily logs. Deduplicates and statistics for analysis.

### Trading & Execution

- **`agents/trader.py`**: Executes trades in dry-run or live mode. Handles order placement, position tracking, P&L calculation. Includes realistic simulation (fees, slippage, partial fills).

- **`agents/backtester.py`**: Simulated historical replay. Tests strategies on past data with simple Kalshi odds simulation.

- **`agents/kalshi_historical.py`**: Fetches real historical Kalshi market data. Uses RSA-PSS authentication for API access. Enables backtesting with actual market data.

### System Management

- **`agents/base.py`**: Base agent class. Implements retry logic (exponential backoff), circuit breaker pattern, and error handling for resilience.

- **`orchestrator.py`**: Manages agent lifecycle. Starts/stops agents, monitors health, handles restarts on failure.

### Entry Points

- **`run_agents.py`**: Live monitoring. Starts price monitor, Kalshi monitor, and arbitrage detector. Streams signals to JSON logs.

- **`run_trader.py`**: Trading system. Executes trades based on signals in dry-run or live mode with multiple safety gates.

- **`run_backtest.py`**: Simulated backtest. Tests strategy on historical data with artificial Kalshi odds.

- **`run_backtest_real.py`**: Real data backtest. Uses actual historical Kalshi market data for more accurate testing. Fetches data from APIs and caches it.

- **`binance_mcp_server.py`**: Claude integration. Provides tools for Claude to analyze momentum, detect arbitrage, and execute trades.

- **`main.py`**: Standalone CLI analyzer. One-off analysis of prices and opportunities without running full system.

### Strategy Testing

- **`test_all_strategies.py`**: Main permutation tester. Tests all 2^N combinations of strategies (1024 for 10 strategies). Generates comprehensive markdown report with rankings and impact analysis.

- **`test_strategies.py`**: Quick preset tests. Pre-configured strategy combinations for rapid testing.

- **`compare_strategies.py`**: Result analyzer. Loads backtest results and generates comparison tables.

- **`quick_backtest.py`**: Fast cached backtest. Uses previously cached data for quick testing without API calls.

- **`diagnose.py`**: Diagnostic utility. Checks cache status, environment variables, and recent backtest results.

### Documentation

- **`README.md`**: Complete project documentation including setup, usage, configuration, and architecture.

- **`CHANGELOG.md`**: Version history. Documents all features, improvements, and bug fixes by release.

- **`STRATEGIES.md`**: Strategy guide. Detailed explanation of each of the 10 strategies, why they help, and how to tune them.

- **`TESTING_GUIDE.md`**: How to test strategies. Complete guide to using the permutation testing system, interpreting results, and iterating on configurations.

- **`TROUBLESHOOTING.md`**: Common issues. Debugging guide for timeouts, missing logs, cache problems, and API issues.

- **`EXAMPLE_STRATEGY_RESULTS.md`**: Example report output. Shows what a complete strategy test report looks like with sample data.

## Event Types

| Event | Description | Publisher |
|-------|-------------|-----------|
| `PRICE_UPDATE` | Binance price + momentum data | PriceMonitorAgent |
| `KALSHI_ODDS` | Prediction market odds | KalshiMonitorAgent |
| `ARBITRAGE_SIGNAL` | Detected opportunity | ArbitrageDetectorAgent |
| `ALERT` | General alerts | Any agent |

## Arbitrage Detection Logic

1. **Monitor Momentum**: Calculate % of recent candles closing higher (momentum)
2. **Track Odds**: Fetch Kalshi yes/no prices for crypto prediction markets
3. **Detect Lag**: When momentum ≥70% (bullish) or ≤30% (bearish) but Kalshi odds are 45-55 (neutral)
4. **Signal**: If spread between expected odds and actual odds ≥10 cents, emit signal
5. **Recommend**: BUY YES (bullish) or BUY NO (bearish) based on momentum direction

## Strategy Testing Workflow

### Overview

The strategy testing system allows you to:
1. **Configure**: Enable/disable 10 independent improvement strategies
2. **Test**: Run permutations (2^10 = 1024 combinations) against historical data
3. **Analyze**: Get detailed rankings and impact analysis
4. **Optimize**: Fine-tune thresholds to maximize performance

### Workflow

```
1. POPULATE CACHE (run once)
   └─> python run_backtest_real.py --symbol BTCUSDT --days 7
       Creates logs/cache.db with historical data

2. QUICK EXPLORATION (5 minutes)
   └─> python test_all_strategies.py --quick --limit-strategies 5
       Tests 32 permutations to find patterns

3. DEEPER TESTING (15 minutes)
   └─> python test_all_strategies.py --quick --limit-strategies 7
       Tests 128 permutations for more coverage

4. FULL ANALYSIS (30-60 minutes)
   └─> python test_all_strategies.py --quick
       Tests all 1024 permutations

5. VALIDATE WINNERS (overnight)
   └─> python test_all_strategies.py --full --limit-strategies 5
       Validates top candidates with 7-day backtests

6. REVIEW RESULTS
   └─> cat STRATEGY_RESULTS_*.md
       Analyze rankings, impact analysis, and comparisons
```

### Output

Each test run generates `STRATEGY_RESULTS_YYYYMMDD_HHMMSS.md` with:

- **Summary Statistics**: Best/worst/avg metrics across all permutations
- **Top 20 Rankings**: By Return on Risk, Total P&L, Win Rate
- **Strategy Impact Analysis**: Shows which strategies add the most value
- **Complete Results**: All permutations ranked and sortable

### Key Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Win Rate** | % of profitable trades | 55-58% |
| **P&L** | Total profit/loss | Maximize |
| **Max Drawdown** | Largest loss from peak | Minimize |
| **Return on Risk** | P&L ÷ Max Drawdown | Maximize (>2.0 is excellent) |
| **Profit Factor** | Avg Win ÷ Avg Loss | >1.5 is healthy |

## Backtest Metrics

The backtester calculates:

- **Win Rate**: Percentage of profitable trades
- **Total P&L**: Cumulative profit/loss
- **Max Drawdown**: Largest peak-to-trough decline
- **Profit Factor**: Average winning trade ÷ average losing trade
- **Return on Risk**: P&L ÷ Max Drawdown (primary optimization metric)
- **Trades/Day**: Signal frequency for portfolio diversification

## Error Handling

The system includes:

- **Retry Logic**: Exponential backoff (1s → 2s → 4s → 8s → 16s) for failed API calls
- **Circuit Breaker**: Agents pause after 5 consecutive failures, auto-recover after 60s
- **Rate Limiting**: Respects API rate limits with configurable delays
- **Health Monitoring**: Orchestrator checks agent health every 30s

## Logging

- **Console**: Color-coded output (blue=info, yellow=warning, green=opportunity, red=error)
- **JSON Files**: Daily logs in `logs/signals_YYYY-MM-DD.json`
- **Backtest Results**: Saved to `logs/backtest_<symbol>_<timestamp>.json`

## Known Limitations & Future Work

### Current Limitations

- **Multi-timeframe Confirmation**: Framework in place but 5-minute candle aggregation not yet implemented
- **Cache Corruption**: Large backtests may occasionally corrupt cache.db; solution: delete and rebuild
- **Kalshi API Rate Limits**: Historic data fetching is slow; recommend using cache after first run

### Planned Improvements

- [ ] Implement 5-minute timeframe confirmation
- [ ] Add position sizing based on Kelly criterion
- [ ] Support for additional cryptocurrency pairs (ETH, SOL)
- [ ] Live trading integration (order execution)
- [ ] Real-time performance monitoring dashboard
- [ ] Statistical significance testing for strategy comparisons

### Testing Limitations

- Backtests use historical market data; future performance may differ
- Strategy optimization on recent data may overfit
- Real execution costs (fees, slippage) may exceed simulation estimates

## License

MIT
