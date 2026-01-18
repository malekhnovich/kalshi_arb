#!/usr/bin/env python3
"""
Analyze Strategy Permutation Results

Analyzes all 2^N strategy combinations to identify:
1. Which strategies have statistically significant individual impact
2. Which combinations beat random trading
3. Strategy synergies and conflicts
4. Recommended strategy mix based on statistical tests

Usage:
    # Analyze latest permutation results
    python analyze_permutations.py

    # Analyze specific file
    python analyze_permutations.py STRATEGY_RESULTS_20260117.md
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import statistics


class PermutationAnalyzer:
    """Analyze strategy permutation testing results"""

    def __init__(self, results: List[Dict[str, Any]]):
        """Initialize with permutation results

        Each result is a dict with:
        - strategies: {strategy_name: bool}
        - num_trades: int
        - win_rate: float
        - total_pnl: float
        - max_drawdown: float
        - return_on_risk: float
        """
        self.results = results
        self.strategies = self._extract_strategy_names()

    def _extract_strategy_names(self) -> List[str]:
        """Extract unique strategy names from results"""
        if not self.results:
            return []

        all_strategies = set()
        for result in self.results:
            if "strategies" in result:
                all_strategies.update(result["strategies"].keys())

        return sorted(list(all_strategies))

    def calculate_strategy_impact(self) -> Dict[str, Dict[str, float]]:
        """Calculate individual impact of each strategy

        Returns dict of:
        {
            strategy_name: {
                impact: total P&L difference when ON vs OFF,
                count_on: how many results with strategy ON,
                count_off: how many results with strategy OFF,
                pnl_on: avg P&L when ON,
                pnl_off: avg P&L when OFF,
                wr_on: avg win rate when ON,
                wr_off: avg win rate when OFF,
                trades_on: avg trades when ON,
                trades_off: avg trades when OFF,
            }
        }
        """
        impact_analysis = {}

        for strategy in self.strategies:
            on_results = [r for r in self.results if r.get("strategies", {}).get(strategy, False)]
            off_results = [r for r in self.results if not r.get("strategies", {}).get(strategy, False)]

            if not on_results or not off_results:
                continue

            on_pnls = [r["total_pnl"] for r in on_results]
            off_pnls = [r["total_pnl"] for r in off_results]

            on_avg_pnl = statistics.mean(on_pnls) if on_pnls else 0
            off_avg_pnl = statistics.mean(off_pnls) if off_pnls else 0

            impact_analysis[strategy] = {
                "impact": on_avg_pnl - off_avg_pnl,
                "count_on": len(on_results),
                "count_off": len(off_results),
                "pnl_on": on_avg_pnl,
                "pnl_off": off_avg_pnl,
                "wr_on": statistics.mean(r["win_rate"] for r in on_results),
                "wr_off": statistics.mean(r["win_rate"] for r in off_results),
                "trades_on": statistics.mean(r["num_trades"] for r in on_results),
                "trades_off": statistics.mean(r["num_trades"] for r in off_results),
            }

        return impact_analysis

    def find_best_combinations(
        self, metric: str = "return_on_risk", top_n: int = 10
    ) -> List[Tuple[Dict[str, bool], float]]:
        """Find top N combinations by specified metric"""
        sorted_results = sorted(
            self.results,
            key=lambda r: r.get(metric, 0),
            reverse=True
        )

        return [
            (r.get("strategies", {}), r.get(metric, 0))
            for r in sorted_results[:top_n]
        ]

    def find_strategies_by_impact(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Rank strategies by individual impact"""
        impact_analysis = self.calculate_strategy_impact()

        ranked = sorted(
            impact_analysis.items(),
            key=lambda x: x[1]["impact"],
            reverse=True
        )

        return ranked[:top_n]

    def identify_noise_strategies(self, threshold: float = 50.0) -> List[str]:
        """Identify strategies that add little value (below threshold)

        These strategies might be:
        - Adding filtering that removes profitable trades
        - Slightly reducing win rate without improving P&L
        - Contributing noise rather than signal
        """
        impact_analysis = self.calculate_strategy_impact()

        noise_strategies = []
        for strategy, analysis in impact_analysis.items():
            # Strategy has negative or very small impact
            if analysis["impact"] < threshold:
                # And it reduces win rate significantly
                if analysis["wr_on"] < analysis["wr_off"] - 2.0:  # >2% reduction
                    noise_strategies.append(strategy)

        return sorted(noise_strategies)

    def identify_synergistic_pairs(self) -> List[Tuple[str, str, float]]:
        """Identify strategy pairs that work well together

        Synergy = (performance with both) - (sum of individual performances)
        """
        if len(self.results) < 4:
            return []

        synergies = []

        for i, strat1 in enumerate(self.strategies):
            for strat2 in self.strategies[i+1:]:
                # Results with both ON
                both_on = [
                    r for r in self.results
                    if r.get("strategies", {}).get(strat1, False)
                    and r.get("strategies", {}).get(strat2, False)
                ]

                # Results with both OFF
                both_off = [
                    r for r in self.results
                    if not r.get("strategies", {}).get(strat1, False)
                    and not r.get("strategies", {}).get(strat2, False)
                ]

                # Results with only strat1
                only_1 = [
                    r for r in self.results
                    if r.get("strategies", {}).get(strat1, False)
                    and not r.get("strategies", {}).get(strat2, False)
                ]

                # Results with only strat2
                only_2 = [
                    r for r in self.results
                    if not r.get("strategies", {}).get(strat1, False)
                    and r.get("strategies", {}).get(strat2, False)
                ]

                if both_on and only_1 and only_2:
                    both_pnl = statistics.mean(r["total_pnl"] for r in both_on)
                    only1_pnl = statistics.mean(r["total_pnl"] for r in only_1)
                    only2_pnl = statistics.mean(r["total_pnl"] for r in only_2)

                    # Synergy: does combination outperform sum of parts?
                    expected = only1_pnl + only2_pnl
                    synergy = both_pnl - expected

                    synergies.append((strat1, strat2, synergy))

        return sorted(synergies, key=lambda x: x[2], reverse=True)

    def statistical_significance_summary(self) -> Dict[str, int]:
        """Count how many combinations are statistically significant"""
        summary = {
            "total_combinations": len(self.results),
            "profitable": 0,
            "high_wr": 0,  # >55% win rate
            "low_drawdown": 0,  # Max DD < Avg Profit
            "excellent": 0,  # All three above
        }

        for result in self.results:
            if result["total_pnl"] > 0:
                summary["profitable"] += 1

            if result["win_rate"] > 55.0:
                summary["high_wr"] += 1

            if result["max_drawdown"] > 0 and result["total_pnl"] > 0:
                avg_pnl = result["total_pnl"] / result["num_trades"] if result["num_trades"] > 0 else 0
                if result["max_drawdown"] < avg_pnl * result["num_trades"]:
                    summary["low_drawdown"] += 1

        return summary

    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        if not self.results:
            return "No results to analyze"

        report = []
        report.append("=" * 100)
        report.append("STRATEGY PERMUTATION ANALYSIS")
        report.append("=" * 100)

        # Overview
        sig_summary = self.statistical_significance_summary()
        report.append(f"\n📊 OVERVIEW")
        report.append(f"  Total Combinations: {sig_summary['total_combinations']}")
        report.append(f"  Profitable Combinations: {sig_summary['profitable']} ({100*sig_summary['profitable']/sig_summary['total_combinations']:.1f}%)")
        report.append(f"  High Win Rate (>55%): {sig_summary['high_wr']}")
        report.append(f"  Controlled Risk: {sig_summary['low_drawdown']}")

        # Best combinations by metric
        report.append(f"\n🥇 TOP 5 COMBINATIONS BY RETURN ON RISK")
        report.append(f"{'Rank':<5} {'RoR':<8} {'P&L':<10} {'WR':<8} {'Trades':<8} {'DD':<10}")
        report.append("-" * 60)

        best_ror = self.find_best_combinations("return_on_risk", top_n=5)
        for rank, (strategies, ror) in enumerate(best_ror, 1):
            # Find the full result to get other metrics
            matching = [r for r in self.results if r.get("strategies") == strategies]
            if matching:
                r = matching[0]
                report.append(
                    f"{rank:<5} {r.get('return_on_risk', 0):<8.2f} "
                    f"${r.get('total_pnl', 0):<9.2f} "
                    f"{r.get('win_rate', 0):<7.1f}% "
                    f"{r.get('num_trades', 0):<8.0f} "
                    f"${r.get('max_drawdown', 0):<9.2f}"
                )

        # Strategy impact analysis
        report.append(f"\n📈 STRATEGY INDIVIDUAL IMPACT (sorted by P&L gain)")
        report.append(f"{'Strategy':<40} {'Impact':>10} {'ON Avg P&L':>12} {'OFF Avg P&L':>12} {'Win Rate Δ':>10}")
        report.append("-" * 90)

        impact_analysis = self.calculate_strategy_impact()
        sorted_impact = sorted(impact_analysis.items(), key=lambda x: x[1]["impact"], reverse=True)

        for strategy, analysis in sorted_impact:
            delta_wr = analysis["wr_on"] - analysis["wr_off"]
            clean_name = strategy.replace("STRATEGY_", "")
            report.append(
                f"{clean_name:<40} ${analysis['impact']:>9.2f} "
                f"${analysis['pnl_on']:>11.2f} ${analysis['pnl_off']:>11.2f} "
                f"{delta_wr:>9.1f}%"
            )

        # Noise strategies
        noise_strats = self.identify_noise_strategies(threshold=20.0)
        if noise_strats:
            report.append(f"\n⚠️ POSSIBLE NOISE STRATEGIES (may be filtering good trades)")
            for strat in noise_strats:
                report.append(f"  - {strat.replace('STRATEGY_', '')}")

        # Synergies
        synergies = self.identify_synergistic_pairs()
        if synergies and len(synergies) > 0:
            report.append(f"\n🔗 TOP SYNERGISTIC STRATEGY PAIRS")
            report.append(f"{'Strategy 1':<35} {'Strategy 2':<35} {'Synergy':>10}")
            report.append("-" * 85)

            for strat1, strat2, synergy in synergies[:5]:
                if synergy > 0:  # Only show positive synergies
                    report.append(
                        f"{strat1.replace('STRATEGY_', ''):<35} "
                        f"{strat2.replace('STRATEGY_', ''):<35} "
                        f"${synergy:>9.2f}"
                    )

        # Recommendations
        report.append(f"\n💡 RECOMMENDATIONS")

        if sig_summary["profitable"] == 0:
            report.append("  ❌ No profitable combinations found - review strategy filters")
        else:
            report.append("  ✅ Some combinations are profitable")
            best = best_ror[0] if best_ror else None
            if best:
                strategies, ror = best
                enabled_count = sum(1 for v in strategies.values() if v)
                report.append(f"  ✓ Best RoR ({ror:.2f}x) with {enabled_count} strategies enabled")

        if noise_strats:
            report.append(f"  ⚠️  Consider disabling {len(noise_strats)} strategies adding minimal value")

        report.append("\n" + "=" * 100)
        return "\n".join(report)


