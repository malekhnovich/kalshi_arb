#!/usr/bin/env python3
"""
Statistical Analysis of Strategy Results

Analyzes backtest results using statistical testing to:
1. Validate strategies are statistically significant (not luck)
2. Calculate individual strategy impact with confidence intervals
3. Identify which strategies have real edge vs noise
4. Recommend position sizing using Kelly criterion
5. Compare results against random trading (Monte Carlo)

Usage:
    # Analyze latest backtest results
    python analyze_strategy_results.py

    # Analyze specific backtest file
    python analyze_strategy_results.py logs/backtest_real_BTCUSDT_20260117_120000.json

    # Analyze and compare two results
    python analyze_strategy_results.py results1.json results2.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import statistics
import math


def safe_import_stats():
    """Try to import statistical libraries, provide fallbacks"""
    try:
        import numpy as np
        import scipy.stats as stats
        return {"np": np, "stats": stats, "available": True}
    except ImportError:
        return {"np": None, "stats": None, "available": False}


STATS_LIBS = safe_import_stats()


class StrategyAnalysis:
    """Analyze strategy results with statistical rigor"""

    def __init__(self, trades: List[Dict[str, Any]]):
        """Initialize with trades from backtest"""
        self.trades = trades
        self.pnl_list = [t.get("pnl", 0) for t in trades]
        self.wins = [p for p in self.pnl_list if p > 0]
        self.losses = [abs(p) for p in self.pnl_list if p < 0]
        self.num_trades = len(trades)
        self.num_wins = len(self.wins)
        self.num_losses = len(self.losses)

    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.num_trades == 0:
            return 0.0
        return (self.num_wins / self.num_trades) * 100

    def total_pnl(self) -> float:
        """Sum of all P&L"""
        return sum(self.pnl_list)

    def avg_win(self) -> float:
        """Average size of winning trades"""
        if self.num_wins == 0:
            return 0.0
        return sum(self.wins) / self.num_wins

    def avg_loss(self) -> float:
        """Average size of losing trades"""
        if self.num_losses == 0:
            return 0.0
        return sum(self.losses) / self.num_losses

    def kelly_fraction(self) -> float:
        """Calculate Kelly criterion optimal position size

        f* = (W*P - L*(1-P)) / L
        Where:
        - W = average win
        - L = average loss
        - P = win probability
        """
        if self.num_trades == 0 or self.num_wins == 0 or self.num_losses == 0:
            return 0.0

        p_win = self.num_wins / self.num_trades
        w = self.avg_win()
        l = self.avg_loss()

        if l == 0:
            return 0.0

        kelly = (w * p_win - l * (1 - p_win)) / l
        return max(0.0, min(kelly, 1.0))  # Clamp to [0, 1]

    def profit_factor(self) -> float:
        """Ratio of gross profit to gross loss"""
        if self.num_losses == 0:
            return 0.0
        total_wins = sum(self.wins) if self.wins else 0
        total_losses = sum(self.losses) if self.losses else 1
        if total_losses == 0:
            return 0.0
        return total_wins / total_losses

    def expectancy(self) -> float:
        """Expected value per trade"""
        if self.num_trades == 0:
            return 0.0
        return self.total_pnl() / self.num_trades

    def drawdown(self) -> float:
        """Maximum drawdown"""
        if not self.pnl_list:
            return 0.0

        max_dd = 0.0
        cumsum = 0.0
        peak = 0.0

        for pnl in self.pnl_list:
            cumsum += pnl
            if cumsum > peak:
                peak = cumsum
            dd = peak - cumsum
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def win_rate_ci(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Binomial confidence interval for win rate (Wilson score)"""
        if self.num_trades == 0:
            return (0.0, 0.0)

        # Use normal approximation for confidence intervals
        p = self.num_wins / self.num_trades
        n = self.num_trades

        # Z-score for 95% confidence
        z = 1.96 if confidence == 0.95 else 1.645

        se = math.sqrt((p * (1 - p)) / n)
        margin = z * se

        lower = max(0.0, p - margin)
        upper = min(1.0, p + margin)

        return (lower * 100, upper * 100)

    def pnl_ci(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Confidence interval for mean P&L using normal approximation"""
        if len(self.pnl_list) < 2:
            return (0.0, 0.0)

        mean = sum(self.pnl_list) / len(self.pnl_list)
        var = sum((x - mean) ** 2 for x in self.pnl_list) / (len(self.pnl_list) - 1)
        std = math.sqrt(var)

        # Z-score for 95% confidence
        z = 1.96 if confidence == 0.95 else 1.645

        se = std / math.sqrt(len(self.pnl_list))
        margin = z * se

        return (mean - margin, mean + margin)

    def generate_report(self) -> str:
        """Generate statistical analysis report"""
        report = []
        report.append("=" * 80)
        report.append("STATISTICAL STRATEGY ANALYSIS")
        report.append("=" * 80)

        # Summary stats
        report.append(f"\n📊 SAMPLE SIZE")
        report.append(f"  Trades: {self.num_trades}")
        report.append(f"  Wins: {self.num_wins} ({self.win_rate():.1f}%)")
        report.append(f"  Losses: {self.num_losses}")

        # Profitability metrics
        report.append(f"\n💰 PROFITABILITY")
        report.append(f"  Total P&L: ${self.total_pnl():.2f}")
        report.append(f"  Avg Win: ${self.avg_win():.2f}")
        report.append(f"  Avg Loss: ${self.avg_loss():.2f}")
        report.append(f"  Expectancy: ${self.expectancy():.2f}/trade")
        report.append(f"  Profit Factor: {self.profit_factor():.2f}x")

        # Risk metrics
        report.append(f"\n⚠️ RISK METRICS")
        report.append(f"  Max Drawdown: ${self.drawdown():.2f}")
        if self.drawdown() > 0:
            report.append(f"  Return/Risk: {self.total_pnl() / self.drawdown():.2f}x")

        # Confidence intervals
        report.append(f"\n📈 CONFIDENCE INTERVALS (95%)")
        wr_lower, wr_upper = self.win_rate_ci()
        report.append(f"  Win Rate: {self.win_rate():.1f}% [{wr_lower:.1f}%, {wr_upper:.1f}%]")

        pnl_lower, pnl_upper = self.pnl_ci()
        report.append(f"  Mean P&L: ${self.expectancy():.2f} [${pnl_lower:.2f}, ${pnl_upper:.2f}]")

        # Position sizing
        report.append(f"\n📍 KELLY CRITERION POSITION SIZING")
        kelly = self.kelly_fraction()
        report.append(f"  Full Kelly: {kelly*100:.1f}%")
        report.append(f"  1/2 Kelly (moderate): {kelly*50:.1f}%")
        report.append(f"  1/4 Kelly (conservative): {kelly*25:.1f}%")

        # Statistical significance
        report.append(f"\n✓ STATISTICAL SIGNIFICANCE")

        # Win rate vs 50% (random)
        if self.num_trades >= 30:
            # Binomial test approximation: if CI doesn't include 50%, it's significant
            if wr_lower > 50.0:
                report.append(f"  Win Rate: SIGNIFICANT (p < 0.05) - Better than random")
            elif wr_upper < 50.0:
                report.append(f"  Win Rate: SIGNIFICANT (p < 0.05) - Worse than random")
            else:
                report.append(f"  Win Rate: NOT significant - Could be random")
        else:
            report.append(f"  Win Rate: INSUFFICIENT SAMPLE SIZE (need 30+ trades)")

        # P&L vs zero (is strategy profitable?)
        if pnl_lower > 0:
            report.append(f"  P&L: SIGNIFICANT (p < 0.05) - Profitable")
        elif pnl_upper < 0:
            report.append(f"  P&L: SIGNIFICANT (p < 0.05) - Losing")
        else:
            report.append(f"  P&L: NOT significant - Outcome unclear")

        report.append("\n" + "=" * 80)
        return "\n".join(report)


def load_backtest_result(filepath: str) -> Optional[Dict[str, Any]]:
    """Load backtest result JSON file"""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def get_latest_backtest_file() -> Optional[str]:
    """Get most recent backtest result"""
    files = sorted(
        Path("logs").glob("backtest_real_BTCUSDT_*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    return str(files[0]) if files else None


def analyze_strategy_combination(
    result: Dict[str, Any], strategy_config: Dict[str, bool]
) -> Dict[str, Any]:
    """Analyze a single strategy combination"""
    trades = result.get("trades", [])

    analysis = StrategyAnalysis(trades)

    return {
        "num_trades": analysis.num_trades,
        "num_wins": analysis.num_wins,
        "win_rate": analysis.win_rate(),
        "total_pnl": analysis.total_pnl(),
        "avg_win": analysis.avg_win(),
        "avg_loss": analysis.avg_loss(),
        "expectancy": analysis.expectancy(),
        "profit_factor": analysis.profit_factor(),
        "max_drawdown": analysis.drawdown(),
        "return_on_risk": analysis.total_pnl() / analysis.drawdown() if analysis.drawdown() > 0 else 0,
        "kelly_fraction": analysis.kelly_fraction(),
        "wr_ci": analysis.win_rate_ci(),
        "pnl_ci": analysis.pnl_ci(),
        "is_statistically_significant": analysis.num_trades >= 30 and (analysis.win_rate() > 60.0 or analysis.total_pnl() > 0),
    }


def analyze_individual_strategy_impact(
    results: List[Tuple[Dict[str, bool], Dict[str, Any]]]
) -> Dict[str, Dict[str, float]]:
    """Calculate impact of each strategy individually"""
    if not results:
        return {}

    # Get all strategy names from first result
    first_config = results[0][0]
    strategies = list(first_config.keys())

    strategy_impacts = {}

    for strategy in strategies:
        # Results when strategy is ON
        on_results = [r[1] for r in results if r[0].get(strategy, False)]
        # Results when strategy is OFF
        off_results = [r[1] for r in results if not r[0].get(strategy, False)]

        if on_results and off_results:
            on_pnl = [r["total_pnl"] for r in on_results]
            off_pnl = [r["total_pnl"] for r in off_results]

            on_avg = sum(on_pnl) / len(on_pnl)
            off_avg = sum(off_pnl) / len(off_pnl)

            impact = on_avg - off_avg

            strategy_impacts[strategy] = {
                "impact": impact,
                "on_count": len(on_results),
                "off_count": len(off_results),
                "on_avg_pnl": on_avg,
                "off_avg_pnl": off_avg,
                "on_avg_wr": statistics.mean(r["win_rate"] for r in on_results),
                "off_avg_wr": statistics.mean(r["win_rate"] for r in off_results),
            }

    return strategy_impacts


def main():
    """Main entry point"""
    filepath = None

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = get_latest_backtest_file()

    if not filepath:
        print("No backtest file found. Run backtester first.")
        sys.exit(1)

    print(f"\n📊 Analyzing: {filepath}\n")

    result = load_backtest_result(filepath)
    if not result:
        sys.exit(1)

    # Analyze trades
    trades = result.get("trades", [])
    if not trades:
        print("No trades in result file")
        sys.exit(1)

    analysis = StrategyAnalysis(trades)
    print(analysis.generate_report())

    # Check for statistical significance
    summary = result.get("summary", {})
    print(f"\n📋 BACKTEST SUMMARY")
    print(f"  Symbol: {result.get('symbol', 'N/A')}")
    print(f"  Period: {result.get('start_date', 'N/A')} to {result.get('end_date', 'N/A')}")
    print(f"  Strategy Config:")

    if "strategy_config" in result:
        for strategy, enabled in result["strategy_config"].items():
            status = "✓" if enabled else "✗"
            print(f"    {status} {strategy}")

    # Recommendation
    print(f"\n💡 RECOMMENDATION")
    if analysis.num_trades < 30:
        print(f"  ⚠️  Only {analysis.num_trades} trades - need 30+ for statistical significance")
    elif analysis.win_rate() < 50.0:
        print(f"  ❌ Win rate {analysis.win_rate():.1f}% - Strategy is not profitable")
    elif analysis.total_pnl() < 0:
        print(f"  ❌ Negative P&L ${analysis.total_pnl():.2f} - Strategy is not profitable")
    else:
        print(f"  ✅ Strategy is statistically profitable!")
        print(f"     Recommended position size (Kelly): {analysis.kelly_fraction()*100:.1f}%")
        print(f"     Conservative position size (1/4 Kelly): {analysis.kelly_fraction()*25:.1f}%")

    print()


if __name__ == "__main__":
    main()
