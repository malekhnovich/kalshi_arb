"""
Agent package for the arbitrage detection system.
"""

from .base import BaseAgent, CircuitBreaker, retry_with_backoff
from .price_monitor import PriceMonitorAgent
from .coingecko_price_monitor import CoinGeckoMonitorAgent
from .kalshi_monitor import KalshiMonitorAgent
from .arbitrage_detector import ArbitrageDetectorAgent
from .signal_aggregator import SignalAggregatorAgent
from .backtester import BacktestAgent
from .trader import TraderAgent

# Optional WebSocket agents (require websockets library)
try:
    from .kalshi_websocket import KalshiWebSocketClient, KalshiWebSocketAgent
    from .binance_websocket import BinanceWebSocketClient, BinanceWebSocketAgent

    _WS_AVAILABLE = True
except ImportError:
    KalshiWebSocketClient = None
    KalshiWebSocketAgent = None
    BinanceWebSocketClient = None
    BinanceWebSocketAgent = None
    _WS_AVAILABLE = False

__all__ = [
    "BaseAgent",
    "CircuitBreaker",
    "retry_with_backoff",
    "PriceMonitorAgent",
    "CoinGeckoMonitorAgent",
    "KalshiMonitorAgent",
    "ArbitrageDetectorAgent",
    "SignalAggregatorAgent",
    "BacktestAgent",
    "TraderAgent",
    "KalshiWebSocketClient",
    "KalshiWebSocketAgent",
    "BinanceWebSocketClient",
    "BinanceWebSocketAgent",
]
