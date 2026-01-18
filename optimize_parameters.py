#!/usr/bin/env python3
"""
Parameter optimization for trading strategies.

Tests different threshold values to find optimal parameters.

Usage:
    python optimize_parameters.py --quick          # 2-day test, fewer combinations
    python optimize_parameters.py --days 5         # 5-day test
    python optimize_parameters.py --full           # 7-day test, all combinations
"""

import subprocess
import os
import sys
import json
import argparse
import time
from itertools import product
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
import statistics


# Parameters to optimize with their test values
PARAMETER_GRID = {
    # Volatility filter threshold (stdev of returns)
    "STRATEGY_VOLATILITY_THRESHOLD": [0.010, 0.015, 0.020, 0.030],

    # Pullback entry threshold (%)
    "STRATEGY_PULLBACK_THRESHOLD": [0.1, 0.3, 0.5, 1.0],

    # Minimum spread in cents
    "STRATEGY_MIN_SPREAD_CENTS": [8, 12, 15, 20],

    # Multiframe momentum threshold
    "STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD": [52, 55, 58, 60],
}

# Reduced grid for quick testing
PARAMETER_GRID_QUICK = {
    "STRATEGY_VOLATILITY_THRESHOLD": [0.012, 0.020],
    "STRATEGY_PULLBACK_THRESHOLD": [0.2, 0.5],
    "STRATEGY_MIN_SPREAD_CENTS": [10, 15],
    "STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD": [53, 58],
}

# Which strategies to enable during parameter testing
# We disable the most aggressive blockers and enable the ones we're tuning
BASE_STRATEGY_CONFIG = {
    "STRATEGY_MOMENTUM_ACCELERATION": "false",  # Often too restrictive
    "STRATEGY_TREND_CONFIRMATION": "true",
    "STRATEGY_DYNAMIC_NEUTRAL_RANGE": "true",
    "STRATEGY_IMPROVED_CONFIDENCE": "true",
    "STRATEGY_VOLATILITY_FILTER": "true",       # Testing this
    "STRATEGY_PULLBACK_ENTRY": "true",          # Testing this
    "STRATEGY_TIGHT_SPREAD_FILTER": "true",     # Testing this
    "STRATEGY_CORRELATION_CHECK": "false",      # Keep simple
    "STRATEGY_TIME_FILTER": "false",            # Disable to get more trades
    "STRATEGY_MULTIFRAME_CONFIRMATION": "true", # Testing this
}


