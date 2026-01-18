# Dry-Run Feedback Loop & Strategy Optimization

**Continuous learning cycle: Run → Analyze → Optimize → Validate → Repeat**

## Overview

The feedback loop allows you to use real-world dry-run data to identify improvements, test them in backtests, and validate them in the next dry-run iteration.

```
┌─────────────────┐
│   RUN DRY-RUN   │ ← Real market conditions, realistic fees/slippage
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   ANALYZE DATA  │ ← What worked? What failed?
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  FORM HYPOTHESIS│ ← Why did trades fail? What can improve?
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  TEST IN BACKTEST│ ← Validate hypothesis with historical data
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   OPTIMIZE CODE  │ ← Update config/strategy if promising
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   RUN DRY-RUN 2  │ ← Compare with baseline (iteration)
└────────┬────────┘
         │
         ↓
     REPEAT...
```

---

## Step 1: Run Dry-Run (Collect Data)

### Start trading in dry-run mode:

```bash
# Clean output, just trade alerts
make dryrun &

# OR with debug output for troubleshooting
make dryrun-debug &
```

**What gets recorded:**
- `logs/dryrun_*.log` - Full execution log with all trades
- `logs/trades_dryrun_*.json` - Structured trade data (entry/exit prices, P&L)
- `logs/trades_dryrun_*.json` - Statistics (win rate, total P&L, slippage)

**Suggested duration:**
- Initial: 24-48 hours to get 10-15 trades
- Ongoing: 7 days for statistical significance
- Quick test: 4-6 hours for rapid feedback

---

## Step 2: Analyze Results

### Quick summary (latest run):

```bash
make check-trades
```

Output:
```
=== CHECKING FOR EXECUTED TRADES ===
Latest log: logs/dryrun_20260117_222306.log

✅ Found 12 trade events

=== WIN/LOSS SUMMARY ===
Wins: 8 | Losses: 4
```

### See winning trades:

```bash
make check-wins
```

Output:
```
=== WINNING TRADES ===
🎉 [Trader] [DRY-RUN] TRADE CLOSED - WIN
  Market:       KXBTC-26JAN1722-B95125
  Entry Price:  45c
  Close Price:  100c
  Contracts:    10
  P&L:          +$55.00
```

### See losing trades:

```bash
make check-losses
```

### Compare across all dry-runs:

```bash
make check-trades-all
```

Output:
```
=== CHECKING ALL DRY-RUN LOGS ===
Found 3 log files

logs/dryrun_20260117_220833.log: Trades=6 | Wins=4 | Losses=2
logs/dryrun_20260117_222306.log: Trades=12 | Wins=8 | Losses=4
logs/dryrun_20260118_001234.log: Trades=15 | Wins=11 | Losses=4
```

---

## Step 3: Form Hypothesis

### Questions to ask:

1. **Win Rate Analysis**
   - Expected from backtest: 71.4%
   - Actual in dry-run: ?
   - If lower: Why? (filters too strict? slippage too high? spreads too tight?)
   - If higher: Why? (real market better than historical? skill-based edge growing?)

2. **Trade Frequency**
   - Expected from backtest: 3-4 trades per day
   - Actual in dry-run: ?
   - If fewer: Filters are too restrictive (MIN_ODDS_SPREAD, momentum threshold, etc.)
   - If more: System found more opportunities than backtest predicted

3. **P&L Analysis**
   - Expected per trade: $19.14 (from backtest)
   - Actual per trade: ?
   - If lower: Slippage/fees eating into profits (realistic simulation working)
   - If negative: Check if spreads are actually achievable

4. **Slippage Observations**
   - Expected: 1-3 cents per trade (from config)
   - Actual: Check `total_slippage` in JSON
   - If higher: Real markets more volatile than expected
   - If lower: Our estimates were conservative

### Common issues and hypotheses:

| Issue | Likely Cause | Test |
|-------|--------------|------|
| Zero trades | Filters too strict | Lower MIN_ODDS_SPREAD, momentum_threshold |
| Low win rate | Bad entries | Enable PULLBACK_ENTRY, lower confidence threshold |
| High slippage | Tight spreads selected | Disable STRATEGY_TIGHT_SPREAD_FILTER |
| Missed signals | 15-min threshold too high | Lower STRATEGY_15MIN_MOMENTUM_THRESHOLD |
| Losses on good setups | Execution issues | Check if partial fills are happening |

