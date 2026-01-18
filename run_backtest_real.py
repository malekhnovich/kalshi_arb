#!/usr/bin/env python3
"""
Backtest with Real Kalshi Data

Uses actual Kalshi market candlestick data instead of simulated odds.

Requirements:
    - KALSHI_API_KEY environment variable
    - KALSHI_PRIVATE_KEY_PATH environment variable (path to RSA private key)
    - pip install cryptography

Usage:
    python run_backtest_real.py --symbol BTCUSDT --days 7
    python run_backtest_real.py --symbol BTCUSDT --start 2026-01-01 --end 2026-01-14
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import httpx

import config
import strategies
from cache import get_cache
from agents.kalshi_historical import KalshiHistoricalClient

# Configure logger with file, line, and time
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(filename)s:%(lineno)d | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a backtest trade."""

    timestamp: datetime
    symbol: str
    direction: str  # "YES" or "NO"
    entry_price: float  # cents
    market_ticker: str
    confidence: float
    spot_momentum: float
    resolved: bool = False
    exit_price: Optional[float] = None
    pnl: float = 0.0
    market_result: Optional[str] = None  # "yes" or "no"


@dataclass
class BacktestResult:
    """Results from backtest."""

    start_time: datetime
    end_time: datetime
    symbol: str
    kalshi_markets_used: int = 0
    kalshi_candles_loaded: int = 0
    total_signals: int = 0
    trades_taken: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0
    trades: List[Trade] = field(default_factory=list)