def get_latest_backtest_file() -> str:
    """Get the most recently created backtest file"""
    files = sorted(
        Path("logs").glob("backtest_real_BTCUSDT_*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    return str(files[0]) if files else None


def load_metrics_from_backtest(filepath: str) -> Dict[str, float]:
    """Load metrics from latest backtest result"""
    try:
        with open(filepath, "r") as f:
            result = json.load(f)

        summary = result.get("summary", {})
        metrics = {
            "win_rate": summary.get("win_rate", 0),
            "total_pnl": summary.get("total_pnl", 0),
            "max_drawdown": summary.get("max_drawdown", 0),
            "trades": summary.get("trades_taken", 0),
            "wins": summary.get("winning_trades", 0),
            "losses": summary.get("losing_trades", 0),
        }

        # Calculate derived metrics
        if metrics["trades"] > 0:
            metrics["avg_pnl_per_trade"] = metrics["total_pnl"] / metrics["trades"]
        else:
            metrics["avg_pnl_per_trade"] = 0

        if metrics["max_drawdown"] > 0:
            metrics["return_on_risk"] = metrics["total_pnl"] / metrics["max_drawdown"]
        else:
            metrics["return_on_risk"] = metrics["total_pnl"] if metrics["total_pnl"] > 0 else 0

        # Sharpe-like ratio (simplified)
        if metrics["trades"] > 0 and metrics["max_drawdown"] > 0:
            metrics["risk_adjusted_score"] = (metrics["win_rate"] / 100) * metrics["return_on_risk"]
        else:
            metrics["risk_adjusted_score"] = 0

        return metrics
    except Exception as e:
        print(f"Error loading metrics from {filepath}: {e}")
        return None


def run_backtest_with_params(
    params: Dict[str, Any], days: int = 2, verbose: bool = False
) -> Dict[str, float]:
    """Run a single backtest with specified parameters"""
    env = os.environ.copy()

    # Set base strategy config
    for strategy, value in BASE_STRATEGY_CONFIG.items():
        env[strategy] = value

    # Set parameter values
    for param, value in params.items():
        env[param] = str(value)

    timeout_seconds = 600 if days <= 2 else 1200

    try:
        process = subprocess.Popen(
            [
                "python",
                "-u",
                "run_backtest_real.py",
                "--symbol",
                "BTCUSDT",
                "--days",
                str(days),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        start_time = time.time()

        while True:
            if process.poll() is not None:
                remaining = process.stdout.read()
                if remaining:
                    for line in remaining.splitlines():
                        output_lines.append(line)
                        if verbose:
                            print(f"    {line}")
                break

            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                process.kill()
                print(f"\n  ⚠ Backtest timed out after {timeout_seconds}s")
                return None

            try:
                line = process.stdout.readline()
                if line:
                    line = line.rstrip()
                    output_lines.append(line)
                    if verbose:
                        print(f"    {line}")
                    elif any(k in line for k in ["Progress:", "% complete"]):
                        print(f"\r    {line[:70]:<70}", end="", flush=True)
            except Exception:
                time.sleep(0.1)

        print("\r" + " " * 75 + "\r", end="")

        if process.returncode != 0:
            print(f"  ⚠ Backtest failed (exit code {process.returncode})")
            return None

        latest = get_latest_backtest_file()
        if latest:
            return load_metrics_from_backtest(latest)
        return None

    except Exception as e:
        print(f"  ⚠ Error running backtest: {e}")
        return None


def params_to_string(params: Dict[str, Any]) -> str:
    """Convert params to compact string"""
    parts = []
    for key, value in params.items():
        short_key = key.replace("STRATEGY_", "").replace("_THRESHOLD", "").replace("_", "")[:6]
        parts.append(f"{short_key}={value}")
    return " | ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Optimize strategy parameters")
    parser.add_argument("--quick", action="store_true", help="Quick test with fewer combinations")
    parser.add_argument("--full", action="store_true", help="Full test (7 days)")
    parser.add_argument("--days", type=int, default=None, help="Days to backtest")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.days:
        days = args.days
    elif args.full:
        days = 7
    else:
        days = 2

    # Choose parameter grid
    param_grid = PARAMETER_GRID_QUICK if args.quick else PARAMETER_GRID

    # Generate all combinations
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    all_combinations = list(product(*param_values))
    total_perms = len(all_combinations)

    print(f"\n{'=' * 100}")
    print(f"PARAMETER OPTIMIZATION")
    print(f"{'=' * 100}")
    print(f"Parameters being optimized:")
    for name, values in param_grid.items():
        print(f"  {name}: {values}")
    print(f"\nTotal combinations: {total_perms}")
    print(f"Days per backtest: {days}")
    print(f"{'=' * 100}\n")

    results: List[Tuple[Dict[str, Any], Dict[str, float]]] = []
    failed = 0

    for i, values in enumerate(all_combinations):
        params = dict(zip(param_names, values))

        print(f"[{i + 1:3d}/{total_perms:3d}] {params_to_string(params)}")

        metrics = run_backtest_with_params(params, days, verbose=args.verbose)

        if metrics:
            results.append((params, metrics))
            print(
                f"  ✓ PnL: ${metrics['total_pnl']:7.2f} | "
                f"WR: {metrics['win_rate']:5.1f}% | "
                f"Trades: {metrics['trades']:3.0f} | "
                f"RoR: {metrics['return_on_risk']:5.2f}"
            )
        else:
            failed += 1
            print(f"  ✗ FAILED")

    print(f"\n{'=' * 100}")
    print(f"RESULTS: {len(results)} successful, {failed} failed")
    print(f"{'=' * 100}\n")

    if not results:
        print("No successful backtests. Exiting.")
        return

    generate_report(results, param_grid, days)


def generate_report(
    results: List[Tuple[Dict[str, Any], Dict[str, float]]],
    param_grid: Dict[str, List],
    days: int,
):
    """Generate optimization report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = f"PARAM_OPTIMIZATION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    # Sort by different metrics
    by_pnl = sorted(results, key=lambda x: x[1]["total_pnl"], reverse=True)
    by_ror = sorted(results, key=lambda x: x[1]["return_on_risk"], reverse=True)
    by_winrate = sorted(results, key=lambda x: x[1]["win_rate"], reverse=True)
    by_score = sorted(results, key=lambda x: x[1]["risk_adjusted_score"], reverse=True)

    with open(output_file, "w") as f:
        f.write("# Parameter Optimization Results\n\n")
        f.write(f"**Generated**: {timestamp}\n")
        f.write(f"**Test Duration**: {days} days per backtest\n")
        f.write(f"**Total Combinations**: {len(results)}\n\n")

        # Parameters tested
        f.write("## Parameters Tested\n\n")
        for param, values in param_grid.items():
            f.write(f"- `{param}`: {values}\n")
        f.write("\n")

        # Best by P&L
        f.write("## Top 10 by Total P&L\n\n")
        f.write("| Rank | Parameters | P&L | Win% | Trades | Drawdown | RoR |\n")
        f.write("|------|-----------|-----|------|--------|----------|-----|\n")
        for rank, (params, metrics) in enumerate(by_pnl[:10], 1):
            param_str = " / ".join(f"{v}" for v in params.values())
            f.write(
                f"| {rank} | {param_str} | "
                f"${metrics['total_pnl']:.2f} | "
                f"{metrics['win_rate']:.1f}% | "
                f"{metrics['trades']:.0f} | "
                f"${metrics['max_drawdown']:.2f} | "
                f"{metrics['return_on_risk']:.2f} |\n"
            )
        f.write("\n")

        # Best by Return on Risk
        f.write("## Top 10 by Return on Risk\n\n")
        f.write("| Rank | Parameters | RoR | P&L | Win% | Trades | Drawdown |\n")
        f.write("|------|-----------|-----|-----|------|--------|----------|\n")
        for rank, (params, metrics) in enumerate(by_ror[:10], 1):
            param_str = " / ".join(f"{v}" for v in params.values())
            f.write(
                f"| {rank} | {param_str} | "
                f"{metrics['return_on_risk']:.2f} | "
                f"${metrics['total_pnl']:.2f} | "
                f"{metrics['win_rate']:.1f}% | "
                f"{metrics['trades']:.0f} | "
                f"${metrics['max_drawdown']:.2f} |\n"
            )
        f.write("\n")

        # Best by Win Rate (with min trades)
        min_trades_results = [(p, m) for p, m in results if m["trades"] >= 10]
        if min_trades_results:
            by_wr_filtered = sorted(min_trades_results, key=lambda x: x[1]["win_rate"], reverse=True)
            f.write("## Top 10 by Win Rate (min 10 trades)\n\n")
            f.write("| Rank | Parameters | Win% | P&L | Trades | RoR |\n")
            f.write("|------|-----------|------|-----|--------|-----|\n")
            for rank, (params, metrics) in enumerate(by_wr_filtered[:10], 1):
                param_str = " / ".join(f"{v}" for v in params.values())
                f.write(
                    f"| {rank} | {param_str} | "
                    f"{metrics['win_rate']:.1f}% | "
                    f"${metrics['total_pnl']:.2f} | "
                    f"{metrics['trades']:.0f} | "
                    f"{metrics['return_on_risk']:.2f} |\n"
                )
            f.write("\n")

        # Parameter sensitivity analysis
        f.write("## Parameter Sensitivity Analysis\n\n")
        f.write("Average P&L for each parameter value:\n\n")

        for param_name, param_values in param_grid.items():
            f.write(f"### {param_name}\n\n")
            f.write("| Value | Avg P&L | Avg Win% | Avg Trades | Avg RoR |\n")
            f.write("|-------|---------|----------|------------|--------|\n")

            for value in param_values:
                matching = [(p, m) for p, m in results if p[param_name] == value]
                if matching:
                    avg_pnl = statistics.mean(m["total_pnl"] for _, m in matching)
                    avg_wr = statistics.mean(m["win_rate"] for _, m in matching)
                    avg_trades = statistics.mean(m["trades"] for _, m in matching)
                    avg_ror = statistics.mean(m["return_on_risk"] for _, m in matching)
                    f.write(f"| {value} | ${avg_pnl:.2f} | {avg_wr:.1f}% | {avg_trades:.1f} | {avg_ror:.2f} |\n")
            f.write("\n")

        # Recommended parameters
        f.write("## Recommended Parameters\n\n")
        if by_ror:
            best = by_ror[0]
            f.write("Based on best Return on Risk:\n\n")
            f.write("```python\n")
            for param, value in best[0].items():
                f.write(f'{param} = {value}\n')
            f.write("```\n\n")
            f.write(f"**Expected Performance**: P&L ${best[1]['total_pnl']:.2f}, "
                    f"Win Rate {best[1]['win_rate']:.1f}%, "
                    f"RoR {best[1]['return_on_risk']:.2f}\n")

    print(f"✅ Report generated: {output_file}")
    print(f"\nBest parameters by Return on Risk:")
    if by_ror:
        best_params, best_metrics = by_ror[0]
        for param, value in best_params.items():
            print(f"  {param} = {value}")
        print(f"\n  P&L: ${best_metrics['total_pnl']:.2f}")
        print(f"  Win Rate: {best_metrics['win_rate']:.1f}%")
        print(f"  Return on Risk: {best_metrics['return_on_risk']:.2f}")


if __name__ == "__main__":
    main()
