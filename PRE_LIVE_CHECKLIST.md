# Pre-Live Trading Checklist

Comprehensive checklist before deploying capital to live trading. Use this to validate system readiness.

## Phase 1: Strategy Validation (Statistical Rigor)

- [ ] **Run baseline backtest**
  ```bash
  make test-baseline  # Get baseline P&L with no filters
  ```
  - Target: 50+ trades, positive P&L
  - Record: Trades count, total P&L, win rate

- [ ] **Analyze statistical significance**
  ```bash
  make stats  # Validate results beat random trading
  ```
  - Requirement: p-value < 0.05 (win rate vs 50%)
  - Requirement: Confidence interval doesn't cross zero for P&L
  - Requirement: 30+ trades minimum sample size

- [ ] **Run full strategy permutation test**
  ```bash
  make test-suite-quick  # Test 32 combinations
  ```
  - Result: Review top 5 performing combinations
  - Check: At least 3 combinations are statistically significant
  - Decision: Select best combination based on RoR (Return on Risk)

- [ ] **Verify permutation analysis**
  ```bash
  make analyze-permutations
  ```
  - Review: Individual strategy impact (which add value vs noise)
  - Remove: Any strategies with negative impact
  - Confirm: No synergistic pairs are missing

- [ ] **Validate against multiple timeframes**
  ```bash
  # Run on different date ranges
  uv run python run_backtest_real.py --symbol BTCUSDT --days 7
  uv run python run_backtest_real.py --symbol BTCUSDT --days 14
  ```
  - Consistency check: Results similar across different periods?
  - If results vary significantly, strategy may be overfitted

- [ ] **Multi-symbol validation**
  ```bash
  make multi-quick  # Test on BTC, ETH, SOL
  ```
  - Requirement: Profitable on at least 2 symbols
  - Edge case check: Strategy doesn't crash on different assets

## Phase 2: Risk Management Setup

- [ ] **Position sizing review**
  ```bash
  make kelly  # Review Kelly criterion recommendations
  ```
  - Set: Starting with 1/4 Kelly (conservative)
  - Example: If Kelly = 10%, start with 2.5% position size
  - Document: Position sizing decision and rationale

- [ ] **Define maximum position size**
  - [ ] Max capital per trade: `$____`
  - [ ] Max total open positions: `___` contracts
  - [ ] Max daily loss limit: `$____`
  - [ ] Max drawdown threshold: `$____`
  - [ ] Record in `config.py`: `MAX_POSITION_SIZE`, `MAX_OPEN_TRADES`, `BACKTEST_MAX_DAILY_LOSS`

- [ ] **Set stop-loss and profit-taking rules**
  - [ ] Stop loss: Max loss per trade (e.g., 5% of position)
  - [ ] Profit target: When to close winners (e.g., 10% gain)
  - [ ] Trailing stop: Optional risk management (e.g., 3% below peak)
  - [ ] Time-based exit: Max hold time (e.g., 24 hours)

- [ ] **Drawdown management**
  - [ ] Maximum acceptable drawdown: `_____%`
  - [ ] Action if exceeded: Halt trading, reduce position size, or investigate
  - [ ] Recovery plan: How to return to normal operations

## Phase 3: System Reliability & Monitoring

- [ ] **API connectivity validation**
  - [ ] Test Kalshi API authentication (RSA key works)
  - [ ] Test Binance.US API connectivity
  - [ ] Verify WebSocket connections work
  - [ ] Test fallback to REST polling if WebSocket fails
  - [ ] Run: `python run_agents.py --debug` for 5 minutes

- [ ] **Error handling verification**
  - [ ] Network timeout handling: System recovers gracefully
  - [ ] API rate limit handling: Proper backoff implemented
  - [ ] Missing data handling: System doesn't crash on gaps
  - [ ] Partial fill handling: Orders reconciled correctly
  - [ ] Order rejection: System handles failed orders

- [ ] **Data quality checks**
  - [ ] Binance OHLCV data completeness: No gaps
  - [ ] Kalshi market data completeness: No gaps
  - [ ] Price feed latency: Acceptable delay (< 2 seconds)
  - [ ] Trade settlement accuracy: P&L matches manual calculation

- [ ] **Monitoring setup**
  - [ ] Logging enabled and working
  - [ ] Alert system configured (email/Slack)
  - [ ] Key metrics tracked: Trades/day, P&L, win rate
  - [ ] Dashboard or log viewer prepared
  - [ ] Person assigned to monitor during trading hours

- [ ] **Dry-run in live market conditions**
  - [ ] Run trader in dry-run mode for 5+ business days
  - [ ] Monitor: Signals generated, trade candidates identified
  - [ ] Compare: Dry-run P&L to backtest expectations
  - [ ] Validate: Orders would have filled at expected prices
  - [ ] Document: Any discrepancies found and remediated

