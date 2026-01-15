"""
Backtest Agent - Replays historical data to test arbitrage detection strategy.
"""

import asyncio
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx

from .base import BaseAgent
from events import (
    EventBus,
    EventType,
    BaseEvent,
    PriceUpdateEvent,
    KalshiOddsEvent,
    ArbitrageSignalEvent,
)
import config


@dataclass
class Trade:
    """Represents a simulated trade"""
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


@dataclass
class BacktestResult:
    """Results from a backtest run"""
    start_time: datetime
    end_time: datetime
    symbol: str
    total_signals: int = 0
    trades_taken: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0
    trades: List[Trade] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "symbol": self.symbol,
            "total_signals": self.total_signals,
            "trades_taken": self.trades_taken,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": round(self.total_pnl, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "win_rate": round(self.win_rate * 100, 1),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
        }


class HistoricalDataFetcher:
    """Fetches historical data from Binance"""

    def __init__(self, base_url: str = config.BINANCE_US_API_URL):
        self.base_url = base_url
        self.timeout = 30.0

    async def get_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[List]:
        """Fetch historical klines for a time range"""
        all_klines = []
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while current_start < end_ms:
                params = {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": current_start,
                    "endTime": end_ms,
                    "limit": 1000,
                }

                try:
                    response = await client.get(
                        f"{self.base_url}/klines", params=params
                    )
                    response.raise_for_status()
                    klines = response.json()

                    if not klines:
                        break

                    all_klines.extend(klines)
                    # Move to next batch
                    current_start = klines[-1][6] + 1  # closeTime + 1ms

                except httpx.HTTPError as e:
                    print(f"Error fetching historical data: {e}")
                    break

        return all_klines


