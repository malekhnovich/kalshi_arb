# Strategy Configuration Guide

This document explains all the strategies you can toggle on/off to optimize your arbitrage bot.

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
**Status**: ✓ Enabled by default
**Env Variable**: `STRATEGY_MOMENTUM_ACCELERATION`

**What it does**: Only enter trades where momentum is still accelerating (not peaked).

**Why it helps**:
- Avoids entering right at momentum peaks
- Catches momentum shifts early
- Filters out mean-reversion trades

**Impact**: Medium - Reduces false signals

**Configuration**:
- None (boolean only)

---

### 2. Trend Confirmation
**Status**: ✓ Enabled by default
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
**Status**: ✓ Enabled by default
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
**Status**: ✓ Enabled by default
**Env Variable**: `STRATEGY_VOLATILITY_FILTER`

**What it does**: Skip trades when recent price volatility is too high.

**Why it helps**:
- Avoids unpredictable periods
- Reduces false signals during market chaos
- Improves win rate in stable periods

**Impact**: High - Filters noise, improves signal quality

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
**Status**: ✓ Enabled by default
**Env Variable**: `STRATEGY_PULLBACK_ENTRY`

**What it does**: Wait for price to pull back from recent peak before entering. This avoids buying the top of a move.

**Why it helps**:
- Better risk-reward (lower entry)
- Avoids peak entries
- Catches trending consolidations

**Impact**: High - Improves entry prices significantly

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
**Status**: ✓ Enabled by default
**Env Variable**: `STRATEGY_TIGHT_SPREAD_FILTER`

**What it does**: Increases minimum required spread to filter out tiny edges that get eaten by fees.

**Why it helps**:
- Eliminates unprofitable trades
- Better risk-reward
- Reduces false positives

**Impact**: High - Critical for profitability

**Configuration**:
```bash
STRATEGY_MIN_SPREAD_CENTS=15.0  # Minimum spread in cents (default: 15c)
```

**Tuning Guide**:
- Lower value (10): Accept smaller edges
- Higher value (20): Only large edges
- Default (15): Good balance between quality and quantity

---

### 8. Correlation Check
**Status**: ✓ Enabled by default
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
**Status**: ✓ Enabled by default
**Env Variable**: `STRATEGY_TIME_FILTER`

**What it does**: Only trade during active market hours (UTC).

**Why it helps**:
- Avoids low-liquidity periods
- Better spreads and fills
- Higher probability setups

**Impact**: Medium - Filters low-volume noise

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
**Status**: Pending implementation
**Env Variable**: `STRATEGY_MULTIFRAME_CONFIRMATION`

**What it does**: Confirm signal on both 1-min and 5-min timeframes before entering.

**Why it helps**:
- Filters false signals
- Catches only strong setups
- Higher win rate

**Impact**: High - Reduces noise

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
# Boolean strategies (true/false)
STRATEGY_MOMENTUM_ACCELERATION=true
STRATEGY_TREND_CONFIRMATION=true
STRATEGY_DYNAMIC_NEUTRAL_RANGE=true
STRATEGY_IMPROVED_CONFIDENCE=true
STRATEGY_VOLATILITY_FILTER=true
STRATEGY_PULLBACK_ENTRY=true
STRATEGY_TIGHT_SPREAD_FILTER=true
STRATEGY_CORRELATION_CHECK=true
STRATEGY_TIME_FILTER=true
STRATEGY_MULTIFRAME_CONFIRMATION=true

# Numeric thresholds
STRATEGY_VOLATILITY_THRESHOLD=0.015      # Volatility stdev
STRATEGY_PULLBACK_THRESHOLD=0.3          # Pullback %
STRATEGY_MIN_SPREAD_CENTS=15.0           # Minimum spread
STRATEGY_TRADING_HOURS_START=14          # Hour UTC
STRATEGY_TRADING_HOURS_END=22            # Hour UTC
STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD=55.0  # %
```

---

## Next Steps

1. Run initial backtests with different strategy combinations
2. Identify which strategies have the biggest impact
3. Fine-tune thresholds for best performance
4. Document results in `STRATEGY_RESULTS.md`
5. Implement multi-timeframe confirmation (pending)
