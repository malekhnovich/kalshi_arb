# Changelog

All notable changes to the arbitrage detection system.

## [1.6.0] - 2026-01-17

### Parameter Optimization & Workflow

Added parameter optimization capabilities and formalized the development workflow.

#### New Features

**1. Parameter Optimization**
- Added support for testing parameter ranges (volatility, spread, pullback)
- Sensitivity analysis reporting
- Results saved to `PARAM_OPTIMIZATION_YYYYMMDD_HHMMSS.md`

**2. Workflow Documentation**
- Added comprehensive Workflow section to README
- Defined clear steps from data collection to live trading

#### Improvements
- Updated strategy results with latest 2026-01-17 data (Win rates >90% observed)
- Refined documentation for clarity

## [1.5.0] - 2026-01-16

### Strategy Permutation Testing System

Complete overhaul of strategy optimization with modular, testable improvements and comprehensive analysis tools.

#### New Features

**1. Modular Strategy System** (`strategies.py`)
- 10 independent, toggleable improvement strategies
- Each strategy configurable via environment variables
- No code changes needed—configure via env vars only
- Strategies can be enabled/disabled for A/B testing

**2. Permutation Testing Framework** (`test_all_strategies.py`)
- Tests all 2^N combinations of strategies automatically
- 1024 permutations for 10 strategies
- Real-time progress output with streaming
- Generates comprehensive markdown reports

**3. Enhanced Backtester** (`run_backtest_real.py`)
- Real-time progress updates (20% intervals)
- Better error handling and timeout management
- Per-market request timeout (10s each)
- Improved logging with flush=True on all prints

**4. Strategy Implementations**

| Strategy | File | Purpose | Impact |
|----------|------|---------|--------|
| Momentum Acceleration | `arbitrage_detector.py` | Skip decelerating momentum | Medium |
| Trend Confirmation | `price_monitor.py`, `arbitrage_detector.py` | Higher highs/lows bonus | Low-Medium |
| Dynamic Neutral Range | `arbitrage_detector.py` | Spread-based range adjustment | High |
| Improved Confidence | `arbitrage_detector.py` | Edge-quality bonuses | High |
| Volatility Filter | `arbitrage_detector.py` | Skip high volatility | High |
| Pullback Entry | `arbitrage_detector.py` | Wait for pullback | High |
| Tight Spread Filter | `arbitrage_detector.py` | Min 15c spread | High |
| Correlation Check | `arbitrage_detector.py` | No same-symbol overlap | Medium |
| Time Filter | `arbitrage_detector.py` | Active hours only | Medium |
| Multi-timeframe | (Pending) | 1m + 5m confirmation | Medium |

**5. Analysis & Reporting**
- **`test_all_strategies.py`**: Generates `STRATEGY_RESULTS_*.md` with:
  - Summary statistics (best/worst/avg metrics)
  - Top 20 rankings (by RoR, PnL, Win Rate)
  - Strategy impact analysis (enabled vs disabled)
  - Complete results table for all permutations
- **`compare_strategies.py`**: Analyzes and compares multiple runs
- **`diagnose.py`**: Checks system health (cache, logs, environment)

**6. Testing Utilities**
- `quick_backtest.py`: Fast backtest using cached data
- `test_strategies.py`: Pre-configured quick tests
- Real-time output streaming with progress indicators

#### Configuration Changes

```python
# New strategies.py with 10 toggleable strategies
STRATEGY_MOMENTUM_ACCELERATION = True      # Skip peaks
STRATEGY_TREND_CONFIRMATION = True         # Higher highs/lows
STRATEGY_DYNAMIC_NEUTRAL_RANGE = True      # Spread-based
STRATEGY_IMPROVED_CONFIDENCE = True        # Edge quality
STRATEGY_VOLATILITY_FILTER = True          # Skip noise
STRATEGY_PULLBACK_ENTRY = True             # Better entry
STRATEGY_TIGHT_SPREAD_FILTER = True        # Avoid tiny edges
STRATEGY_CORRELATION_CHECK = True          # Risk mgmt
STRATEGY_TIME_FILTER = True                # Active hours
STRATEGY_MULTIFRAME_CONFIRMATION = True    # 1m+5m

# Adjustable thresholds
STRATEGY_VOLATILITY_THRESHOLD = 0.015      # Max 1.5%
STRATEGY_PULLBACK_THRESHOLD = 0.3          # Min 0.3%
STRATEGY_MIN_SPREAD_CENTS = 15.0           # Min 15c
STRATEGY_TRADING_HOURS_START = 14          # 2pm UTC
STRATEGY_TRADING_HOURS_END = 22            # 10pm UTC
```

#### Files Modified

| File | Changes |
|------|---------|
| `arbitrage_detector.py` | Added 8 new strategy filters with toggles |
| `price_monitor.py` | Enhanced trend confirmation calculation |
| `run_backtest_real.py` | Better progress output, timeout handling |
| `test_all_strategies.py` | Real-time output streaming, better error handling |
| `config.py` | Reduced MOMENTUM_WINDOW from 60 to 20 |