class BacktestAgent(BaseAgent):
    """
    Backtests the arbitrage detection strategy on historical data.

    Features:
    - Replays historical Binance price data
    - Simulates Kalshi odds based on price levels
    - Tracks hypothetical trades and P&L
    - Generates performance reports
    """

    def __init__(
        self,
        event_bus: EventBus,
        symbol: str = "BTCUSDT",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        initial_capital: float = 10000.0,
    ):
        super().__init__("Backtester", event_bus)
        self.fetcher = HistoricalDataFetcher()
        self.symbol = symbol
        self.start_date = start_date or (datetime.now() - timedelta(days=7))
        self.end_date = end_date or datetime.now()
        self.initial_capital = initial_capital

        # Trading state
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.open_trades: List[Trade] = []
        self.signals_received: List[ArbitrageSignalEvent] = []

        # Backtest settings
        self.trade_size = 100.0  # $100 per trade
        self.min_confidence = 70.0
        self.max_open_trades = 3

        # Historical data
        self._klines: List[List] = []
        self._current_index = 0

        # Kalshi simulation state (improved model)
        self._simulated_odds: float = 50.0  # Current simulated market odds
        self._odds_velocity: float = 0.0    # Rate of change in odds
        self._momentum_history: List[float] = []  # Track recent momentum
        self._kalshi_lag_minutes: int = 5   # How many minutes the market lags
        self._odds_noise_std: float = 2.0   # Standard deviation of random noise

        # Results
        self.result: Optional[BacktestResult] = None

    async def on_stop(self) -> None:
        """Ensure results are finalized on stop"""
        if not self.result and self._klines:
            await self._finalize()

    async def on_start(self) -> None:
        """Fetch historical data and setup"""
        # Subscribe to arbitrage signals first
        self.subscribe(EventType.ARBITRAGE_SIGNAL, self._handle_signal)

        print(f"[{self.name}] Fetching historical data for {self.symbol}...")
        print(f"[{self.name}] Period: {self.start_date} to {self.end_date}")

        self._klines = await self.fetcher.get_historical_klines(
            self.symbol, "1m", self.start_date, self.end_date
        )

        print(f"[{self.name}] Loaded {len(self._klines)} candles")

        if not self._klines:
            print(f"[{self.name}] WARNING: No historical data found!")
            self._running = False

    async def _handle_signal(self, event: BaseEvent) -> None:
        """Handle arbitrage signals during backtest"""
        if isinstance(event, ArbitrageSignalEvent):
            self.signals_received.append(event)
            await self._maybe_open_trade(event)

    async def _maybe_open_trade(self, signal: ArbitrageSignalEvent) -> None:
        """Decide whether to open a trade based on signal"""
        if signal.confidence < self.min_confidence:
            return

        if len(self.open_trades) >= self.max_open_trades:
            return

        if signal.symbol != self.symbol:
            return

        # Determine trade direction
        if signal.direction == "UP":
            direction = "YES"
            entry_price = signal.kalshi_yes_price
        else:
            direction = "NO"
            entry_price = signal.kalshi_no_price

        trade = Trade(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            direction=direction,
            entry_price=entry_price,
            market_ticker=signal.market_ticker,
            confidence=signal.confidence,
            spot_momentum=signal.spot_momentum_pct,
        )

        self.open_trades.append(trade)
        self.trades.append(trade)

    async def run(self) -> None:
        """Run through historical data and emit events"""
        if not self._klines:
            self._running = False
            return

        if self._current_index >= len(self._klines):
            # Backtest complete
            await self._finalize()
            self._running = False
            return

        # Process batch of candles
        batch_size = 60  # Process 60 candles at a time (1 hour)
        end_index = min(self._current_index + batch_size, len(self._klines))

        # Progress indicator
        if self._current_index % 360 == 0:  # Every 6 hours
            progress = (self._current_index / len(self._klines)) * 100
            print(f"[{self.name}] Progress: {progress:.1f}% ({self._current_index}/{len(self._klines)} candles)")

        for i in range(self._current_index, end_index):
            kline = self._klines[i]
            await self._process_candle(kline, i)

        self._current_index = end_index

        # Small delay to allow event processing
        await asyncio.sleep(0.01)

    async def _process_candle(self, kline: List, index: int) -> None:
        """Process a single candle and emit events"""
        # Calculate momentum from recent candles
        window_start = max(0, index - config.MOMENTUM_WINDOW)
        recent_candles = self._klines[window_start : index + 1]

        # Calculate hybrid momentum (matching price_monitor.py)
        simple_up = 0
        weighted_up = 0.0
        weighted_down = 0.0

        for k in recent_candles:
            open_price = float(k[1])
            close_price_k = float(k[4])
            volume = float(k[5])

            is_up = close_price_k >= open_price
            if is_up:
                simple_up += 1

            if open_price > 0 and volume > 0:
                magnitude = abs(close_price_k - open_price) / open_price
                weight = volume * (magnitude + 0.0001)

                if is_up:
                    weighted_up += weight
                else:
                    weighted_down += weight

        total_candles = len(recent_candles)
        total_weight = weighted_up + weighted_down

        # Hybrid: 70% volume-weighted + 30% simple count
        simple_pct = (simple_up / total_candles * 100) if total_candles > 0 else 50
        volume_pct = (weighted_up / total_weight * 100) if total_weight > 0 else 50
        momentum = 0.7 * volume_pct + 0.3 * simple_pct

        close_price = float(kline[4])
        timestamp = datetime.fromtimestamp(kline[0] / 1000)

        # Calculate price trend confirmation
        prices = [float(k[4]) for k in recent_candles]
        trend_confirmed = False
        if len(prices) >= 20:
            recent_high = max(prices[-10:])
            older_high = max(prices[-20:-10])
            recent_low = min(prices[-10:])
            older_low = min(prices[-20:-10])

            uptrend = recent_high > older_high and recent_low > older_low
            downtrend = recent_high < older_high and recent_low < older_low
            trend_confirmed = (momentum >= 60 and uptrend) or (momentum <= 40 and downtrend)

        # Emit price update
        price_event = PriceUpdateEvent(
            timestamp=timestamp,
            symbol=self.symbol,
            price=close_price,
            volume_24h=float(kline[5]),
            price_change_24h=0,  # Not calculated in backtest
            momentum_up_pct=round(momentum, 2),
            momentum_window_minutes=config.MOMENTUM_WINDOW,
            candles_analyzed=len(recent_candles),
            trend_confirmed=trend_confirmed,
        )
        await self.publish(price_event)

        # Simulate Kalshi odds based on price movement
        await self._simulate_kalshi_odds(timestamp, close_price, momentum)

        # Resolve open trades (simulate market resolution)
        await self._check_trade_resolution(timestamp, close_price, momentum)

    async def _simulate_kalshi_odds(
        self, timestamp: datetime, price: float, momentum: float
    ) -> None:
        """
        Simulate realistic Kalshi market odds with lag and noise.

        This improved model simulates:
        1. Temporal lag: Prediction market reacts slower than spot
        2. Mean reversion: Odds tend to drift toward 50 without strong signals
        3. Momentum tracking: Eventually follows spot price direction
        4. Market noise: Random fluctuations from market makers/retail
        5. Liquidity effects: Wider spreads during volatility
        """
        # Store momentum history for lag calculation
        self._momentum_history.append(momentum)
        if len(self._momentum_history) > self._kalshi_lag_minutes:
            self._momentum_history.pop(0)

        # Use lagged momentum (from N minutes ago)
        lagged_momentum = self._momentum_history[0] if self._momentum_history else 50

        # Calculate target odds based on lagged momentum
        # Map momentum (0-100) to odds (0-100) with some dampening
        if lagged_momentum >= 60:
            # Bullish: odds should rise above 50
            target_odds = 50 + (lagged_momentum - 50) * 0.6
        elif lagged_momentum <= 40:
            # Bearish: odds should fall below 50
            target_odds = 50 + (lagged_momentum - 50) * 0.6
        else:
            # Neutral: mean revert toward 50
            target_odds = 50 + (self._simulated_odds - 50) * 0.1

        # Smooth transition with momentum-based velocity
        alpha = 0.15  # EMA smoothing factor (lower = more lag)
        self._odds_velocity = alpha * (target_odds - self._simulated_odds)
        self._simulated_odds += self._odds_velocity

        # Add realistic market noise
        noise = random.gauss(0, self._odds_noise_std)
        noisy_odds = self._simulated_odds + noise

        # Clamp to valid range
        yes_price = max(1, min(99, noisy_odds))
        no_price = 100 - yes_price

        # Simulate bid-ask spread (wider during high volatility)
        volatility_factor = abs(momentum - 50) / 50
        spread = 1 + volatility_factor * 3  # 1-4 cent spread

        # Simulate volume based on momentum strength
        base_volume = 1000
        volume = int(base_volume * (1 + volatility_factor * 2))
        open_interest = int(volume * 0.5)

        # Create simulated market event
        kalshi_event = KalshiOddsEvent(
            timestamp=timestamp,
            market_ticker=f"KXBTC-SIM-{timestamp.strftime('%H%M')}",
            market_title=f"BTC above ${int(price):,}?",
            yes_price=round(yes_price, 1),
            no_price=round(no_price, 1),
            volume=volume,
            open_interest=open_interest,
            underlying_symbol=config.SYMBOL_MAP.get(self.symbol, {}).get("base", "BTC"),
            strike_price=price,
            expiration=timestamp + timedelta(hours=1),
        )
        await self.publish(kalshi_event)

    async def _check_trade_resolution(
        self, current_time: datetime, price: float, momentum: float
    ) -> None:
        """Check if any open trades should be resolved"""
        resolved_trades = []

        for trade in self.open_trades:
            # Simple resolution: if momentum confirms direction, win
            # Otherwise, random resolution based on actual momentum
            age = current_time - trade.timestamp
            age_minutes = age.total_seconds() / 60

            if age_minutes >= 60:  # Resolve after 1 hour
                # Determine outcome
                if trade.direction == "YES":
                    # Win if momentum stayed high
                    won = momentum >= 60
                    exit_price = 100 if won else 0
                else:
                    # Win if momentum stayed low
                    won = momentum <= 40
                    exit_price = 100 if won else 0

                trade.resolved = True
                trade.exit_price = exit_price

                # Calculate P&L
                contracts = self.trade_size / trade.entry_price
                if won:
                    trade.pnl = (exit_price - trade.entry_price) * contracts
                else:
                    trade.pnl = -trade.entry_price * contracts

                self.capital += trade.pnl
                resolved_trades.append(trade)

        for trade in resolved_trades:
            self.open_trades.remove(trade)

    async def _finalize(self) -> None:
        """Finalize backtest and calculate results"""
        # Close any remaining open trades at breakeven
        for trade in self.open_trades:
            trade.resolved = True
            trade.exit_price = trade.entry_price
            trade.pnl = 0

        # Calculate statistics
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in self.trades)

        # Calculate max drawdown
        running_pnl = 0
        peak = 0
        max_dd = 0
        for trade in self.trades:
            running_pnl += trade.pnl
            peak = max(peak, running_pnl)
            drawdown = peak - running_pnl
            max_dd = max(max_dd, drawdown)

        # Calculate Sharpe ratio
        sharpe = self._calculate_sharpe_ratio()

        self.result = BacktestResult(
            start_time=self.start_date,
            end_time=self.end_date,
            symbol=self.symbol,
            total_signals=len(self.signals_received),
            trades_taken=len(self.trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            win_rate=len(winning) / len(self.trades) if self.trades else 0,
            avg_trade_pnl=total_pnl / len(self.trades) if self.trades else 0,
            trades=self.trades,
        )

        self._print_results()

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.05) -> float:
        """
        Calculate annualized Sharpe ratio from trade returns.

        Args:
            risk_free_rate: Annual risk-free rate (default 5%)

        Returns:
            Annualized Sharpe ratio
        """
        if len(self.trades) < 2:
            return 0.0

        # Calculate return per trade as percentage of trade size
        returns = [t.pnl / self.trade_size for t in self.trades if t.resolved]

        if not returns:
            return 0.0

        # Mean and standard deviation of returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        if std_dev == 0:
            return 0.0

        # Estimate trades per year (assume ~250 trading days, ~4 trades/day)
        backtest_days = (self.end_date - self.start_date).days or 1
        trades_per_day = len(returns) / backtest_days
        trades_per_year = trades_per_day * 252

        # Annualize: multiply mean by trades/year, std by sqrt(trades/year)
        annualized_return = mean_return * trades_per_year
        annualized_std = std_dev * math.sqrt(trades_per_year)

        # Sharpe = (annualized_return - risk_free_rate) / annualized_std
        sharpe = (annualized_return - risk_free_rate) / annualized_std

        return sharpe

    def _print_results(self) -> None:
        """Print backtest results to console"""
        if not self.result:
            return

        r = self.result
        print("\n" + "=" * 60)
        print("  BACKTEST RESULTS")
        print("=" * 60)
        print(f"  Symbol:           {r.symbol}")
        print(f"  Period:           {r.start_time.date()} to {r.end_time.date()}")
        print(f"  Initial Capital:  ${self.initial_capital:,.2f}")
        print("-" * 60)
        print(f"  Total Signals:    {r.total_signals}")
        print(f"  Trades Taken:     {r.trades_taken}")
        print(f"  Winning Trades:   {r.winning_trades}")
        print(f"  Losing Trades:    {r.losing_trades}")
        print(f"  Win Rate:         {r.win_rate * 100:.1f}%")
        print("-" * 60)
        print(f"  Total P&L:        ${r.total_pnl:,.2f}")
        print(f"  Avg Trade P&L:    ${r.avg_trade_pnl:,.2f}")
        print(f"  Max Drawdown:     ${r.max_drawdown:,.2f}")
        print(f"  Sharpe Ratio:     {r.sharpe_ratio:.3f}")
        print(f"  Final Capital:    ${self.capital:,.2f}")
        print(f"  Return:           {((self.capital / self.initial_capital) - 1) * 100:.1f}%")
        print("=" * 60 + "\n")

    async def save_results(self, path: Optional[Path] = None) -> None:
        """Save backtest results to JSON file"""
        if not self.result:
            return

        if path is None:
            path = config.LOG_DIR / f"backtest_{self.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "summary": self.result.to_dict(),
            "trades": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "confidence": t.confidence,
                    "spot_momentum": t.spot_momentum,
                }
                for t in self.result.trades
            ],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[{self.name}] Results saved to {path}")