## Phase 4: Safety Gates & Guardrails

- [ ] **Safety gate testing**
  ```bash
  python run_trader.py --check-safety
  ```
  - Requirement 1: `KALSHI_ENABLE_LIVE_TRADING=true` set
  - Requirement 2: `./ENABLE_LIVE_TRADING` file exists
  - Requirement 3: `--live` flag passed on command line
  - Requirement 4: Interactive confirmation prompt works
  - Requirement 5: No `./STOP_TRADING` kill switch file

- [ ] **Kill switch testing**
  - [ ] Verify kill switch file functionality
  - [ ] Test: `touch ./STOP_TRADING` stops trading immediately
  - [ ] Test: Remove file resumes trading
  - [ ] Assign: Who can activate kill switch (should be multiple people)

- [ ] **Maximum position limits**
  - [ ] Test: System rejects trade if max open positions exceeded
  - [ ] Test: System rejects trade if max capital exceeded
  - [ ] Test: Error messages are clear and actionable

- [ ] **Daily loss limits**
  - [ ] Test: System tracks cumulative daily loss
  - [ ] Test: Trading halts if daily loss limit hit
  - [ ] Test: Limit resets daily at correct time (e.g., 8am UTC)

- [ ] **Emergency shutdown plan**
  - [ ] Kill switch person on call: `_____________`
  - [ ] Escalation contact: `_____________`
  - [ ] Manual kill sequence documented
  - [ ] Time to kill: < 5 minutes from any location

## Phase 5: Trade Execution & P&L

- [ ] **Order execution validation**
  - [ ] Test with small position: $10-50
  - [ ] Verify order reaches Kalshi successfully
  - [ ] Verify order fill price matches expected
  - [ ] Verify position reflected in account
  - [ ] Verify settlement occurs correctly

- [ ] **Partial fill handling**
  - [ ] Test: Order fills partially (80% fill, 20% cancel)
  - [ ] Verify: P&L calculated correctly for partial fill
  - [ ] Verify: Remaining position tracked separately

- [ ] **Fee accuracy**
  - [ ] Confirm Kalshi taker fees: 3¢/contract
  - [ ] Confirm commission deducted from P&L
  - [ ] Verify: Net P&L = Gross P&L - Fees

- [ ] **Slippage validation**
  - [ ] Compare entry price prediction vs actual
  - [ ] Acceptable slippage: < 1¢ (configurable)
  - [ ] If slippage > threshold: Log warning and investigate

- [ ] **P&L reconciliation**
  - [ ] Manual calculation of first 5 trades
  - [ ] Compare with system P&L
  - [ ] Any discrepancies must be understood and resolved

## Phase 6: Trading Hours & Market Conditions

- [ ] **Trading hours definition**
  - [ ] Start time (UTC): `____:____`
  - [ ] End time (UTC): `____:____`
  - [ ] Rationale: When markets are most liquid/accurate
  - [ ] Test: System respects trading hours limits

- [ ] **Market condition validation**
  - [ ] Test during high volatility (system should reduce positions)
  - [ ] Test during low liquidity (system should skip trades)
  - [ ] Test at market open (check for gaps/dislocations)
  - [ ] Test at market close (check for late-day volatility)

- [ ] **Cryptocurrency event handling**
  - [ ] Planned maintenance windows identified
  - [ ] Exchange downtime impact: Plan for it
  - [ ] News events that affect correlation: Documented

## Phase 7: Documentation & Knowledge Transfer

- [ ] **System documentation complete**
  - [ ] README.md reviewed and current
  - [ ] CHANGELOG.md lists all active features
  - [ ] STRATEGIES.md explains each strategy
  - [ ] All environment variables documented

- [ ] **Operational runbooks created**
  - [ ] Daily startup procedure
  - [ ] Daily shutdown procedure
  - [ ] Emergency restart procedure
  - [ ] Kill switch activation procedure
  - [ ] P&L reconciliation procedure

- [ ] **Troubleshooting guide prepared**
  - [ ] Common error messages and solutions
  - [ ] Debugging commands for each component
  - [ ] Who to contact for different issues
  - [ ] Escalation procedures documented

- [ ] **Knowledge transfer**
  - [ ] At least 2 people understand full system
  - [ ] Trading strategy clearly explained
  - [ ] Risk limits understood by all operators
  - [ ] Emergency procedures reviewed with team

## Phase 8: Compliance & Governance

- [ ] **Account setup verified**
  - [ ] Trading account confirmed active with Kalshi
  - [ ] API credentials working and tested
  - [ ] Account funding confirmed
  - [ ] Account permissions correct (trade enabled)

- [ ] **Regulatory/Legal review**
  - [ ] Company legal: Reviewed trading system
  - [ ] Compliance: Approved deployment
  - [ ] Account: Authorized to trade
  - [ ] Risk: All risks documented and accepted

