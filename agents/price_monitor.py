"""
Price Monitor Agent - Tracks Binance.US prices and calculates momentum.
"""

import asyncio
from typing import Dict, List, Any, Optional

import httpx

from .base import BaseAgent, retry_with_backoff, CircuitBreaker
from events import EventBus, PriceUpdateEvent
import config


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
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self._circuit_breaker = CircuitBreaker(failure_threshold=5)
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
            raise Exception("Circuit breaker is open")

        await self._rate_limit()

        async def _do_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    params=params or {}
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
            raise


class BinanceClient:
    """Async HTTP client for Binance.US API with resilience"""

    def __init__(self, base_url: str = config.BINANCE_US_API_URL):
        self._client = ResilientHttpClient(
            base_url=base_url,
            timeout=10.0,
            max_retries=3,
            rate_limit_delay=0.05,  # Binance allows ~1200 req/min
        )

    async def get_klines(
        self, symbol: str, interval: str = "1m", limit: int = 60
    ) -> List[List]:
        """Fetch candlestick data"""
        return await self._client.get(
            "/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit}
        )

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch 24hr ticker data"""
        return await self._client.get(
            "/ticker/24hr",
            params={"symbol": symbol}
        )


class PriceMonitorAgent(BaseAgent):
    """
    Monitors Binance.US prices for configured symbols.

    Polls at regular intervals and calculates momentum based on
    the percentage of up vs down candles in the analysis window.
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("PriceMonitor", event_bus)
        self.client = BinanceClient()
        self.symbols = config.BINANCE_SYMBOLS
        self.poll_interval = config.POLL_INTERVAL_BINANCE
        self.momentum_window = config.MOMENTUM_WINDOW

    async def run(self) -> None:
        """Poll prices for all symbols and emit events"""
        tasks = [self._fetch_and_emit(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(self.poll_interval)

    async def _fetch_and_emit(self, symbol: str) -> None:
        """Fetch price data for a symbol and emit event"""
        try:
            # Fetch candles for momentum analysis
            klines = await self.client.get_klines(
                symbol, "1m", min(self.momentum_window, 1000)
            )

            if not klines:
                return

            # Calculate hybrid momentum: combines simple count with volume weighting
            # This avoids edge cases where low volatility gives 0% momentum
            simple_up = 0
            weighted_up = 0.0
            weighted_down = 0.0

            for k in klines:
                open_price = float(k[1])
                close_price = float(k[4])
                volume = float(k[5])

                is_up = close_price >= open_price
                if is_up:
                    simple_up += 1

                # Calculate magnitude as % move, weighted by volume
                if open_price > 0 and volume > 0:
                    magnitude = abs(close_price - open_price) / open_price
                    weight = volume * (magnitude + 0.0001)  # Small floor to avoid zero

                    if is_up:
                        weighted_up += weight
                    else:
                        weighted_down += weight

            total_candles = len(klines)
            total_weight = weighted_up + weighted_down

            # Hybrid: 70% volume-weighted + 30% simple count
            simple_pct = (simple_up / total_candles * 100) if total_candles > 0 else 50
            volume_pct = (weighted_up / total_weight * 100) if total_weight > 0 else 50
            momentum_up_pct = 0.7 * volume_pct + 0.3 * simple_pct

            # Calculate price trend confirmation (higher highs/lows)
            prices = [float(k[4]) for k in klines]
            trend_confirmed = False
            if len(prices) >= 20:
                recent_high = max(prices[-10:])
                older_high = max(prices[-20:-10])
                recent_low = min(prices[-10:])
                older_low = min(prices[-20:-10])

                uptrend = recent_high > older_high and recent_low > older_low
                downtrend = recent_high < older_high and recent_low < older_low
                trend_confirmed = (momentum_up_pct >= 60 and uptrend) or (momentum_up_pct <= 40 and downtrend)

            # Get latest price and 24h stats
            ticker = await self.client.get_ticker(symbol)

            event = PriceUpdateEvent(
                symbol=symbol,
                price=float(ticker.get("lastPrice", 0)),
                volume_24h=float(ticker.get("volume", 0)),
                price_change_24h=float(ticker.get("priceChangePercent", 0)),
                momentum_up_pct=round(momentum_up_pct, 2),
                momentum_window_minutes=self.momentum_window,
                candles_analyzed=total_candles,
                trend_confirmed=trend_confirmed
            )

            await self.publish(event)

        except httpx.HTTPError as e:
            print(f"[{self.name}] HTTP error fetching {symbol}: {e}")
        except Exception as e:
            print(f"[{self.name}] Error processing {symbol}: {e}")
