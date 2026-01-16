"""
Configuration settings for the arbitrage agent system.

All settings can be overridden via environment variables with the prefix shown in comments.
"""

import os
from pathlib import Path
from typing import List, Tuple


def _get_env_str(key: str, default: str) -> str:
    """Get string from environment variable"""
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    """Get integer from environment variable"""
    value = os.environ.get(key)
    return int(value) if value else default


def _get_env_float(key: str, default: float) -> float:
    """Get float from environment variable"""
    value = os.environ.get(key)
    return float(value) if value else default


def _get_env_list(key: str, default: List[str]) -> List[str]:
    """Get list from comma-separated environment variable"""
    value = os.environ.get(key)
    if value:
        return [s.strip() for s in value.split(",") if s.strip()]
    return default


def _get_env_tuple(key: str, default: Tuple[int, int]) -> Tuple[int, int]:
    """Get tuple from comma-separated environment variable"""
    value = os.environ.get(key)
    if value:
        parts = [int(s.strip()) for s in value.split(",")]
        if len(parts) == 2:
            return (parts[0], parts[1])
    return default


# Binance.US Configuration
# Env: BINANCE_API_URL
BINANCE_US_API_URL = _get_env_str("BINANCE_API_URL", "https://api.binance.us/api/v3")
# Env: BINANCE_SYMBOLS (comma-separated, e.g., "BTCUSDT,ETHUSDT")
BINANCE_SYMBOLS = _get_env_list("BINANCE_SYMBOLS", ["SOLUSDT", "BTCUSDT", "ETHUSDT"])
# Env: POLL_INTERVAL_BINANCE
POLL_INTERVAL_BINANCE = _get_env_int("POLL_INTERVAL_BINANCE", 5)  # seconds

# Kalshi Configuration
# Env: KALSHI_API_URL
KALSHI_API_URL = _get_env_str("KALSHI_API_URL", "https://api.elections.kalshi.com/trade-api/v2")
# Env: POLL_INTERVAL_KALSHI
POLL_INTERVAL_KALSHI = _get_env_int("POLL_INTERVAL_KALSHI", 10)  # seconds
# Env: KALSHI_CRYPTO_SERIES (comma-separated)
KALSHI_CRYPTO_SERIES = _get_env_list("KALSHI_CRYPTO_SERIES", ["KXBTC", "KXETH"])

# Kalshi API Authentication (for historical data access)
# Env: KALSHI_API_KEY
KALSHI_API_KEY = _get_env_str("KALSHI_API_KEY", "")
# Env: KALSHI_PRIVATE_KEY_PATH (path to private key file for RSA signing)
KALSHI_PRIVATE_KEY_PATH = _get_env_str("KALSHI_PRIVATE_KEY_PATH", "")

# Kalshi WebSocket Configuration
# Env: KALSHI_WS_URL
KALSHI_WS_URL = _get_env_str("KALSHI_WS_URL", "wss://api.elections.kalshi.com/trade-api/ws/v2")
# Env: KALSHI_WS_RECONNECT_DELAY
KALSHI_WS_RECONNECT_DELAY = _get_env_int("KALSHI_WS_RECONNECT_DELAY", 5)  # seconds
# Env: KALSHI_WS_HEARTBEAT_INTERVAL
KALSHI_WS_HEARTBEAT_INTERVAL = _get_env_int("KALSHI_WS_HEARTBEAT_INTERVAL", 10)  # seconds
# Env: KALSHI_WS_ENABLED
KALSHI_WS_ENABLED = _get_env_str("KALSHI_WS_ENABLED", "true").lower() == "true"

# ============================================================================
# LIVE TRADING SAFETY GATES
# ============================================================================
# CRITICAL: Live trading is DISABLED by default. Multiple safety checks must
# pass before any real orders can be placed. This prevents accidental trading.
#
# To enable live trading, ALL of these must be true:
#   1. KALSHI_ENABLE_LIVE_TRADING=true environment variable
#   2. ./ENABLE_LIVE_TRADING file must exist in working directory
#   3. --live flag passed to CLI
#   4. NOT running in CI/automated environment
#   5. User types "CONFIRM" at interactive prompt
# ============================================================================

# Env: KALSHI_ENABLE_LIVE_TRADING (must be "true" to enable)
_LIVE_TRADING_ENV_VAR = _get_env_str("KALSHI_ENABLE_LIVE_TRADING", "false")

# Production safety limits (only apply if live trading is enabled)
# Env: MAX_POSITION_SIZE
MAX_POSITION_SIZE = _get_env_float("MAX_POSITION_SIZE", 25.0)  # $25 per trade
# Env: MAX_OPEN_POSITIONS
MAX_OPEN_POSITIONS = _get_env_int("MAX_OPEN_POSITIONS", 3)
# Env: MAX_DAILY_LOSS
MAX_DAILY_LOSS = _get_env_float("MAX_DAILY_LOSS", 50.0)  # Stop trading if down $50


def is_live_trading_allowed() -> bool:
    """
    Multiple safety checks before live trading is allowed.

    Returns True ONLY if ALL of these conditions are met:
    1. KALSHI_ENABLE_LIVE_TRADING=true environment variable is set
    2. ./ENABLE_LIVE_TRADING file exists in working directory
    3. NOT running in CI/automated environment

    The CLI must also pass --live flag and user must confirm interactively.
    """
    # Gate 1: Environment variable must explicitly enable live trading
    if _LIVE_TRADING_ENV_VAR.lower() != "true":
        return False

    # Gate 2: File-based confirmation (prevents accidental env var)
    enable_file = Path("./ENABLE_LIVE_TRADING")
    if not enable_file.exists():
        return False

    # Gate 3: Never allow in CI/automated environments
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return False

    # Gate 4: Check for kill switch
    if Path("./STOP_TRADING").exists():
        return False

    return True


