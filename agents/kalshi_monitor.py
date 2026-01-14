"""
Kalshi Monitor Agent - Tracks Kalshi prediction market odds for crypto events.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx

from .base import BaseAgent, retry_with_backoff, CircuitBreaker
from events import EventBus, KalshiOddsEvent
import config


class ResilientHttpClient:
    """
    Async HTTP client with retry logic, rate limiting, and circuit breaker.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        max_retries: int = 3,
        rate_limit_delay: float = 0.2,
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
                base_delay=1.0,
                max_delay=15.0,
            )
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            raise


class KalshiClient:
    """Async HTTP client for Kalshi API with resilience"""

    def __init__(self, base_url: str = config.KALSHI_API_URL):
        self._client = ResilientHttpClient(
            base_url=base_url,
            timeout=15.0,
            max_retries=3,
            rate_limit_delay=0.2,  # Conservative rate limiting for Kalshi
        )

    async def get_markets(
        self,
        series_ticker: Optional[str] = None,
        status: str = "open",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets from Kalshi.

        Args:
            series_ticker: Filter by series (e.g., "KXBTC" for Bitcoin)
            status: Market status filter ("open", "closed", etc.)
            limit: Max number of markets to return
        """
        params = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker

        try:
            data = await self._client.get("/markets", params=params)
            return data.get("markets", [])
        except Exception as e:
            print(f"[KalshiClient] Error fetching markets: {e}")
            return []

    async def get_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific market by ticker"""
        try:
            data = await self._client.get(f"/markets/{ticker}")
            return data.get("market")
        except Exception:
            return None


class KalshiMonitorAgent(BaseAgent):
    """
    Monitors Kalshi crypto prediction markets.

    Tracks markets related to cryptocurrency price predictions
    (e.g., "Will BTC be above $100k by end of month?").
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("KalshiMonitor", event_bus)
        self.client = KalshiClient()
        self.poll_interval = config.POLL_INTERVAL_KALSHI
        self.crypto_series = config.KALSHI_CRYPTO_SERIES
        self._last_markets: Dict[str, Dict] = {}

    async def run(self) -> None:
        """Poll Kalshi markets and emit events"""
        for series in self.crypto_series:
            await self._fetch_and_emit_series(series)

        await asyncio.sleep(self.poll_interval)

    async def _fetch_and_emit_series(self, series_ticker: str) -> None:
        """Fetch markets for a series and emit events"""
        try:
            markets = await self.client.get_markets(
                series_ticker=series_ticker,
                status="open"
            )

            for market in markets:
                await self._process_market(market, series_ticker)

        except Exception as e:
            print(f"[{self.name}] Error fetching series {series_ticker}: {e}")

    async def _process_market(
        self, market: Dict[str, Any], series_ticker: str
    ) -> None:
        """Process a market and emit an odds event"""
        ticker = market.get("ticker", "")
        if not ticker:
            return

        # Extract pricing - Kalshi uses cents (0-100)
        yes_price = market.get("yes_ask", 50)  # Default to 50 if not available
        no_price = market.get("no_ask", 50)

        # Try to get last traded prices as fallback
        if yes_price == 0:
            yes_price = market.get("last_price", 50)
        if no_price == 0:
            no_price = 100 - yes_price

        # Parse expiration
        expiration = None
        exp_str = market.get("expiration_time") or market.get("close_time")
        if exp_str:
            try:
                expiration = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Determine underlying symbol from series
        underlying = self._extract_underlying(series_ticker)

        event = KalshiOddsEvent(
            market_ticker=ticker,
            market_title=market.get("title", ""),
            yes_price=float(yes_price),
            no_price=float(no_price),
            volume=int(market.get("volume", 0)),
            open_interest=int(market.get("open_interest", 0)),
            underlying_symbol=underlying,
            strike_price=self._extract_strike_price(market),
            expiration=expiration
        )

        await self.publish(event)

    def _extract_underlying(self, series_ticker: str) -> str:
        """Extract the underlying asset symbol from series ticker"""
        # KXBTC -> BTC, KXETH -> ETH, KXSOL -> SOL
        if series_ticker.startswith("KX"):
            return series_ticker[2:]
        return series_ticker

    def _extract_strike_price(self, market: Dict[str, Any]) -> Optional[float]:
        """Try to extract strike price from market title or metadata"""
        title = market.get("title", "")
        # Try to parse price from title like "Bitcoin above $100,000?"
        import re
        match = re.search(r'\$([0-9,]+(?:\.[0-9]+)?)', title)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None
