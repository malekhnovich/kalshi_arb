# Real-Data Backtest Strategy Documentation

## 🎯 Core Thesis: Temporal Arbitrage
This strategy exploits the **time lag** between price discovery on high-frequency spot exchanges (Binance) and probability adjustments on prediction markets (Kalshi).

**The Inefficiency:**
When Bitcoin makes a violent move (e.g., +1% in 5 minutes), spot traders react instantly. However, prediction market participants often hesitate or react slower, leaving "Yes" contracts priced near 50¢ despite the underlying asset having already moved significantly.

## ⚙️ Strategy Mechanics

### 1. Spot Momentum (The Leading Indicator)
We analyze Binance.US 1-minute candles to detect "unstoppable" moves.
*   **Source**: Binance.US `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
*   **Window**: Last 60 minutes (configurable).
*   **Formula**: Hybrid Weighted Momentum.
    $$ \text{Momentum} = (0.7 \times \text{Volume\%}) + (0.3 \times \text{Count\%}) $$
    *   *Volume%*: Percentage of total volume occurring in green candles.
    *   *Count%*: Percentage of total candles that are green.
    *   *Why?* High volume confirms the move isn't a fake-out.

### 2. Trend Confirmation
To filter out chop/noise, we verify the market structure over the last 20 minutes:
*   **Uptrend**: Recent High > Previous High AND Recent Low > Previous Low.
*   **Downtrend**: Recent High < Previous High AND Recent Low < Previous Low.

### 3. The Signal Trigger
We generate a trade signal only when **three conditions** align:

1.  **Strong Momentum**: Spot momentum is extreme (>70% or <30%).
2.  **Stale Odds**: Kalshi odds are still "Neutral" (approx. 45¢ - 55¢).
    *   *Dynamic Range*: If the momentum is massive, we tolerate slightly wider odds (e.g., 40¢-60¢).
3.  **Positive Expected Value**: The spread between our calculated probability (Momentum) and the market price (Kalshi) exceeds a threshold (default 10¢).

### 4. Confidence Scoring
We calculate a `confidence` score (0-100) to size positions:
*   **Base**: Raw Momentum value.
*   **+ Spread Bonus**: Up to +10 points if the edge is large.
*   **+ Neutrality Bonus**: Up to +5 points if Kalshi is exactly at 50¢.
*   **+ Trend Bonus**: +5 points if market structure confirms direction.

## 📊 Trade Execution Logic

*   **Entry**: Buy "Yes" if Bullish, Buy "No" if Bearish.
*   **Price**: We use the actual traded price from Kalshi history (tick-level accuracy).
*   **Exit/Resolution**:
    1.  **Primary**: Use the official Kalshi market result (`yes` or `no`) if the market settled.
    2.  **Fallback**: If settlement data is missing, we assume the trade wins if momentum continued in our direction (>60% or <40%) after 1 hour.

## 📝 Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MOMENTUM_WINDOW` | 60 min | Lookback period for spot analysis. |
| `CONFIDENCE_THRESHOLD` | 70 | Minimum momentum required to consider a trade. |
| `MIN_ODDS_SPREAD` | 10¢ | Minimum edge required (e.g., Model says 80%, Market says 50%). |
| `trade_size` | $100 | Fixed bet size per trade. |
| `max_open_trades` | 3 | Risk management limit. |

## 🚀 Running the Backtest

```bash
# Test Bitcoin over the last week
python run_backtest_real.py --symbol BTCUSDT --days 7

# Test Solana for a specific volatile month
python run_backtest_real.py --symbol SOLUSDT --start 2023-11-01 --end 2023-11-30
```

## ⚠️ Data Note
The backtester caches data in `logs/cache.db`.
*   **Binance Data**: 1-minute OHLCV candles.
*   **Kalshi Data**: Tick-by-tick trade data (aggregated to minute).
*   **First Run**: Will be slower as it fetches data from APIs. Subsequent runs are instant.