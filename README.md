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
│ Polls Binance │  │ Polls Kalshi    │  │ Detects lag between  │
│ every 5s      │  │ every 10s       │  │ spot & prediction    │
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

### Run Live Agent System

Monitor real-time prices and detect arbitrage opportunities:

```bash
# Standard run
python run_agents.py

# With debug logging
python run_agents.py --debug
```

Press `Ctrl+C` to stop gracefully.

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
- `binance_get_order_book` - Get bid/ask depth
- `binance_get_ticker` - Get 24h price stats
- `binance_get_klines` - Get candlestick data
- `binance_analyze_price_momentum` - Momentum analysis
- `binance_detect_temporal_lag` - Lag detection

## Configuration

Configuration is managed in `config.py` with environment variable overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_URL` | `https://api.binance.us/api/v3` | Binance.US API endpoint |
| `KALSHI_API_URL` | `https://api.elections.kalshi.com/trade-api/v2` | Kalshi API endpoint |
| `POLL_INTERVAL_BINANCE` | `5` | Binance polling interval (seconds) |
| `POLL_INTERVAL_KALSHI` | `10` | Kalshi polling interval (seconds) |
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
