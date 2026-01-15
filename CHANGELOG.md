# Changelog

All notable changes to the arbitrage detection system.

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