- [ ] **Audit trail setup**
  - [ ] All trades logged to JSON with full details
  - [ ] All signals logged with confidence/reasoning
  - [ ] All errors logged with timestamps
  - [ ] Logs encrypted and backed up

- [ ] **Approval signoff**
  - [ ] Strategy developer: `_____________ Date: _____`
  - [ ] Risk manager: `_____________ Date: _____`
  - [ ] Compliance: `_____________ Date: _____`
  - [ ] Authorized trader: `_____________ Date: _____`

## Phase 9: Canary Deployment (First Real Money)

- [ ] **Start with minimal capital**
  - [ ] First deployment: $100-500 maximum
  - [ ] Monitor closely for 1-2 weeks
  - [ ] Zero issues required before increasing

- [ ] **Daily P&L validation**
  - [ ] Compare actual P&L to backtest
  - [ ] Investigate any major deviations
  - [ ] Check for slippage, fees, unexpected losses

- [ ] **Weekly review**
  - [ ] Trade log review: All trades have expected qualities
  - [ ] Win rate: Matches backtest expectations (±5%)
  - [ ] Drawdown: Within expected range
  - [ ] Market conditions: Normal or abnormal?

- [ ] **Two-week evaluation**
  - [ ] Decision: Continue, pause, or halt?
  - [ ] If all green: Can increase to next tier
  - [ ] If any issues: Investigate and fix before expanding

## Phase 10: Scale Up Gradually

- [ ] **Tier 2: $5,000 capital (if Tier 1 successful)**
  - [ ] Monitor for 1 week
  - [ ] Review: P&L tracking backtest? Risk controls working?
  - [ ] Decision: Continue or adjust?

- [ ] **Tier 3: $25,000 capital (if Tier 2 successful)**
  - [ ] Monitor for 1-2 weeks
  - [ ] More realistic volume/slippage data
  - [ ] Final validation before full deployment

- [ ] **Full deployment (if all tiers successful)**
  - [ ] Deploy full capital allocation
  - [ ] Maintain monitoring schedule
  - [ ] Monthly performance reviews

## Pre-Live Validation Template

Copy and fill this out before going live:

```
STRATEGY VALIDATION
- Baseline backtest P&L: $_____ (Target: > $0)
- Number of trades: _____ (Target: > 30)
- Win rate: _____% (Target: > 52%)
- P-value from statistical test: _____ (Target: < 0.05)
- Statistically significant?: YES / NO
- Best strategy combination: ___________
- Reason for this combination: _________

RISK MANAGEMENT
- Max position size: $_____ per trade
- Max open positions: _____
- Daily loss limit: $_____
- Maximum drawdown: _____% of capital
- Position sizing: _____ Kelly (1/4 / 1/2 / Full)

SYSTEM HEALTH
- API connectivity tested: YES / NO
- Error handling verified: YES / NO
- Data quality confirmed: YES / NO
- Dry-run duration: _____ days
- Dry-run results matched backtest: YES / NO

SAFETY GATES
- Kill switch functional: YES / NO
- Position limits enforced: YES / NO
- Daily loss limits enforced: YES / NO
- Monitoring setup: YES / NO

APPROVALS
- Strategy developer sign-off: _________ Date: _____
- Risk manager sign-off: _________ Date: _____
- Go/No-Go decision: GO / NO-GO
- Initial deployment capital: $_____
```

## Red Flags (STOP - Do Not Deploy)

🛑 **Do NOT go live if any of these are true:**

- [ ] Backtest P&L is negative
- [ ] Win rate is below 50% (not beating random)
- [ ] Statistical test shows p-value > 0.05 (not significant)
- [ ] Less than 30 trades in backtest sample
- [ ] Kill switch doesn't work
- [ ] Position limits can't be enforced
- [ ] Risk management limits not implemented
- [ ] No monitoring plan in place
- [ ] Team doesn't understand the system
- [ ] Dry-run results differ significantly from backtest
- [ ] APIs fail during testing
- [ ] Error handling doesn't work
- [ ] Any approval is missing

## Success Criteria (Green Light to Deploy)

✅ **All of these must be TRUE to deploy:**

- [x] Backtest shows positive P&L
- [x] Win rate > 52% (statistical significance)
- [x] P-value < 0.05 (beats random trading)
- [x] 50+ trades in backtest
- [x] Multi-symbol validation passes (2+ symbols profitable)
- [x] Dry-run matches backtest expectations
- [x] All safety gates functional
- [x] Risk limits properly enforced
- [x] Monitoring system ready
- [x] Team trained and prepared
- [x] All required approvals obtained
- [x] Audit trail established
- [x] Canary deployment plan approved

---

**Final Decision:**

Ready to deploy: **YES / NO**

Deployment date: `_____________`

Initial capital: `$_____________`

Approved by: `_____________` Date: `_____`
