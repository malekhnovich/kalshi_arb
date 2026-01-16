"""
Binance WebSocket Client - Real-time streaming of Binance.US market data.

Provides real-time price updates using Binance WebSockets to minimize latency.
"""

import asyncio
import json
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

try:
    from websockets.asyncio.client import connect as ws_connect
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    try:
        from websockets import connect as ws_connect
        from websockets.exceptions import ConnectionClosed, ConnectionClosedError

        WEBSOCKETS_AVAILABLE = True
    except ImportError:
        WEBSOCKETS_AVAILABLE = False

from .base import BaseAgent
from events import EventBus, PriceUpdateEvent
import config


# Type alias for message handlers
MessageHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class BinanceWebSocketClient:
    """
    WebSocket client for Binance.US real-time market data.
    """

    def __init__(self, base_url: str = "wss://stream.binance.us:9443"):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library required. Install with: pip install websockets"
            )

        self.ws_url = f"{base_url}/ws"
        self._ws: Optional[Any] = None
        self._running = False
        self._connected = False
        self._reconnect_delay = 5

        # Message handlers by stream name
        self._handlers: Dict[str, List[MessageHandler]] = {}

        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._last_message_time = 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    def register_handler(self, stream: str, handler: MessageHandler) -> None:
        """Register a handler for a specific stream."""
        if stream not in self._handlers:
            self._handlers[stream] = []
        self._handlers[stream].append(handler)

    async def connect(self, streams: List[str]) -> bool:
        """
        Connect to Binance WebSocket and subscribe to streams.

        Args:
            streams: List of stream names (e.g., ["btcusdt@aggTrade", "ethusdt@aggTrade"])
        """
        if self._connected:
            return True

        if len(streams) > 1:
            combined_url = (
                f"{self.ws_url.replace('/ws', '/stream')}?streams={'/'.join(streams)}"
            )
        else:
            combined_url = f"{self.ws_url}/{streams[0]}"

        try:
            print(f"[BinanceWS] Connecting to {combined_url}...")
            self._ws = await ws_connect(combined_url)
            self._connected = True
            self._running = True
            self._last_message_time = time.time()

            # Start receive task
            self._receive_task = asyncio.create_task(self._receive_loop())

            print("[BinanceWS] Connected successfully")
            return True
        except Exception as e:
            print(f"[BinanceWS] Connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._running = False
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        print("[BinanceWS] Disconnected")

    async def _receive_loop(self) -> None:
        """Main loop to receive and process WebSocket messages."""
        while self._running and self._ws:
            try:
                message = await asyncio.wait_for(self._ws.recv(), timeout=30.0)
                self._last_message_time = time.time()
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except (ConnectionClosed, ConnectionClosedError) as e:
                print(f"[BinanceWS] Connection closed: {e}")
                self._connected = False
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BinanceWS] Receive error: {e}")
                await asyncio.sleep(1)

    async def _handle_message(self, raw_message: str) -> None:
        """Parse and dispatch a WebSocket message."""
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        stream = message.get("stream")
        if not stream:
            return

        # Simple dispatch based on stream name prefix or exact match
        for handler_stream, handlers in self._handlers.items():
            if stream.startswith(handler_stream):
                for handler in handlers:
                    try:
                        await handler(message.get("data", {}))
                    except Exception as e:
                        print(f"[BinanceWS] Handler error for {stream}: {e}")


class BinanceWebSocketAgent(BaseAgent):
    """
    Agent that manages Binance WebSocket connection and publishes events.
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("BinanceWebSocket", event_bus)
        self.client = BinanceWebSocketClient()
        self.symbols = [s.lower() for s in config.BINANCE_SYMBOLS]
        self._momentum_window = config.MOMENTUM_WINDOW

        # State for momentum calculation
        self._price_history: Dict[str, List[Dict]] = {s: [] for s in self.symbols}
        self._running_up_moves: Dict[str, int] = {s: 0 for s in self.symbols}
        self._running_total_moves: Dict[str, int] = {s: 0 for s in self.symbols}

        # Register handlers for each symbol
        for symbol in self.symbols:
            self.client.register_handler(f"{symbol}@aggTrade", self._handle_trade)

    async def on_start(self) -> None:
        """Connect on start."""
        streams = [f"{s}@aggTrade" for s in self.symbols]
        await self.client.connect(streams)

    async def on_stop(self) -> None:
        """Disconnect on stop."""
        await self.client.disconnect()

    async def run(self) -> None:
        """Periodic health check or secondary task."""
        while True:
            if not self.client.is_connected:
                print(f"[{self.name}] Reconnecting...")
                streams = [f"{s}@aggTrade" for s in self.symbols]
                await self.client.connect(streams)
            await asyncio.sleep(10)

    async def _handle_trade(self, data: Dict[str, Any]) -> None:
        """Handle trade data and emit event."""
        symbol = data.get("s", "").upper()
        price = float(data.get("p", 0))
        timestamp = data.get("E", time.time() * 1000) / 1000

        # Update price history and running counts for momentum
        history = self._price_history.get(symbol.lower(), [])

        # Add new transition to running counts
        if history:
            prev_price = history[-1]["price"]
            self._running_total_moves[symbol.lower()] += 1
            if price > prev_price:
                self._running_up_moves[symbol.lower()] += 1

        history.append({"price": price, "time": timestamp})

        # Clean up old history (beyond momentum window) and subtract from running counts
        cutoff = timestamp - (self._momentum_window * 60)
        while len(history) >= 2 and history[0]["time"] < cutoff:
            t0 = history[0]
            t1 = history[1]

            # Remove the transition between t0 and t1 from running counts
            self._running_total_moves[symbol.lower()] -= 1
            if t1["price"] > t0["price"]:
                self._running_up_moves[symbol.lower()] -= 1

            history.pop(0)

        # Calculate momentum using running counts (O(1))
        up_moves = self._running_up_moves.get(symbol.lower(), 0)
        total_moves = self._running_total_moves.get(symbol.lower(), 0)
        momentum_up_pct = (up_moves / total_moves * 100) if total_moves > 0 else 50.0

        # Emit event
        event = PriceUpdateEvent(
            symbol=symbol,
            price=price,
            volume_24h=0.0,
            price_change_24h=0.0,
            momentum_up_pct=round(momentum_up_pct, 2),
            momentum_window_minutes=self._momentum_window,
            candles_analyzed=len(history),
            trend_confirmed=False,
        )
        await self.publish(event)
