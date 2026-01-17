"""
Strategy configuration system for the arbitrage detector.

Each strategy can be independently enabled/disabled to test different combinations.
"""

import os
from typing import Dict, Any


def _get_env_bool(key: str, default: bool) -> bool:
    """Get boolean from environment variable"""
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return default


def _get_env_float(key: str, default: float) -> float:
    """Get float from environment variable"""
    value = os.environ.get(key)
    return float(value) if value else default


def _get_env_int(key: str, default: int) -> int:
    """Get integer from environment variable"""
    value = os.environ.get(key)
    return int(value) if value else default


# ============================================================================
# STRATEGY TOGGLES - Enable/disable each improvement independently
# ============================================================================
# Env: STRATEGY_MOMENTUM_ACCELERATION
# Filter out trades where momentum is decelerating (already implemented)
STRATEGY_MOMENTUM_ACCELERATION = _get_env_bool(
    "STRATEGY_MOMENTUM_ACCELERATION", True
)

# Env: STRATEGY_TREND_CONFIRMATION
# Only trade when price structure confirms direction (higher highs/lows)
STRATEGY_TREND_CONFIRMATION = _get_env_bool(
    "STRATEGY_TREND_CONFIRMATION", True
)

# Env: STRATEGY_DYNAMIC_NEUTRAL_RANGE
# Adjust neutral range based on spread size
STRATEGY_DYNAMIC_NEUTRAL_RANGE = _get_env_bool(
    "STRATEGY_DYNAMIC_NEUTRAL_RANGE", True
)

# Env: STRATEGY_IMPROVED_CONFIDENCE
# Enhanced confidence formula with spread/trend/acceleration bonuses
STRATEGY_IMPROVED_CONFIDENCE = _get_env_bool(
    "STRATEGY_IMPROVED_CONFIDENCE", True
)

# Env: STRATEGY_VOLATILITY_FILTER
# Skip trades during high volatility periods
STRATEGY_VOLATILITY_FILTER = _get_env_bool(
    "STRATEGY_VOLATILITY_FILTER", True
)
# Env: STRATEGY_VOLATILITY_THRESHOLD
# Skip if volatility > this value (stdev of returns)
STRATEGY_VOLATILITY_THRESHOLD = _get_env_float(
    "STRATEGY_VOLATILITY_THRESHOLD", 0.015
)

# Env: STRATEGY_PULLBACK_ENTRY
# Wait for price pullback from momentum peak before entering
STRATEGY_PULLBACK_ENTRY = _get_env_bool(
    "STRATEGY_PULLBACK_ENTRY", True
)
# Env: STRATEGY_PULLBACK_THRESHOLD
# Minimum pullback % required (e.g., 0.2 = 0.2% pullback)
STRATEGY_PULLBACK_THRESHOLD = _get_env_float(
    "STRATEGY_PULLBACK_THRESHOLD", 0.3
)

# Env: STRATEGY_TIGHT_SPREAD_FILTER
# Increase minimum spread threshold to avoid tiny edges
STRATEGY_TIGHT_SPREAD_FILTER = _get_env_bool(
    "STRATEGY_TIGHT_SPREAD_FILTER", True
)
# Env: STRATEGY_MIN_SPREAD_CENTS
# Minimum spread in cents (overrides config.MIN_ODDS_SPREAD when enabled)
STRATEGY_MIN_SPREAD_CENTS = _get_env_float(
    "STRATEGY_MIN_SPREAD_CENTS", 15.0
)

# Env: STRATEGY_CORRELATION_CHECK
# Skip if already holding position on same symbol
STRATEGY_CORRELATION_CHECK = _get_env_bool(
    "STRATEGY_CORRELATION_CHECK", True
)

# Env: STRATEGY_TIME_FILTER
# Only trade during active hours (UTC)
STRATEGY_TIME_FILTER = _get_env_bool(
    "STRATEGY_TIME_FILTER", True
)
# Env: STRATEGY_TRADING_HOURS_START (UTC hour, 0-23)
STRATEGY_TRADING_HOURS_START = _get_env_int(
    "STRATEGY_TRADING_HOURS_START", 14
)  # 2pm UTC
# Env: STRATEGY_TRADING_HOURS_END (UTC hour, 0-23)
STRATEGY_TRADING_HOURS_END = _get_env_int(
    "STRATEGY_TRADING_HOURS_END", 22
)  # 10pm UTC

# Env: STRATEGY_MULTIFRAME_CONFIRMATION
# Confirm signal on both 1-min and 5-min timeframes
STRATEGY_MULTIFRAME_CONFIRMATION = _get_env_bool(
    "STRATEGY_MULTIFRAME_CONFIRMATION", True
)
# Env: STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD
# Minimum momentum for 5-min candles (less strict than 1-min)
STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD = _get_env_float(
    "STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD", 55.0
)

# Env: STRATEGY_SHORTER_MOMENTUM_WINDOW
# Use 10-minute window instead of 20
STRATEGY_SHORTER_MOMENTUM_WINDOW = _get_env_bool(
    "STRATEGY_SHORTER_MOMENTUM_WINDOW", False
)  # Disabled by default - requires separate data
# Env: STRATEGY_MOMENTUM_WINDOW_MINUTES
STRATEGY_MOMENTUM_WINDOW_MINUTES = _get_env_int(
    "STRATEGY_MOMENTUM_WINDOW_MINUTES", 10
)


def get_enabled_strategies() -> Dict[str, bool]:
    """Get dictionary of all enabled strategies for logging"""
    return {
        "momentum_acceleration": STRATEGY_MOMENTUM_ACCELERATION,
        "trend_confirmation": STRATEGY_TREND_CONFIRMATION,
        "dynamic_neutral_range": STRATEGY_DYNAMIC_NEUTRAL_RANGE,
        "improved_confidence": STRATEGY_IMPROVED_CONFIDENCE,
        "volatility_filter": STRATEGY_VOLATILITY_FILTER,
        "pullback_entry": STRATEGY_PULLBACK_ENTRY,
        "tight_spread_filter": STRATEGY_TIGHT_SPREAD_FILTER,
        "correlation_check": STRATEGY_CORRELATION_CHECK,
        "time_filter": STRATEGY_TIME_FILTER,
        "multiframe_confirmation": STRATEGY_MULTIFRAME_CONFIRMATION,
        "shorter_momentum_window": STRATEGY_SHORTER_MOMENTUM_WINDOW,
    }


def get_strategy_summary() -> str:
    """Get human-readable summary of active strategies"""
    enabled = get_enabled_strategies()
    active = [name for name, is_enabled in enabled.items() if is_enabled]
    disabled = [name for name, is_enabled in enabled.items() if not is_enabled]

    summary = f"Active Strategies ({len(active)}):\n"
    for strategy in active:
        summary += f"  ✓ {strategy}\n"

    if disabled:
        summary += f"\nDisabled Strategies ({len(disabled)}):\n"
        for strategy in disabled:
            summary += f"  ✗ {strategy}\n"

    return summary