class RealKalshiBacktester:
    """Backtester using real Kalshi historical data."""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        initial_capital: float = 10000.0,
        trading_fee_rate: float = 0.03,  # 3% estimate (Kalshi taker fees + slippage)
    ):
        self.symbol = symbol
        self.start_date = start_date or (datetime.now() - timedelta(days=7))
        self.end_date = end_date or datetime.now()
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trading_fee_rate = trading_fee_rate

        # Clients
        self.kalshi_client = KalshiHistoricalClient()

        # Trading settings
        self.trade_size = 100.0
        self.min_confidence = 70.0
        self.max_open_trades = 3
        self.confidence_threshold = config.CONFIDENCE_THRESHOLD

        # State
        self.trades: List[Trade] = []
        self.open_trades: List[Trade] = []
        self.signals_count = 0

        # Data storage
        self.binance_klines: List[List] = []
        self.kalshi_candles: Dict[int, Dict] = {}  # timestamp -> candle data
        self.kalshi_markets: List[Dict] = []

    async def load_binance_data(self) -> bool:
        """Load historical Binance klines."""
        cache = get_cache()
        current_start = int(self.start_date.timestamp() * 1000)
        end_ms = int(self.end_date.timestamp() * 1000)

        # Check cache first
        logger.info(f"Checking cache for Binance data ({self.symbol})...")
        cached_klines = cache.get_binance_klines(self.symbol, current_start, end_ms)

        expected_minutes = (end_ms - current_start) / 60000
        coverage = len(cached_klines) / expected_minutes if expected_minutes > 0 else 0

        if coverage > 0.95:
            logger.info(
                f"Found {len(cached_klines)} candles in cache ({coverage:.1%}). Using cached data."
            )
            self.binance_klines = cached_klines
            return True  # Exit early if sufficient cache coverage

        logger.info(f"Fetching Binance data for {self.symbol}...")
        print(f"  Progress: Fetching Binance data for {self.symbol}...", flush=True)
        all_klines = []

        async with httpx.AsyncClient(timeout=30) as client:
            while current_start < end_ms:
                params = {
                    "symbol": self.symbol,
                    "interval": "1m",
                    "startTime": current_start,
                    "endTime": end_ms,
                    "limit": 1000,
                }

                try:
                    resp = await client.get(
                        f"{config.BINANCE_US_API_URL}/klines", params=params
                    )
                    resp.raise_for_status()
                    klines = resp.json()

                    if not klines:
                        break

                    all_klines.extend(klines)
                    current_start = klines[-1][6] + 1

                except Exception as e:
                    logger.error(f"Error fetching Binance data: {e}")
                    break

        self.binance_klines = all_klines

        if all_klines:
            logger.info(f"Saving {len(all_klines)} candles to cache...")
            cache.save_binance_klines(self.symbol, all_klines)

        logger.info(f"Loaded {len(self.binance_klines)} Binance candles")
        return len(self.binance_klines) > 0

    async def load_kalshi_data(self) -> bool:
        """Load historical Kalshi market data."""
        # Map Binance symbol to Kalshi series
        symbol_to_series = {
            "BTCUSDT": "KXBTC",
            "ETHUSDT": "KXETH",
            "SOLUSDT": "KXSOL",
        }
        series = symbol_to_series.get(self.symbol, "KXBTC")
        start_ts = int(self.start_date.timestamp())
        end_ts = int(self.end_date.timestamp())

        logger.info(f"Fetching Kalshi {series} markets...")

        # Get settled markets for this series
        # Fetch both settled and open markets to maximize data
        settled_markets = await self.kalshi_client.get_markets(
            series_ticker=series, status="settled", limit=200
        )
        open_markets = await self.kalshi_client.get_markets(
            series_ticker=series, status="open", limit=200
        )

        # Combine and remove duplicates (though unlikely for different statuses)
        self.kalshi_markets = {
            m["ticker"]: m for m in settled_markets + open_markets
        }.values()
        self.kalshi_markets = list(self.kalshi_markets)

        logger.info(f"Found {len(self.kalshi_markets)} settled markets")

        if not self.kalshi_markets:
            # Try open markets as fallback
            logger.info("Trying open markets...")
            self.kalshi_markets = await self.kalshi_client.get_markets(
                series_ticker=series,
                status="open",
                limit=50,
            )
            logger.info(f"Found {len(self.kalshi_markets)} open markets")

        if not self.kalshi_markets:
            logger.warning("No Kalshi markets found")
            return False

        # Filter out low volume markets to save time and avoid noise, and markets outside time range
        original_count = len(self.kalshi_markets)

        def get_market_open_ts(market: Dict) -> int:
            """Parse market open_time ISO string to unix timestamp in seconds."""
            open_time = market.get("open_time")
            if not open_time:
                return 0
            try:
                # Handle ISO format like "2023-11-07T05:31:56Z"
                dt = datetime.fromisoformat(open_time.replace("Z", "+00:00"))
                return int(dt.timestamp())
            except (ValueError, AttributeError):
                return 0

        self.kalshi_markets = [
            m
            for m in self.kalshi_markets
            if m.get("volume", 0) >= config.BACKTEST_MIN_VOLUME_THRESHOLD
            and start_ts <= get_market_open_ts(m) < end_ts
        ]
        if len(self.kalshi_markets) < original_count:
            logger.info(
                f"Filtered out {original_count - len(self.kalshi_markets)} low-volume or out-of-range markets"
            )
        if len(self.kalshi_markets) == 0:
            logger.warning("No Kalshi markets left after filtering.")
            exit(0)

        # Check cache for these specific markets
        cache = get_cache()
        market_tickers = [m["ticker"] for m in self.kalshi_markets]
        logger.info(f"Checking cache for {len(market_tickers)} markets...")

        cached_candles = cache.get_kalshi_candles(market_tickers, start_ts, end_ts)
        if cached_candles and len(cached_candles) > 0:
            # Check if cached data covers a significant portion of the requested period
            # A simple heuristic: if we have more than 10% of the expected candles
            if len(cached_candles) / (end_ts - start_ts) > 0.1:
                self.kalshi_candles = {
                    ts: [data]  # Ensure it's a list of dicts for consistency
                    for ts_list in cached_candles.values()
                    for ts, data in ts_list.items()
                }  # Flatten for easier lookup
                return True
            else:
                logger.info("Cache coverage too low, fetching fresh data...")

        # Load candlesticks for each market
        total_candles = 0
        market_results = {m.get("ticker"): m.get("result") for m in self.kalshi_markets}

        # Fetch candlesticks
        logger.info(f"Fetching candlesticks for {series} series...")

        # Use asyncio.gather to fetch candles for multiple markets concurrently
        # but respect the KALSHI_READ_LIMIT_PER_SECOND

        async def fetch_market_candles(market_idx, market_data):
            ticker = market_data["ticker"]
            if market_idx % 5 == 0:
                logger.info(
                    f"Fetching candles for market {market_idx + 1}/{len(self.kalshi_markets)}: {ticker}"
                )
                print(
                    f"  Progress: {market_idx + 1}/{len(self.kalshi_markets)} markets...",
                    flush=True,
                )

            try:
                # Use the market's actual open/close time, not full backtest range
                # Markets typically only exist for 1 hour
                market_open = market_data.get("open_time")
                market_close = market_data.get("close_time")

                if market_open and market_close:
                    try:
                        market_start = int(
                            datetime.fromisoformat(
                                market_open.replace("Z", "+00:00")
                            ).timestamp()
                        )
                        market_end = int(
                            datetime.fromisoformat(
                                market_close.replace("Z", "+00:00")
                            ).timestamp()
                        )
                        # Clamp to our backtest period
                        req_start = max(start_ts, market_start)
                        req_end = min(end_ts, market_end)
                    except (ValueError, AttributeError):
                        req_start, req_end = start_ts, end_ts
                else:
                    req_start, req_end = start_ts, end_ts

                # Skip if market time range doesn't overlap with backtest period
                if req_start >= req_end:
                    return []

                # Chunk requests to stay under 5000 candle limit if needed
                # 3 days of 1-min candles = 4320 < 5000
                chunk_seconds = 3 * 24 * 60 * 60  # 3 days in seconds
                all_candles = []
                chunk_start = req_start

                while chunk_start < req_end:
                    chunk_end = min(chunk_start + chunk_seconds, req_end)

                    candles = await asyncio.wait_for(
                        self.kalshi_client.get_candlesticks(
                            series_ticker=series,
                            market_ticker=ticker,
                            start_ts=chunk_start,
                            end_ts=chunk_end,
                            period_interval=1,
                        ),
                        timeout=15.0,
                    )
                    all_candles.extend(candles)
                    chunk_start = chunk_end

                processed_candles = []
                for candle in all_candles:
                    ts = candle.get("end_period_ts")
                    if not ts:
                        continue

                    # Align timestamp: Kalshi returns end of period, Binance uses start
                    # Subtract 60s to match Binance Open Time
                    ts = ts - 60

                    # Extract yes_price from candle data
                    # Priority: yes_bid.close (what you'd pay), then price.close, then default
                    yes_price = 50.0
                    yes_bid = candle.get("yes_bid")
                    yes_ask = candle.get("yes_ask")
                    price_data = candle.get("price")

                    if yes_bid and isinstance(yes_bid, dict):
                        bid_close = yes_bid.get("close")
                        if bid_close is not None:
                            yes_price = float(bid_close)
                    elif yes_ask and isinstance(yes_ask, dict):
                        ask_close = yes_ask.get("close")
                        if ask_close is not None:
                            yes_price = float(ask_close)
                    elif price_data and isinstance(price_data, dict):
                        price_close = price_data.get("close")
                        if price_close is not None:
                            yes_price = float(price_close)

                    no_price = 100.0 - yes_price

                    processed_candles.append(
                        (
                            ts,
                            {
                                "yes_price": yes_price,
                                "no_price": no_price,
                                "market_ticker": ticker,
                                "market_result": market_results.get(ticker),
                            },
                        )
                    )
                return processed_candles
            except asyncio.TimeoutError:
                print(f"  Warning: Timeout fetching {ticker}", flush=True)
                return []
            except Exception as e:
                print(f"  Error fetching {ticker}: {e}", flush=True)
                return []

        tasks = [
            fetch_market_candles(i, market)
            for i, market in enumerate(self.kalshi_markets)
        ]
        all_processed_candles = await asyncio.gather(*tasks)

        for market_candles in all_processed_candles:
            for ts, candle_data in market_candles:
                if ts not in self.kalshi_candles:
                    self.kalshi_candles[ts] = []
                self.kalshi_candles[ts].append(candle_data)
                total_candles += 1

        if self.kalshi_candles:
            logger.info(f"Saving {total_candles} Kalshi candles to cache...")
            cache.save_kalshi_candles(self.kalshi_candles)

        logger.info(f"Loaded {total_candles} Kalshi candles")
        return total_candles > 0

    def get_kalshi_at_time(self, timestamp: datetime) -> Optional[Dict]:
        """Get Kalshi trade data closest to given timestamp."""
        ts = int(timestamp.timestamp())

        # Kalshi timestamps are end_period_ts, so we need to find the candle that *covers* this timestamp.
        # Binance klines are open_time. So if Binance kline is at T, we need Kalshi candle for T to T+59s.
        # Our stored Kalshi candles are (end_period_ts - 60), meaning they represent the start of the minute.
        # So we look for a Kalshi candle whose start_ts matches the Binance kline's open_time.

        # Round Binance timestamp down to the minute for lookup
        binance_open_ts_minute = ts - (ts % 60)

        # Find the closest Kalshi candle. We prioritize exact match, then look nearby.
        # This is a simplified lookup. A more robust solution might involve interpolation
        # or finding the candle whose time range [start_ts, end_ts] contains the target ts.

        # For now, let's assume our `kalshi_candles` dict keys are the start_ts of the minute.
        # We want the candle that started at `binance_open_ts_minute`.

        # We need to find the *most recent* Kalshi candle that is <= `binance_open_ts_minute`
        # This is because Kalshi data might not be perfectly aligned or continuous.

        # Find all Kalshi candles that are available up to the current Binance timestamp
        available_kalshi_candles = {
            k: v for k, v in self.kalshi_candles.items() if k <= binance_open_ts_minute
        }

        if not available_kalshi_candles:
            return None

        # Get the latest available candle(s)
        latest_kalshi_ts = max(available_kalshi_candles.keys())
        candidates = available_kalshi_candles[latest_kalshi_ts]

        # If multiple markets active, pick the one with price closest to 50c
        # This assumes the "active" market is the one being contested
        if isinstance(candidates, list):
            best_market = min(
                candidates, key=lambda x: abs(x.get("yes_price", 50) - 50)
            )
            return best_market
        return candidates

    def calculate_momentum(self, klines: List[List]) -> tuple[float, bool]:
        """Calculate hybrid momentum and trend confirmation."""
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

            if open_price > 0 and volume > 0:
                magnitude = abs(close_price - open_price) / open_price
                weight = volume * (magnitude + 0.0001)

                if is_up:
                    weighted_up += weight
                else:
                    weighted_down += weight

        total = len(klines)
        total_weight = weighted_up + weighted_down

        simple_pct = (simple_up / total * 100) if total > 0 else 50
        volume_pct = (weighted_up / total_weight * 100) if total_weight > 0 else 50
        momentum = 0.7 * volume_pct + 0.3 * simple_pct

        # Trend confirmation
        prices = [float(k[4]) for k in klines]
        trend_confirmed = False
        if len(prices) >= 20:
            recent_high = max(prices[-10:])
            older_high = max(prices[-20:-10])
            recent_low = min(prices[-10:])
            older_low = min(prices[-20:-10])

            uptrend = recent_high > older_high and recent_low > older_low
            downtrend = recent_high < older_high and recent_low < older_low
            trend_confirmed = (momentum >= 60 and uptrend) or (
                momentum <= 40 and downtrend
            )

        return momentum, trend_confirmed

    def calculate_volatility(self, klines: List[List]) -> float:
        """Calculate volatility as standard deviation of returns."""
        if len(klines) < 2:
            return 0.0

        returns = []
        for i in range(1, len(klines)):
            prev_close = float(klines[i - 1][4])
            curr_close = float(klines[i][4])
            if prev_close > 0:
                returns.append((curr_close - prev_close) / prev_close)

        if not returns:
            return 0.0

        return float(np.std(returns))

    def calculate_momentum_acceleration(
        self, klines: List[List], window: int = 10
    ) -> tuple[float, float, bool]:
        """
        Calculate momentum and whether it's accelerating.
        Returns (current_momentum, previous_momentum, is_accelerating).
        """
        if len(klines) < window * 2:
            return 50.0, 50.0, True  # Default to no filtering

        # Recent window momentum
        recent = klines[-window:]
        recent_momentum, _ = self.calculate_momentum(recent)

        # Previous window momentum
        previous = klines[-window * 2 : -window]
        prev_momentum, _ = self.calculate_momentum(previous)

        # Accelerating if momentum is moving further from 50 in the same direction
        if recent_momentum >= 50:
            is_accelerating = recent_momentum >= prev_momentum
        else:
            is_accelerating = recent_momentum <= prev_momentum

        return recent_momentum, prev_momentum, is_accelerating

    def check_pullback(
        self, klines: List[List], direction: str, threshold: float = 0.3
    ) -> bool:
        """
        Check if price has pulled back from recent extreme.
        For UP signals: price should have pulled back from recent high.
        For DOWN signals: price should have pulled back from recent low.
        """
        if len(klines) < 10:
            return True  # Not enough data, allow trade

        recent_prices = [float(k[4]) for k in klines[-10:]]
        current_price = recent_prices[-1]

        if direction == "UP":
            recent_high = max(recent_prices[:-1])  # Exclude current
            if recent_high > 0:
                pullback_pct = (recent_high - current_price) / recent_high * 100
                return pullback_pct >= threshold
        else:
            recent_low = min(recent_prices[:-1])  # Exclude current
            if recent_low > 0:
                pullback_pct = (current_price - recent_low) / recent_low * 100
                return pullback_pct >= threshold

        return True

    def calculate_multiframe_momentum(self, klines: List[List], period: int = 5) -> float:
        """
        Calculate momentum on aggregated candles (e.g., 5-min from 1-min data).
        """
        if len(klines) < period * 4:  # Need at least 4 aggregated candles
            return 50.0

        # Aggregate 1-min candles into larger period candles
        aggregated = []
        for i in range(0, len(klines) - period + 1, period):
            chunk = klines[i : i + period]
            if len(chunk) == period:
                agg_candle = [
                    chunk[0][0],  # Open time
                    chunk[0][1],  # Open price
                    max(float(k[2]) for k in chunk),  # High
                    min(float(k[3]) for k in chunk),  # Low
                    chunk[-1][4],  # Close price
                    sum(float(k[5]) for k in chunk),  # Volume
                ]
                aggregated.append(agg_candle)

        if len(aggregated) < 4:
            return 50.0

        momentum, _ = self.calculate_momentum(aggregated[-20:])
        return momentum

    def check_signal(
        self,
        momentum: float,
        trend_confirmed: bool,
        kalshi_yes: float,
        market_ticker: str = "",
    ) -> Optional[tuple[str, float, float]]:
        """Check if conditions warrant a signal."""
        # Use market-specific threshold (65% for 15-min, 70% for hourly)
        market_threshold = strategies.get_momentum_threshold_for_market(market_ticker)
        strong_up = momentum >= market_threshold
        strong_down = momentum <= (100 - market_threshold)

        if not (strong_up or strong_down):
            return None

        expected_odds = momentum if strong_up else (100 - momentum)
        spread = abs(expected_odds - kalshi_yes)

        # STRATEGY: Dynamic Neutral Range
        if strategies.STRATEGY_DYNAMIC_NEUTRAL_RANGE:
            if spread >= 25:
                neutral_range = (40, 60)
            elif spread >= 15:
                neutral_range = (45, 55)
            else:
                neutral_range = (47, 53)
        else:
            neutral_range = config.ODDS_NEUTRAL_RANGE

        odds_neutral = neutral_range[0] <= kalshi_yes <= neutral_range[1]
        if not odds_neutral:
            return None

        # STRATEGY: Tight Spread Filter
        min_spread = config.MIN_ODDS_SPREAD
        if strategies.STRATEGY_TIGHT_SPREAD_FILTER:
            min_spread = max(min_spread, strategies.STRATEGY_MIN_SPREAD_CENTS)

        if spread < min_spread:
            return None

        direction = "UP" if strong_up else "DOWN"

        # Calculate confidence with bonuses
        base_confidence = momentum if strong_up else (100 - momentum)
        spread_bonus = 0.0
        neutrality_bonus = 0.0

        if strategies.STRATEGY_IMPROVED_CONFIDENCE:
            spread_bonus = min(spread / 30 * 10, 10)
            center_distance = abs(kalshi_yes - 50)
            neutrality_bonus = max(0, (5 - center_distance) / 5 * 5)

        trend_bonus = (
            5.0 if (strategies.STRATEGY_TREND_CONFIRMATION and trend_confirmed) else 0.0
        )

        confidence = min(
            base_confidence + spread_bonus + neutrality_bonus + trend_bonus, 95
        )

        return direction, confidence, spread

    async def run(self) -> Optional[BacktestResult]:
        """Run backtest with real Kalshi data."""
        print("\n" + "=" * 60, flush=True)
        print("  ARBITRAGE STRATEGY BACKTEST (Real Kalshi Data)", flush=True)
        print("=" * 60, flush=True)
        print(f"  Symbol:    {self.symbol}", flush=True)
        print(
            f"  Period:    {self.start_date.date()} to {self.end_date.date()}",
            flush=True,
        )
        print(f"  Capital:   ${self.initial_capital:,.2f}", flush=True)
        print("=" * 60 + "\n", flush=True)

        print("  Progress: Initializing backtest...", flush=True)

        # Load data
        if not await self.load_binance_data():
            logger.error("Failed to load Binance data")
            return None

        if not await self.load_kalshi_data():
            logger.error("Failed to load Kalshi data")
            logger.error("Make sure KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH are set")
            return None

        logger.info("Running backtest...")
        print(f"\nProcessing {len(self.binance_klines)} candles...", flush=True)

        window = config.MOMENTUM_WINDOW
        last_signal_time = None
        matches_found = 0
        kalshi_data_points_used = 0
        last_progress = 0

        for i in range(window, len(self.binance_klines)):
            # Progress output every 20% of candles
            progress_pct = (i - window) / (len(self.binance_klines) - window)
            if progress_pct - last_progress > 0.2:
                print(
                    f"  {progress_pct * 100:.0f}% complete ({i}/{len(self.binance_klines)} candles)",
                    flush=True,
                )
                last_progress = progress_pct

            kline = self.binance_klines[i]
            timestamp = datetime.fromtimestamp(kline[0] / 1000)

            # Get recent candles for momentum
            # FIX: Only use COMPLETED candles (up to i-1) to avoid lookahead bias
            recent = self.binance_klines[i - window : i]
            momentum, trend_confirmed = self.calculate_momentum(recent)

            # Get real Kalshi data at this time
            kalshi_market_data = self.get_kalshi_at_time(timestamp)
            if not kalshi_market_data:
                continue

            kalshi_data_points_used += 1
            matches_found += 1

            # Extract yes price and market ticker from trade data
            yes_price = kalshi_market_data.get("yes_price", 50)
            market_ticker = kalshi_market_data.get("market_ticker", "")

            # Check for signal
            signal = self.check_signal(momentum, trend_confirmed, yes_price, market_ticker)

            if signal and len(self.open_trades) < self.max_open_trades:
                direction, confidence, spread = signal

                # Cooldown check (using config.BACKTEST_SIGNAL_COOLDOWN)
                if last_signal_time and (timestamp - last_signal_time).seconds < 300:
                    continue

                # STRATEGY: Time Filter - only trade during active hours
                if strategies.STRATEGY_TIME_FILTER:
                    hour_utc = timestamp.hour
                    start_hour = strategies.STRATEGY_TRADING_HOURS_START
                    end_hour = strategies.STRATEGY_TRADING_HOURS_END
                    if start_hour <= end_hour:
                        in_trading_hours = start_hour <= hour_utc < end_hour
                    else:  # Handles overnight range (e.g., 22 to 6)
                        in_trading_hours = hour_utc >= start_hour or hour_utc < end_hour
                    if not in_trading_hours:
                        continue

                # STRATEGY: Volatility Filter - skip high volatility periods
                if strategies.STRATEGY_VOLATILITY_FILTER:
                    volatility = self.calculate_volatility(recent)
                    if volatility > strategies.STRATEGY_VOLATILITY_THRESHOLD:
                        continue

                # STRATEGY: Momentum Acceleration - skip if momentum is decelerating
                if strategies.STRATEGY_MOMENTUM_ACCELERATION:
                    _, _, is_accelerating = self.calculate_momentum_acceleration(
                        self.binance_klines[max(0, i - window * 2) : i]
                    )
                    if not is_accelerating:
                        continue

                # STRATEGY: Pullback Entry - wait for pullback before entering
                if strategies.STRATEGY_PULLBACK_ENTRY:
                    has_pullback = self.check_pullback(
                        recent, direction, strategies.STRATEGY_PULLBACK_THRESHOLD
                    )
                    if not has_pullback:
                        continue

                # STRATEGY: Correlation Check - skip if already holding same symbol
                if strategies.STRATEGY_CORRELATION_CHECK:
                    already_holding = any(
                        t.symbol == self.symbol and not t.resolved
                        for t in self.open_trades
                    )
                    if already_holding:
                        continue

                # STRATEGY: Multiframe Confirmation - confirm on 5-min timeframe
                if strategies.STRATEGY_MULTIFRAME_CONFIRMATION:
                    # Need enough data for 5-min aggregation
                    lookback = min(i, 100)  # Look back up to 100 1-min candles
                    multiframe_data = self.binance_klines[i - lookback : i]
                    multiframe_momentum = self.calculate_multiframe_momentum(
                        multiframe_data, period=5
                    )
                    # Check if 5-min momentum agrees with direction
                    threshold = strategies.STRATEGY_MULTIFRAME_MOMENTUM_THRESHOLD
                    if direction == "UP" and multiframe_momentum < threshold:
                        continue
                    if direction == "DOWN" and multiframe_momentum > (100 - threshold):
                        continue

                if confidence >= self.min_confidence:
                    self.signals_count += 1

                    entry_price = yes_price if direction == "UP" else (100 - yes_price)
                    trade = Trade(
                        timestamp=timestamp,
                        symbol=self.symbol,
                        direction="YES" if direction == "UP" else "NO",
                        entry_price=entry_price,
                        market_ticker=kalshi_market_data.get("market_ticker", ""),
                        confidence=confidence,
                        spot_momentum=momentum,
                        market_result=kalshi_market_data.get("market_result"),
                    )
                    self.open_trades.append(trade)
                    self.trades.append(trade)
                    last_signal_time = timestamp

            # Resolve trades using actual market result or momentum
            for trade in self.open_trades[:]:
                # Resolve trades after a fixed duration or if market result is known
                # Use config.BACKTEST_TRADE_DURATION

                # Check if market has resolved (only if market_result is available)
                market_resolved = trade.market_result is not None

                # Check if trade duration has passed
                trade_duration_passed = (
                    timestamp - trade.timestamp
                ).total_seconds() / 60 >= config.BACKTEST_TRADE_DURATION

                if market_resolved or trade_duration_passed:
                    if not trade.resolved:  # Only resolve once
                        won = False
                        if market_resolved:
                            won = (
                                trade.direction == "YES"
                                and trade.market_result == "yes"
                            ) or (
                                trade.direction == "NO" and trade.market_result == "no"
                            )
                        else:
                            # If market didn't resolve within trade duration, assume it closed at 50c
                            # This is a simplification; a real backtest would need to simulate exit price
                            # based on market conditions at the end of the trade duration.
                            # For now, let's assume a neutral exit if not resolved.
                            won = (
                                trade.direction == "YES"
                                and kalshi_market_data.get("yes_price", 50) > 50
                            ) or (
                                trade.direction == "NO"
                                and kalshi_market_data.get("no_price", 50) > 50
                            )

                        trade.resolved = True
                        trade.exit_price = 100 if won else 0  # Simplified exit price

                        # PnL calculation (simplified, assuming 1 contract for now)
                        trade.pnl = (
                            (trade.exit_price - trade.entry_price)
                            if won
                            else -(trade.entry_price)
                        )
                        self.capital += trade.pnl
                        self.open_trades.remove(trade)

        # Calculate results
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in self.trades)

        # Calculate drawdown
        running_pnl = 0
        peak = 0
        max_dd = 0.0
        for trade in self.trades:
            running_pnl += trade.pnl
            peak = max(peak, running_pnl)
            max_dd = max(max_dd, peak - running_pnl)

        result = BacktestResult(
            start_time=self.start_date,
            end_time=self.end_date,
            symbol=self.symbol,
            kalshi_markets_used=len(self.kalshi_markets),
            kalshi_candles_loaded=len(self.kalshi_candles),
            total_signals=self.signals_count,  # This counts actual trades taken
            trades_taken=len(self.trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            win_rate=len(winning) / len(self.trades) if self.trades else 0,
            avg_trade_pnl=total_pnl / len(self.trades) if self.trades else 0,
            trades=self.trades,
        )

        self._print_results(result, kalshi_data_points_used)
        await self._save_results(result)
        return result

    def _print_results(self, result: BacktestResult, matches: int):
        """Print backtest results."""
        print("\n" + "=" * 60, flush=True)
        print("  BACKTEST RESULTS (Real Kalshi Data)", flush=True)
        print("=" * 60, flush=True)
        print(f"  Symbol:           {result.symbol}", flush=True)
        print(
            f"  Period:           {result.start_time.date()} to {result.end_time.date()}",
            flush=True,
        )
        print(f"  Initial Capital:  ${self.initial_capital:,.2f}", flush=True)
        print("-" * 60, flush=True)
        print(f"  DATA QUALITY", flush=True)
        print(
            f"  Kalshi Markets: {result.kalshi_markets_used} (filtered from {len(self.kalshi_markets)})",
            flush=True,
        )
        print(f"  Kalshi Candles:   {result.kalshi_candles_loaded}", flush=True)
        print(f"  Time Matches:     {matches}", flush=True)
        print("-" * 60, flush=True)
        print(f"  TRADING RESULTS", flush=True)
        print(f"  Total Signals:    {result.total_signals}", flush=True)
        print(f"  Trades Taken:     {result.trades_taken}", flush=True)
        print(f"  Winning Trades:   {result.winning_trades}", flush=True)
        print(f"  Losing Trades:    {result.losing_trades}", flush=True)
        print(f"  Win Rate:         {result.win_rate * 100:.1f}%", flush=True)
        print("-" * 60, flush=True)
        print(f"  P&L SUMMARY", flush=True)
        print(f"  Total P&L:        ${result.total_pnl:,.2f}", flush=True)
        print(f"  Avg Trade P&L:    ${result.avg_trade_pnl:,.2f}", flush=True)
        print(f"  Max Drawdown:     ${result.max_drawdown:,.2f}", flush=True)
        print(f"  Final Capital:    ${self.capital:,.2f}", flush=True)
        print(
            f"  Return:           {((self.capital / self.initial_capital) - 1) * 100:.1f}%",
            flush=True,
        )
        print("=" * 60 + "\n", flush=True)

    async def _save_results(self, result: BacktestResult):
        """Save results to JSON."""
        output = {
            "summary": {
                "symbol": result.symbol,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat(),
                "kalshi_markets": result.kalshi_markets_used,
                "kalshi_candles": result.kalshi_candles_loaded,
                "total_signals": result.total_signals,
                "trades_taken": result.trades_taken,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "win_rate": round(result.win_rate * 100, 1),
                "total_pnl": round(result.total_pnl, 2),
                "max_drawdown": round(result.max_drawdown, 2),
            },
            "trades": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": round(t.pnl, 2),
                    "confidence": t.confidence,
                    "momentum": t.spot_momentum,
                    "market_ticker": t.market_ticker,
                    "market_result": t.market_result,
                }
                for t in result.trades
            ],
        }

        path = (
            config.LOG_DIR
            / f"backtest_real_{result.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(output, f, indent=2)

        # Save CSV for easier analysis
        csv_path = path.with_suffix(".csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Timestamp",
                    "Symbol",
                    "Direction",
                    "Entry Price",
                    "Exit Price",
                    "PnL",
                    "Confidence",
                    "Momentum",
                    "Market Ticker",
                    "Result",
                ]
            )
            for t in result.trades:
                writer.writerow(
                    [
                        t.timestamp.isoformat(),
                        t.symbol,
                        t.direction,
                        t.entry_price,
                        t.exit_price,
                        round(t.pnl, 2),
                        t.confidence,
                        round(t.spot_momentum, 2),
                        t.market_ticker,
                        t.market_result,
                    ]
                )

        logger.info(f"Results saved to {path}")
        logger.info(f"CSV export saved to {csv_path}")


async def main():
    parser = argparse.ArgumentParser(description="Backtest with real Kalshi data")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    parser.add_argument(
        "--days", type=int, default=7, help="Number of days to backtest"
    )
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=10000, help="Initial capital")
    parser.add_argument(
        "--cache-only", action="store_true", help="Use only cached data (faster)"
    )
    args = parser.parse_args()

    if args.start:
        start = datetime.fromisoformat(args.start)
    else:
        start = datetime.now() - timedelta(days=args.days)

    if args.end:
        end = datetime.fromisoformat(args.end)
    else:
        end = datetime.now()

    backtester = RealKalshiBacktester(
        symbol=args.symbol,
        start_date=start,
        end_date=end,
        initial_capital=args.capital,
    )

    # Add timeout for data loading
    try:
        result = await asyncio.wait_for(
            backtester.run(), timeout=600
        )  # 10 minute timeout
        if not result:
            logger.error("Backtest returned no result")
            sys.exit(1)
    except asyncio.TimeoutError:
        logger.error("Backtest timed out after 10 minutes")
        logger.error("Try running with --cache-only flag to use only cached data")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backtest failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
