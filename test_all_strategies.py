#!/usr/bin/env python3
"""
Exhaustive strategy permutation tester.

Tests all 2^N combinations of strategies and generates a markdown report.

Usage:
    # Quick test all permutations (2-day backtest)
    python test_all_strategies.py --quick

    # Full test all permutations (7-day backtest)
    python test_all_strategies.py --full

    # Test subset of strategies (faster)
    python test_all_strategies.py --quick --limit-strategies 5
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


# Strategies to test (in order)
STRATEGIES = [
    "STRATEGY_MOMENTUM_ACCELERATION",
    "STRATEGY_TREND_CONFIRMATION",
    "STRATEGY_DYNAMIC_NEUTRAL_RANGE",
    "STRATEGY_IMPROVED_CONFIDENCE",
    "STRATEGY_VOLATILITY_FILTER",
    "STRATEGY_PULLBACK_ENTRY",
    "STRATEGY_TIGHT_SPREAD_FILTER",
    "STRATEGY_CORRELATION_CHECK",
    "STRATEGY_TIME_FILTER",
    "STRATEGY_MULTIFRAME_CONFIRMATION",
]


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
        if metrics["losses"] > 0 and metrics["wins"] > 0:
            avg_win = metrics["total_pnl"] / metrics["wins"]
            avg_loss = abs(metrics["total_pnl"]) / metrics["losses"]
            metrics["profit_factor"] = avg_win / avg_loss if avg_loss > 0 else 0
        else:
            metrics["profit_factor"] = 0

        if metrics["max_drawdown"] > 0:
            metrics["return_on_risk"] = metrics["total_pnl"] / metrics["max_drawdown"]
        else:
            metrics["return_on_risk"] = 0

        # Expected value per trade
        if metrics["trades"] > 0:
            metrics["expectancy"] = metrics["total_pnl"] / metrics["trades"]
        else:
            metrics["expectancy"] = 0

        return metrics
    except Exception as e:
        print(f"Error loading metrics from {filepath}: {e}")
        return None


def run_backtest_with_config(
    config: List[bool], days: int = 2, verbose: bool = False, strategies_to_test: List[str] = None
) -> Dict[str, float]:
    """Run a single backtest with specified strategy configuration"""
    # Build environment
    env = os.environ.copy()

    # Set the strategies being tested
    strategies_to_test = strategies_to_test or STRATEGIES
    for strategy, enabled in zip(strategies_to_test, config):
        env[strategy] = "true" if enabled else "false"

    # IMPORTANT: Disable strategies NOT being tested to avoid them blocking trades
    for strategy in STRATEGIES:
        if strategy not in strategies_to_test:
            env[strategy] = "false"

    # Run backtest with longer timeout (2 days = ~5 min, 7 days = ~15-20 min)
    timeout_seconds = 600 if days <= 2 else 1200  # 10 min for quick, 20 min for full

    try:
        # Use Popen for real-time output streaming
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
            bufsize=1,  # Line buffered
        )

        # Stream output in real-time
        output_lines = []
        try:
            start_time = time.time()
            while True:
                # Check if process is still running
                if process.poll() is not None:
                    # Process finished, read remaining output
                    remaining = process.stdout.read()
                    if remaining:
                        for line in remaining.splitlines():
                            output_lines.append(line)
                            if verbose:
                                print(f"    {line}")
                    break

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    process.kill()
                    print(f"\n  ⚠ Backtest timed out after {timeout_seconds}s")
                    return None

                # Read available output (non-blocking on Unix)
                try:
                    line = process.stdout.readline()
                    if line:
                        line = line.rstrip()
                        output_lines.append(line)
                        if verbose:
                            print(f"    {line}")
                        elif any(
                            k in line
                            for k in ["Progress:", "% complete", "Fetching", "Loading"]
                        ):
                            # Show progress updates
                            print(f"\r    {line[:75]:<75}", end="", flush=True)
                except Exception:
                    time.sleep(0.1)

        except Exception as e:
            print(f"\n  ⚠ Error reading output: {e}")

        # Clear progress line
        print("\r" + " " * 80 + "\r", end="")

        returncode = process.returncode
        if returncode != 0:
            print(f"  ⚠ Backtest failed (exit code {returncode})")
            if output_lines:
                # Show last few lines
                for line in output_lines[-3:]:
                    print(f"    {line}")
            return None

        # Load latest backtest file
        latest = get_latest_backtest_file()
        if latest:
            return load_metrics_from_backtest(latest)
        else:
            print(f"  ⚠ No backtest results file found")
            return None

    except Exception as e:
        print(f"  ⚠ Error running backtest: {e}")
        import traceback

        traceback.print_exc()

    return None


def config_to_string(config: List[bool]) -> str:
    """Convert config boolean list to compact string"""
    return "".join("1" if c else "0" for c in config)


def config_to_strategy_flags(config: List[bool]) -> Dict[str, bool]:
    """Convert config to strategy flags dict"""
    return {strategy: enabled for strategy, enabled in zip(STRATEGIES, config)}


def print_strategy_flags(config: List[bool]) -> str:
    """Get human-readable strategy flags"""
    flags = []
    for strategy, enabled in zip(STRATEGIES, config):
        short_name = strategy.replace("STRATEGY_", "").replace("_", "")[:3]
        flags.append(short_name if enabled else "---")
    return " ".join(flags)


def main():
    parser = argparse.ArgumentParser(description="Test all strategy permutations")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test (2 days per backtest)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full test (7 days per backtest)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Custom number of days to backtest",
    )
    parser.add_argument(
        "--limit-strategies",
        type=int,
        default=None,
        help="Only test first N strategies (for quick iteration)",
    )
    parser.add_argument(
        "--skip-count",
        type=int,
        default=0,
        help="Skip first N permutations (for resuming)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show full backtest output (for debugging)",
    )
    args = parser.parse_args()

    # Determine days to test
    if args.days:
        days = args.days
    elif args.full:
        days = 7
    else:
        days = 2  # Default quick

    # Limit strategies if requested
    strategies_to_test = STRATEGIES
    if args.limit_strategies:
        strategies_to_test = STRATEGIES[: args.limit_strategies]
        print(f"\n⚠ Limiting to first {args.limit_strategies} strategies")

    # Generate all permutations
    num_strategies = len(strategies_to_test)
    total_perms = 2**num_strategies

    print(f"\n{'=' * 100}", flush=True)
    print(f"STRATEGY PERMUTATION TESTING", flush=True)
    print(f"{'=' * 100}", flush=True)
    print(
        f"Testing {num_strategies} strategies ({total_perms} total permutations)",
        flush=True,
    )
    print(f"Days per backtest: {days}", flush=True)
    print(f"Starting at permutation: {args.skip_count}", flush=True)
    print(f"Verbose mode: {args.verbose}", flush=True)
    print(f"{'=' * 100}\n", flush=True)
    sys.stdout.flush()

    results: List[Tuple[List[bool], Dict[str, float]]] = []
    failed = 0

    for i, config in enumerate(product([False, True], repeat=num_strategies)):
        config_list = list(config)
        perm_num = i + args.skip_count

        if i < args.skip_count:
            continue

        print(
            f"[{perm_num + 1:4d}/{total_perms:4d}] Testing: {config_to_string(config_list)}",
            flush=True,
        )

        metrics = run_backtest_with_config(config_list, days, verbose=args.verbose, strategies_to_test=strategies_to_test)

        if metrics:
            results.append((config_list, metrics))
            print(
                f"  ✓ PnL: ${metrics['total_pnl']:7.2f} | WR: {metrics['win_rate']:5.1f}% | RoR: {metrics['return_on_risk']:5.2f}"
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

    # Generate markdown report
    generate_markdown_report(results, strategies_to_test, days)


def generate_markdown_report(
    results: List[Tuple[List[bool], Dict[str, float]]],
    strategies_to_test: List[str],
    days: int,
):
    """Generate comprehensive markdown report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = f"STRATEGY_RESULTS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(output_file, "w") as f:
        # Header
        f.write("# Strategy Permutation Test Results\n\n")
        f.write(f"**Generated**: {timestamp}\n")
        f.write(f"**Test Duration**: {days} days per backtest\n")
        f.write(f"**Strategies Tested**: {len(strategies_to_test)}\n")
        f.write(f"**Total Permutations**: {len(results)}\n")
        f.write(f"**Symbol**: BTCUSDT\n\n")

        # Strategy legend
        f.write("## Strategy Legend\n\n")
        f.write("| Code | Strategy Name |\n")
        f.write("|------|---------------|\n")
        for i, strategy in enumerate(strategies_to_test):
            short = strategy.replace("STRATEGY_", "")
            f.write(f"| {i:02d} | `{short}` |\n")
        f.write("\n")

        # Summary statistics
        f.write("## Summary Statistics\n\n")
        win_rates = [r[1]["win_rate"] for r in results]
        pnls = [r[1]["total_pnl"] for r in results]
        rors = [r[1]["return_on_risk"] for r in results]
        trades = [r[1]["trades"] for r in results]

        f.write(f"### Win Rate\n")
        f.write(f"- Best: **{max(win_rates):.1f}%**\n")
        f.write(f"- Worst: **{min(win_rates):.1f}%**\n")
        f.write(f"- Average: **{statistics.mean(win_rates):.1f}%**\n")
        f.write(f"- Median: **{statistics.median(win_rates):.1f}%**\n\n")

        f.write(f"### Total P&L\n")
        f.write(f"- Best: **${max(pnls):.2f}**\n")
        f.write(f"- Worst: **${min(pnls):.2f}**\n")
        f.write(f"- Average: **${statistics.mean(pnls):.2f}**\n")
        f.write(f"- Median: **${statistics.median(pnls):.2f}**\n\n")

        f.write(f"### Return on Risk (PnL / Max Drawdown)\n")
        f.write(f"- Best: **{max(rors):.2f}**\n")
        f.write(f"- Worst: **{min(rors):.2f}**\n")
        f.write(f"- Average: **{statistics.mean(rors):.2f}**\n")
        f.write(f"- Median: **{statistics.median(rors):.2f}**\n\n")

        f.write(f"### Trade Count\n")
        f.write(f"- Max: **{max(trades):.0f}**\n")
        f.write(f"- Min: **{min(trades):.0f}**\n")
        f.write(f"- Average: **{statistics.mean(trades):.1f}**\n\n")

        # Top 20 performers
        f.write("## Top 20 Strategies by Return on Risk\n\n")
        sorted_by_ror = sorted(
            results, key=lambda x: x[1]["return_on_risk"], reverse=True
        )

        f.write("| Rank | Strategies | Win% | P&L | Drawdown | RoR | PF | Trades |\n")
        f.write("|------|-----------|------|-----|----------|-----|----|---------|\n")

        for rank, (config, metrics) in enumerate(sorted_by_ror[:20], 1):
            strategy_str = config_to_string(config)
            f.write(
                f"| {rank:2d} | `{strategy_str}` | "
                f"{metrics['win_rate']:5.1f}% | "
                f"${metrics['total_pnl']:7.2f} | "
                f"${metrics['max_drawdown']:7.2f} | "
                f"{metrics['return_on_risk']:5.2f} | "
                f"{metrics['profit_factor']:4.2f} | "
                f"{metrics['trades']:7.0f} |\n"
            )

        f.write("\n")

        # Top 20 by P&L
        f.write("## Top 20 Strategies by Total P&L\n\n")
        sorted_by_pnl = sorted(results, key=lambda x: x[1]["total_pnl"], reverse=True)

        f.write("| Rank | Strategies | Win% | P&L | Drawdown | RoR | PF | Trades |\n")
        f.write("|------|-----------|------|-----|----------|-----|----|---------|\n")

        for rank, (config, metrics) in enumerate(sorted_by_pnl[:20], 1):
            strategy_str = config_to_string(config)
            f.write(
                f"| {rank:2d} | `{strategy_str}` | "
                f"{metrics['win_rate']:5.1f}% | "
                f"${metrics['total_pnl']:7.2f} | "
                f"${metrics['max_drawdown']:7.2f} | "
                f"{metrics['return_on_risk']:5.2f} | "
                f"{metrics['profit_factor']:4.2f} | "
                f"{metrics['trades']:7.0f} |\n"
            )

        f.write("\n")

        # Top 20 by win rate
        f.write("## Top 20 Strategies by Win Rate\n\n")
        sorted_by_wr = sorted(results, key=lambda x: x[1]["win_rate"], reverse=True)

        f.write("| Rank | Strategies | Win% | P&L | Drawdown | RoR | PF | Trades |\n")
        f.write("|------|-----------|------|-----|----------|-----|----|---------|\n")

        for rank, (config, metrics) in enumerate(sorted_by_wr[:20], 1):
            strategy_str = config_to_string(config)
            f.write(
                f"| {rank:2d} | `{strategy_str}` | "
                f"{metrics['win_rate']:5.1f}% | "
                f"${metrics['total_pnl']:7.2f} | "
                f"${metrics['max_drawdown']:7.2f} | "
                f"{metrics['return_on_risk']:5.2f} | "
                f"{metrics['profit_factor']:4.2f} | "
                f"{metrics['trades']:7.0f} |\n"
            )

        f.write("\n")

        # Strategy impact analysis
        f.write("## Strategy Impact Analysis\n\n")
        f.write("Average metrics when each strategy is ENABLED vs DISABLED:\n\n")

        f.write("| Strategy | Enabled | Disabled | Difference |\n")
        f.write("|----------|---------|----------|------------|\n")

        for strategy_idx, strategy_name in enumerate(strategies_to_test):
            enabled_results = [r for r in results if r[0][strategy_idx]]
            disabled_results = [r for r in results if not r[0][strategy_idx]]

            if enabled_results and disabled_results:
                enabled_ror = statistics.mean(
                    r[1]["return_on_risk"] for r in enabled_results
                )
                disabled_ror = statistics.mean(
                    r[1]["return_on_risk"] for r in disabled_results
                )
                diff = enabled_ror - disabled_ror

                enabled_pnl = statistics.mean(
                    r[1]["total_pnl"] for r in enabled_results
                )
                disabled_pnl = statistics.mean(
                    r[1]["total_pnl"] for r in disabled_results
                )

                short_name = strategy_name.replace("STRATEGY_", "")
                marker = "📈" if diff > 0 else "📉"
                f.write(
                    f"| {short_name:<35} | "
                    f"RoR: {enabled_ror:5.2f} | "
                    f"RoR: {disabled_ror:5.2f} | "
                    f"{marker} {diff:+5.2f} |\n"
                )

        f.write("\n")

        # Statistical significance filtering
        f.write("## Statistical Significance Analysis\n\n")
        f.write("Results filtered by statistical significance criteria:\n\n")

        significant_results = [
            (config, metrics) for config, metrics in results
            if metrics["trades"] >= 30  # Minimum sample size
            and metrics["total_pnl"] > 0  # Profitable
            and metrics["win_rate"] > 50  # Above random
        ]

        f.write(f"**Statistically Significant Combinations**: {len(significant_results)} / {len(results)}\n\n")

        if significant_results:
            f.write("| Strategies | Win% | P&L | RoR | Confidence | Trades |\n")
            f.write("|-----------|------|-----|-----|------------|--------|\n")

            sorted_sig = sorted(significant_results, key=lambda x: x[1]["return_on_risk"], reverse=True)
            for config, metrics in sorted_sig[:15]:
                strategy_str = config_to_string(config)
                # Approximate confidence: higher win rate = higher confidence
                confidence = int(min(99, 50 + (metrics["win_rate"] - 50) * 2))
                f.write(
                    f"| `{strategy_str}` | "
                    f"{metrics['win_rate']:5.1f}% | "
                    f"${metrics['total_pnl']:7.2f} | "
                    f"{metrics['return_on_risk']:5.2f} | "
                    f"{confidence}% | "
                    f"{metrics['trades']:7.0f} |\n"
                )

        f.write("\n")

        # Kelly criterion recommendations
        f.write("## Position Sizing Recommendations (Kelly Criterion)\n\n")
        f.write("Based on top 5 strategies by Return on Risk:\n\n")

        f.write("| Strategy | Kelly % | 1/2 Kelly | 1/4 Kelly | Expected P&L |\n")
        f.write("|----------|---------|-----------|-----------|---------------|\n")

        top_5_ror = sorted_by_ror[:5]
        for rank, (config, metrics) in enumerate(top_5_ror, 1):
            if metrics["trades"] > 0 and metrics["win_rate"] > 0:
                # Calculate Kelly
                p_win = metrics["win_rate"] / 100.0
                if metrics["losses"] > 0 and metrics["wins"] > 0:
                    avg_win = metrics["total_pnl"] / metrics["wins"]
                    avg_loss = abs(metrics["total_pnl"]) / metrics["losses"] if metrics["total_pnl"] < 0 else abs(metrics["total_pnl"]) / max(1, metrics["losses"])
                    if avg_loss > 0:
                        kelly = (avg_win * p_win - avg_loss * (1 - p_win)) / avg_loss
                        kelly = max(0, min(kelly, 1.0))  # Clamp to [0, 1]
                    else:
                        kelly = 0.25  # Default if can't calculate
                else:
                    kelly = 0.25  # Default if insufficient data

                strategy_str = config_to_string(config)
                f.write(
                    f"| `{strategy_str}` | "
                    f"{kelly*100:.1f}% | "
                    f"{kelly*50:.1f}% | "
                    f"{kelly*25:.1f}% | "
                    f"${metrics['expectancy']:.2f}/trade |\n"
                )

        f.write("\n")

        # All results (sorted by RoR)
        f.write("## All Results (Sorted by Return on Risk)\n\n")
        f.write(
            "| Strategies | Win% | P&L | Drawdown | RoR | PF | Trades | Trades/Day |\n"
        )
        f.write(
            "|-----------|------|-----|----------|-----|----|---------|-----------|\n"
        )

        for config, metrics in sorted_by_ror:
            strategy_str = config_to_string(config)
            trades_per_day = metrics["trades"] / days
            f.write(
                f"| `{strategy_str}` | "
                f"{metrics['win_rate']:5.1f}% | "
                f"${metrics['total_pnl']:7.2f} | "
                f"${metrics['max_drawdown']:7.2f} | "
                f"{metrics['return_on_risk']:5.2f} | "
                f"{metrics['profit_factor']:4.2f} | "
                f"{metrics['trades']:7.0f} | "
                f"{trades_per_day:7.2f} |\n"
            )

    print(f"✅ Report generated: {output_file}")
    print(f"\nTo view results:")
    print(f"  cat {output_file}")
    print(f"\nTo view in markdown viewer:")
    print(f"  open {output_file}  # macOS")
    print(f"  xdg-open {output_file}  # Linux")


if __name__ == "__main__":
    main()
