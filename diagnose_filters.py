#!/usr/bin/env python3
"""
Diagnose which strategy filters are blocking all trades.

Run this to see which filters are enabled and why trades might be blocked.
"""

import os
import strategies


def main():
    print("\n" + "=" * 80)
    print("STRATEGY FILTER DIAGNOSTIC")
    print("=" * 80)

    # Show all strategy statuses
    filters = {
        "VOLATILITY_FILTER": (strategies.STRATEGY_VOLATILITY_FILTER, strategies.STRATEGY_VOLATILITY_THRESHOLD),
        "PULLBACK_ENTRY": (strategies.STRATEGY_PULLBACK_ENTRY, strategies.STRATEGY_PULLBACK_THRESHOLD),
        "MOMENTUM_ACCELERATION": (strategies.STRATEGY_MOMENTUM_ACCELERATION, None),
        "TIME_FILTER": (strategies.STRATEGY_TIME_FILTER, (strategies.STRATEGY_TRADING_HOURS_START, strategies.STRATEGY_TRADING_HOURS_END)),
        "TIGHT_SPREAD_FILTER": (strategies.STRATEGY_TIGHT_SPREAD_FILTER, strategies.STRATEGY_MIN_SPREAD_CENTS),
        "CORRELATION_CHECK": (strategies.STRATEGY_CORRELATION_CHECK, None),
        "MULTIFRAME_CONFIRMATION": (strategies.STRATEGY_MULTIFRAME_CONFIRMATION, strategies.STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD),
        "TREND_CONFIRMATION": (strategies.STRATEGY_TREND_CONFIRMATION, None),
        "DYNAMIC_NEUTRAL_RANGE": (strategies.STRATEGY_DYNAMIC_NEUTRAL_RANGE, None),
        "IMPROVED_CONFIDENCE": (strategies.STRATEGY_IMPROVED_CONFIDENCE, None),
    }

    enabled_filters = []
    disabled_filters = []

    for name, (enabled, threshold) in filters.items():
        status = "✓ ENABLED" if enabled else "✗ DISABLED"
        print(f"\n{status}: {name}")

        if threshold is not None:
            if isinstance(threshold, tuple):
                print(f"   Parameters: {threshold}")
            else:
                print(f"   Threshold: {threshold}")

        if enabled:
            enabled_filters.append(name)
        else:
            disabled_filters.append(name)

    print("\n" + "=" * 80)
    print(f"SUMMARY: {len(enabled_filters)} filters ENABLED, {len(disabled_filters)} DISABLED")
    print("=" * 80)

    print(f"\nEnabled Filtering Strategies ({len(enabled_filters)}):")
    for f in enabled_filters:
        print(f"  • {f}")

    if len(enabled_filters) >= 4:
        print("\n⚠️  WARNING: Many filters enabled (may be too restrictive!)")
        print("\nTo get trades, try disabling some filters:")
        print("\n  # Option 1: Disable the 3 most aggressive filters")
        print("  export STRATEGY_MOMENTUM_ACCELERATION=false")
        print("  export STRATEGY_PULLBACK_ENTRY=false")
        print("  export STRATEGY_VOLATILITY_FILTER=false")
        print("  uv run python run_backtest_real.py --symbol BTCUSDT --days 2")
        print("\n  # Option 2: Start with baseline (all filters off)")
        print("  export STRATEGY_VOLATILITY_FILTER=false")
        print("  export STRATEGY_PULLBACK_ENTRY=false")
        print("  export STRATEGY_TIGHT_SPREAD_FILTER=false")
        print("  export STRATEGY_MOMENTUM_ACCELERATION=false")
        print("  export STRATEGY_TIME_FILTER=false")
        print("  export STRATEGY_MULTIFRAME_CONFIRMATION=false")
        print("  uv run python run_backtest_real.py --symbol BTCUSDT --days 2")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
