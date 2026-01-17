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

### Run Backtesting

Test the strategy on historical data:

```bash
# Default: BTC, last 7 days
python run_backtest.py

# Custom symbol and date range
python run_backtest.py --symbol ETHUSDT --days 30

# Specify exact dates
python run_backtest.py --symbol BTCUSDT --start 2024-01-01 --end 2024-01-31

# Custom initial capital
python run_backtest.py --capital 50000

# Skip saving results
python run_backtest.py --no-save
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

Configuration is managed in `config.py` with environment variable overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_URL` | `https://api.binance.us/api/v3` | Binance.US API endpoint |
| `KALSHI_API_URL` | `https://api.elections.kalshi.com/trade-api/v2` | Kalshi API endpoint |
| `BINANCE_WS_ENABLED` | `true` | Enable real-time Binance price stream |
| `KALSHI_WS_ENABLED` | `true` | Enable real-time Kalshi odds stream |
| `STRIKE_DISTANCE_THRESHOLD_PCT` | `0.5` | Max % distance to strike for signal |
| `MOMENTUM_WINDOW` | `60` | Minutes to analyze for momentum |
| `CONFIDENCE_THRESHOLD` | `70` | Minimum confidence % for signals |
| `MIN_ODDS_SPREAD` | `10.0` | Minimum spread (cents) for opportunity |

### Symbols Monitored

- **Binance.US**: BTCUSDT, ETHUSDT, SOLUSDT
- **Kalshi**: KXBTC (Bitcoin), KXETH (Ethereum)

## Project Structure

```
arbitrage/
├── agents/
│   ├── __init__.py           # Package exports
│   ├── base.py               # BaseAgent with retry/circuit breaker
│   ├── price_monitor.py      # Binance price monitoring
│   ├── kalshi_monitor.py     # Kalshi odds monitoring
│   ├── arbitrage_detector.py # Lag detection logic
│   ├── signal_aggregator.py  # Logging & statistics
│   └── backtester.py         # Historical replay & P&L
├── logs/                     # JSON signal logs
├── config.py                 # Configuration with env var support
├── events.py                 # Event types & async event bus
├── orchestrator.py           # Agent lifecycle manager
├── main.py                   # Standalone analyzer CLI
├── binance_mcp_server.py     # MCP server for Claude
├── run_agents.py             # Live system entry point
├── run_backtest.py           # Backtest entry point
├── pyproject.toml            # Project metadata
└── .mcp.json                 # Claude MCP configuration
```

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

## Backtest Metrics

The backtester calculates:

- **Win Rate**: Percentage of profitable trades
- **Total P&L**: Cumulative profit/loss
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (annualized)
- **Average Trade P&L**: Mean profit per trade

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

## Limitations

- **Simulated Kalshi Data**: Backtester uses simulated odds with artificial lag (not real historical Kalshi data)
- **No Live Trading**: System is detection-only; no execution capabilities
- **API Authentication**: Kalshi authenticated endpoints not implemented

## License

MIT