#### Files Added

| File | Purpose |
|------|---------|
| `strategies.py` | Strategy configuration system |
| `test_all_strategies.py` | Permutation testing (1024 combinations) |
| `test_strategies.py` | Quick preset tests |
| `compare_strategies.py` | Result analysis tool |
| `quick_backtest.py` | Fast backtest with cache |
| `diagnose.py` | System diagnostics |
| `STRATEGIES.md` | Strategy documentation |
| `TESTING_GUIDE.md` | How to test strategies |
| `TROUBLESHOOTING.md` | Common issues & solutions |
| `EXAMPLE_STRATEGY_RESULTS.md` | Example report output |

#### Documentation

- **`STRATEGIES.md`**: Comprehensive guide to all 10 strategies, why they work, and how to tune them
- **`TESTING_GUIDE.md`**: Complete workflow for strategy testing from exploration to validation
- **`TROUBLESHOOTING.md`**: Debugging guide for timeouts, missing logs, and cache issues
- **`EXAMPLE_STRATEGY_RESULTS.md`**: Example of generated report format with sample data

#### Usage Examples

```bash
# Populate cache once (5-10 min)
python run_backtest_real.py --symbol BTCUSDT --days 7

# Quick exploration (32 permutations, 2 min)
python test_all_strategies.py --quick --limit-strategies 5

# Full testing (1024 permutations, 30-60 min)
python test_all_strategies.py --quick

# Verbose debug mode
python test_all_strategies.py --quick --limit-strategies 3 --verbose

# Custom strategy config
STRATEGY_VOLATILITY_FILTER=false STRATEGY_MIN_SPREAD_CENTS=20 \
  python run_backtest_real.py --symbol BTCUSDT --days 2
```

#### Expected Improvements

Based on testing, the new strategy system aims to:
- Increase win rate from 51.6% to 55-58%
- Improve Return on Risk from 0.72 to >1.5
- Reduce max drawdown below total PnL
- Generate fewer, higher-quality trades

---

## [1.4.0] - 2026-01-15

### Latency Optimization & Strategy Refinement

Reduction of price latency via Binance WebSockets and improved strategy via strike-price sensitivity and statistical probability modeling.

#### New Features

**1. Binance WebSocket Integration**
- **File**: `agents/binance_websocket.py` (NEW)
- Implemented `BinanceWebSocketClient` and `BinanceWebSocketAgent`.
- Provides sub-second price updates for Binance.US symbols.
- Significantly reduces the temporal lag between spot price movements and arbitrage signal generation.
- Configurable via `BINANCE_WS_ENABLED` (default: true).

**2. Strike-Price Sensitivity**
- **File**: `agents/arbitrage_detector.py`
- Added `STRIKE_DISTANCE_THRESHOLD_PCT` configuration.
- Arbitrage signals are now only triggered if the spot price is within X% of the Kalshi strike price (default: 0.5%).
- Filters out non-actionable markets where the spot price is too far from the strike price.

**3. Volatility-Based Fair Probability**
- **File**: `agents/arbitrage_detector.py`
- Implemented `_calculate_fair_probability` based on recent price volatility and distance to strike.
- Assigns a statistical "fair value" (0-100) to the probability of the market settling YES.
- Used to boost or dampen signal confidence based on statistical confirmation.

#### Improvements

- **Orchestration**: Updated `orchestrator.py` and `run_trader.py` to seamlessly integrate Binance WebSockets with existing fallback mechanisms.
- **Event Bus**: Added `fair_probability` field to `ArbitrageSignalEvent` for enhanced transparency.
- **Error Handling**: Improved WebSocket reconnection logic and linting in monitoring agents.

---

## [1.3.0] - 2026-01-15

### WebSocket Real-Time Data, Safety Gates & Realistic Simulation

Major upgrade adding real-time WebSocket streaming, comprehensive safety controls, and realistic dry-run simulation.

#### New Features

**1. Realistic Dry-Run Simulation**
- **File**: `config.py:214-252`, `agents/trader.py:336-410`
- Dry-run mode now simulates real trading conditions:
  - **Fees**: Kalshi taker fees (3¢/contract default)
  - **Slippage**: Adverse price movement on entry (1-3¢ typical)
  - **Partial Fills**: ~15% of orders may partially fill
  - **Latency Effects**: Price movement during execution delay
- Provides much more accurate P&L estimates
- Enabled by default (`SIM_REALISTIC_MODE=true`)
- To disable: `export SIM_REALISTIC_MODE=false`

**2. WebSocket Integration**
- **File**: `agents/kalshi_websocket.py` (NEW)
- Real-time price streaming via `wss://api.elections.kalshi.com`
- Sub-second price updates (vs 10-second polling)
- Automatic reconnection with exponential backoff
- Channels: `ticker`, `orderbook_delta`, `trade`
- Fallback to polling if WebSocket unavailable

