#!/usr/bin/env python3
"""
Multi-Symbol Backtesting Framework

Test strategies across multiple cryptocurrency pairs (BTC, ETH, SOL).
Helps validate if strategies are robust across different volatility profiles.

Usage:
    # Quick test all symbols (2 days each)
    python test_multi_symbol.py --quick

    # Full test (7 days each symbol)
    python test_multi_symbol.py --full

    # Test specific symbol
    python test_multi_symbol.py --symbol BTCUSDT --days 5
"""

import subprocess
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Dict
import statistics


SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
SYMBOL_NAMES = {
    "BTCUSDT": "Bitcoin",
    "ETHUSDT": "Ethereum",
    "SOLUSDT": "Solana",
}


def get_latest_backtest_file(symbol: str) -> str:
    """Get most recent backtest file for a symbol"""
    files = sorted(
        Path("logs").glob(f"backtest_real_{symbol}_*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    return str(files[0]) if files else None


def load_metrics_from_backtest(filepath: str) -> Dict[str, float]:
    """Load metrics from backtest result"""
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
            "kalshi_candles": summary.get("kalshi_candles", 0),
        }

        if metrics["max_drawdown"] > 0:
            metrics["return_on_risk"] = metrics["total_pnl"] / metrics["max_drawdown"]
        else:
            metrics["return_on_risk"] = 0

        if metrics["trades"] > 0:
            metrics["avg_pnl_per_trade"] = metrics["total_pnl"] / metrics["trades"]
        else:
            metrics["avg_pnl_per_trade"] = 0

        return metrics
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def run_backtest(symbol: str, days: int = 2, verbose: bool = False) -> Dict[str, float]:
    """Run backtest for a specific symbol"""
    print(f"\n{'='*80}")
    print(f"Testing {SYMBOL_NAMES[symbol]} ({symbol})")
    print(f"{'='*80}")

    cmd = [
        "python",
        "run_backtest_real.py",
        "--symbol",
        symbol,
        "--days",
        str(days),
    ]

    timeout_seconds = 600 if days <= 2 else 1200

    try:
        process = subprocess.Popen(
            cmd,
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
                            print(f"  {line}")
                break

            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                process.kill()
                print(f"⚠ Backtest timed out after {timeout_seconds}s")
                return None

            try:
                line = process.stdout.readline()
                if line:
                    line = line.rstrip()
                    output_lines.append(line)
                    if verbose:
                        print(f"  {line}")
                    elif any(k in line for k in ["Progress:", "% complete"]):
                        print(f"\r  {line[:70]:<70}", end="", flush=True)
            except Exception:
                time.sleep(0.1)

        print("\r" + " " * 75 + "\r", end="")

        if process.returncode != 0:
            print(f"✗ Backtest failed (exit code {process.returncode})")
            return None

        latest = get_latest_backtest_file(symbol)
        if latest:
            return load_metrics_from_backtest(latest)
        return None

    except Exception as e:
        print(f"✗ Error running backtest: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test strategies across multiple symbols")
    parser.add_argument("--symbol", default=None, help="Test only this symbol")
    parser.add_argument("--quick", action="store_true", help="Quick test (2 days)")
    parser.add_argument("--full", action="store_true", help="Full test (7 days)")
    parser.add_argument("--days", type=int, default=None, help="Custom days")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.days:
        days = args.days
    elif args.full:
        days = 7
    else:
        days = 2

    symbols = [args.symbol] if args.symbol else SYMBOLS

    print(f"\n{'='*80}")
    print(f"MULTI-SYMBOL BACKTEST")
    print(f"{'='*80}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Days per symbol: {days}")
    print(f"{'='*80}")

    results: Dict[str, Dict[str, float]] = {}

    for symbol in symbols:
        metrics = run_backtest(symbol, days, verbose=args.verbose)

        if metrics:
            results[symbol] = metrics
            print(
                f"✓ {SYMBOL_NAMES[symbol]:12} | "
                f"Trades: {metrics['trades']:4.0f} | "
                f"P&L: ${metrics['total_pnl']:8.2f} | "
                f"WR: {metrics['win_rate']:5.1f}% | "
                f"RoR: {metrics['return_on_risk']:5.2f}"
            )
        else:
            print(f"✗ {SYMBOL_NAMES[symbol]:12} | Failed")

    if not results:
        print("No successful backtests.")
        return

    generate_report(results, days)


def generate_report(results: Dict[str, Dict[str, float]], days: int):
    """Generate multi-symbol comparison report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = f"MULTI_SYMBOL_RESULTS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(output_file, "w") as f:
        f.write("# Multi-Symbol Backtest Results\n\n")
        f.write(f"**Generated**: {timestamp}\n")
        f.write(f"**Test Duration**: {days} days per symbol\n")
        f.write(f"**Symbols Tested**: {len(results)}\n\n")

        # Summary table
        f.write("## Summary Comparison\n\n")
        f.write("| Symbol | Name | Trades | P&L | Win% | Drawdown | RoR | Trades/Day |\n")
        f.write("|--------|------|--------|-----|------|----------|-----|------------|\n")

        for symbol in SYMBOLS:
            if symbol not in results:
                continue

            metrics = results[symbol]
            trades_per_day = metrics["trades"] / days if days > 0 else 0

            f.write(
                f"| {symbol:8} | {SYMBOL_NAMES[symbol]:15} | "
                f"{metrics['trades']:6.0f} | "
                f"${metrics['total_pnl']:8.2f} | "
                f"{metrics['win_rate']:5.1f}% | "
                f"${metrics['max_drawdown']:8.2f} | "
                f"{metrics['return_on_risk']:5.2f} | "
                f"{trades_per_day:7.2f} |\n"
            )

        f.write("\n")

        # Statistics
        f.write("## Cross-Symbol Statistics\n\n")

        if len(results) > 1:
            pnls = [m["total_pnl"] for m in results.values()]
            win_rates = [m["win_rate"] for m in results.values()]
            rors = [m["return_on_risk"] for m in results.values()]
            trades_list = [m["trades"] for m in results.values()]

            f.write(f"### Total P&L\n")
            f.write(f"- Total: ${sum(pnls):.2f}\n")
            f.write(f"- Average: ${statistics.mean(pnls):.2f}\n")
            f.write(f"- Best: ${max(pnls):.2f}\n")
            f.write(f"- Worst: ${min(pnls):.2f}\n\n")

            f.write(f"### Win Rate\n")
            f.write(f"- Average: {statistics.mean(win_rates):.1f}%\n")
            f.write(f"- Best: {max(win_rates):.1f}%\n")
            f.write(f"- Worst: {min(win_rates):.1f}%\n\n")

            f.write(f"### Return on Risk\n")
            f.write(f"- Average: {statistics.mean(rors):.2f}\n")
            f.write(f"- Best: {max(rors):.2f}\n")
            f.write(f"- Worst: {min(rors):.2f}\n\n")

            f.write(f"### Trade Count\n")
            f.write(f"- Total: {sum(trades_list):.0f}\n")
            f.write(f"- Average: {statistics.mean(trades_list):.1f}\n\n")

        # Detailed metrics per symbol
        f.write("## Detailed Results\n\n")

        for symbol in SYMBOLS:
            if symbol not in results:
                continue

            metrics = results[symbol]
            f.write(f"### {SYMBOL_NAMES[symbol]} ({symbol})\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Trades Taken | {metrics['trades']:.0f} |\n")
            f.write(f"| Winning Trades | {metrics['wins']:.0f} |\n")
            f.write(f"| Losing Trades | {metrics['losses']:.0f} |\n")
            f.write(f"| Win Rate | {metrics['win_rate']:.1f}% |\n")
            f.write(f"| Total P&L | ${metrics['total_pnl']:.2f} |\n")
            f.write(f"| Avg P&L per Trade | ${metrics['avg_pnl_per_trade']:.2f} |\n")
            f.write(f"| Max Drawdown | ${metrics['max_drawdown']:.2f} |\n")
            f.write(f"| Return on Risk | {metrics['return_on_risk']:.2f} |\n")
            f.write(f"| Kalshi Candles Loaded | {metrics['kalshi_candles']:.0f} |\n")
            f.write(f"\n")

        # Analysis
        f.write("## Analysis\n\n")

        if len(results) > 1:
            best_symbol = max(results.items(), key=lambda x: x[1]["return_on_risk"])
            f.write(f"**Best Performer**: {SYMBOL_NAMES[best_symbol[0]]} ({best_symbol[0]})\n")
            f.write(f"- P&L: ${best_symbol[1]['total_pnl']:.2f}\n")
            f.write(f"- Return on Risk: {best_symbol[1]['return_on_risk']:.2f}\n")
            f.write(f"- Win Rate: {best_symbol[1]['win_rate']:.1f}%\n\n")

            # Check consistency
            f.write("**Strategy Consistency**\n\n")
            all_positive = all(m["total_pnl"] > 0 for m in results.values())
            if all_positive:
                f.write("✓ All symbols profitable - strategy is robust\n")
            else:
                losing_symbols = [s for s, m in results.items() if m["total_pnl"] <= 0]
                f.write(f"⚠ Some symbols unprofitable: {', '.join(losing_symbols)}\n")
            f.write("\n")

    print(f"✅ Report generated: {output_file}")


if __name__ == "__main__":
    main()
