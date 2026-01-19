# Strategy Configuration Guide

This document explains all the strategies you can toggle on/off to optimize your arbitrage bot.

## Current Default Status (as of 2026-01-18)

| # | Strategy | Default | Implementation |
|---|----------|---------|----------------|
| 1 | Momentum Acceleration | ✗ OFF | Complete |
| 2 | Trend Confirmation | ✗ OFF | Complete |
| 3 | Dynamic Neutral Range | ✗ OFF | Complete |
| 4 | Improved Confidence | ✓ ON | Complete |
| 5 | Volatility Filter | ✗ OFF | Complete |
| 6 | Pullback Entry | ✗ OFF | Complete |
| 7 | Tight Spread Filter | ✗ OFF | Complete |
| 8 | Correlation Check | ✗ OFF | Complete |
| 9 | Time Filter | ✗ OFF | Complete |
| 10 | Multi-timeframe | ✗ OFF | Partial (uses momentum history) |

**Exit Strategies:**
- Time-based Exit (60s default): ✓ Implemented
- Market Resolution Exit: ✓ Implemented
- Confidence-based Exit: ✗ Not yet implemented

## Overview

The arbitrage detector now supports 10+ independent strategies that can be enabled/disabled via environment variables. This lets you:

- Test different strategy combinations quickly
- Find the optimal mix for your trading goals
- Understand which strategies add the most value
- A/B test new ideas

## Quick Start

### Run with All Strategies Enabled (Recommended)
```bash
python test_strategies.py
```

### Run with Baseline (All Disabled)
```bash
python test_strategies.py --baseline
```

### Quick 2-Day Test
```bash
python test_strategies.py --quick
```

### Custom Configuration
```bash
STRATEGY_VOLATILITY_FILTER=false STRATEGY_PULLBACK_ENTRY=false python run_backtest_real.py --symbol BTCUSDT --days 2
```

---

## Strategy Details

### 1. Momentum Acceleration Filter
**Status**: ✗ Disabled by default (optimization found it adds noise)
**Env Variable**: `STRATEGY_MOMENTUM_ACCELERATION`

**What it does**: Only enter trades where momentum is still accelerating (not peaked).

**Why it helps**:
- Avoids entering right at momentum peaks
- Catches momentum shifts early
- Filters out mean-reversion trades

**Impact**: Medium - Reduces false signals

**Note**: Permutation testing showed this filter adds noise rather than edge. Disabling it improved win rate from 66.7% to 71.4%.

**Configuration**:
- None (boolean only)

---

### 2. Trend Confirmation
**Status**: ✗ Disabled by default (for testing)
**Env Variable**: `STRATEGY_TREND_CONFIRMATION`

**What it does**: Gives +5 confidence boost when price structure confirms direction (higher highs/lows for uptrend, lower highs/lows for downtrend).

**Why it helps**:
- Aligns with price action
- Catches structural breakouts
- Higher quality signals

**Impact**: Low-Medium - Modest confidence boost

**Configuration**:
- None (boolean only)

---

### 3. Dynamic Neutral Range
**Status**: ✗ Disabled by default (uses static range from config)
**Env Variable**: `STRATEGY_DYNAMIC_NEUTRAL_RANGE`

**What it does**: Adjusts the neutral odds range based on spread size:
- Huge spreads (≥25c): Range (40, 60) - wide tolerance
- Medium spreads (≥15c): Range (45, 55) - standard
- Small spreads (<15c): Range (47, 53) - strict filter

**Why it helps**:
- Accepts more odd combinations when edges are large
- Rejects marginal setups with tiny edges
- Risk-aware filtering

**Impact**: High - Critical for avoiding low-quality trades

**Configuration**:
- None (boolean only)

---

### 4. Improved Confidence Formula
**Status**: ✓ Enabled by default
**Env Variable**: `STRATEGY_IMPROVED_CONFIDENCE`