---

## Step 4: Test Hypothesis in Backtest

### Run baseline backtest:

```bash
make test-baseline
```

Check output:
```
Win Rate:      66.7%
Total P&L:     $92.00
Avg Trade P&L: $15.33
```

Compare to dry-run results. Are they aligned?

### Test specific hypothesis with environment variables:

**Hypothesis: Spreads too tight, missing opportunities**

```bash
# Test with looser spreads
MIN_ODDS_SPREAD=3.0 uv run python run_backtest_real.py --symbol BTCUSDT --days 2
```

**Hypothesis: Momentum threshold too high**

```bash
# Test with lower threshold (65% instead of 70%)
STRATEGY_15MIN_MOMENTUM_THRESHOLD=65 uv run python run_backtest_real.py --symbol BTCUSDT --days 2
```

**Hypothesis: Specific filter is hurting performance**

```bash
# Disable tight spread filter
STRATEGY_TIGHT_SPREAD_FILTER=false uv run python run_backtest_real.py --symbol BTCUSDT --days 2
```

### Run quick permutation test:

```bash
make test-suite-quick
```

Compare results with previous baseline to see if changes help or hurt.

---

## Step 5: Optimize Code (If Promising)

### If hypothesis is confirmed in backtest:

**Example 1: Spreads were too tight**

Edit `config.py`:
```python
MIN_ODDS_SPREAD = _get_env_float("MIN_ODDS_SPREAD", 3.0)  # Was 5.0
```

**Example 2: 15-min momentum threshold too high**

Edit `strategies.py`:
```python
STRATEGY_15MIN_MOMENTUM_THRESHOLD = _get_env_int(
    "STRATEGY_15MIN_MOMENTUM_THRESHOLD", 60  # Was 65
)
```

**Example 3: Disable noisy filter**

Edit `strategies.py`:
```python
STRATEGY_TIGHT_SPREAD_FILTER = _get_env_bool(
    "STRATEGY_TIGHT_SPREAD_FILTER", False  # Was True
)
```

### Commit changes:

```bash
git add config.py strategies.py
git commit -m "Optimize: Lower MIN_ODDS_SPREAD to 3.0c for more opportunities"
```

---

## Step 6: Validate in Full Backtest

### Run full baseline with new settings:

```bash
make test-baseline
```

### Check if improvement holds across all symbols:

```bash
make multi-quick
```

### Get statistical validation:

```bash
make stats
```

**Success criteria:**
- ✅ Win rate ≥ 65%
- ✅ P&L positive
- ✅ Improvement over previous iteration

---

## Step 7: Run Next Dry-Run (Compare)

### Start new dry-run with optimized settings:

```bash
make dryrun &
```

### Compare with baseline:

```bash
make check-trades-all
```

Output:
```
logs/dryrun_baseline_20260117_222306.log: Trades=12 | Wins=8 | Losses=4  (71.4%)
logs/dryrun_optimized_20260118_001234.log: Trades=18 | Wins=13 | Losses=5 (72.2%)
```

### Questions to answer:

- Did trade frequency improve? (18 vs 12 trades)
- Did win rate improve? (72.2% vs 71.4%)
- Did P&L improve? (check JSON files)
- Were the improvements real or random variation?

---

## Example Workflow: First Iteration

### Session 1: Initial Baseline

```bash
# Start dry-run
make dryrun-debug &

# Wait 24 hours...

# Check results
make check-trades
# Output: Trades=6, Wins=4, Losses=2 (66.7% win rate)

# Compare to backtest expectation
make test-baseline
# Output: Trades=6, Wins=4, Losses=2 (66.7% win rate)
# ✅ Matches! Good sign
```

### Session 2: Observation & Hypothesis

```bash
# Analyze: Only 6 trades in 24 hours (expected 3-4/day)
# Expected: ~24 trades, got 6
# Hypothesis: Filters are too strict, spreading is too wide

# Look at losing trades
make check-losses
# Output: Entry 45c, Close 0c → Lost full entry because spread closed

# New hypothesis: Need lower spreads to capture more opportunities
```

### Session 3: Test Hypothesis

