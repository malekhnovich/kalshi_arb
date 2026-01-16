"""
Kalshi WebSocket Client - Real-time streaming of market data.

Provides sub-second price updates instead of polling every 10 seconds.
Supports ticker, orderbook, and trade channels.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from .base import BaseAgent
from events import EventBus, KalshiOddsEvent
import config


# Type alias for message handlers
MessageHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class KalshiWebSocketClient:
    """
    WebSocket client for Kalshi real-time market data.

    Channels supported:
    - ticker: Price updates (yes/no prices, volume, open interest)
    - orderbook_delta: Real-time orderbook changes
    - trade: Public trade notifications
    - fill: Your order fills (authenticated)
    - market_positions: Position updates (authenticated)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library required. Install with: pip install websockets"
            )

        self.ws_url = config.KALSHI_WS_URL
        self.api_key = api_key or config.KALSHI_API_KEY
        self.private_key_path = private_key_path or config.KALSHI_PRIVATE_KEY_PATH

        self._ws: Optional[Any] = None
        self._running = False
        self._connected = False
        self._reconnect_delay = config.KALSHI_WS_RECONNECT_DELAY
        self._heartbeat_interval = config.KALSHI_WS_HEARTBEAT_INTERVAL

        # Subscriptions: {sid: {channel, market_tickers}}
        self._subscriptions: Dict[int, Dict[str, Any]] = {}
        self._next_cmd_id = 1
        self._pending_commands: Dict[int, asyncio.Future] = {}

        # Message handlers by channel
        self._handlers: Dict[str, List[MessageHandler]] = {}

        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Connection state
        self._last_message_time = 0.0
        self._reconnect_count = 0
        self._max_reconnect_attempts = 10

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    def register_handler(self, channel: str, handler: MessageHandler) -> None:
        """Register a handler for a specific channel."""
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

    async def connect(self) -> bool:
        """
        Connect to Kalshi WebSocket.

        Returns True if connection successful, False otherwise.
        """
        if self._connected:
            return True

        try:
            # Build connection URL with auth if available
            url = self.ws_url
            headers = {}

            if self.api_key:
                # Add authentication headers
                timestamp = str(int(time.time() * 1000))
                headers = {
                    "KALSHI-ACCESS-KEY": self.api_key,
                    "KALSHI-ACCESS-TIMESTAMP": timestamp,
                }
                # Note: Full auth requires signature - for now using key-only
                # WebSocket auth may differ from REST auth

            print(f"[KalshiWS] Connecting to {url}...")
            self._ws = await websockets.connect(
                url,
                extra_headers=headers if headers else None,
                ping_interval=None,  # We handle heartbeat manually
                ping_timeout=None,
            )

            self._connected = True
            self._running = True
            self._reconnect_count = 0
            self._last_message_time = time.time()

            # Start receive and heartbeat tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            print(f"[KalshiWS] Connected successfully")
            return True

        except Exception as e:
            print(f"[KalshiWS] Connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._running = False
        self._connected = False

        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close connection
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        print("[KalshiWS] Disconnected")

    async def subscribe(
        self,
        channel: str,
        market_tickers: List[str],
    ) -> Optional[int]:
        """
        Subscribe to a channel for specific markets.

        Args:
            channel: Channel name (ticker, orderbook_delta, trade, etc.)
            market_tickers: List of market tickers to subscribe to

        Returns:
            Subscription ID if successful, None otherwise
        """
        if not self.is_connected:
            print(f"[KalshiWS] Cannot subscribe - not connected")
            return None

        cmd_id = self._next_cmd_id
        self._next_cmd_id += 1

        command = {
            "id": cmd_id,
            "cmd": "subscribe",
            "params": {
                "channels": [channel],
                "market_tickers": market_tickers,
            }
        }

        try:
            await self._ws.send(json.dumps(command))
            print(f"[KalshiWS] Subscribing to {channel} for {len(market_tickers)} markets")
            return cmd_id
        except Exception as e:
            print(f"[KalshiWS] Subscribe failed: {e}")
            return None

    async def unsubscribe(self, subscription_id: int) -> bool:
        """Unsubscribe from a subscription by ID."""
        if not self.is_connected:
            return False

        cmd_id = self._next_cmd_id
        self._next_cmd_id += 1

        command = {
            "id": cmd_id,
            "cmd": "unsubscribe",
            "params": {
                "sids": [subscription_id]
            }
        }

        try:
            await self._ws.send(json.dumps(command))
            return True
        except Exception:
            return False

    async def update_subscription(
        self,
        subscription_id: int,
        market_tickers: List[str],
        action: str = "add_markets"
    ) -> bool:
        """
        Update a subscription to add or remove markets.

        Args:
            subscription_id: The subscription ID to update
            market_tickers: Markets to add or remove
            action: "add_markets" or "remove_markets"
        """
        if not self.is_connected:
            return False

        cmd_id = self._next_cmd_id
        self._next_cmd_id += 1

        command = {
            "id": cmd_id,
            "cmd": "update_subscription",
            "params": {
                "sids": [subscription_id],
                "market_tickers": market_tickers,
                "action": action,
            }
        }

        try:
            await self._ws.send(json.dumps(command))
            return True
        except Exception:
            return False

    async def _receive_loop(self) -> None:
        """Main loop to receive and process WebSocket messages."""
        while self._running and self._ws:
            try:
                message = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=30.0
                )
                self._last_message_time = time.time()
                await self._handle_message(message)

            except asyncio.TimeoutError:
                # No message received - check if heartbeat needed
                continue

            except (ConnectionClosed, ConnectionClosedError) as e:
                print(f"[KalshiWS] Connection closed: {e}")
                self._connected = False
                if self._running:
                    await self._reconnect()
                break

            except asyncio.CancelledError:
                break

            except Exception as e:
                print(f"[KalshiWS] Receive error: {e}")
                if self._running:
                    await asyncio.sleep(1)

    async def _handle_message(self, raw_message: str) -> None:
        """Parse and dispatch a WebSocket message."""
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            print(f"[KalshiWS] Invalid JSON: {raw_message[:100]}")
            return

        msg_type = message.get("type")

        # Handle subscription confirmations
        if msg_type == "subscribed":
            sid = message.get("msg", {}).get("sid")
            channel = message.get("msg", {}).get("channel")
            if sid:
                self._subscriptions[sid] = {
                    "channel": channel,
                    "subscribed_at": datetime.now(),
                }
                print(f"[KalshiWS] Subscribed: sid={sid}, channel={channel}")
            return

        # Handle errors
        if msg_type == "error":
            error = message.get("msg", {})
            print(f"[KalshiWS] Error: code={error.get('code')}, msg={error.get('msg')}")
            return

        # Handle data messages - dispatch to handlers
        if msg_type in self._handlers:
            for handler in self._handlers[msg_type]:
                try:
                    await handler(message)
                except Exception as e:
                    print(f"[KalshiWS] Handler error for {msg_type}: {e}")

        # Also try channel-specific handlers from the message itself
        channel = message.get("channel")
        if channel and channel in self._handlers:
            for handler in self._handlers[channel]:
                try:
                    await handler(message)
                except Exception as e:
                    print(f"[KalshiWS] Handler error for {channel}: {e}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to keep connection alive."""
        while self._running and self._ws:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                if not self.is_connected:
                    continue

                # Send ping frame
                try:
                    pong = await self._ws.ping()
                    await asyncio.wait_for(pong, timeout=5.0)
                except Exception:
                    print("[KalshiWS] Heartbeat failed - connection may be dead")

            except asyncio.CancelledError:
                break

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        self._reconnect_count += 1

        if self._reconnect_count > self._max_reconnect_attempts:
            print(f"[KalshiWS] Max reconnect attempts reached ({self._max_reconnect_attempts})")
            return

        # Exponential backoff: 5, 10, 20, 40... up to 60 seconds
        delay = min(self._reconnect_delay * (2 ** (self._reconnect_count - 1)), 60)
        print(f"[KalshiWS] Reconnecting in {delay}s (attempt {self._reconnect_count})")

        await asyncio.sleep(delay)

        if await self.connect():
            # Resubscribe to previous subscriptions
            # Note: This is simplified - full implementation would restore all subs
            pass


class KalshiWebSocketAgent(BaseAgent):
    """
    Agent that manages Kalshi WebSocket connection and publishes events.

    Integrates WebSocket data with the event bus, providing real-time
    market data to other agents.
    """

    def __init__(self, event_bus: EventBus):
        super().__init__("KalshiWebSocket", event_bus)

        if not WEBSOCKETS_AVAILABLE:
            print(f"[{self.name}] Warning: websockets library not available")
            self._ws_client = None
        else:
            self._ws_client = KalshiWebSocketClient()
            self._ws_client.register_handler("ticker", self._handle_ticker)

        self._subscribed_markets: Set[str] = set()
        self._poll_fallback = True  # Fall back to polling if WS fails
        self._last_data: Dict[str, Dict] = {}  # Cache last known data

    async def on_start(self) -> None:
        """Connect to WebSocket on agent start."""
        if not config.KALSHI_WS_ENABLED:
            print(f"[{self.name}] WebSocket disabled in config")
            return

        if not self._ws_client:
            print(f"[{self.name}] WebSocket client not available")
            return

        connected = await self._ws_client.connect()
        if connected:
            # Subscribe to crypto series markets
            await self._subscribe_to_crypto_markets()
        else:
            print(f"[{self.name}] Failed to connect - will use polling fallback")

    async def on_stop(self) -> None:
        """Disconnect from WebSocket on agent stop."""
        if self._ws_client:
            await self._ws_client.disconnect()

    async def run(self) -> None:
        """Main loop - just keeps agent alive, WS handles data."""
        # Check if WS is connected
        if self._ws_client and self._ws_client.is_connected:
            # Connection healthy - just sleep
            await asyncio.sleep(5)
        else:
            # Connection lost or unavailable - could trigger fallback
            if self._poll_fallback:
                # Note: Actual polling done by KalshiMonitorAgent as fallback
                pass
            await asyncio.sleep(config.KALSHI_WS_RECONNECT_DELAY)

    async def _subscribe_to_crypto_markets(self) -> None:
        """Subscribe to ticker channel for crypto markets."""
        # For now, we'd need to fetch market tickers first
        # This is a simplified version - real implementation would:
        # 1. Fetch available markets via REST
        # 2. Subscribe to those tickers via WebSocket
        print(f"[{self.name}] Ready to subscribe to market tickers")

        # Example subscription (requires actual market tickers)
        # await self._ws_client.subscribe("ticker", ["KXBTC-...", "KXETH-..."])

    async def add_market_subscription(self, market_ticker: str) -> None:
        """Add a market to the WebSocket subscription."""
        if not self._ws_client or not self._ws_client.is_connected:
            return

        if market_ticker in self._subscribed_markets:
            return

        await self._ws_client.subscribe("ticker", [market_ticker])
        self._subscribed_markets.add(market_ticker)

    async def _handle_ticker(self, message: Dict[str, Any]) -> None:
        """Handle ticker updates from WebSocket."""
        try:
            data = message.get("msg", {})
            market_ticker = data.get("ticker") or data.get("market_ticker", "")

            if not market_ticker:
                return

            # Extract pricing data
            yes_price = data.get("yes_price", data.get("yes_ask", 50))
            no_price = data.get("no_price", data.get("no_ask", 50))
            volume = data.get("volume", 0)
            open_interest = data.get("open_interest", 0)

            # Determine underlying symbol from ticker
            underlying = self._extract_underlying(market_ticker)

            # Create and publish event
            event = KalshiOddsEvent(
                market_ticker=market_ticker,
                market_title=data.get("title", ""),
                yes_price=float(yes_price),
                no_price=float(no_price),
                volume=int(volume),
                open_interest=int(open_interest),
                underlying_symbol=underlying,
                strike_price=None,
                expiration=None,
            )

            await self.publish(event)

            # Cache the data
            self._last_data[market_ticker] = {
                "yes_price": yes_price,
                "no_price": no_price,
                "volume": volume,
                "updated_at": datetime.now(),
            }

        except Exception as e:
            print(f"[{self.name}] Error handling ticker: {e}")

    def _extract_underlying(self, market_ticker: str) -> str:
        """Extract underlying asset from market ticker."""
        # Tickers like "KXBTC-..." -> "BTC"
        for series in config.KALSHI_CRYPTO_SERIES:
            if market_ticker.startswith(series):
                return series[2:] if series.startswith("KX") else series
        return ""

    def get_status(self) -> Dict[str, Any]:
        """Get WebSocket connection status."""
        return {
            "enabled": config.KALSHI_WS_ENABLED,
            "available": WEBSOCKETS_AVAILABLE,
            "connected": self._ws_client.is_connected if self._ws_client else False,
            "subscribed_markets": len(self._subscribed_markets),
            "cached_data_count": len(self._last_data),
        }