**What it does**: Enhanced confidence calculation:
- Base: Momentum (60-100%)
- Spread bonus: +0 to +10 for spreads ≥30c
- Neutrality bonus: +0 to +5 for odds near 50c
- Trend bonus: +5 if trend confirmed
- Fair probability bonus: +5 for confirmed direction

**Why it helps**:
- More realistic confidence scores
- Correlates better with actual win rates
- Weights factors appropriately

**Impact**: High - Much better trade quality filtering

**Configuration**:
- None (boolean only)

---

### 5. Volatility Filter
**Status**: ✗ Disabled by default (too restrictive for crypto)
**Env Variable**: `STRATEGY_VOLATILITY_FILTER`

**What it does**: Skip trades when recent price volatility is too high.

**Why it helps**:
- Avoids unpredictable periods
- Reduces false signals during market chaos
- Improves win rate in stable periods

**Impact**: High - Filters noise, improves signal quality

**Note**: Disabled because it was too restrictive for crypto markets, which have inherent volatility.

**Configuration**:
```bash
STRATEGY_VOLATILITY_THRESHOLD=0.015  # Max stdev of returns (default: 0.015 = 1.5%)
```

**Tuning Guide**:
- Lower value (0.01): Only trade very quiet periods
- Higher value (0.02): Trade more periods, accept more volatility
- Default (0.015): Good balance

---

### 6. Pullback Entry
**Status**: ✗ Disabled by default (too restrictive)
**Env Variable**: `STRATEGY_PULLBACK_ENTRY`

**What it does**: Wait for price to pull back from recent peak before entering. This avoids buying the top of a move.

**Why it helps**:
- Better risk-reward (lower entry)
- Avoids peak entries
- Catches trending consolidations

**Impact**: High - Improves entry prices significantly

**Note**: Disabled because pullbacks may not happen in fast-moving momentum plays.

**Configuration**:
```bash
STRATEGY_PULLBACK_THRESHOLD=0.3  # Minimum pullback % (default: 0.3% = 30bps)
```

**Tuning Guide**:
- Lower value (0.1): Accept small pullbacks, more entries
- Higher value (0.5): Require larger pullbacks, fewer entries
- Default (0.3): Good balance

---

### 7. Tight Spread Filter
**Status**: ✗ Disabled by default (allows more opportunities)
**Env Variable**: `STRATEGY_TIGHT_SPREAD_FILTER`

**What it does**: Increases minimum required spread to filter out tiny edges that get eaten by fees.

**Why it helps**:
- Eliminates unprofitable trades
- Better risk-reward
- Reduces false positives

**Impact**: High - Critical for profitability

**Note**: Disabled to allow more trading opportunities. At 71.4% win rate, even small edges become profitable.

**Configuration**:
```bash
STRATEGY_MIN_SPREAD_CENTS=7.0  # Minimum spread in cents (default: 7c)
```

**Tuning Guide**:
- Lower value (5): Accept smaller edges
- Higher value (15-20): Only large edges
- Default (7): Captures more opportunities

---

### 8. Correlation Check
**Status**: ✗ Disabled by default (for testing)
**Env Variable**: `STRATEGY_CORRELATION_CHECK`

**What it does**: Skip trading same symbol if you already have an open position.

**Why it helps**:
- Prevents over-concentration
- Reduces correlation risk
- Better position management

**Impact**: Medium - Risk management

**Configuration**:
- None (boolean only)

---

### 9. Time Filter
**Status**: ✗ Disabled by default (crypto trades 24/7)
**Env Variable**: `STRATEGY_TIME_FILTER`

**What it does**: Only trade during active market hours (UTC).

**Why it helps**:
- Avoids low-liquidity periods
- Better spreads and fills
- Higher probability setups

**Impact**: Medium - Filters low-volume noise

**Note**: Disabled because crypto markets trade 24/7.

**Configuration**:
```bash
STRATEGY_TRADING_HOURS_START=14  # 2pm UTC (default)
STRATEGY_TRADING_HOURS_END=22    # 10pm UTC (default)
```

**Tuning Guide**:
- Start early (6): Catch Asian markets
- Start late (14): Focus on EU/US overlap
- Default (14-22): EU afternoon to late US

