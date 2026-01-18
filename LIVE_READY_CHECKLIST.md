e# Live Trading Readiness - Quick Reference

**TL;DR Checklist - Use this to get live-ready in order**

## Step 1: Validate Strategy (15-30 min)

```bash
# 1. Get baseline P&L
make test-baseline

# 2. Verify it's statistically significant
make stats

✅ If BOTH pass (positive P&L + p-value < 0.05), proceed to Step 2
❌ If either fails, STOP - strategy needs improvement
```

## Step 2: Find Optimal Strategy (30-60 min)

```bash
# 3. Test all strategy combinations
make test-suite-quick

# 4. Analyze synergies and impact
make analyze-permutations

✅ Document best performing combination
❌ If no winning combinations, review strategy filters
```

## Step 3: Risk Management Setup (15 min)

```
Set in config.py:
- MAX_POSITION_SIZE = $ _____ per trade
- MAX_OPEN_TRADES = _____ contracts
- MAX_DAILY_LOSS = $ _____
- MAX_DRAWDOWN = _____% of capital

Position Sizing:
- Kelly % from stats = _____%
- Start conservative: Use 1/4 Kelly = _____%
- Dollar amount per trade = $ _____
```

## Step 4: System Validation (30-45 min)

```bash
# 5. Check API connectivity
make diagnose

# 6. Run live agent system (5 minutes)
python run_agents.py --debug
# Should show: Price updates, Kalshi odds, Arbitrage signals
# Ctrl+C to stop after 5 minutes

# 7. Test dry-run mode (simulated trading)
python run_trader.py
# Should see: Simulated trades with realistic fees/slippage
# Ctrl+C to stop
```

## Step 5: Dry-Run Testing (5-10 business days)

```bash
# 8. Run in dry-run for a week+ in actual market conditions
python run_trader.py | tee logs/dryrun_$(date +%Y%m%d).log

Daily checks:
□ Trades executing in expected frequency
□ P&L matching backtest expectations (±10%)
□ Win rate tracking with backtest (±5%)
□ No system errors or crashes
□ No data gaps
```

## Step 6: Final Verification (15 min)

```bash
# 9. Safety gate check
python run_trader.py --check-safety

✅ Required: All 5 safety gates must pass:
   1. KALSHI_ENABLE_LIVE_TRADING=true
   2. ./ENABLE_LIVE_TRADING file exists
   3. --live flag can be passed
   4. Confirmation prompt works
   5. No ./STOP_TRADING file

# 10. Set kill switch
touch ./ENABLE_LIVE_TRADING  # Enable live trading
# Keep ./STOP_TRADING ready to use in emergency
```

## Step 7: Go Live (Start Small)

```bash
# Deploy with minimal capital (~$100-500)
export KALSHI_ENABLE_LIVE_TRADING=true
python run_trader.py --live --max-position 100

Daily monitoring:
□ All trades log to JSON file
□ P&L reconciles with manual check
□ No slippage surprises
□ System stability

Duration: 1-2 weeks minimum

Decision:
- All green? → Scale to Tier 2 ($5,000)
- Any issues? → Investigate and fix before scaling
```

## Absolute Requirements (Do NOT Skip)

❌ **STOP if any of these fail:**

- No positive backtest P&L
- No statistical significance (p > 0.05)
- Less than 30 trades in backtest
- Kill switch doesn't work
- Position limits can't be enforced
- Team doesn't understand system
- Dry-run differs from backtest by >20%

✅ **All of these MUST pass:**

- [x] Positive backtest P&L
- [x] Statistical significance confirmed (p < 0.05)
- [x] 50+ trades in sample
- [x] Multi-symbol tested (2+ symbols profitable)
- [x] All safety gates working
- [x] Risk controls enforced
- [x] Dry-run matches expectations
- [x] Monitoring system ready
- [x] Team trained

## Timeline Example

```
Monday:    Step 1-2 (Validate strategy) - 1 hour
Tuesday:   Step 3-4 (Setup & verify) - 1 hour
Wed-Fri:   Step 5 (Dry-run starts)
Next Mon:  Step 5 complete, evaluate results
Next Tue:  Step 6-7 (Deploy with $100) if all pass
Week 2:    Monitor Tier 1, scale if successful
Week 3:    Tier 2 ($5,000) if Tier 1 successful
Week 4+:   Scale to full capital
```

## Commands Quick Reference

```bash
make help                   # See all commands
make diagnose              # Check filter status
make test-baseline         # Quick baseline backtest
make stats                 # Statistical validation
make test-suite-quick      # Strategy permutation test
make analyze-permutations  # Find best combination
make kelly                 # Position sizing recommendations

python run_agents.py       # Test live data feeds
python run_trader.py       # Dry-run simulated trading
python run_trader.py --live  # LIVE TRADING (careful!)
```

## Checklist Progress

| Step | Task | Status | Time |
|------|------|--------|------|
| 1 | Validate Strategy | ⬜ | 15-30 min |
| 2 | Find Optimal Mix | ⬜ | 30-60 min |
| 3 | Risk Setup | ⬜ | 15 min |
| 4 | System Validation | ⬜ | 30-45 min |
| 5 | Dry-Run | ⬜ | 5-10 days |
| 6 | Final Verification | ⬜ | 15 min |
| 7 | Go Live (Minimal) | ⬜ | 1-2 weeks |
| 8 | Scale to Tier 2 | ⬜ | 1-2 weeks |
| 9 | Full Deployment | ⬜ | When ready |

---

**REMEMBER:** This is real money. The checklist exists to keep it safe. Don't skip steps.