**2. Live Trading Safety Gates**
- **File**: `config.py:79-144`
- Multiple safety checks required before live trading:
  1. `KALSHI_ENABLE_LIVE_TRADING=true` environment variable
  2. `./ENABLE_LIVE_TRADING` file must exist
  3. `--live` CLI flag passed
  4. Interactive "CONFIRM" prompt
  5. No `./STOP_TRADING` kill switch file
  6. Not running in CI environment
- Run `python run_trader.py --check-safety` to see status

**3. Full Order Placement API**
- **File**: `agents/trader.py:161-515`
- Complete Kalshi order API implementation
- RSA-PSS authentication for trading
- Balance checking (read-only, always safe)
- Position fetching (read-only, always safe)
- Order placement blocked unless ALL safety gates pass
- `immediate_or_cancel` orders for safety

**4. Enhanced Monitor with WS Support**
- **File**: `agents/kalshi_monitor.py`
- Hybrid WebSocket/polling mode
- Auto-fallback to polling on WS disconnect
- `get_mode()` returns "websocket" or "polling"

#### Configuration

```bash
# WebSocket (auto-enabled if websockets library installed)
export KALSHI_WS_ENABLED=true

# Safety gates for live trading
export KALSHI_ENABLE_LIVE_TRADING=true
touch ./ENABLE_LIVE_TRADING

# Kill switch to stop all trading
touch ./STOP_TRADING
```

#### Usage

```bash
# Check safety gate status
python run_trader.py --check-safety

# Run in dry-run mode (default, safe)
python run_trader.py

# Attempt live trading (requires all gates + confirmation)
python run_trader.py --live --max-position 25
```

#### Dependencies

```bash
pip install websockets  # Optional, for WebSocket support
pip install cryptography  # Required for trading API auth
```

---

## [1.2.0] - 2026-01-14

### Real Kalshi Data Backtesting

Added ability to backtest using actual Kalshi market data instead of simulated odds.

#### New Files
- `agents/kalshi_historical.py` - Historical data client with RSA-PSS authentication
- `run_backtest_real.py` - Backtester using real Kalshi candlestick data

#### Features
- Fetches real Kalshi market candlesticks via API
- Uses actual market settlement results for trade resolution
- Supports RSA-PSS signed authentication
- Aligns Kalshi candles with Binance klines by timestamp

#### Configuration
```bash
export KALSHI_API_KEY="your-api-key-id"
export KALSHI_PRIVATE_KEY_PATH="/path/to/private-key.pem"
```

#### Usage
```bash
python run_backtest_real.py --symbol BTCUSDT --days 7
```

---

## [1.1.0] - 2026-01-14

### Win Rate Improvements

Implemented 5 improvements to increase win probability from 43.5% to 55.8% (+12.3%).

#### 1. Hybrid Volume-Weighted Momentum
- **File**: `agents/price_monitor.py:132-163`
- **Change**: Replaced simple candle count with hybrid approach (70% volume-weighted + 30% simple count)
- **Impact**: Filters out noise, focuses on meaningful price moves with volume confirmation

#### 2. Momentum Acceleration Filter
- **File**: `agents/arbitrage_detector.py:109-126`
- **Change**: Tracks last 5 momentum readings; skips signals when momentum is decelerating
- **Impact**: Avoids late entries when momentum has already peaked

#### 3. Dynamic Neutral Range
- **File**: `agents/arbitrage_detector.py:139-146`
- **Change**: Neutral range now varies by spread size:
  - Spread >= 25c: (40, 60) - wide tolerance for huge edges
  - Spread >= 15c: (45, 55) - standard range
  - Spread < 15c: (47, 53) - strict filter for small edges
- **Impact**: Only takes smaller-edge trades when odds are truly mispriced

#### 4. Trend Confirmation Bonus
- **Files**: `agents/price_monitor.py:165-176`, `agents/arbitrage_detector.py:132-133`
- **Change**: Added `trend_confirmed` field to PriceUpdateEvent; +5 confidence bonus when price makes higher highs/lows matching direction
- **Impact**: Rewards signals aligned with price structure

#### 5. Edge-Quality Confidence Scaling
- **File**: `agents/arbitrage_detector.py:157-168`
- **Change**: Confidence now factors in:
  - Base momentum confidence
  - Spread bonus: up to +10 for 30c+ spread
  - Neutrality bonus: up to +5 when odds near 50
  - Trend bonus: +5 when trend confirmed
- **Impact**: Better position sizing via Kelly criterion

### Backtest Results

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Win Rate | 43.5% | 55.8% | +12.3% |
| Total P&L | -$2,383 | +$3,352 | +$5,735 |
| Sharpe Ratio | -8.57 | 12.86 | +21.4 |
| Trades | 255 | 231 | -24 |

---

## [1.0.0] - 2026-01-13

### Initial Release

- Multi-agent event-driven architecture
- Binance.US price monitoring with momentum calculation
- Kalshi prediction market odds tracking
- Temporal lag arbitrage detection
- Dry-run and live trading modes
- Backtesting with simulated Kalshi odds
- Position management and P&L tracking
- JSON logging for signals and trades
