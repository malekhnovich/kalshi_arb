#!/usr/bin/env python3
"""
Strategy comparison tool - Analyze and compare backtest results from different strategy configurations.

Usage:
    # Compare all backtest results
    python compare_strategies.py

    # Compare specific backtest files
    python compare_strategies.py logs/backtest_*.json
"""

import json
import glob
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import statistics


def load_backtest_result(filepath: str) -> Dict[str, Any]:
    """Load a single backtest result"""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def extract_metrics(result: Dict[str, Any]) -> Dict[str, float]:
    """Extract key metrics from backtest result"""
    if not result or "summary" not in result:
        return None

    summary = result["summary"]
    return {
        "win_rate": summary.get("win_rate", 0),
        "total_pnl": summary.get("total_pnl", 0),
        "max_drawdown": summary.get("max_drawdown", 0),
        "trades": summary.get("trades_taken", 0),
        "wins": summary.get("winning_trades", 0),
        "losses": summary.get("losing_trades", 0),
    }


def calculate_derived_metrics(metrics: Dict[str, float]) -> Dict[str, float]:
    """Calculate derived metrics"""
    derived = metrics.copy()

    # Profit factor
    if metrics["losses"] > 0:
        avg_win = metrics["total_pnl"] / metrics["wins"] if metrics["wins"] > 0 else 0
        avg_loss = abs(metrics["total_pnl"]) / metrics["losses"]
        if avg_loss > 0:
            derived["profit_factor"] = avg_win / avg_loss
    else:
        derived["profit_factor"] = float("inf") if metrics["total_pnl"] > 0 else 0

    # Risk-adjusted return (PnL / Drawdown)
    if metrics["max_drawdown"] > 0:
        derived["return_on_risk"] = metrics["total_pnl"] / metrics["max_drawdown"]
    else:
        derived["return_on_risk"] = 0

    # Trades per day (assuming ~7 day backtest)
    derived["trades_per_day"] = metrics["trades"] / 7

    return derived


def print_comparison(results: List[tuple[str, Dict[str, float]]]):
    """Print comparison table of strategies"""
    if not results:
        print("No results to compare")
        return

    print("\n" + "=" * 120)
    print("STRATEGY COMPARISON RESULTS")
    print("=" * 120)

    # Header
    print(
        f"{'Backtest':<40} {'Win%':>8} {'PnL':>10} {'Drawdown':>10} {'RoR':>8} {'PF':>6} {'Trades':>8}"
    )
    print("-" * 120)

    # Sort by return on risk
    sorted_results = sorted(
        results, key=lambda x: x[1].get("return_on_risk", 0), reverse=True
    )

    best_ror = sorted_results[0][1].get("return_on_risk", 0) if sorted_results else 0

    for name, metrics in sorted_results:
        ror = metrics.get("return_on_risk", 0)
        ror_marker = " ⭐" if ror == best_ror else ""

        # Truncate name for display
        display_name = name[-39:] if len(name) > 39 else name

        print(
            f"{display_name:<40} "
            f"{metrics['win_rate']:>7.1f}% "
            f"${metrics['total_pnl']:>8.2f} "
            f"${metrics['max_drawdown']:>9.2f} "
            f"{ror:>7.2f} "
            f"{metrics['profit_factor']:>5.2f} "
            f"{metrics['trades']:>7.0f}{ror_marker}"
        )

    print("=" * 120)
    print("\nMetrics explained:")
    print("  Win%: Percentage of winning trades")
    print("  PnL: Total profit/loss")
    print("  Drawdown: Maximum peak-to-trough decline")
    print("  RoR: Return on Risk (PnL / Drawdown) - Higher is better")
    print("  PF: Profit Factor (Avg Win / Avg Loss) - >1.5 is good")
    print("  Trades: Number of trades taken")
    print("\n⭐ = Best Return on Risk (most efficient strategy)")


def main():
    # Find all recent backtest results
    backtest_files = sorted(
        glob.glob("logs/backtest_real_BTCUSDT_*.json"), key=lambda x: x, reverse=True
    )

    if not backtest_files:
        print("No backtest results found in logs/")
        return

    print(f"Found {len(backtest_files)} backtest results")

    results = []
    for filepath in backtest_files[:10]:  # Compare last 10
        result = load_backtest_result(filepath)
        if result:
            metrics = extract_metrics(result)
            if metrics:
                derived = calculate_derived_metrics(metrics)

                # Extract timestamp from filename
                filename = Path(filepath).stem
                results.append((filename, derived))

    print_comparison(results)

    # Summary stats
    if results:
        print("\n" + "=" * 120)
        print("SUMMARY STATISTICS")
        print("=" * 120)

        win_rates = [m[1]["win_rate"] for m in results]
        pnls = [m[1]["total_pnl"] for m in results]
        rors = [m[1]["return_on_risk"] for m in results]

        print(f"\nWin Rate:")
        print(f"  Best: {max(win_rates):.1f}%")
        print(f"  Worst: {min(win_rates):.1f}%")
        print(f"  Average: {statistics.mean(win_rates):.1f}%")

        print(f"\nTotal PnL:")
        print(f"  Best: ${max(pnls):.2f}")
        print(f"  Worst: ${min(pnls):.2f}")
        print(f"  Average: ${statistics.mean(pnls):.2f}")

        print(f"\nReturn on Risk:")
        print(f"  Best: {max(rors):.2f}")
        print(f"  Worst: {min(rors):.2f}")
        print(f"  Average: {statistics.mean(rors):.2f}")

        print("\n" + "=" * 120)


if __name__ == "__main__":
    main()
