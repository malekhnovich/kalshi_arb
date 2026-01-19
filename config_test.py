"""
TEST CONFIGURATION - Bare minimum filters for workflow validation

This is a SEPARATE configuration file for testing the end-to-end workflow.
It has maximum permissiveness to ensure signals flow and trades execute.

DO NOT use this for alpha generation. Use config.py for production trading.

MODES:
  Normal mode:    make dryrun-test-debug
  Scalping mode:  SCALPING_MODE=true make dryrun-test-debug
    - More aggressive (45% momentum vs 50%)
    - Tighter spreads (0.5c acceptance)
    - Goal: Many small wins instead of few big ones

To use this test config:
    export CONFIG_MODULE=config_test
    make dryrun

To revert to production config:
    unset CONFIG_MODULE
    make dryrun
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


# Binance.US Configuration (DEPRECATED - Replaced with CoinGecko)
BINANCE_US_API_URL = _get_env_str("BINANCE_API_URL", "https://api.binance.us/api/v3")
BINANCE_SYMBOLS = _get_env_list("BINANCE_SYMBOLS", ["SOLUSDT", "BTCUSDT", "ETHUSDT", "XRPUSDT"])
# Price Monitor Polling Interval (applies to both CoinGecko and Binance)
# 20s = 12 req/min (safe), 30s = 8 req/min (very safe)
PRICE_POLL_INTERVAL = _get_env_int("PRICE_POLL_INTERVAL", 20)  # seconds
# BUGFIX: WebSocket publishes individual trades, not 1-min candles
# This causes momentum to be meaningless with only 2-3 ticks
# Use polling API which correctly fetches complete 1-minute OHLCV candles
BINANCE_WS_ENABLED = _get_env_str("BINANCE_WS_ENABLED", "false").lower() == "true"

# Kalshi Configuration
KALSHI_API_URL = _get_env_str("KALSHI_API_URL", "https://api.elections.kalshi.com/trade-api/v2")
POLL_INTERVAL_KALSHI = _get_env_int("POLL_INTERVAL_KALSHI", 10)
KALSHI_CRYPTO_SERIES = _get_env_list("KALSHI_CRYPTO_SERIES", ["KXBTC", "KXETH", "KXSOL", "KXXRP"])

# Kalshi API Authentication
KALSHI_API_KEY = _get_env_str("KALSHI_API_KEY", "")
KALSHI_PRIVATE_KEY_PATH = _get_env_str("KALSHI_PRIVATE_KEY_PATH", "private_key.pem")

# Kalshi WebSocket Configuration
KALSHI_WS_URL = _get_env_str("KALSHI_WS_URL", "wss://api.elections.kalshi.com/trade-api/ws/v2")
KALSHI_WS_RECONNECT_DELAY = _get_env_int("KALSHI_WS_RECONNECT_DELAY", 5)
KALSHI_WS_HEARTBEAT_INTERVAL = _get_env_int("KALSHI_WS_HEARTBEAT_INTERVAL", 10)
KALSHI_WS_ENABLED = _get_env_str("KALSHI_WS_ENABLED", "true").lower() == "true"

# Live Trading Safety Gates (Always disabled for testing)
_LIVE_TRADING_ENV_VAR = "false"

# Production safety limits
MAX_POSITION_SIZE = _get_env_float("MAX_POSITION_SIZE", 10.0)
MAX_OPEN_POSITIONS = _get_env_int("MAX_OPEN_POSITIONS", 3)
MAX_DAILY_LOSS = _get_env_float("MAX_DAILY_LOSS", 30.0)


def is_live_trading_allowed() -> bool:
    """Always False for test config"""
    return False


def get_live_trading_status() -> dict:
    """Always disabled for test config"""
    return {
        "env_var_set": False,
        "enable_file_exists": False,
        "not_in_ci": True,
        "no_kill_switch": True,
        "all_gates_passed": False,
    }


# ============================================================================
# TEST CONFIGURATION: BARE MINIMUM FILTERS
# ============================================================================

# Check if scalping mode is enabled
_SCALPING_MODE = _get_env_str("SCALPING_MODE", "false").lower() == "true"

# Price Monitor Selection
# Env: PRICE_MONITOR_SOURCE (binance or coingecko)
PRICE_MONITOR_SOURCE = _get_env_str("PRICE_MONITOR_SOURCE", "binance").lower()

# Analysis Configuration
MOMENTUM_WINDOW = _get_env_int("MOMENTUM_WINDOW", 20)

# TEST: Accept momentum > 50% (normal) or > 45% (scalping mode)
CONFIDENCE_THRESHOLD = _get_env_int(
    "CONFIDENCE_THRESHOLD",
    45 if _SCALPING_MODE else 50
)

# Arbitrage Detection Thresholds
# TEST: Accept ANY spread (even 0c), or 0.5c for scalping
MIN_ODDS_SPREAD = _get_env_float(
    "MIN_ODDS_SPREAD",
    0.5 if _SCALPING_MODE else 0.0
)

# TEST: Accept ANY odds from 0-100 cents
# Looser odds filter = more potential trades (Kalshi odds are typically 1-99c)
ODDS_NEUTRAL_RANGE = _get_env_tuple("ODDS_NEUTRAL_RANGE", (0, 100))

# TEST: Allow any distance (100% = no restriction)
STRIKE_DISTANCE_THRESHOLD_PCT = _get_env_float("STRIKE_DISTANCE_THRESHOLD_PCT", 100.0)

# Logging Configuration
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
AGENT_HEALTH_CHECK_INTERVAL = _get_env_int("AGENT_HEALTH_CHECK_INTERVAL", 30)
MAX_RESTART_ATTEMPTS = _get_env_int("MAX_RESTART_ATTEMPTS", 3)

# HTTP Client Configuration
HTTP_TIMEOUT = _get_env_float("HTTP_TIMEOUT", 10.0)
HTTP_MAX_RETRIES = _get_env_int("HTTP_MAX_RETRIES", 3)
CIRCUIT_BREAKER_THRESHOLD = _get_env_int("CIRCUIT_BREAKER_THRESHOLD", 5)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = _get_env_float("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 60.0)

# Symbol mapping between exchanges
SYMBOL_MAP = {
    "SOLUSDT": {"binance": "SOLUSDT", "kalshi_prefix": "KXSOL", "base": "SOL"},
    "BTCUSDT": {"binance": "BTCUSDT", "kalshi_prefix": "KXBTC", "base": "BTC"},
    "ETHUSDT": {"binance": "ETHUSDT", "kalshi_prefix": "KXETH", "base": "ETH"},
    "XRPUSDT": {"binance": "XRPUSDT", "kalshi_prefix": "KXXRP", "base": "XRP"},
}

# Backtesting Configuration
BACKTEST_TRADE_SIZE = _get_env_float("BACKTEST_TRADE_SIZE", 100.0)
BACKTEST_MIN_CONFIDENCE = _get_env_float("BACKTEST_MIN_CONFIDENCE", 50.0)  # TEST: Low bar
BACKTEST_MAX_OPEN_TRADES = _get_env_int("BACKTEST_MAX_OPEN_TRADES", 3)
BACKTEST_SIGNAL_COOLDOWN = _get_env_int("BACKTEST_SIGNAL_COOLDOWN", 300)
BACKTEST_TRADE_DURATION = _get_env_int("BACKTEST_TRADE_DURATION", 60)
BACKTEST_MIN_VOLUME_THRESHOLD = _get_env_int("BACKTEST_MIN_VOLUME_THRESHOLD", 20)
BACKTEST_TRADING_FEE_RATE = _get_env_float("BACKTEST_TRADING_FEE_RATE", 0.03)
BACKTEST_PARALLEL_BATCH_SIZE = _get_env_int("BACKTEST_PARALLEL_BATCH_SIZE", 25)
KALSHI_READ_LIMIT_PER_SECOND = _get_env_int("KALSHI_READ_LIMIT_PER_SECOND", 10)

# ============================================================================
# REALISTIC SIMULATION SETTINGS (Dry-Run Mode)
# ============================================================================

SIM_REALISTIC_MODE = _get_env_str("SIM_REALISTIC_MODE", "true").lower() == "true"

# Kalshi Fee Structure
SIM_TAKER_FEE_CENTS = _get_env_float("SIM_TAKER_FEE_CENTS", 3.0)

# Slippage Simulation
SIM_SLIPPAGE_BASE_CENTS = _get_env_float("SIM_SLIPPAGE_BASE_CENTS", 1.0)
SIM_SLIPPAGE_PER_CONTRACT = _get_env_float("SIM_SLIPPAGE_PER_CONTRACT", 0.1)
SIM_SLIPPAGE_VOLATILITY = _get_env_float("SIM_SLIPPAGE_VOLATILITY", 0.5)

# Partial Fill Simulation
SIM_FILL_RATE_BASE = _get_env_float("SIM_FILL_RATE_BASE", 0.85)
SIM_MIN_FILL_RATE = _get_env_float("SIM_MIN_FILL_RATE", 0.3)

# Latency Simulation
SIM_LATENCY_MS = _get_env_int("SIM_LATENCY_MS", 250)
SIM_LATENCY_JITTER_MS = _get_env_int("SIM_LATENCY_JITTER_MS", 100)

# Price Movement During Latency
SIM_PRICE_MOVE_PROBABILITY = _get_env_float("SIM_PRICE_MOVE_PROBABILITY", 0.3)
SIM_PRICE_MOVE_MAX_CENTS = _get_env_float("SIM_PRICE_MOVE_MAX_CENTS", 3.0)

# ============================================================================
# POSITION SIZING - STAGE-BASED DEPLOYMENT
# ============================================================================

STAGE_1_CAPITAL_BASE = _get_env_float("STAGE_1_CAPITAL_BASE", 200.0)
STAGE_1_MAX_POSITION = _get_env_float("STAGE_1_MAX_POSITION", 10.0)
STAGE_1_DAILY_LOSS_LIMIT = _get_env_float("STAGE_1_DAILY_LOSS_LIMIT", 30.0)
STAGE_1_MAX_DRAWDOWN_PERCENT = _get_env_float("STAGE_1_MAX_DRAWDOWN_PERCENT", 10.0)
