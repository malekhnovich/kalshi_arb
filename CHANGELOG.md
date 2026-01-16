# Changelog

All notable changes to the arbitrage detection system.

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