```bash
# Test with lower spread
MIN_ODDS_SPREAD=3.0 make test-baseline

# Output: Trades=14 | Wins=10 | Losses=4 (71.4%)
# ✅ More trades! But better win rate too
```

### Session 4: Optimize

```bash
# Update config
# Edit config.py: MIN_ODDS_SPREAD = 3.0 (was 5.0)

# Validate in backtest
make test-baseline
# Output: Trades=14 | Wins=10 | Losses=4 (71.4%)
# ✅ Confirmed
```

### Session 5: Deploy & Compare

```bash
# Run new dry-run
make dryrun-debug &

# Wait 24 hours...

# Compare
make check-trades-all
# Output:
#   Baseline: 6 trades, 66.7% WR
#   Optimized: 14 trades, 71.4% WR
# ✅ Success! More trades + better win rate
```

---

## Key Metrics to Track

Track these across iterations to spot trends:

| Metric | Backtest | Dry-Run 1 | Dry-Run 2 | Dry-Run 3 | Trend |
|--------|----------|-----------|-----------|-----------|-------|
| Trade Count | 6 | 6 | 14 | 15 | ↑ Improving |
| Win Rate % | 66.7% | 66.7% | 71.4% | 72% | ↑ Improving |
| P&L | $92 | $92 | $134 | $145 | ↑ Improving |
| Avg/Trade | $15.33 | $15.33 | $9.57 | $9.67 | → Stable |
| Slippage | Est 1-2c | Actual 1.5c | Actual 1.8c | Actual 2.0c | → Consistent |

---

## Common Optimization Patterns

### Pattern 1: Too Few Trades

**Symptom:** Expected 20 trades, got 5

**Likely cause:** Filters rejecting good opportunities

**Solution:**
```bash
# Lower spread requirement
MIN_ODDS_SPREAD=3.0

# Lower momentum threshold
STRATEGY_15MIN_MOMENTUM_THRESHOLD=60

# Disable tight spread filter
STRATEGY_TIGHT_SPREAD_FILTER=false
```

### Pattern 2: Good Trade Count, Low Win Rate

**Symptom:** 20 trades but only 50% win rate

**Likely cause:** Entering on bad setups

**Solution:**
```bash
# Enable pullback filter (wait for better entry)
STRATEGY_PULLBACK_ENTRY=true
STRATEGY_PULLBACK_THRESHOLD=0.5

# Require trend confirmation
STRATEGY_TREND_CONFIRMATION=true

# Higher minimum confidence
CONFIDENCE_THRESHOLD=75
```

### Pattern 3: High Slippage

**Symptom:** Slippage 3-5c per trade, eating profits

**Likely cause:** Selecting very tight spreads

**Solution:**
```bash
# Set minimum spread to enforce
MIN_ODDS_SPREAD=7.0

# Only trade when spreads are meaningful
STRATEGY_MIN_SPREAD_CENTS=10.0
STRATEGY_TIGHT_SPREAD_FILTER=true
```

---

## When to Stop Iterating

**Stop when:**
- Win rate consistently ≥ 70% (backtest + dry-run aligned)
- P&L positive and stable across runs
- Trade frequency matches expectations
- Slippage/fees within budget
- Ready for small live trading (Stage 1)

**Don't stop if:**
- Dry-run results differ >10% from backtest
- Win rate fluctuating wildly (< 50% to > 70%)
- P&L trending negative
- Getting rejected trades on good setups

---

## Tools Available

| Command | Purpose |
|---------|---------|
| `make dryrun` | Run trading simulator |
| `make dryrun-debug` | Run with verbose output |
| `make check-trades` | Quick summary |
| `make check-wins` | Show winning trades |
| `make check-losses` | Show losing trades |
| `make check-trades-all` | Compare all runs |
| `make test-baseline` | Validate with backtest |
| `make test-suite-quick` | Test strategy combos |
| `make stats` | Statistical analysis |
| `make multi-quick` | Multi-symbol test |

---

## Next: Ready for Stage 1 Live Trading

Once feedback loop confirms:
- ✅ 70%+ win rate (consistent)
- ✅ Positive P&L (per trade > fees)
- ✅ Dry-run matches backtest expectations
- ✅ All 4 symbols (BTC, ETH, SOL, XRP) trading

Proceed to **LIVE_READY_CHECKLIST.md** for Stage 1 deployment with real capital.
