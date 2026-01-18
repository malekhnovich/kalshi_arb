# Parameter Optimization Results

**Generated**: 2026-01-17 18:07:48
**Test Duration**: 2 days per backtest
**Total Combinations**: 16

## Parameters Tested

- `STRATEGY_VOLATILITY_THRESHOLD`: [0.012, 0.02]
- `STRATEGY_PULLBACK_THRESHOLD`: [0.2, 0.5]
- `STRATEGY_MIN_SPREAD_CENTS`: [10, 15]
- `STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD`: [53, 58]

## Top 10 by Total P&L

| Rank | Parameters | P&L | Win% | Trades | Drawdown | RoR |
|------|-----------|-----|------|--------|----------|-----|
| 1 | 0.012 / 0.2 / 10 / 53 | $54.00 | 100.0% | 1 | $0.00 | 54.00 |
| 2 | 0.012 / 0.2 / 15 / 53 | $54.00 | 100.0% | 1 | $0.00 | 54.00 |
| 3 | 0.02 / 0.2 / 10 / 53 | $54.00 | 100.0% | 1 | $0.00 | 54.00 |
| 4 | 0.02 / 0.2 / 15 / 53 | $54.00 | 100.0% | 1 | $0.00 | 54.00 |
| 5 | 0.012 / 0.2 / 10 / 58 | $0.00 | 0.0% | 0 | $0.00 | 0.00 |
| 6 | 0.012 / 0.2 / 15 / 58 | $0.00 | 0.0% | 0 | $0.00 | 0.00 |
| 7 | 0.012 / 0.5 / 10 / 53 | $0.00 | 0.0% | 0 | $0.00 | 0.00 |
| 8 | 0.012 / 0.5 / 10 / 58 | $0.00 | 0.0% | 0 | $0.00 | 0.00 |
| 9 | 0.012 / 0.5 / 15 / 53 | $0.00 | 0.0% | 0 | $0.00 | 0.00 |
| 10 | 0.012 / 0.5 / 15 / 58 | $0.00 | 0.0% | 0 | $0.00 | 0.00 |

## Top 10 by Return on Risk

| Rank | Parameters | RoR | P&L | Win% | Trades | Drawdown |
|------|-----------|-----|-----|------|--------|----------|
| 1 | 0.012 / 0.2 / 10 / 53 | 54.00 | $54.00 | 100.0% | 1 | $0.00 |
| 2 | 0.012 / 0.2 / 15 / 53 | 54.00 | $54.00 | 100.0% | 1 | $0.00 |
| 3 | 0.02 / 0.2 / 10 / 53 | 54.00 | $54.00 | 100.0% | 1 | $0.00 |
| 4 | 0.02 / 0.2 / 15 / 53 | 54.00 | $54.00 | 100.0% | 1 | $0.00 |
| 5 | 0.012 / 0.2 / 10 / 58 | 0.00 | $0.00 | 0.0% | 0 | $0.00 |
| 6 | 0.012 / 0.2 / 15 / 58 | 0.00 | $0.00 | 0.0% | 0 | $0.00 |
| 7 | 0.012 / 0.5 / 10 / 53 | 0.00 | $0.00 | 0.0% | 0 | $0.00 |
| 8 | 0.012 / 0.5 / 10 / 58 | 0.00 | $0.00 | 0.0% | 0 | $0.00 |
| 9 | 0.012 / 0.5 / 15 / 53 | 0.00 | $0.00 | 0.0% | 0 | $0.00 |
| 10 | 0.012 / 0.5 / 15 / 58 | 0.00 | $0.00 | 0.0% | 0 | $0.00 |

## Parameter Sensitivity Analysis

Average P&L for each parameter value:

### STRATEGY_VOLATILITY_THRESHOLD

| Value | Avg P&L | Avg Win% | Avg Trades | Avg RoR |
|-------|---------|----------|------------|--------|
| 0.012 | $13.50 | 25.0% | 0.2 | 13.50 |
| 0.02 | $13.50 | 25.0% | 0.2 | 13.50 |

### STRATEGY_PULLBACK_THRESHOLD

| Value | Avg P&L | Avg Win% | Avg Trades | Avg RoR |
|-------|---------|----------|------------|--------|
| 0.2 | $27.00 | 50.0% | 0.5 | 27.00 |
| 0.5 | $0.00 | 0.0% | 0.0 | 0.00 |

### STRATEGY_MIN_SPREAD_CENTS

| Value | Avg P&L | Avg Win% | Avg Trades | Avg RoR |
|-------|---------|----------|------------|--------|
| 10 | $13.50 | 25.0% | 0.2 | 13.50 |
| 15 | $13.50 | 25.0% | 0.2 | 13.50 |

### STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD

| Value | Avg P&L | Avg Win% | Avg Trades | Avg RoR |
|-------|---------|----------|------------|--------|
| 53 | $27.00 | 50.0% | 0.5 | 27.00 |
| 58 | $0.00 | 0.0% | 0.0 | 0.00 |

## Recommended Parameters

Based on best Return on Risk:

```python
STRATEGY_VOLATILITY_THRESHOLD = 0.012
STRATEGY_PULLBACK_THRESHOLD = 0.2
STRATEGY_MIN_SPREAD_CENTS = 10
STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD = 53
```

**Expected Performance**: P&L $54.00, Win Rate 100.0%, RoR 54.00
