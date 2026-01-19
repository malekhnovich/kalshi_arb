"""
CoinGecko Price Monitor Agent - Free cryptocurrency price data (no API key required).

Uses CoinGecko public API to track prices and calculate momentum.
Much more reliable than Binance.US which frequently has connectivity issues.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
import time

import httpx

from .base import BaseAgent, retry_with_backoff, CircuitBreaker
from events import EventBus, PriceUpdateEvent
import config

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ResilientHttpClient:
    """
    Async HTTP client with retry logic, rate limiting, and circuit breaker.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        rate_limit_delay: float = 0.1,
        api_key: str = "",
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.api_key = api_key
        # Increased failure threshold from 5 to 15 for better resilience to transient API issues
        self._circuit_breaker = CircuitBreaker(failure_threshold=15, recovery_timeout=30.0)
        self._last_request_time: float = 0

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests"""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make a GET request with retry logic and circuit breaker"""
        if not self._circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker OPEN | State: {self._circuit_breaker.state} | Failures: {self._circuit_breaker._failure_count}/{self._circuit_breaker.failure_threshold}")
            raise Exception("Circuit breaker is open - service recovering")

        await self._rate_limit()

        async def _do_request():
            request_params = params or {}
            # Add API key if provided
            if self.api_key:
                request_params["x_cg_pro_api_key"] = self.api_key

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    params=request_params
                )
                response.raise_for_status()
                return response.json()

        try:
            result = await retry_with_backoff(
                _do_request,
                max_retries=self.max_retries,
                base_delay=0.5,
                max_delay=10.0,
            )
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            failure_rate = f"{self._circuit_breaker._failure_count}/{self._circuit_breaker.failure_threshold}"
            logger.warning(f"Request failed ({failure_rate}) | Endpoint: {endpoint} | Error: {str(e)[:100]}")
            raise


