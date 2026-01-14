"""
Signal Aggregator Agent - Consolidates signals and handles logging.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

import aiofiles

from .base import BaseAgent
from events import (
    EventBus,
    EventType,
    BaseEvent,
    PriceUpdateEvent,
    KalshiOddsEvent,
    ArbitrageSignalEvent,
    AlertEvent,
)
import config


class SignalAggregatorAgent(BaseAgent):
    """
    Aggregates signals from all agents and handles output.

    Responsibilities:
    - Console logging with colored output
    - File-based JSON logging
    - Signal deduplication
    - Summary statistics
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("SignalAggregator", event_bus)

        self.log_dir = config.LOG_DIR
        self.colors = config.CONSOLE_COLORS

        # Deduplication tracking
        self._recent_signals: Set[str] = set()
        self._signal_ttl = 60  # seconds

        # Statistics
        self._stats = {
            "price_updates": 0,
            "kalshi_updates": 0,
            "arbitrage_signals": 0,
            "alerts": 0,
        }

        # Current log file handle
        self._log_file_path: Path = Path()

    async def on_start(self) -> None:
        """Setup logging and subscribe to events"""
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create daily log file
        today = datetime.now().strftime("%Y-%m-%d")
        self._log_file_path = self.log_dir / f"signals_{today}.json"

        # Subscribe to all event types
        self.subscribe(EventType.PRICE_UPDATE, self._handle_price_update)
        self.subscribe(EventType.KALSHI_ODDS, self._handle_kalshi_odds)
        self.subscribe(EventType.ARBITRAGE_SIGNAL, self._handle_arbitrage_signal)
        self.subscribe(EventType.ALERT, self._handle_alert)

        self._log_console("INFO", "Signal aggregator started")

    async def _handle_price_update(self, event: BaseEvent) -> None:
        """Handle price update events - log periodically"""
        if isinstance(event, PriceUpdateEvent):
            self._stats["price_updates"] += 1

            # Only log significant momentum
            if event.momentum_up_pct >= 65 or event.momentum_up_pct <= 35:
                direction = "UP" if event.momentum_up_pct >= 65 else "DOWN"
                self._log_console(
                    "INFO",
                    f"[{event.symbol}] ${event.price:.2f} | "
                    f"Momentum: {event.momentum_up_pct:.1f}% {direction} "
                    f"({event.candles_analyzed} candles)"
                )

    async def _handle_kalshi_odds(self, event: BaseEvent) -> None:
        """Handle Kalshi odds events"""
        if isinstance(event, KalshiOddsEvent):
            self._stats["kalshi_updates"] += 1

            # Log if odds are extreme (potential opportunity)
            if event.yes_price <= 30 or event.yes_price >= 70:
                self._log_console(
                    "INFO",
                    f"[Kalshi:{event.underlying_symbol}] {event.market_ticker} | "
                    f"YES: {event.yes_price}c NO: {event.no_price}c"
                )

    async def _handle_arbitrage_signal(self, event: BaseEvent) -> None:
        """Handle arbitrage signal events - always log these prominently"""
        if isinstance(event, ArbitrageSignalEvent):
            self._stats["arbitrage_signals"] += 1

            # Deduplication check
            signal_key = f"{event.symbol}_{event.market_ticker}_{event.direction}"
            if signal_key in self._recent_signals:
                return
            self._recent_signals.add(signal_key)

            # Log to console with emphasis
            self._log_console(
                "OPPORTUNITY",
                f"\n{'='*60}\n"
                f"ARBITRAGE DETECTED: {event.symbol}\n"
                f"Direction: {event.direction} | Confidence: {event.confidence}%\n"
                f"Spot Momentum: {event.spot_momentum_pct:.1f}%\n"
                f"Kalshi Odds: YES {event.kalshi_yes_price}c / NO {event.kalshi_no_price}c\n"
                f"Spread: {event.spread}c\n"
                f"Market: {event.market_ticker}\n"
                f"Recommendation: {event.recommendation}\n"
                f"{'='*60}"
            )

            # Write to log file
            await self._write_to_file(event)

    async def _handle_alert(self, event: BaseEvent) -> None:
        """Handle general alert events"""
        if isinstance(event, AlertEvent):
            self._stats["alerts"] += 1
            self._log_console(event.level, f"[{event.source_agent}] {event.message}")

    def _log_console(self, level: str, message: str) -> None:
        """Print colored message to console"""
        color = self.colors.get(level, "")
        reset = self.colors.get("RESET", "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] [{level}] {message}{reset}")

    async def _write_to_file(self, event: BaseEvent) -> None:
        """Append event to JSON log file"""
        try:
            entry = {
                "logged_at": datetime.now().isoformat(),
                "event_type": event.event_type.value,
                **event.to_dict()
            }

            async with aiofiles.open(self._log_file_path, "a") as f:
                await f.write(json.dumps(entry) + "\n")

        except Exception as e:
            print(f"[{self.name}] Error writing to log file: {e}")

    async def run(self) -> None:
        """Periodic maintenance"""
        # Clean up old signal keys
        await asyncio.sleep(self._signal_ttl)
        self._recent_signals.clear()

    async def on_stop(self) -> None:
        """Log final statistics on shutdown"""
        self._log_console(
            "INFO",
            f"Session stats: "
            f"Price updates: {self._stats['price_updates']}, "
            f"Kalshi updates: {self._stats['kalshi_updates']}, "
            f"Arbitrage signals: {self._stats['arbitrage_signals']}, "
            f"Alerts: {self._stats['alerts']}"
        )
