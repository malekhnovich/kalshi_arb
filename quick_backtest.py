#!/usr/bin/env python3
"""
Quick backtest using cached data only (no API calls).

This is much faster for strategy permutation testing.
Perfect for iterating quickly on strategy combinations.

Usage:
    python quick_backtest.py --symbol BTCUSDT --days 2
    python quick_backtest.py --symbol BTCUSDT --days 7
"""

import subprocess
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def check_cache_exists() -> bool:
    """Check if cache database exists and has data"""
    cache_db = Path("logs/cache.db")
    if not cache_db.exists():
        logger.error("Cache database not found at logs/cache.db")
        logger.error("Run: python run_backtest_real.py --symbol BTCUSDT --days 7")
        logger.error("This will populate the cache with real data.")
        return False

    size_mb = cache_db.stat().st_size / (1024 * 1024)
    logger.info(f"Cache database found ({size_mb:.1f} MB)")
    return True


def run_quick_backtest(days: int = 2) -> bool:
    """Run backtest using cached data"""
    logger.info(f"Running quick backtest ({days} days)...")

    try:
        # Run the normal backtest script
        result = subprocess.run(
            ["python", "run_backtest_real.py", "--symbol", "BTCUSDT", "--days", str(days)],
            timeout=300,  # 5 min timeout
            capture_output=False,  # Show output in real-time
        )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        logger.error(f"Backtest timed out after 5 minutes")
        logger.info("Possible causes:")
        logger.info("  1. API is slow/unreachable")
        logger.info("  2. Cache is corrupted - delete logs/cache.db and retry")
        logger.info("  3. Network issues")
        return False
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return False


def get_latest_result() -> dict:
    """Get the latest backtest result"""
    files = sorted(
        Path("logs").glob("backtest_real_BTCUSDT_*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )

    if not files:
        return None

    try:
        with open(files[0], "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load results: {e}")
        return None


def print_results(result: dict):
    """Print backtest results"""
    if not result or "summary" not in result:
        logger.error("Invalid results format")
        return

    s = result["summary"]
    print("\n" + "=" * 60)
    print(f"Win Rate:     {s.get('win_rate', 0):.1f}%")
    print(f"P&L:          ${s.get('total_pnl', 0):.2f}")
    print(f"Max Drawdown: ${s.get('max_drawdown', 0):.2f}")
    print(f"Trades:       {s.get('trades_taken', 0)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Quick backtest with cached data")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()

    if not check_cache_exists():
        sys.exit(1)

    success = run_quick_backtest(args.days)

    if success:
        result = get_latest_result()
        if result:
            print_results(result)
            logger.info("✓ Backtest completed successfully")
        else:
            logger.error("Backtest ran but no results found")
            sys.exit(1)
    else:
        logger.error("✗ Backtest failed")
        sys.exit(1)