class CoinGeckoClient:
    """
    Async HTTP client for CoinGecko free API with resilience.

    No API key required, free tier supports reasonable request rates.
    Maps cryptocurrency symbols to CoinGecko IDs.
    """

    # Map trading symbols to CoinGecko IDs
    SYMBOL_TO_COINGECKO_ID = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "SOLUSDT": "solana",
        "XRPUSDT": "ripple",
    }

    def __init__(self, base_url: str = "https://api.coingecko.com/api/v3"):
        # Use rate limit from config, which can be overridden via COINGECKO_RATE_LIMIT env var
        rate_limit_delay = 1.0 / config.COINGECKO_RATE_LIMIT if config.COINGECKO_RATE_LIMIT > 0 else 0.2

        self._client = ResilientHttpClient(
            base_url=base_url,
            timeout=10.0,
            max_retries=3,
            rate_limit_delay=rate_limit_delay,
            api_key=config.COINGECKO_API_KEY,
        )

        has_api_key = "✓" if config.COINGECKO_API_KEY else "✗"
        logger.info(f"CoinGecko client initialized | API Key: {has_api_key} | Rate Limit: {1/rate_limit_delay:.1f} req/min")

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current market data for a cryptocurrency.

        Returns price, market cap, 24h change, etc.
        """
        coingecko_id = self.SYMBOL_TO_COINGECKO_ID.get(symbol, symbol.lower())

        return await self._client.get(
            f"/coins/{coingecko_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
            }
        )

    async def get_market_chart(
        self, symbol: str, days: int = 1, interval: str = "minutely"
    ) -> Dict[str, Any]:
        """
        Fetch historical price data for momentum calculation.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            days: Number of days to fetch (1-90)
            interval: Data interval ("hourly" or "daily")

        Returns:
            Dict with prices, market_caps, volumes arrays
        """
        coingecko_id = self.SYMBOL_TO_COINGECKO_ID.get(symbol, symbol.lower())

        return await self._client.get(
            f"/coins/{coingecko_id}/market_chart",
            params={
                "vs_currency": "usd",
                "days": str(days),
                "interval": interval,
            }
        )


class CoinGeckoMonitorAgent(BaseAgent):
    """
    Monitors cryptocurrency prices via CoinGecko (free, no API key needed).

    Polls at regular intervals and calculates momentum based on
    the percentage of up vs down price movements in the analysis window.

    Advantages over Binance.US:
    - No API key required
    - Free tier is quite generous (10-50 calls/min)
    - More reliable uptime
    - Global data (not just Binance.US)
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("CoinGeckoMonitor", event_bus)
        self.client = CoinGeckoClient()
        self.symbols = config.BINANCE_SYMBOLS
        self.poll_interval = config.PRICE_POLL_INTERVAL
        self.momentum_window = config.MOMENTUM_WINDOW

        # Track price history per symbol for momentum calculation
        self._price_history: Dict[str, List[Dict]] = {s: [] for s in self.symbols}

        # Logging
        logger.info(f"✓ CoinGeckoMonitorAgent initialized | Symbols: {', '.join(self.symbols)} | Poll interval: {self.poll_interval}s | Momentum window: {self.momentum_window}min")

    async def run(self) -> None:
        """Poll prices for all symbols and emit events"""
        logger.info(f"✓ CoinGeckoMonitorAgent started | Polling every {self.poll_interval}s")

        while self.is_running:
            tasks = [self._fetch_and_emit(symbol) for symbol in self.symbols]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(self.poll_interval)

    async def _fetch_and_emit(self, symbol: str) -> None:
        """Fetch price data and emit PriceUpdateEvent"""
        try:
            market_data = await self.client.get_market_data(symbol)

            # Extract current price and 24h data
            current_price = market_data.get("market_data", {}).get("current_price", {}).get("usd", 0)
            price_change_24h = market_data.get("market_data", {}).get("price_change_percentage_24h", 0)
            market_cap = market_data.get("market_data", {}).get("market_cap", {}).get("usd", 0)

            if not current_price:
                raise ValueError(f"No price data for {symbol}")

            # Update price history for momentum calculation
            history = self._price_history[symbol]
            now = time.time()

            # Add current price to history
            history.append({"price": current_price, "time": now})

            # Keep only last N readings (approximately momentum_window minutes)
            cutoff_time = now - (self.momentum_window * 60)
            self._price_history[symbol] = [
                h for h in history if h["time"] >= cutoff_time
            ]

            # Calculate momentum from price movements
            history = self._price_history[symbol]
            momentum_up_pct = 50.0  # Default neutral

            if len(history) >= 2:
                # Count up vs down moves in the history
                up_moves = 0
                total_moves = 0

                for i in range(1, len(history)):
                    prev_price = history[i-1]["price"]
                    curr_price = history[i]["price"]

                    if prev_price != curr_price:
                        total_moves += 1
                        if curr_price > prev_price:
                            up_moves += 1

                if total_moves > 0:
                    momentum_up_pct = (up_moves / total_moves) * 100

            # Log price fetch success
            direction = "🔴 DOWN" if momentum_up_pct < 50 else "🟢 UP" if momentum_up_pct > 50 else "🟡 NEUTRAL"
            logger.info(f"[{symbol}] ${current_price:.2f} | {direction} ({momentum_up_pct:.1f}%) | {len(history)} candles | 24h change: {price_change_24h:.2f}%")

            # Emit price update event
            event = PriceUpdateEvent(
                symbol=symbol,
                price=current_price,
                volume_24h=0.0,
                price_change_24h=price_change_24h,
                momentum_up_pct=round(momentum_up_pct, 2),
                momentum_window_minutes=self.momentum_window,
                candles_analyzed=len(history),
                trend_confirmed=False,  # CoinGecko doesn't provide OHLC data on free tier
            )

            await self.publish(event)

        except Exception as e:
            error_msg = str(e)
            if "Circuit breaker is open" in error_msg:
                logger.warning(f"[{symbol}] Cannot fetch - Circuit breaker recovering. Retrying in {self.poll_interval}s")
            else:
                logger.error(f"[{symbol}] Error: {error_msg[:200]}")
