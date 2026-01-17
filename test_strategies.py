#!/usr/bin/env python3
"""
Quick strategy testing script to compare different strategy combinations.

Usage:
    # Test with all strategies enabled (default)
    python test_strategies.py

    # Test with specific strategies disabled
    STRATEGY_VOLATILITY_FILTER=false STRATEGY_PULLBACK_ENTRY=false python test_strategies.py

    # Test baseline (all strategies disabled)
    python test_strategies.py --baseline

    # Quick 2-day test
    python test_strategies.py --quick
"""

import subprocess
import os
import sys
import argparse
from datetime import datetime
import json


def run_backtest(strategy_config: dict, days: int = 7, label: str = ""):
    """Run a backtest with specific strategy configuration"""
    print(f"\n{'='*80}")
    print(f"Testing: {label or 'Custom Strategy Config'}")
    print(f"{'='*80}")

    # Set environment variables
    env = os.environ.copy()
    for key, value in strategy_config.items():
        env[key] = str(value).lower()

    # Run backtest
    cmd = ["python", "run_backtest_real.py", "--symbol", "BTCUSDT", "--days", str(days)]

    print(f"Command: {' '.join(cmd)}")
    print(f"Strategies:")
    for k, v in strategy_config.items():
        if k.startswith("STRATEGY_"):
            strategy_name = k.replace("STRATEGY_", "").replace("_", " ").title()
            status = "✓" if v else "✗"
            print(f"  {status} {strategy_name}")

    result = subprocess.run(cmd, env=env, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Test different strategy combinations")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test with 2 days instead of 7",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Test with all strategies disabled (baseline)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=2,
        help="Number of days to backtest (default: 2 for quick, 7 for full)",
    )
    args = parser.parse_args()

    days = args.days if args.days != 2 or not args.quick else 2

    if args.baseline:
        # Test with all strategies disabled
        baseline_config = {
            "STRATEGY_MOMENTUM_ACCELERATION": False,
            "STRATEGY_TREND_CONFIRMATION": False,
            "STRATEGY_DYNAMIC_NEUTRAL_RANGE": False,
            "STRATEGY_IMPROVED_CONFIDENCE": False,
            "STRATEGY_VOLATILITY_FILTER": False,
            "STRATEGY_PULLBACK_ENTRY": False,
            "STRATEGY_TIGHT_SPREAD_FILTER": False,
            "STRATEGY_CORRELATION_CHECK": False,
            "STRATEGY_TIME_FILTER": False,
            "STRATEGY_MULTIFRAME_CONFIRMATION": False,
        }
        run_backtest(baseline_config, days, "BASELINE (All Strategies Disabled)")

    else:
        # Default: All strategies enabled
        full_config = {
            "STRATEGY_MOMENTUM_ACCELERATION": True,
            "STRATEGY_TREND_CONFIRMATION": True,
            "STRATEGY_DYNAMIC_NEUTRAL_RANGE": True,
            "STRATEGY_IMPROVED_CONFIDENCE": True,
            "STRATEGY_VOLATILITY_FILTER": True,
            "STRATEGY_PULLBACK_ENTRY": True,
            "STRATEGY_TIGHT_SPREAD_FILTER": True,
            "STRATEGY_CORRELATION_CHECK": True,
            "STRATEGY_TIME_FILTER": True,
            "STRATEGY_MULTIFRAME_CONFIRMATION": True,
        }
        run_backtest(full_config, days, "FULL STRATEGY SET (All Enabled)")


if __name__ == "__main__":
    main()
