"""
Strategy configuration system for the arbitrage detector.

Each strategy can be independently enabled/disabled to test different combinations.
"""

import os
from typing import Dict


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
# OPTIMIZATION: Disabled by default - permutation testing shows this filter adds
# noise rather than edge. Removing it improves from 66.7% to 71.4% win rate (+$42 P&L).
STRATEGY_MOMENTUM_ACCELERATION = _get_env_bool(
    "STRATEGY_MOMENTUM_ACCELERATION", False
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
# OPTIMIZATION: Disabled to allow more trading opportunities with tighter spreads
# At 71.4% win rate, even small edges become profitable
STRATEGY_TIGHT_SPREAD_FILTER = _get_env_bool(
    "STRATEGY_TIGHT_SPREAD_FILTER", False
)
# Env: STRATEGY_MIN_SPREAD_CENTS
# Minimum spread in cents (overrides config.MIN_ODDS_SPREAD when enabled)
# Lowered to 7.0c to capture more opportunities without sacrificing edge
STRATEGY_MIN_SPREAD_CENTS = _get_env_float(
    "STRATEGY_MIN_SPREAD_CENTS", 7.0
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

# Env: STRATEGY_15MIN_MARKETS
# Enable trading on 15-minute crypto markets (separate from hourly)
STRATEGY_15MIN_MARKETS = _get_env_bool(
    "STRATEGY_15MIN_MARKETS", True
)
# Env: STRATEGY_15MIN_MOMENTUM_WINDOW
# Shorter window for 15-min markets (15 minutes)
STRATEGY_15MIN_MOMENTUM_WINDOW = _get_env_int(
    "STRATEGY_15MIN_MOMENTUM_WINDOW", 15
)
# Env: STRATEGY_15MIN_MOMENTUM_THRESHOLD
# Slightly lower threshold for 15-min markets (they're shorter duration)
STRATEGY_15MIN_MOMENTUM_THRESHOLD = _get_env_int(
    "STRATEGY_15MIN_MOMENTUM_THRESHOLD", 65
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
        "15min_markets": STRATEGY_15MIN_MARKETS,
    }


def is_15min_market(market_ticker: str) -> bool:
    """
    Detect if a market is a 15-minute market vs hourly.

    Kalshi 15-minute markets have different resolution and typically
    different naming patterns than hourly markets.

    This can be refined based on actual Kalshi market naming conventions.
    For now, returns True if market is tagged/identified as 15-min market.
    """
    # TODO: Calibrate based on actual Kalshi market ticker patterns
    # This is a placeholder that will be refined based on live market data
    market_lower = market_ticker.lower()

    # Check for common patterns that indicate 15-min markets
    # (to be updated based on actual Kalshi conventions)
    if "15m" in market_lower or "15min" in market_lower:
        return True

    return False


def get_momentum_window_for_market(market_ticker: str) -> int:
    """
    Get appropriate momentum window (in minutes) for a market.

    - 15-min markets: Use shorter 15-minute window
    - Hourly markets: Use standard 60-minute window
    """
    if STRATEGY_15MIN_MARKETS and is_15min_market(market_ticker):
        return STRATEGY_15MIN_MOMENTUM_WINDOW  # 15 minutes
    else:
        return 60  # 1 hour (default)


def get_momentum_threshold_for_market(market_ticker: str) -> int:
    """
    Get appropriate momentum threshold for a market.

    - 15-min markets: 65% (slightly lower for shorter duration)
    - Hourly markets: 70% (standard)
    """
    if STRATEGY_15MIN_MARKETS and is_15min_market(market_ticker):
        return STRATEGY_15MIN_MOMENTUM_THRESHOLD  # 65%
    else:
        return 70  # standard threshold


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