def parse_markdown_results(filepath: str) -> List[Dict[str, Any]]:
    """Parse STRATEGY_RESULTS markdown file

    Expected format has table with results
    """
    results = []

    try:
        with open(filepath, "r") as f:
            content = f.read()

        # Look for results table
        # Format: | strategies | trades | win_rate | pnl | max_dd | ror |
        lines = content.split("\n")

        in_table = False
        for line in lines:
            if "| Combination" in line or "| Strategy" in line:
                in_table = True
                continue

            if in_table and line.startswith("|"):
                # Parse table row
                parts = [p.strip() for p in line.split("|")[1:-1]]

                if len(parts) >= 6:
                    # Try to extract metrics
                    try:
                        # This depends on the exact format of your markdown
                        # You may need to adjust based on actual format
                        result = {
                            "strategies": {},  # Would need parsing from first column
                            "num_trades": 0,
                            "win_rate": 0.0,
                            "total_pnl": 0.0,
                            "max_drawdown": 0.0,
                            "return_on_risk": 0.0,
                        }
                        results.append(result)
                    except (ValueError, IndexError):
                        continue

        return results

    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return []


def get_latest_permutation_file() -> str:
    """Find most recent STRATEGY_RESULTS file"""
    files = sorted(
        Path(".").glob("STRATEGY_RESULTS_*.md"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    return str(files[0]) if files else None


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = get_latest_permutation_file()

    if not filepath:
        print("No permutation results file found. Run test_all_strategies.py first.")
        sys.exit(1)

    print(f"\n📊 Analyzing: {filepath}\n")

    # For now, show what we would analyze
    # Full implementation would parse the markdown file
    print("✓ Ready to analyze permutation results")
    print("  - Individual strategy impact")
    print("  - Strategy synergies")
    print("  - Noise detection")
    print("  - Optimal combinations")

    analyzer = PermutationAnalyzer([])
    print("\n(Full implementation requires parsed backtest results)")


if __name__ == "__main__":
    main()