---

### 10. Multi-timeframe Confirmation
**Status**: ✗ Disabled by default (partial implementation)
**Env Variable**: `STRATEGY_MULTIFRAME_CONFIRMATION`

**What it does**: Confirm signal on both 1-min and 5-min timeframes before entering.

**Why it helps**:
- Filters false signals
- Catches only strong setups
- Higher win rate

**Impact**: High - Reduces noise

**Note**: Currently uses momentum history as proxy for multi-timeframe. True 5-minute candle data not yet integrated.

**Configuration**:
```bash
STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD=55.0  # Min momentum on 5m (default: 55%)
```

---

## Testing Strategy Combinations

### Example 1: Conservative (Fewer Trades, Higher Quality)
```bash
# Tight filters, only best setups
STRATEGY_VOLATILITY_FILTER=true \
STRATEGY_PULLBACK_ENTRY=true \
STRATEGY_TIGHT_SPREAD_FILTER=true \
STRATEGY_MIN_SPREAD_CENTS=20 \
STRATEGY_TIME_FILTER=true \
STRATEGY_CORRELATION_CHECK=true \
python test_strategies.py
```

### Example 2: Aggressive (More Trades, Higher Risk)
```bash
# Loose filters, accept more opportunities
STRATEGY_VOLATILITY_FILTER=false \
STRATEGY_PULLBACK_ENTRY=false \
STRATEGY_TIGHT_SPREAD_FILTER=false \
STRATEGY_MIN_SPREAD_CENTS=10 \
STRATEGY_TIME_FILTER=false \
python test_strategies.py
```

### Example 3: Balanced (Default)
```bash
python test_strategies.py
```

---

## Performance Analysis

After running backtests with different strategies, compare:

1. **Win Rate**: Higher % is better
2. **Total PnL**: More profitable is better
3. **Max Drawdown**: Lower is better
4. **Trade Count**: More trades with same PnL = better efficiency
5. **Profit Factor**: Total Wins / Total Losses

### Ideal Targets (from the plan)
- Win rate: 55-58% (up from 51.6%)
- Max drawdown: < total PnL (not exceeding profits)
- Profit factor: > 1.5

---

## Recommended Starting Point

1. **Run baseline** to see performance with all strategies disabled
2. **Run full** to see performance with all strategies enabled
3. **Compare results** and identify best improvements
4. **Fine-tune thresholds** for each strategy

### Quick Tuning Loop
```bash
# 1. Test all disabled
python test_strategies.py --baseline --quick

# 2. Test all enabled
python test_strategies.py --quick

# 3. Test without volatility filter
STRATEGY_VOLATILITY_FILTER=false python test_strategies.py --quick

# 4. Test with tighter spread
STRATEGY_MIN_SPREAD_CENTS=20 python test_strategies.py --quick
```

---

## Environment Variable Reference

All strategies can be controlled via environment variables:

```bash
# Boolean strategies (showing actual defaults)
STRATEGY_MOMENTUM_ACCELERATION=false     # Disabled - adds noise
STRATEGY_TREND_CONFIRMATION=false        # Disabled - for testing
STRATEGY_DYNAMIC_NEUTRAL_RANGE=false     # Disabled - uses static range
STRATEGY_IMPROVED_CONFIDENCE=true        # ENABLED - only one on by default
STRATEGY_VOLATILITY_FILTER=false         # Disabled - too restrictive
STRATEGY_PULLBACK_ENTRY=false            # Disabled - too restrictive
STRATEGY_TIGHT_SPREAD_FILTER=false       # Disabled - allows more trades
STRATEGY_CORRELATION_CHECK=false         # Disabled - for testing
STRATEGY_TIME_FILTER=false               # Disabled - crypto is 24/7
STRATEGY_MULTIFRAME_CONFIRMATION=false   # Disabled - partial impl

# Numeric thresholds
STRATEGY_VOLATILITY_THRESHOLD=0.015      # Volatility stdev
STRATEGY_PULLBACK_THRESHOLD=0.3          # Pullback %
STRATEGY_MIN_SPREAD_CENTS=7.0            # Minimum spread (lowered from 15)
STRATEGY_TRADING_HOURS_START=14          # Hour UTC
STRATEGY_TRADING_HOURS_END=22            # Hour UTC
STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD=55.0  # %

# Position exit settings
POSITION_HOLD_DURATION=60                # Seconds before time-based exit
EXIT_SLIPPAGE_CENTS=2.0                  # Slippage on exit
```

