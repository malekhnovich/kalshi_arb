"""
Arbitrage Detector Agent - Detects temporal lag between spot momentum and Kalshi odds.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

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

        # Configurable thresholds
        self.confidence_threshold = config.CONFIDENCE_THRESHOLD
        self.min_odds_spread = config.MIN_ODDS_SPREAD
        self.neutral_range = config.ODDS_NEUTRAL_RANGE
        self.signal_cooldown = timedelta(seconds=60)  # Avoid spam

    async def on_start(self) -> None:
        """Subscribe to price and odds events"""
        self.subscribe(EventType.PRICE_UPDATE, self._handle_price_update)
        self.subscribe(EventType.KALSHI_ODDS, self._handle_kalshi_odds)

    async def _handle_price_update(self, event: BaseEvent) -> None:
        """Handle incoming price update"""
        if isinstance(event, PriceUpdateEvent):
            self._price_data[event.symbol] = event
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
        self,
        price_event: PriceUpdateEvent,
        kalshi_event: KalshiOddsEvent
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

        # Determine if spot shows strong direction
        strong_up = momentum >= self.confidence_threshold
        strong_down = momentum <= (100 - self.confidence_threshold)

        # Check if Kalshi odds are neutral (mispriced)
        odds_neutral = self.neutral_range[0] <= yes_price <= self.neutral_range[1]

        # Calculate expected odds based on spot momentum
        # If 80% of candles are up, we'd expect yes odds around 70-80
        expected_odds = momentum if strong_up else (100 - momentum)

        # Arbitrage exists if spot is directional but odds are neutral
        if (strong_up or strong_down) and odds_neutral:
            direction = "UP" if strong_up else "DOWN"
            spread = abs(expected_odds - yes_price)

            # Only signal if spread is significant
            if spread >= self.min_odds_spread:
                confidence = min(momentum if strong_up else (100 - momentum), 95)

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
                    recommendation=recommendation
                )

                await self.publish(signal)
                self._last_signal_time[signal_key] = event_time

    def _generate_recommendation(
        self,
        direction: str,
        kalshi_event: KalshiOddsEvent,
        yes_price: float,
        momentum: float
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

    async def run(self) -> None:
        """Main loop - just sleep as we're event-driven"""
        await asyncio.sleep(1)