def get_live_trading_status() -> dict:
    """Get detailed status of each live trading safety gate."""
    return {
        "env_var_set": _LIVE_TRADING_ENV_VAR.lower() == "true",
        "enable_file_exists": Path("./ENABLE_LIVE_TRADING").exists(),
        "not_in_ci": not (os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")),
        "no_kill_switch": not Path("./STOP_TRADING").exists(),
        "all_gates_passed": is_live_trading_allowed(),
    }


# Analysis Configuration
# Env: MOMENTUM_WINDOW
MOMENTUM_WINDOW = _get_env_int("MOMENTUM_WINDOW", 60)  # minutes to analyze for momentum
# Env: CONFIDENCE_THRESHOLD
CONFIDENCE_THRESHOLD = _get_env_int("CONFIDENCE_THRESHOLD", 70)  # percent confidence

# Arbitrage Detection Thresholds
# Env: MIN_ODDS_SPREAD
MIN_ODDS_SPREAD = _get_env_float("MIN_ODDS_SPREAD", 10.0)  # Minimum spread (cents)
# Env: ODDS_NEUTRAL_RANGE (comma-separated, e.g., "45,55")
ODDS_NEUTRAL_RANGE = _get_env_tuple("ODDS_NEUTRAL_RANGE", (45, 55))

# Logging Configuration
# Env: LOG_DIR
LOG_DIR = Path(_get_env_str("LOG_DIR", "logs"))
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
CONSOLE_COLORS = {
    "INFO": "\033[94m",      # Blue
    "WARNING": "\033[93m",   # Yellow
    "OPPORTUNITY": "\033[92m",  # Green
    "ERROR": "\033[91m",     # Red
    "RESET": "\033[0m"
}

# Agent Configuration
# Env: AGENT_HEALTH_CHECK_INTERVAL
AGENT_HEALTH_CHECK_INTERVAL = _get_env_int("AGENT_HEALTH_CHECK_INTERVAL", 30)  # seconds
# Env: MAX_RESTART_ATTEMPTS
MAX_RESTART_ATTEMPTS = _get_env_int("MAX_RESTART_ATTEMPTS", 3)

# HTTP Client Configuration
# Env: HTTP_TIMEOUT
HTTP_TIMEOUT = _get_env_float("HTTP_TIMEOUT", 10.0)  # seconds
# Env: HTTP_MAX_RETRIES
HTTP_MAX_RETRIES = _get_env_int("HTTP_MAX_RETRIES", 3)
# Env: CIRCUIT_BREAKER_THRESHOLD
CIRCUIT_BREAKER_THRESHOLD = _get_env_int("CIRCUIT_BREAKER_THRESHOLD", 5)
# Env: CIRCUIT_BREAKER_RECOVERY_TIMEOUT
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = _get_env_float("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 60.0)

# Symbol mapping between exchanges
SYMBOL_MAP = {
    "SOLUSDT": {"binance": "SOLUSDT", "kalshi_prefix": "KXSOL", "base": "SOL"},
    "BTCUSDT": {"binance": "BTCUSDT", "kalshi_prefix": "KXBTC", "base": "BTC"},
    "ETHUSDT": {"binance": "ETHUSDT", "kalshi_prefix": "KXETH", "base": "ETH"},
}

# Backtesting Configuration
# Env: BACKTEST_TRADE_SIZE
BACKTEST_TRADE_SIZE = _get_env_float("BACKTEST_TRADE_SIZE", 100.0)
# Env: BACKTEST_MIN_CONFIDENCE
BACKTEST_MIN_CONFIDENCE = _get_env_float("BACKTEST_MIN_CONFIDENCE", 70.0)
# Env: BACKTEST_MAX_OPEN_TRADES
BACKTEST_MAX_OPEN_TRADES = _get_env_int("BACKTEST_MAX_OPEN_TRADES", 3)
# Env: BACKTEST_SIGNAL_COOLDOWN (seconds)
BACKTEST_SIGNAL_COOLDOWN = _get_env_int("BACKTEST_SIGNAL_COOLDOWN", 300)
# Env: BACKTEST_TRADE_DURATION (minutes)
BACKTEST_TRADE_DURATION = _get_env_int("BACKTEST_TRADE_DURATION", 60)
# Env: BACKTEST_MIN_VOLUME_THRESHOLD
BACKTEST_MIN_VOLUME_THRESHOLD = _get_env_int("BACKTEST_MIN_VOLUME_THRESHOLD", 100)
# Env: BACKTEST_TRADING_FEE_RATE (percentage)
BACKTEST_TRADING_FEE_RATE = _get_env_float("BACKTEST_TRADING_FEE_RATE", 0.03)
# Env: BACKTEST_PARALLEL_BATCH_SIZE (concurrent API requests)
BACKTEST_PARALLEL_BATCH_SIZE = _get_env_int("BACKTEST_PARALLEL_BATCH_SIZE", 25)
# Env: KALSHI_READ_LIMIT_PER_SECOND
KALSHI_READ_LIMIT_PER_SECOND = _get_env_int("KALSHI_READ_LIMIT_PER_SECOND", 30)
