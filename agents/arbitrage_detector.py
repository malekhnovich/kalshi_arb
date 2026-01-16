import asyncio
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict

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


class ArbitrageDetectorAgent(BaseAgent):
    """
    Detects arbitrage opportunities by comparing:
    - Spot price momentum from Binance
    - Prediction market odds from Kalshi

    When spot shows strong directional momentum but Kalshi odds
    are still near 50/50, this indicates exploitable temporal lag.
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("ArbitrageDetector", event_bus)

        # State tracking
        self._price_data: Dict[str, PriceUpdateEvent] = {}
        self._kalshi_data: Dict[str, KalshiOddsEvent] = {}
        self._last_signal_time: Dict[str, datetime] = {}
        self._momentum_history: Dict[str, list] = {}  # Track momentum for acceleration
        self._price_history: Dict[str, list] = {}  # Track prices for volatility

        # Configurable thresholds
        self.confidence_threshold = config.CONFIDENCE_THRESHOLD
        self.min_odds_spread = config.MIN_ODDS_SPREAD
        self.neutral_range = config.ODDS_NEUTRAL_RANGE
        self.strike_distance_threshold = config.STRIKE_DISTANCE_THRESHOLD_PCT / 100
        self.signal_cooldown = timedelta(seconds=60)  # Avoid spam

    async def on_start(self) -> None:
        """Subscribe to price and odds events"""
        self.subscribe(EventType.PRICE_UPDATE, self._handle_price_update)
        self.subscribe(EventType.KALSHI_ODDS, self._handle_kalshi_odds)

    async def _handle_price_update(self, event: BaseEvent) -> None:
        """Handle incoming price update"""
        if isinstance(event, PriceUpdateEvent):
            self._price_data[event.symbol] = event

            # Track price history for volatility
            if event.symbol not in self._price_history:
                self._price_history[event.symbol] = []
            self._price_history[event.symbol].append(event.price)
            if len(self._price_history[event.symbol]) > 60:  # 1 hour of history
                self._price_history[event.symbol].pop(0)

            await self._check_arbitrage(event.symbol)

    async def _handle_kalshi_odds(self, event: BaseEvent) -> None:
        """Handle incoming Kalshi odds update"""
        if isinstance(event, KalshiOddsEvent):
            # Store by underlying symbol for cross-reference
            key = f"{event.underlying_symbol}_{event.market_ticker}"
            self._kalshi_data[key] = event

    async def _check_arbitrage(self, symbol: str) -> None:
        """
        Check for arbitrage opportunities for a given symbol.

        Arbitrage exists when:
        1. Spot momentum is strongly directional (>70% up or down)
        2. Kalshi odds are still near neutral (45-55 range)
        """
        price_event = self._price_data.get(symbol)
        if not price_event:
            return

        # Find matching Kalshi markets for this symbol
        base_symbol = config.SYMBOL_MAP.get(symbol, {}).get("base", "")
        if not base_symbol:
            return

        matching_markets = [
            (key, event)
            for key, event in self._kalshi_data.items()
            if event.underlying_symbol == base_symbol
        ]

        for key, kalshi_event in matching_markets:
            await self._evaluate_opportunity(price_event, kalshi_event)

    async def _evaluate_opportunity(
        self, price_event: PriceUpdateEvent, kalshi_event: KalshiOddsEvent
    ) -> None:
        """Evaluate if there's an exploitable opportunity"""
        # Use event timestamp (supports backtesting with simulated time)
        event_time = price_event.timestamp

        # Check cooldown using event timestamp
        signal_key = f"{price_event.symbol}_{kalshi_event.market_ticker}"
        last_signal = self._last_signal_time.get(signal_key)
        if last_signal and event_time - last_signal < self.signal_cooldown:
            return

        momentum = price_event.momentum_up_pct
        yes_price = kalshi_event.yes_price
        symbol = price_event.symbol

        # IMPROVEMENT 2: Track momentum history for acceleration check
        if symbol not in self._momentum_history:
            self._momentum_history[symbol] = []
        self._momentum_history[symbol].append(momentum)
        if len(self._momentum_history[symbol]) > 5:
            self._momentum_history[symbol].pop(0)

        # Check momentum acceleration - skip if momentum is decelerating
        history = self._momentum_history[symbol]
        is_accelerating = True
        if len(history) >= 3:
            recent_avg = sum(history[-2:]) / 2
            older_avg = sum(history[:-2]) / max(1, len(history) - 2)
            # For bullish: recent should be higher; for bearish: recent should be lower
            if momentum >= 50:
                is_accelerating = recent_avg >= older_avg - 2  # Allow small decel
            else:
                is_accelerating = recent_avg <= older_avg + 2

        # Determine if spot shows strong direction
        strong_up = momentum >= self.confidence_threshold
        strong_down = momentum <= (100 - self.confidence_threshold)

        # IMPROVEMENT 4: Trend confirmation as confidence boost (not hard filter)
        trend_bonus = 5.0 if price_event.trend_confirmed else 0.0

        # Calculate expected spread first (needed for dynamic range)
        expected_odds = momentum if strong_up else (100 - momentum)
        spread = abs(expected_odds - yes_price)

        # IMPROVEMENT 3: Dynamic neutral range based on spread size
        # Larger spreads = more tolerance, smaller spreads = stricter
        if spread >= 25:
            neutral_range = (40, 60)  # Wide range for huge edges
        elif spread >= 15:
            neutral_range = (45, 55)  # Standard range
        else:
            neutral_range = (47, 53)  # Tight range for small edges

        # Check if Kalshi odds are neutral (mispriced)
        odds_neutral = neutral_range[0] <= yes_price <= neutral_range[1]

        # IMPROVEMENT 6: Strike price distance check
        strike_price = kalshi_event.strike_price
        dist_check = True
        if strike_price:
            distance_pct = abs(price_event.price - strike_price) / strike_price
            dist_check = distance_pct <= self.strike_distance_threshold

        # Arbitrage exists if spot is directional but odds are neutral
        if (
            (strong_up or strong_down)
            and odds_neutral
            and is_accelerating
            and dist_check
        ):
            direction = "UP" if strong_up else "DOWN"

            # Only signal if spread is significant
            if spread >= self.min_odds_spread:
                # IMPROVEMENT 5: Scale confidence by edge quality
                base_confidence = momentum if strong_up else (100 - momentum)

                # Boost for larger spreads (more mispricing = higher confidence)
                spread_bonus = min(spread / 30 * 10, 10)  # Up to +10 for 30c+ spread

                # Boost if odds are very neutral (closer to 50 = more mispriced)
                center_distance = abs(yes_price - 50)
                neutrality_bonus = max(0, (5 - center_distance) / 5 * 5)  # +5 if at 50

                # Combine factors (including trend bonus from improvement 4)
                confidence = min(
                    base_confidence + spread_bonus + neutrality_bonus + trend_bonus, 95
                )

                # IMPROVEMENT 7: Calculate fair probability
                fair_prob = 50.0
                strike_price = kalshi_event.strike_price
                if strike_price:
                    fair_prob = self._calculate_fair_probability(
                        price_event.symbol, strike_price, price_event.price
                    )

                # Adjust confidence based on fair probability confirmation
                if direction == "UP" and fair_prob > 60:
                    confidence = min(confidence + 5, 98)
                elif direction == "DOWN" and fair_prob < 40:
                    confidence = min(confidence + 5, 98)

                recommendation = self._generate_recommendation(
                    direction, kalshi_event, yes_price, momentum
                )

                signal = ArbitrageSignalEvent(
                    timestamp=event_time,  # Use event timestamp for backtesting
                    symbol=price_event.symbol,
                    direction=direction,
                    confidence=round(confidence, 1),
                    spot_momentum_pct=momentum,
                    kalshi_yes_price=yes_price,
                    kalshi_no_price=kalshi_event.no_price,
                    market_ticker=kalshi_event.market_ticker,
                    spread=round(spread, 1),
                    fair_probability=round(fair_prob, 1),
                    recommendation=recommendation,
                )

                await self.publish(signal)
                self._last_signal_time[signal_key] = event_time

    def _generate_recommendation(
        self,
        direction: str,
        kalshi_event: KalshiOddsEvent,
        yes_price: float,
        momentum: float,
    ) -> str:
        """Generate actionable recommendation"""
        if direction == "UP":
            action = "BUY YES"
            expected_value = momentum - yes_price
        else:
            action = "BUY NO"
            expected_value = (100 - momentum) - (100 - yes_price)

        return (
            f"{action} on '{kalshi_event.market_title}' "
            f"(current: {yes_price}c, expected: ~{momentum:.0f}c based on spot). "
            f"Expected edge: {expected_value:.1f}c"
        )

    def _calculate_fair_probability(
        self, symbol: str, strike_price: float, current_price: float
    ) -> float:
        """Calculate theoretical probability of price > strike using volatility"""
        history = self._price_history.get(symbol, [])
        if len(history) < 10:
            return 50.0  # Default if not enough data

        # Calculate returns for volatility estimation
        returns = []
        for i in range(1, len(history)):
            returns.append((history[i] - history[i - 1]) / history[i - 1])

        if not returns:
            return 50.0

        volatility = statistics.stdev(returns) if len(returns) > 1 else 0.001
        if volatility == 0:
            volatility = 0.0001

        # Distance to strike in standard deviations
        # Simplified model: assume price follows random walk over very short term
        # Standard deviation scales with sqrt(time), but we'll use a fixed short-term proxy
        dist_pct = (strike_price - current_price) / current_price
        z_score = dist_pct / volatility

        # Calculate probability using error function (approximating Normal CDF)
        # P(X > strike) = 1 - CDF(z)
        prob = 0.5 * (1 - math.erf(z_score / math.sqrt(2)))
        return prob * 100

    async def run(self) -> None:
        """Main loop - just sleep as we're event-driven"""
        await asyncio.sleep(1)
