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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

import config
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
            return True

        logger.info(f"Fetching Binance data for {self.symbol}...")
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
        self.kalshi_markets = await self.kalshi_client.get_markets(
            series_ticker=series,
            status="settled",
            limit=200,
        )

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

        # Filter out low volume markets to save time and avoid noise
        original_count = len(self.kalshi_markets)
        self.kalshi_markets = [
            m for m in self.kalshi_markets if m.get("volume", 0) > 100
        ]
        if len(self.kalshi_markets) < original_count:
            logger.info(
                f"Filtered out {original_count - len(self.kalshi_markets)} low-volume markets (< 100 volume)"
            )

        # Check cache for these specific markets
        cache = get_cache()
        market_tickers = [m["ticker"] for m in self.kalshi_markets]
        logger.info(f"Checking cache for {len(market_tickers)} markets...")

        cached_trades = cache.get_kalshi_trades(market_tickers, start_ts, end_ts)
        if cached_trades:
            logger.info(f"Found cached trades for {len(cached_trades)} timestamps")
            # If we have good coverage (approx 50%), use cache
            if len(cached_trades) > (end_ts - start_ts) / 120:
                self.kalshi_candles = cached_trades
                return True
            else:
                logger.info("Cache coverage too low, fetching fresh data...")

        # Load candlesticks for each market
        total_candles = 0
        market_results = {m.get("ticker"): m.get("result") for m in self.kalshi_markets}

        # Fetch trades (lighter than candlesticks - only price data)
        logger.info(f"Fetching trades for {series} series...")

        # Iterate over markets to avoid global firehose and respect rate limits
        for i, market in enumerate(self.kalshi_markets):
            ticker = market["ticker"]
            if i % 10 == 0:
                logger.info(
                    f"Fetching trades for market {i + 1}/{len(self.kalshi_markets)}: {ticker}"
                )

            trades = await self.kalshi_client.get_trades(
                ticker=ticker,
                min_ts=start_ts,
                max_ts=end_ts,
                limit=1000,
            )

            for trade in trades:
                created = trade.get("created_time", "")
                if not created:
                    continue

                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    ts = int(dt.timestamp())
                    ts = ts - (ts % 60)  # Round to minute

                    if ts not in self.kalshi_candles:
                        self.kalshi_candles[ts] = []

                    self.kalshi_candles[ts].append(
                        {
                            "yes_price": trade.get("yes_price", 50),
                            "no_price": trade.get("no_price", 50),
                            "market_ticker": trade.get("ticker", ""),
                            "market_result": market_results.get(trade.get("ticker")),
                        }
                    )
                    total_candles += 1
                except (ValueError, TypeError):
                    continue

            # Small sleep to respect rate limits
            await asyncio.sleep(0.1)

        if self.kalshi_candles:
            logger.info(f"Saving {total_candles} Kalshi trades to cache...")
            cache.save_kalshi_trades(self.kalshi_candles)

        logger.info(f"Loaded {total_candles} Kalshi candles")
        return total_candles > 0

    def get_kalshi_at_time(self, timestamp: datetime) -> Optional[Dict]:
        """Get Kalshi trade data closest to given timestamp."""
        ts = int(timestamp.timestamp())
        ts = ts - (ts % 60)  # Round to minute

        candidates = []

        # Exact match first
        if ts in self.kalshi_candles:
            candidates = self.kalshi_candles[ts]
        else:
            # Look within 5 minutes
            for offset in range(60, 301, 60):
                if (ts + offset) in self.kalshi_candles:
                    candidates = self.kalshi_candles[ts + offset]
                    break
                if (ts - offset) in self.kalshi_candles:
                    candidates = self.kalshi_candles[ts - offset]
                    break

        if not candidates:
            return None

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

    def check_signal(
        self,
        momentum: float,
        trend_confirmed: bool,
        kalshi_yes: float,
    ) -> Optional[tuple[str, float, float]]:
        """Check if conditions warrant a signal."""
        strong_up = momentum >= self.confidence_threshold
        strong_down = momentum <= (100 - self.confidence_threshold)

        if not (strong_up or strong_down):
            return None

        expected_odds = momentum if strong_up else (100 - momentum)
        spread = abs(expected_odds - kalshi_yes)

        # Dynamic neutral range
        if spread >= 25:
            neutral_range = (40, 60)
        elif spread >= 15:
            neutral_range = (45, 55)
        else:
            neutral_range = (47, 53)

        odds_neutral = neutral_range[0] <= kalshi_yes <= neutral_range[1]
        if not odds_neutral:
            return None

        if spread < config.MIN_ODDS_SPREAD:
            return None

        direction = "UP" if strong_up else "DOWN"

        # Calculate confidence with bonuses
        base_confidence = momentum if strong_up else (100 - momentum)
        spread_bonus = min(spread / 30 * 10, 10)
        center_distance = abs(kalshi_yes - 50)
        neutrality_bonus = max(0, (5 - center_distance) / 5 * 5)
        trend_bonus = 5.0 if trend_confirmed else 0.0

        confidence = min(
            base_confidence + spread_bonus + neutrality_bonus + trend_bonus, 95
        )

        return direction, confidence, spread

    async def run(self) -> Optional[BacktestResult]:
        """Run backtest with real Kalshi data."""
        print("\n" + "=" * 60)
        print("  ARBITRAGE STRATEGY BACKTEST (Real Kalshi Data)")
        print("=" * 60)
        print(f"  Symbol:    {self.symbol}")
        print(f"  Period:    {self.start_date.date()} to {self.end_date.date()}")
        print(f"  Capital:   ${self.initial_capital:,.2f}")
        print("=" * 60 + "\n")

        # Load data
        if not await self.load_binance_data():
            logger.error("Failed to load Binance data")
            return None

        if not await self.load_kalshi_data():
            logger.error("Failed to load Kalshi data")
            logger.error("Make sure KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH are set")
            return None

        logger.info("Running backtest...")

        window = config.MOMENTUM_WINDOW
        last_signal_time = None
        matches_found = 0

        for i in range(window, len(self.binance_klines)):
            kline = self.binance_klines[i]
            timestamp = datetime.fromtimestamp(kline[0] / 1000)

            # Get recent candles for momentum
            # FIX: Only use COMPLETED candles (up to i-1) to avoid lookahead bias
            recent = self.binance_klines[i - window : i]
            momentum, trend_confirmed = self.calculate_momentum(recent)

            # Get real Kalshi data at this time
            kalshi = self.get_kalshi_at_time(timestamp)
            if not kalshi:
                continue

            matches_found += 1

            # Extract yes price from trade data
            yes_price = kalshi.get("yes_price", 50)

            # Check for signal
            signal = self.check_signal(momentum, trend_confirmed, yes_price)

            if signal and len(self.open_trades) < self.max_open_trades:
                direction, confidence, spread = signal

                # Cooldown check
                if last_signal_time and (timestamp - last_signal_time).seconds < 300:
                    continue

                if confidence >= self.min_confidence:
                    self.signals_count += 1

                    entry_price = yes_price if direction == "UP" else (100 - yes_price)
                    trade = Trade(
                        timestamp=timestamp,
                        symbol=self.symbol,
                        direction="YES" if direction == "UP" else "NO",
                        entry_price=entry_price,
                        market_ticker=kalshi.get("market_ticker", ""),
                        confidence=confidence,
                        spot_momentum=momentum,
                        market_result=kalshi.get("market_result"),
                    )
                    self.open_trades.append(trade)
                    self.trades.append(trade)
                    last_signal_time = timestamp

            # Resolve trades using actual market result or momentum
            for trade in self.open_trades[:]:
                age_minutes = (timestamp - trade.timestamp).seconds / 60

                if age_minutes >= 60:
                    # Use actual market result if available
                    if trade.market_result:
                        won = (
                            trade.direction == "YES" and trade.market_result == "yes"
                        ) or (trade.direction == "NO" and trade.market_result == "no")
                    else:
                        # Skip resolution if we don't have the real market result
                        continue

                    trade.resolved = True
                    trade.exit_price = 100 if won else 0

                    contracts = self.trade_size / trade.entry_price
                    if won:
                        trade.pnl = (100 - trade.entry_price) * contracts
                    else:
                        trade.pnl = -trade.entry_price * contracts

                    self.capital += trade.pnl
                    self.open_trades.remove(trade)

        # Calculate results
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in self.trades)

        # Calculate drawdown
        running_pnl = 0
        peak = 0
        max_dd = 0
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
            total_signals=self.signals_count,
            trades_taken=len(self.trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            win_rate=len(winning) / len(self.trades) if self.trades else 0,
            avg_trade_pnl=total_pnl / len(self.trades) if self.trades else 0,
            trades=self.trades,
        )

        self._print_results(result, matches_found)
        await self._save_results(result)
        return result

    def _print_results(self, result: BacktestResult, matches: int):
        """Print backtest results."""
        print("\n" + "=" * 60)
        print("  BACKTEST RESULTS (Real Kalshi Data)")
        print("=" * 60)
        print(f"  Symbol:           {result.symbol}")
        print(
            f"  Period:           {result.start_time.date()} to {result.end_time.date()}"
        )
        print(f"  Initial Capital:  ${self.initial_capital:,.2f}")
        print("-" * 60)
        print(f"  DATA QUALITY")
        print(f"  Kalshi Markets:   {result.kalshi_markets_used}")
        print(f"  Kalshi Candles:   {result.kalshi_candles_loaded}")
        print(f"  Time Matches:     {matches}")
        print("-" * 60)
        print(f"  TRADING RESULTS")
        print(f"  Total Signals:    {result.total_signals}")
        print(f"  Trades Taken:     {result.trades_taken}")
        print(f"  Winning Trades:   {result.winning_trades}")
        print(f"  Losing Trades:    {result.losing_trades}")
        print(f"  Win Rate:         {result.win_rate * 100:.1f}%")
        print("-" * 60)
        print(f"  P&L SUMMARY")
        print(f"  Total P&L:        ${result.total_pnl:,.2f}")
        print(f"  Avg Trade P&L:    ${result.avg_trade_pnl:,.2f}")
        print(f"  Max Drawdown:     ${result.max_drawdown:,.2f}")
        print(f"  Final Capital:    ${self.capital:,.2f}")
        print(
            f"  Return:           {((self.capital / self.initial_capital) - 1) * 100:.1f}%"
        )
        print("=" * 60 + "\n")

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

    await backtester.run()


if __name__ == "__main__":
    asyncio.run(main())
