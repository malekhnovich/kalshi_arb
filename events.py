"""
Event types and async event bus for the agent system.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type
from enum import Enum


class EventType(Enum):
    PRICE_UPDATE = "price_update"
    KALSHI_ODDS = "kalshi_odds"
    ARBITRAGE_SIGNAL = "arbitrage_signal"
    ALERT = "alert"


@dataclass
class BaseEvent:
    """Base class for all events"""
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: EventType = field(init=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging"""
        result = {}
        for k, v in self.__dict__.items():
            if isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, Enum):
                result[k] = v.value
            else:
                result[k] = v
        return result


@dataclass
class PriceUpdateEvent(BaseEvent):
    """Event emitted when price data is updated"""
    symbol: str = ""
    price: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    momentum_up_pct: float = 0.0  # % of recent candles that are up (volume-weighted)
    momentum_window_minutes: int = 60
    candles_analyzed: int = 0
    trend_confirmed: bool = False  # True if price making higher highs/lows in direction

    def __post_init__(self):
        self.event_type = EventType.PRICE_UPDATE


@dataclass
class KalshiOddsEvent(BaseEvent):
    """Event emitted when Kalshi market odds are updated"""
    market_ticker: str = ""
    market_title: str = ""
    yes_price: float = 0.0  # Price in cents (0-100)
    no_price: float = 0.0
    volume: int = 0
    open_interest: int = 0
    underlying_symbol: str = ""  # e.g., "SOL", "BTC"
    strike_price: Optional[float] = None  # Target price if applicable
    expiration: Optional[datetime] = None

    def __post_init__(self):
        self.event_type = EventType.KALSHI_ODDS


@dataclass
class ArbitrageSignalEvent(BaseEvent):
    """Event emitted when arbitrage opportunity is detected"""
    symbol: str = ""
    direction: str = ""  # "UP" or "DOWN"
    confidence: float = 0.0  # 0-100
    spot_momentum_pct: float = 0.0
    kalshi_yes_price: float = 0.0
    kalshi_no_price: float = 0.0
    market_ticker: str = ""
    spread: float = 0.0  # Difference between expected odds and actual
    recommendation: str = ""

    def __post_init__(self):
        self.event_type = EventType.ARBITRAGE_SIGNAL


@dataclass
class AlertEvent(BaseEvent):
    """Aggregated alert event for actionable opportunities"""
    level: str = "INFO"  # INFO, WARNING, OPPORTUNITY
    message: str = ""
    source_agent: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.event_type = EventType.ALERT


# Type alias for event handlers
EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async event bus for pub/sub communication between agents.
    Thread-safe and supports multiple subscribers per event type.
    """

    def __init__(self):
        self._subscribers: Dict[EventType, List[EventHandler]] = {
            event_type: [] for event_type in EventType
        }
        self._lock = asyncio.Lock()
        self._event_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._running = False
        self._process_task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe a handler to an event type"""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type"""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all subscribers"""
        await self._event_queue.put(event)

    async def start(self) -> None:
        """Start the event bus processing loop"""
        self._running = True
        self._process_task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop the event bus"""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

    async def _process_events(self) -> None:
        """Process events from the queue and dispatch to handlers"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=0.1
                )
                handlers = self._subscribers.get(event.event_type, [])
                if handlers:
                    await asyncio.gather(
                        *[handler(event) for handler in handlers],
                        return_exceptions=True
                    )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing event: {e}")
