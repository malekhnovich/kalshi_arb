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
# Env: BINANCE_WS_ENABLED
BINANCE_WS_ENABLED = _get_env_str("BINANCE_WS_ENABLED", "true").lower() == "true"

# Kalshi Configuration
# Env: KALSHI_API_URL
KALSHI_API_URL = _get_env_str(
    "KALSHI_API_URL", "https://api.elections.kalshi.com/trade-api/v2"
)
# Env: POLL_INTERVAL_KALSHI
POLL_INTERVAL_KALSHI = _get_env_int("POLL_INTERVAL_KALSHI", 10)  # seconds
# Env: KALSHI_CRYPTO_SERIES (comma-separated)
KALSHI_CRYPTO_SERIES = _get_env_list("KALSHI_CRYPTO_SERIES", ["KXBTC", "KXETH"])

# Kalshi API Authentication (for historical data access)
# Env: KALSHI_API_KEY
KALSHI_API_KEY = _get_env_str("KALSHI_API_KEY", "")
# Env: KALSHI_PRIVATE_KEY_PATH (path to private key file for RSA signing)
KALSHI_PRIVATE_KEY_PATH = _get_env_str("KALSHI_PRIVATE_KEY_PATH", "private_key.pem")

# Kalshi WebSocket Configuration
# Env: KALSHI_WS_URL
KALSHI_WS_URL = _get_env_str(
    "KALSHI_WS_URL", "wss://api.elections.kalshi.com/trade-api/ws/v2"
)
# Env: KALSHI_WS_RECONNECT_DELAY
KALSHI_WS_RECONNECT_DELAY = _get_env_int("KALSHI_WS_RECONNECT_DELAY", 5)  # seconds
# Env: KALSHI_WS_HEARTBEAT_INTERVAL
KALSHI_WS_HEARTBEAT_INTERVAL = _get_env_int(
    "KALSHI_WS_HEARTBEAT_INTERVAL", 10
)  # seconds
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
MOMENTUM_WINDOW = _get_env_int("MOMENTUM_WINDOW", 20)  # minutes to analyze for momentum
# Env: CONFIDENCE_THRESHOLD
CONFIDENCE_THRESHOLD = _get_env_int("CONFIDENCE_THRESHOLD", 70)  # percent confidence

# Arbitrage Detection Thresholds
# Env: MIN_ODDS_SPREAD
MIN_ODDS_SPREAD = _get_env_float("MIN_ODDS_SPREAD", 10.0)  # Minimum spread (cents)
# Env: ODDS_NEUTRAL_RANGE (comma-separated, e.g., "45,55")
ODDS_NEUTRAL_RANGE = _get_env_tuple("ODDS_NEUTRAL_RANGE", (45, 55))
# Env: STRIKE_DISTANCE_THRESHOLD_PCT (within X% of strike price)
STRIKE_DISTANCE_THRESHOLD_PCT = _get_env_float("STRIKE_DISTANCE_THRESHOLD_PCT", 0.5)

# Logging Configuration
# Env: LOG_DIR
LOG_DIR = Path(_get_env_str("LOG_DIR", "logs"))
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
CONSOLE_COLORS = {
    "INFO": "\033[94m",  # Blue
    "WARNING": "\033[93m",  # Yellow
    "OPPORTUNITY": "\033[92m",  # Green
    "ERROR": "\033[91m",  # Red
    "RESET": "\033[0m",
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
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = _get_env_float(
    "CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 60.0
)

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

# ============================================================================
# REALISTIC SIMULATION SETTINGS (Dry-Run Mode)
# ============================================================================
# These settings make dry-run mode more realistic by simulating real-world
# trading conditions like fees, slippage, partial fills, and latency.

# Env: SIM_REALISTIC_MODE (enable all realistic simulations)
SIM_REALISTIC_MODE = _get_env_str("SIM_REALISTIC_MODE", "true").lower() == "true"

# Kalshi Fee Structure (per contract, in cents)
# Kalshi charges taker fees for immediate fills
# Env: SIM_TAKER_FEE_CENTS (typical: 2-7 cents per contract)
SIM_TAKER_FEE_CENTS = _get_env_float("SIM_TAKER_FEE_CENTS", 3.0)

# Slippage Simulation
# Env: SIM_SLIPPAGE_BASE_CENTS (base slippage in cents)
SIM_SLIPPAGE_BASE_CENTS = _get_env_float("SIM_SLIPPAGE_BASE_CENTS", 1.0)
# Env: SIM_SLIPPAGE_PER_CONTRACT (additional slippage per contract)
SIM_SLIPPAGE_PER_CONTRACT = _get_env_float("SIM_SLIPPAGE_PER_CONTRACT", 0.1)
# Env: SIM_SLIPPAGE_VOLATILITY (random volatility factor 0-1)
SIM_SLIPPAGE_VOLATILITY = _get_env_float("SIM_SLIPPAGE_VOLATILITY", 0.5)

# Partial Fill Simulation
# Env: SIM_FILL_RATE_BASE (base probability of full fill, 0-1)
SIM_FILL_RATE_BASE = _get_env_float("SIM_FILL_RATE_BASE", 0.85)
# Env: SIM_MIN_FILL_RATE (minimum fill rate when partial, 0-1)
SIM_MIN_FILL_RATE = _get_env_float("SIM_MIN_FILL_RATE", 0.3)

# Latency Simulation
# Env: SIM_LATENCY_MS (average latency in milliseconds)
SIM_LATENCY_MS = _get_env_int("SIM_LATENCY_MS", 250)
# Env: SIM_LATENCY_JITTER_MS (random jitter +/- milliseconds)
SIM_LATENCY_JITTER_MS = _get_env_int("SIM_LATENCY_JITTER_MS", 100)

# Price Movement During Latency
# Env: SIM_PRICE_MOVE_PROBABILITY (chance price moves against you during latency)
SIM_PRICE_MOVE_PROBABILITY = _get_env_float("SIM_PRICE_MOVE_PROBABILITY", 0.3)
# Env: SIM_PRICE_MOVE_MAX_CENTS (max adverse price move in cents)
SIM_PRICE_MOVE_MAX_CENTS = _get_env_float("SIM_PRICE_MOVE_MAX_CENTS", 3.0)
