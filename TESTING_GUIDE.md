# Strategy Testing Guide

Complete guide to testing and evaluating different strategy combinations.

## Quick Start (5 minutes)

```bash
# Test all 1024 strategy combinations quickly (2 days each)
python test_all_strategies.py --quick

# Results will be saved as STRATEGY_RESULTS_YYYYMMDD_HHMMSS.md
```

## How It Works

The permutation tester:
1. Generates all 2^N combinations of strategies (1024 for 10 strategies)
2. Runs a backtest for each combination
3. Extracts key metrics (win rate, P&L, drawdown, RoR, etc)
4. Generates comprehensive markdown report with rankings

## Usage

### Basic Usage

```bash
# Quick test (2 days per backtest, ~30-60 min total)
python test_all_strategies.py --quick

# Full test (7 days per backtest, ~2-3 hours total)
python test_all_strategies.py --full

# Custom duration
python test_all_strategies.py --days 3
```

### Advanced Options

```bash
# Test only first 5 strategies (32 permutations, much faster for iteration)
python test_all_strategies.py --quick --limit-strategies 5

# Resume from permutation 512 (for interrupted runs)
python test_all_strategies.py --quick --skip-count 512

# Full test with limited strategies (good balance of speed/comprehensiveness)
python test_all_strategies.py --full --limit-strategies 7
```

## Report Format

The script generates a markdown file with:

1. **Summary Statistics**
   - Best/worst/average win rates
   - Best/worst/average P&L
   - Best/worst/average Return on Risk
   - Trade count statistics

2. **Top Performers** (3 rankings)
   - Top 20 by Return on Risk (best efficiency)
   - Top 20 by Total P&L (most profitable)
   - Top 20 by Win Rate (most consistent)

3. **Strategy Impact Analysis**
   - Shows performance with each strategy enabled vs disabled
   - Identifies which strategies add the most value
   - Highlights negative-impact strategies

4. **Complete Results Table**
   - All permutations ranked by Return on Risk
   - Includes win%, P&L, drawdown, profit factor, trade count

## Key Metrics Explained

### Return on Risk (RoR)
**Formula**: `Total P&L / Max Drawdown`

**What it means**: How much profit you make per dollar of risk
- Higher is better
- Accounts for both profitability and risk management
- Best indicator of overall strategy quality

**Example**:
- RoR = 2.5 means $2.50 profit for every $1 of drawdown
- RoR = 0.8 means only $0.80 profit for every $1 of drawdown

### Profit Factor (PF)
**Formula**: `Average Win / Average Loss`

**What it means**: Ratio of avg winning trade to avg losing trade
- >1.5 is generally considered good
- >2.0 is very good
- Focuses on consistency, not total return

### Win Rate (Win%)
**What it means**: Percentage of profitable trades
- Baseline breakeven is around 50% (depends on risk-reward)
- Higher is generally better
- Not the only metric (a 50% win rate with 2:1 reward:risk is better than 60% with 1:2)

### Trades/Day
**What it means**: How many opportunities the strategy generates
- More trades = more opportunities but more fees/slippage
- Fewer trades = higher quality signals but less diversification

## Interpreting Results

### Look For Strategies With:

1. **High Return on Risk** (2.0+)
   - Balances profit and risk well
   - Most important metric

2. **Acceptable Win Rate** (52%+)
   - Better than baseline 51.6%
   - Goal is 55-58%

3. **Reasonable Trade Count**
   - Too few (<5/day) = less opportunity
   - Too many (>30/day) = fee drain
   - Target: 8-15 trades/day

4. **Profit Factor > 1.5**
   - Consistent win structure
   - Healthy reward-to-risk ratio

## Example Report Interpretation

```
Top Strategy by RoR: 1010101010

- Win Rate: 56.2% (✓ above baseline 51.6%)
- Total P&L: $850
- Max Drawdown: $340
- RoR: 2.50 (✓ excellent)
- Profit Factor: 1.85 (✓ good)
- Trades: 62 (~9/day) (✓ good frequency)

Enabled Strategies:
- ✓ Momentum Acceleration
- ✗ Trend Confirmation
- ✓ Dynamic Neutral Range
- ✓ Improved Confidence
- ✓ Volatility Filter
- ✓ Pullback Entry
- ✗ Tight Spread Filter
- ✓ Correlation Check
- ✓ Time Filter
- ✗ Multi-timeframe
```

