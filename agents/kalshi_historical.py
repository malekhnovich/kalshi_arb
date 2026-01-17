"""
Kalshi Historical Data Client - Fetches historical candlesticks and trades for backtesting.

Requires API credentials set via environment variables:
    KALSHI_API_KEY - Your Kalshi API key ID
    KALSHI_PRIVATE_KEY_PATH - Path to your RSA private key file
"""

import asyncio
import base64
import logging
import time
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx

import config

# Configure logger with file, line, and time
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(filename)s:%(lineno)d | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Try to import cryptography for RSA signing
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class KalshiAuthenticator:
    """Handles RSA-PSS authentication for Kalshi API."""

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = None

        if private_key_path and Path(private_key_path).exists():
            self._load_private_key(private_key_path)

    def _load_private_key(self, path: str) -> None:
        """Load RSA private key from PEM file."""
        if not HAS_CRYPTO:
            logger.warning("cryptography package not installed, auth disabled")
            return

        try:
            with open(path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
            logger.info("Private key loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")

    def get_auth_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate authentication headers for a request."""
        if not self.api_key or not self.private_key:
            return {}

        timestamp = str(int(time.time() * 1000))

        # Remove query params from path for signing
        sign_path = path.split("?")[0]

        # Create message to sign: timestamp + method + path
        message = f"{timestamp}{method.upper()}{sign_path}"

        # Sign with RSA-PSS SHA-256
        signature = self.private_key.sign(
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        }


class KalshiHistoricalClient:
    """
    Client for fetching historical Kalshi data.

    Provides access to:
    - Market candlesticks (OHLC data)
    - Historical trades
    - Settled markets for backtesting
    """

    def __init__(
        self,
        base_url: str = config.KALSHI_API_URL,
        api_key: str = config.KALSHI_API_KEY,
        private_key_path: str = config.KALSHI_PRIVATE_KEY_PATH,
    ):
        self.base_url = base_url
        self.timeout = 30.0
        self.auth = KalshiAuthenticator(api_key, private_key_path)
        # Use a semaphore to respect total concurrency limits if needed
        # But we mostly care about the rate (req/s)
        self._rate_limiter = asyncio.Semaphore(config.KALSHI_READ_LIMIT_PER_SECOND)
        self._last_request_times: List[float] = []

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Kalshi API with basic rate limiting."""
        url = f"{self.base_url}{endpoint}"
        headers = self.auth.get_auth_headers(method, endpoint)
        print(f"Making request: {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Simple sliding window rate limit (very basic)
                now = time.time()
                self._last_request_times = [
                    t for t in self._last_request_times if now - t < 1.0
                ]
                if len(self._last_request_times) >= config.KALSHI_READ_LIMIT_PER_SECOND:
                    wait_time = 1.1 - (now - self._last_request_times[0])
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

                self._last_request_times.append(time.time())

                if method.upper() == "GET":
                    resp = await client.get(url, params=params, headers=headers)
                else:
                    resp = await client.request(
                        method, url, params=params, headers=headers
                    )

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    if retry_count >= 3:
                        logger.error(f"Rate limit hit max retries for {endpoint}")
                        return None

                    logger.warning(
                        f"Rate limit hit! Backing off... (attempt {retry_count + 1})"
                    )
                    await asyncio.sleep(1.0 * (retry_count + 1))
                    return await self._request(
                        method, endpoint, params, retry_count + 1
                    )
                else:
                    logger.warning(
                        f"{endpoint} returned {resp.status_code}: {resp.text[:200]}"
                    )
                    return None

            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None

    async def get_candlesticks(
        self,
        series_ticker: str,
        market_ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 1,  # 1, 60, or 1440 minutes
    ) -> List[Dict[str, Any]]:
        """
        Fetch candlestick data for a market.

        Args:
            series_ticker: Series identifier (e.g., "KXBTC")
            market_ticker: Market ticker (e.g., "KXBTC-26JAN14-T95000")
            start_ts: Start timestamp (unix seconds)
            end_ts: End timestamp (unix seconds)
            period_interval: Candle period in minutes (1, 60, or 1440)

        Returns:
            List of candlestick dicts with yes_bid, yes_ask, price OHLC, volume
        """
        endpoint = f"/series/{series_ticker}/markets/{market_ticker}/candlesticks"
        params = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
        }

        data = await self._request("GET", endpoint, params)
        if data:
            return data.get("candlesticks", [])
        return []

    async def get_trades(
        self,
        ticker: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical trades.

        Args:
            ticker: Filter by market ticker
            min_ts: Minimum timestamp (unix seconds)
            max_ts: Maximum timestamp (unix seconds)
            limit: Max results per page (1-1000)

        Returns:
            List of trade dicts with yes_price, no_price, count, created_time
        """
        endpoint = "/markets/trades"
        params = {"limit": limit}

        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts

        all_trades = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            data = await self._request("GET", endpoint, params)
            if not data:
                break

            trades = data.get("trades", [])
            all_trades.extend(trades)

            cursor = data.get("cursor")
            if not cursor or len(trades) < limit:
                break

            # Rate limiting is now handled in _request
        return all_trades

    async def get_events(
        self,
        series_ticker: Optional[str] = None,
        status: str = "settled",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events (groups of related markets).

        Args:
            series_ticker: Filter by series (e.g., "KXBTC")
            status: Event status filter (unopened, open, closed, settled)
            limit: Max results

        Returns:
            List of event dicts
        """
        endpoint = "/events"
        params = {"status": status, "limit": limit}

        if series_ticker:
            params["series_ticker"] = series_ticker

        data = await self._request("GET", endpoint, params)
        if data:
            return data.get("events", [])
        return []

    async def get_markets(
        self,
        series_ticker: Optional[str] = None,
        status: str = "settled",
        limit: int = 100,
        max_close_ts: int = int(
            (datetime.today() - timedelta(days=1)).timestamp() * 1000
        ),
        min_close_ts: int = int(
            (datetime.today() - timedelta(days=7)).timestamp() * 1000
        ),
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets with optional filters.

        Args:
            series_ticker: Filter by series
            status: Market status (open, closed, settled)
            limit: Max results

        Returns:
            List of market dicts
        """
        endpoint = "/markets"
        params = {"status": status, "limit": limit}
        if max_close_ts:
            params["max_close_ts"] = max_close_ts
        if min_close_ts:
            params["min_close_ts"] = min_close_ts
        if series_ticker:
            params["series_ticker"] = series_ticker

        all_markets = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            data = await self._request("GET", endpoint, params)
            if not data:
                break

            markets = data.get("markets", [])
            all_markets.extend(markets)

            cursor = data.get("cursor")
            if not cursor or len(markets) <= limit:
                break

            # Rate limiting is now handled in _request
        return all_markets

    async def get_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch a single market by ticker."""
        endpoint = f"/markets/{ticker}"
        data = await self._request("GET", endpoint)
        if data:
            return data.get("market")
        return None


async def test_client():
    """Test the historical client."""
    client = KalshiHistoricalClient()

    print("Testing Kalshi Historical Client...")
    print()

    # Test getting settled markets
    print("Fetching settled KXBTC markets...")
    markets = await client.get_markets(series_ticker="KXBTC", status="settled", limit=5)
    print(f"Found {len(markets)} settled markets")

    if markets:
        market = markets[0]
        print(f"\nFirst market: {market.get('ticker')}")
        print(f"Title: {market.get('title')}")
        print(f"Result: {market.get('result')}")

        # Try to get candlesticks for this market
        ticker = market.get("ticker", "")
        if ticker:
            print(f"\nFetching candlesticks for {ticker}...")
            now = int(time.time())
            week_ago = now - (7 * 24 * 60 * 60)

            candles = await client.get_candlesticks(
                series_ticker="KXBTC",
                market_ticker=ticker,
                start_ts=week_ago,
                end_ts=now,
                period_interval=60,
            )
            print(f"Found {len(candles)} candlesticks")

            if candles:
                c = candles[0]
                print(
                    f"Sample candle: ts={c.get('end_period_ts')}, vol={c.get('volume')}"
                )


if __name__ == "__main__":
    asyncio.run(test_client())