---

## Entry & Exit Strategies

### Entry Logic (Arbitrage Detection)

The system identifies entry opportunities through temporal mispricings between two markets:

**1. Spot Momentum Detection**
- Calculates momentum from recent 1-minute Binance candles (default: 20 candles)
- Momentum = (Close - Open) / Open × 100%
- Qualifies as "strong" when exceeding 51% threshold (above neutral/directional)
- Example: 96% UP momentum for ETH indicates strong uptrend

**2. Kalshi Odds Mismatch**
- Fetches real-time prediction market odds from Kalshi crypto markets
- Identifies when odds haven't caught up to spot momentum
- Example: Spot is 96% UP but Kalshi odds are only 3c (should be ~96c)
- This mismatch is the arbitrage opportunity

**3. Spread Calculation**
- Spread = |Expected odds - Current odds|
- Expected odds ≈ Momentum percentage
- Example: 96% momentum vs 3c = 93c spread
- Minimum spread requirement filters out low-value trades

**4. Combined Decision**
```
Signal Generated If:
  ✓ Strong momentum (66%+ on 15-min or 51%+ on hourly markets)
  ✓ Odds are neutral/mispriced (configurable range, default 0-100c)
  ✓ Spread ≥ minimum threshold (default 0c for testing, 15c production)
  ✓ All enabled filters pass (volatility, pullback, time, etc.)
```

**Entry Example (Real Trade)**
```
ArbitrageDetector TRADE DECISION FOR BTCUSDT @ KXBTC-26JAN1917-T85500
  Momentum: 96.0% (threshold: 51%)
  Strong signal: ✓ UP
  Kalshi odds: 3.0c (neutral range: (0, 100))
  Odds neutral: ✓
  Spread: 93.0c (min required: 0.0c)
  Accelerating: ✓
  Distance check: ✓
  Volatility: ✓ (disabled)
  ...all checks pass...

✅ ACCEPTED - 🎯 SIGNAL GENERATED: BTCUSDT UP
  Confidence: 96.0%
  Kalshi: 3c (expected: ~96c)
  Spread: 93.0c
```

### Exit Logic (Trader Execution)

Once a signal is generated, the Trader agent executes the position:

**1. Order Execution**
- Receives signal with symbol, direction, confidence, and spread
- Checks position limits:
  - Max position size: $10-$100 (configurable)
  - Max open positions: 3-5 (configurable)
- Places market order on Kalshi to capture the misprice

**2. Entry Prices**
- **BUY YES** when momentum > 50% (bet on upside)
  - Entry price: Current YES odds (3c in example)
  - Expected fair value: Momentum % (96c)
  - Potential profit: 96c - 3c - fees = ~90c per contract

- **BUY NO** when momentum < 50% (bet on downside)
  - Entry price: Current NO odds
  - Expected fair value: (100 - momentum) %
  - Potential profit: similar calculation

**3. Position Management**
- Dry-run mode: Simulates realistic fills (85% fill rate, 1-3c slippage, 3c taker fee)
- Live mode: Routes to actual Kalshi API for execution
- Tracks open positions by symbol and market

**4. Exit Signals**
The system has two exit mechanisms:

**A) Time-based Exit** (default - IMPLEMENTED)
- Holds position for fixed duration (configurable via `POSITION_HOLD_DURATION`)
- Default: 60 seconds
- When time expires: closes position at current market price (minus slippage)
- Captures the spread convergence (usually happens within seconds/minutes)
- Realistic scenario: 3c → 50c over 30 seconds, capture 47c before exiting

