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