## Benchmarking Against Original

Original backtest results (from logs/):
- Win Rate: 51.6%
- Total P&L: $757.09
- Max Drawdown: $1,051.32
- RoR: 0.72
- Trades: 62

**Target improvements**:
- Win Rate: 55-58% (+3-6%)
- RoR: >1.5 (+108%+)
- Fewer losing trades due to better filtering

## Testing Strategies

### Phase 1: Quick Exploration (15 min)
```bash
# Test with only first 5 strategies
python test_all_strategies.py --quick --limit-strategies 5
```
- 32 permutations instead of 1024
- Find initial winners quickly
- Understand strategy interactions

### Phase 2: Deeper Testing (30 min)
```bash
# Test with first 7 strategies
python test_all_strategies.py --quick --limit-strategies 7
```
- 128 permutations
- More comprehensive coverage
- Better understanding of impacts

### Phase 3: Full Testing (1-2 hours)
```bash
# Test all 10 strategies
python test_all_strategies.py --quick
```
- Complete 1024 permutations
- Find absolute best combination
- Generate final report

### Phase 4: Validation (overnight)
```bash
# Validate top 10 with 7-day backtests
for config in "1010101010" "1111111111" "1001110111"; do
  STRATEGY_MOMENTUM_ACCELERATION=${config:0:1} \
  STRATEGY_TREND_CONFIRMATION=${config:1:1} \
  # ... etc
  python run_backtest_real.py --symbol BTCUSDT --days 7
done
```

## Performance Expectations

### Time Estimates (depends on your system)

- **2-day backtest**: 1-2 minutes per configuration
- **7-day backtest**: 3-5 minutes per configuration

### Full Run Times
- 5 strategies (32 perms): ~1-2 min
- 7 strategies (128 perms): ~3-5 min
- 10 strategies (1024 perms): ~30-60 min with 2-day backtests

## Analyzing Strategy Impact

The report shows which individual strategies help/hurt most:

```markdown
| Strategy | Enabled | Disabled | Difference |
|----------|---------|----------|-----------|
| MOMENTUM_ACCELERATION | RoR: 1.85 | RoR: 1.62 | 📈 +0.23 |
| VOLATILITY_FILTER | RoR: 2.10 | RoR: 1.45 | 📈 +0.65 |
| PULLBACK_ENTRY | RoR: 1.95 | RoR: 1.70 | 📈 +0.25 |
```

**Interpretation**:
- `VOLATILITY_FILTER` adds the most value (+0.65 RoR improvement)
- `PULLBACK_ENTRY` adds +0.25 RoR
- Some strategies may show negative impact (📉) - these should be disabled

## Comparing Multiple Runs

Run reports multiple times with different configurations:

```bash
# Run 1: Quick test with defaults
python test_all_strategies.py --quick

# Run 2: Test with different spread threshold
STRATEGY_MIN_SPREAD_CENTS=20 python test_all_strategies.py --quick

# Run 3: Test with different volatility threshold
STRATEGY_VOLATILITY_THRESHOLD=0.02 python test_all_strategies.py --quick
```

Then compare the `STRATEGY_RESULTS_*.md` files to see which configuration works best.

## Resuming Interrupted Runs

If a test is interrupted, resume from where it left off:

```bash
# Original test got to permutation 512
python test_all_strategies.py --quick --skip-count 512
```

Results will be appended to the same report.

## Next Steps After Testing

1. **Identify top 3-5 strategies** from the report
2. **Analyze common patterns** - which strategies appear together?
3. **Test with longer backtest** - validate with 7-day tests
4. **Fine-tune thresholds** - adjust volatility, spread, pullback settings
5. **Deploy best strategy** - use winning configuration for live trading

## Quick Reference

```bash
# Quick exploration
python test_all_strategies.py --quick --limit-strategies 5

# Find winners fast
python test_all_strategies.py --quick --limit-strategies 7

# Comprehensive test
python test_all_strategies.py --quick

# Validate winners
python test_all_strategies.py --full

# Custom configuration
STRATEGY_VOLATILITY_THRESHOLD=0.02 STRATEGY_MIN_SPREAD_CENTS=20 \
  python test_all_strategies.py --quick

# View latest results
cat STRATEGY_RESULTS_*.md | head -100
```
