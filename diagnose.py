#!/usr/bin/env python3
"""
Diagnostic tool - Check backtest status, logs, cache, and recent results.

Usage:
    python diagnose.py
    python diagnose.py --clean-legacy
"""

import argparse
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from cache import get_cache


def check_logs():
    """Check logs directory"""
    print("\n" + "=" * 60)
    print("LOGS DIRECTORY")
    print("=" * 60)

    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("❌ logs/ directory does not exist")
        return False

    print(f"✓ logs/ exists")

    # Count backtest files
    backtest_files = list(logs_dir.glob("backtest_real_BTCUSDT_*.json"))
    print(f"\nBacktest Results: {len(backtest_files)} files")

    if backtest_files:
        # Show 5 most recent
        recent = sorted(backtest_files, key=lambda x: x.stat().st_mtime, reverse=True)[
            :5
        ]
        for f in recent:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            try:
                with open(f) as fp:
                    data = json.load(fp)
                s = data.get("summary", {})
                print(f"  {f.name}")
                print(
                    f"    Win: {s.get('win_rate', 0):.1f}% | PnL: ${s.get('total_pnl', 0):.2f} | DD: ${s.get('max_drawdown', 0):.2f}"
                )
            except Exception as e:
                print(f"  {f.name} - ERROR: {e}")
    else:
        print("  ❌ No backtest files found")

    return True


def check_cache():
    """Check cache database"""
    print("\n" + "=" * 60)
    print("CACHE DATABASE")
    print("=" * 60)

    cache_file = Path("logs/cache.db")
    if not cache_file.exists():
        print("❌ Cache not found (logs/cache.db)")
        print("   Run: python run_backtest_real.py --symbol BTCUSDT --days 7")
        return False

    size_mb = cache_file.stat().st_size / (1024 * 1024)
    print(f"✓ Cache exists ({size_mb:.1f} MB)")

    # Try to check cache health
    try:
        conn = sqlite3.connect(str(cache_file))
        cursor = conn.cursor()

        # Get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\nTables: {len(tables)}")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  {table[0]}: {count} rows")

            if table[0] == "kalshi_candles" and count == 0:
                print("    ⚠️  Table exists but is empty (run backtest to populate)")

        conn.close()
        print("\n✓ Cache is readable")
        return True
    except Exception as e:
        print(f"\n❌ Cache is corrupted: {e}")
        print("   Run: rm logs/cache.db")
        return False


def check_environment():
    """Check environment variables"""
    print("\n" + "=" * 60)
    print("ENVIRONMENT")
    print("=" * 60)

    import os

    has_kalshi_key = bool(os.environ.get("KALSHI_API_KEY"))
    has_kalshi_private = bool(os.environ.get("KALSHI_PRIVATE_KEY_PATH"))

    print(f"KALSHI_API_KEY: {'✓ Set' if has_kalshi_key else '❌ Not set'}")
    print(f"KALSHI_PRIVATE_KEY_PATH: {'✓ Set' if has_kalshi_private else '❌ Not set'}")

    if not (has_kalshi_key and has_kalshi_private):
        print("\nWarning: Kalshi API credentials not configured")
        print("  Some backtests may fail without API access")

    return has_kalshi_key and has_kalshi_private


def clean_legacy():
    """Clean legacy data from cache"""
    print("\n" + "=" * 60)
    print("CLEANING LEGACY DATA")
    print("=" * 60)
    cache = get_cache()

    stats_before = cache.get_stats()
    size_before = stats_before.get("db_size_mb", 0)
    print(f"Current database size: {size_before:.2f} MB")

    cache.clear_legacy_trades()

    stats_after = cache.get_stats()
    size_after = stats_after.get("db_size_mb", 0)

    print("✓ Legacy trades cleared and database vacuumed")
    print(f"✓ New database size:     {size_after:.2f} MB")
    print(f"✓ Space reclaimed:       {size_before - size_after:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Diagnostic tool")
    parser.add_argument(
        "--clean-legacy",
        action="store_true",
        help="Remove legacy trade data to save space",
    )
    args = parser.parse_args()

    if args.clean_legacy:
        clean_legacy()
        return

    print("\n" + "=" * 60)
    print("BACKTEST DIAGNOSTIC TOOL")
    print("=" * 60)

    logs_ok = check_logs()
    cache_ok = check_cache()
    env_ok = check_environment()

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)

    if not logs_ok:
        print("1. Create logs directory: mkdir -p logs")

    if not cache_ok:
        print("1. Populate cache:")
        print("   python run_backtest_real.py --symbol BTCUSDT --days 7")
    else:
        print("1. ✓ Cache is ready")

    if not env_ok:
        print("2. Set Kalshi API credentials (optional)")
    else:
        print("2. ✓ API credentials configured")

    print("\n3. To run quick tests:")
    print("   python test_all_strategies.py --quick --limit-strategies 5")
    print("\nTo see troubleshooting guide:")
    print("   cat TROUBLESHOOTING.md")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
