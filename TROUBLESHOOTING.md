# Troubleshooting Guide

## Backtest Timeouts

### Problem: "Backtest timed out"

**Symptoms:**
- `test_all_strategies.py` shows "⚠ Backtest timed out"
- No logs appear in `logs/` directory
- Command hangs for 10+ minutes

**Root Causes:**

1. **Kalshi API is slow/unreachable**
   - The backtest tries to fetch historical market data from Kalshi API
   - API calls can be slow or timeout

2. **Large dataset**
   - 7-day backtest = ~10,000 candles to analyze
   - Kalshi API calls can be slow with many markets

3. **Cache corruption**
   - The `logs/cache.db` file might be corrupted
   - Cache queries hang or fail

### Solutions

#### Option 1: Use Cached Data Only (RECOMMENDED)
First populate cache with one full backtest, then use cached data for all permutations:

```bash
# Step 1: Populate cache (run once, takes 5-10 min)
python run_backtest_real.py --symbol BTCUSDT --days 7

# Step 2: Clear bad cache if needed
rm logs/cache.db

# Step 3: Run permutations using cached data
python test_all_strategies.py --quick
```

#### Option 2: Use Shorter Backtest Period
Shorter periods = fewer API calls = faster:

```bash
# 2-day backtest instead of 7-day
python test_all_strategies.py --quick --days 2

# 1-day backtest (very fast)
python test_all_strategies.py --quick --days 1
```

#### Option 3: Test Fewer Strategies
Fewer strategies = fewer permutations = faster iteration:

```bash
# Start with just 5 strategies (32 permutations)
python test_all_strategies.py --quick --limit-strategies 5

# Then 7 strategies (128 permutations)
python test_all_strategies.py --quick --limit-strategies 7

# Finally all 10 strategies (1024 permutations)
python test_all_strategies.py --quick
```

#### Option 4: Clean Cache and Restart
If cache is corrupted:

```bash
# Remove corrupted cache
rm logs/cache.db

# Run one backtest to rebuild cache
python run_backtest_real.py --symbol BTCUSDT --days 2

# Now run permutations
python test_all_strategies.py --quick --limit-strategies 5
```

### Expected Times

With clean cache:
- 2-day backtest: 2-3 minutes
- 7-day backtest: 5-10 minutes

With corrupted cache:
- Can hang indefinitely or timeout

## Missing Logs

### Problem: "No logs anywhere"

**Solutions:**

1. **Check logs directory**
```bash
ls -la logs/
cat logs/backtest_real_BTCUSDT_*.json | jq .summary
```

2. **Run with output visible**
```bash
# See progress in real-time
python run_backtest_real.py --symbol BTCUSDT --days 2

# Capture output to file
python run_backtest_real.py --symbol BTCUSDT --days 2 > backtest.log 2>&1
tail -f backtest.log
```

3. **Check specific backtest**
```bash
# List all backtest files
ls logs/backtest_real_BTCUSDT_*.json | tail -5

# View latest one
cat logs/backtest_real_BTCUSDT_*.json | jq . | less
```

## Cache Issues

### Clearing Cache

```bash
# Remove cache database (will rebuild on next run)
rm logs/cache.db

# Or delete specific cache entries
python -c "
from cache import get_cache
cache = get_cache()
cache.clear_all()  # Clear everything
"
```

### Checking Cache Status

```bash
ls -lh logs/cache.db
sqlite3 logs/cache.db ".tables"
sqlite3 logs/cache.db ".schema"
```

## API Issues

### Kalshi API Timeout

If Kalshi API is slow:

```bash
# Check API status
curl https://api.elections.kalshi.com/trade-api/v2/markets?limit=1

# Check if you have API credentials
echo $KALSHI_API_KEY
echo $KALSHI_PRIVATE_KEY_PATH
```

### Rate Limiting

If hitting rate limits:
- Backtest already has delays between requests
- Try running at off-peak times
- Use cached data instead

## Quick Diagnostics

### Run minimal backtest
```bash
python run_backtest_real.py --symbol BTCUSDT --days 1
```

Expected output:
- Progress messages showing % complete
- Final results showing Win%, P&L, Drawdown
- Files created: `logs/backtest_real_BTCUSDT_*.json` and `.csv`

### Check backtest results
```bash
# View latest results
python -c "
import json
from pathlib import Path
files = sorted(Path('logs').glob('backtest_real_BTCUSDT_*.json'), key=lambda x: x.stat().st_mtime)
if files:
    with open(files[-1]) as f:
        result = json.load(f)
    print(f'Win Rate: {result[\"summary\"][\"win_rate\"]}%')
    print(f'P&L: \${result[\"summary\"][\"total_pnl\"]}')
"
```

## Recommended Workflow

### For Quick Iteration

```bash
# 1. Populate cache once (5-10 min)
python run_backtest_real.py --symbol BTCUSDT --days 7

# 2. Explore with 5 strategies (1-2 min)
python test_all_strategies.py --quick --limit-strategies 5

# 3. Expand to 7 strategies (3-5 min)
python test_all_strategies.py --quick --limit-strategies 7

# 4. Run all permutations (20-30 min for 2-day backtests)
python test_all_strategies.py --quick
```

### For Validation

```bash
# Run top 3 strategies with full 7-day backtest
for config in "1010110111" "1011110111" "1010111111"; do
  STRATEGY_MOMENTUM_ACCELERATION=${config:0:1} \
  STRATEGY_TREND_CONFIRMATION=${config:1:1} \
  # ... set all 10 strategies
  python run_backtest_real.py --symbol BTCUSDT --days 7
done
```

## Getting Help

If you're still stuck:

1. **Check logs with more detail**
```bash
python -c "
import json
from pathlib import Path
files = sorted(Path('logs').glob('backtest_real_BTCUSDT_*.json'), key=lambda x: x.stat().st_mtime)
for f in files[-3:]:
    with open(f) as fp:
        r = json.load(fp)
    print(f'{f.name}: WR={r[\"summary\"][\"win_rate\"]}% PnL=\${r[\"summary\"][\"total_pnl\"]}')
"
```

2. **Run single backtest with full output**
```bash
python run_backtest_real.py --symbol BTCUSDT --days 2 2>&1 | tee backtest_debug.log
```

3. **Check if APIs are reachable**
```bash
curl -I https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSDT
curl -I https://api.elections.kalshi.com/trade-api/v2/markets
```