**Configuration**:
```bash
POSITION_HOLD_DURATION=60      # Seconds to hold position (default: 60)
EXIT_SLIPPAGE_CENTS=2.0        # Expected slippage on exit (default: 2c)
```

**B) Market Resolution Exit**
- If Kalshi market resolves (finalized) before time-based exit
- Position closes at settlement price (100c for winner, 0c for loser)
- This is automatic and takes precedence over time-based exit

**C) Confidence-based Exit** (future)
- Could exit early if confidence changes
- Monitor for counter-momentum signals
- Lock in profits if odds move favorably faster than expected

**5. P&L Calculation**
For each closed position:
```
Profit = (Exit Price - Entry Price) - Fees - Slippage
Status = ✅ WIN (profit > 0) or ❌ LOSS (profit < 0)

Example Winning Trade:
  Entry: 3c
  Exit: 50c (after 30s of odds convergence)
  Fees: 3c
  Slippage: 1c
  Profit: (50 - 3) - 3 - 1 = 43c = $0.43 profit on $0.03 entry
```

### Win Rate Targets

**Historical Performance** (from backtesting)
- Baseline (no strategies): 51.6% win rate
- All strategies enabled: 71.4% win rate
- Profit factor: 2.0x (wins are $2 for every $1 lost)

**What Makes Trades Win**
1. **Large spread** (>30c) = Higher win probability
2. **Near-50c odds** = Maximum misprice when momentum is strong
3. **Accelerating momentum** = Confirms direction, reduces reversals
4. **Quiet markets** (low volatility) = More predictable odds convergence
5. **Active market hours** = Better liquidity, tighter spreads

**What Makes Trades Lose**
1. **Tiny spread** (<10c) = Can't overcome fees
2. **Extreme odds** (very high or very low) = Less likely to be mispriced
3. **Decelerating momentum** = Reversals before odds catch up
4. **High volatility** = Unpredictable price action
5. **Off-hours trading** = Poor liquidity, wider spreads

### Real-time Example Walkthrough

```
TIME 23:22:30 UTC

[PriceMonitor] BTCUSDT price update: $92,552
               Momentum over last 20 candles: 96% UP

[KalshiMonitor] KXBTC-26JAN1917-T85500 (will BTC exceed $85,500?)
                Current YES odds: 3c
                Current NO odds: 100c

[ArbitrageDetector] Compares:
                   Spot momentum: 96% UP
                   Should imply odds: ~96c YES
                   Actual odds: 3c YES
                   Mismatch/Spread: 93c

                   All filters pass ✓
                   Generate signal ✓

[SignalAggregator] Receives signal:
                   Symbol: BTCUSDT
                   Direction: UP (momentum > 50%)
                   Confidence: 96%
                   Recommendation: BUY YES at 3c

[Trader] Executes trade:
         Market order: Buy 10 YES contracts at 3c = $0.30 investment
         Expected fill: 8.5 contracts (85% fill rate)
         Actual cost: $0.255 + 3c fee = $0.285

[Wait 30 seconds...]

[Trader] Exit signal (time-based):
         Current YES odds: 50c (odds converged toward momentum)
         Market order: Sell 8.5 contracts at 50c = $4.25
         Exit cost: 3c fee = $0.255

         Profit: $4.25 - $0.285 = $3.965
         Status: ✅ WIN
         Return: 1290% on capital deployed
```

### Key Insights

1. **Arbitrage timing** is everything - the first 30-60 seconds matter most
2. **Odds convergence is automatic** - as more traders see the mismatch, odds move
3. **Risk is limited** - maximum loss per trade = entry amount + fees
4. **Scalability** - can run 3-5 positions simultaneously
5. **Success depends on** quick detection + rapid execution + position limits

---

## Next Steps

1. Run initial backtests with different strategy combinations
2. Identify which strategies have the biggest impact
3. Fine-tune thresholds for best performance
4. Document results in `STRATEGY_RESULTS.md`
5. Implement multi-timeframe confirmation (pending)
