#!/usr/bin/env python3
"""
Kalshi Data Collector - Stores real-time Kalshi prices for backtesting.

Run this continuously to build a historical dataset:
    python collect_kalshi_data.py

Data is saved to logs/kalshi_history_{date}.jsonl
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import httpx

import config


class KalshiDataCollector:
    """Collects and stores Kalshi market data for backtesting."""

    def __init__(self, output_dir: Path = config.LOG_DIR):
        self.base_url = config.KALSHI_API_URL
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval = 60  # seconds between polls
        self.series = config.KALSHI_CRYPTO_SERIES

    def _get_output_file(self) -> Path:
        """Get output file for today's date."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.output_dir / f"kalshi_history_{date_str}.jsonl"

    async def fetch_markets(self, series_ticker: str) -> List[Dict[str, Any]]:
        """Fetch all open markets for a series."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/markets",
                params={"series_ticker": series_ticker, "status": "open", "limit": 100}
            )
            if resp.status_code == 200:
                return resp.json().get("markets", [])
            return []

    def parse_market(self, market: Dict[str, Any], series: str) -> Dict[str, Any]:
        """Parse market data into storage format."""
        return {
            "timestamp": datetime.now().isoformat(),
            "ticker": market.get("ticker", ""),
            "series": series,
            "title": market.get("title", ""),
            "yes_ask": market.get("yes_ask", 0),
            "yes_bid": market.get("yes_bid", 0),
            "no_ask": market.get("no_ask", 0),
            "no_bid": market.get("no_bid", 0),
            "last_price": market.get("last_price", 0),
            "volume": market.get("volume", 0),
            "open_interest": market.get("open_interest", 0),
            "expiration": market.get("expiration_time") or market.get("close_time"),
        }

    async def collect_once(self) -> int:
        """Collect data once for all series. Returns count of markets saved."""
        output_file = self._get_output_file()
        count = 0

        with open(output_file, "a") as f:
            for series in self.series:
                try:
                    markets = await self.fetch_markets(series)
                    for market in markets:
                        data = self.parse_market(market, series)
                        f.write(json.dumps(data) + "\n")
                        count += 1
                except Exception as e:
                    print(f"[Collector] Error fetching {series}: {e}")

        return count

    async def run(self):
        """Run continuous data collection."""
        print(f"[Collector] Starting Kalshi data collection")
        print(f"[Collector] Series: {self.series}")
        print(f"[Collector] Poll interval: {self.poll_interval}s")
        print(f"[Collector] Output: {self.output_dir}")
        print()

        while True:
            try:
                count = await self.collect_once()
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] Collected {count} markets")
            except Exception as e:
                print(f"[Collector] Error: {e}")

            await asyncio.sleep(self.poll_interval)


async def main():
    collector = KalshiDataCollector()
    await collector.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Collector] Stopped")
