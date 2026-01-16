"""
Trader Agent - Executes trades on Kalshi based on arbitrage signals.

Supports dry-run mode for paper trading without real execution.

SAFETY: Live trading is DISABLED by default and requires multiple safety gates:
1. KALSHI_ENABLE_LIVE_TRADING=true environment variable
2. ./ENABLE_LIVE_TRADING file must exist
3. --live flag passed to CLI
4. Interactive confirmation prompt
"""

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx

from .base import BaseAgent, retry_with_backoff
from events import (
    EventBus,
    EventType,
    BaseEvent,
    ArbitrageSignalEvent,
    AlertEvent,
)
import config

# Try to import cryptography for RSA-PSS signing
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@dataclass
class Position:
    """Represents an open position"""
    id: str
    timestamp: datetime
    market_ticker: str
    symbol: str
    side: str  # "yes" or "no"
    quantity: int  # Number of contracts
    entry_price: float  # Price in cents
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    closed: bool = False
    close_timestamp: Optional[datetime] = None
    close_price: Optional[float] = None

    def update_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current price (in dollars)"""
        self.current_price = current_price
        # Prices are in cents, convert to dollars for P&L
        if self.side == "yes":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity / 100
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity / 100

    def close(self, close_price: float, timestamp: datetime) -> float:
        """Close position and calculate realized P&L (in dollars)"""
        self.closed = True
        self.close_timestamp = timestamp
        self.close_price = close_price

        # Prices are in cents, convert to dollars for P&L
        if self.side == "yes":
            self.realized_pnl = (close_price - self.entry_price) * self.quantity / 100
        else:
            self.realized_pnl = (self.entry_price - close_price) * self.quantity / 100

        self.unrealized_pnl = 0.0
        return self.realized_pnl

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "market_ticker": self.market_ticker,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "closed": self.closed,
            "close_timestamp": self.close_timestamp.isoformat() if self.close_timestamp else None,
            "close_price": self.close_price,
        }


@dataclass
class TradingStats:
    """Trading session statistics"""
    start_time: datetime = field(default_factory=datetime.now)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    max_drawdown: float = 0.0
    peak_pnl: float = 0.0
    signals_received: int = 0
    signals_executed: int = 0
    signals_skipped: int = 0
    total_cost: float = 0.0
    total_contracts: int = 0

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def avg_win(self) -> float:
        """Average winning trade P&L"""
        if self.winning_trades == 0:
            return 0.0
        # This would need trade-level tracking for accuracy
        return self.realized_pnl / self.winning_trades if self.realized_pnl > 0 else 0.0

    @property
    def avg_loss(self) -> float:
        """Average losing trade P&L"""
        if self.losing_trades == 0:
            return 0.0
        return abs(self.realized_pnl) / self.losing_trades if self.realized_pnl < 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 1),
            "total_pnl": round(self.total_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "signals_received": self.signals_received,
            "signals_executed": self.signals_executed,
            "signals_skipped": self.signals_skipped,
            "total_cost": round(self.total_cost, 2),
            "total_contracts": self.total_contracts,
        }


class KalshiAuthenticator:
    """RSA-PSS authenticator for Kalshi API requests."""

    def __init__(self, api_key: str, private_key_path: str):
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required for authentication")

        self.api_key = api_key
        self._private_key = None

        # Load private key
        if private_key_path and Path(private_key_path).exists():
            with open(private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )

    def sign_request(
        self,
        method: str,
        path: str,
        body: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate authentication headers for a request."""
        if not self._private_key:
            raise ValueError("Private key not loaded")

        timestamp = str(int(time.time() * 1000))

        # Message to sign: timestamp + method + path + body
        message = timestamp + method.upper() + path
        if body:
            message += body

        # Sign with RSA-PSS
        signature = self._private_key.sign(
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
            "Content-Type": "application/json",
        }


class KalshiTradingClient:
    """
    Kalshi trading client with dry-run support and safety gates.

    SAFETY: Live trading requires ALL of these to be true:
    1. dry_run=False passed to constructor
    2. config.is_live_trading_allowed() returns True
    3. API credentials are valid

    In dry-run mode (default), simulates order execution.
    """

    def __init__(
        self,
        base_url: str = config.KALSHI_API_URL,
        dry_run: bool = True,
        api_key: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ):
        self.base_url = base_url
        self.dry_run = dry_run
        self.api_key = api_key or config.KALSHI_API_KEY
        self.private_key_path = private_key_path or config.KALSHI_PRIVATE_KEY_PATH
        self.timeout = 15.0
        self._order_counter = 0

        # Initialize authenticator for read operations (balance/positions)
        self._authenticator: Optional[KalshiAuthenticator] = None
        if self.api_key and self.private_key_path and CRYPTO_AVAILABLE:
            try:
                self._authenticator = KalshiAuthenticator(
                    self.api_key, self.private_key_path
                )
            except Exception as e:
                print(f"[TradingClient] Auth init failed: {e}")

    def _check_safety_gates(self) -> tuple[bool, str]:
        """
        Check all safety gates before allowing live trading.

        Returns (allowed, reason) tuple.
        """
        if self.dry_run:
            return False, "dry_run mode enabled"

        if not config.is_live_trading_allowed():
            status = config.get_live_trading_status()
            if not status["env_var_set"]:
                return False, "KALSHI_ENABLE_LIVE_TRADING env var not set to 'true'"
            if not status["enable_file_exists"]:
                return False, "./ENABLE_LIVE_TRADING file does not exist"
            if not status["not_in_ci"]:
                return False, "Running in CI environment"
            if not status["no_kill_switch"]:
                return False, "./STOP_TRADING kill switch active"
            return False, "Unknown safety gate failure"

        if not self._authenticator:
            return False, "API credentials not configured"

        return True, "all gates passed"

    async def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance - READ ONLY, always safe.

        Returns balance in cents and portfolio value.
        """
        if not self._authenticator:
            return {"success": False, "error": "Not authenticated"}

        endpoint = "/portfolio/balance"
        try:
            headers = self._authenticator.sign_request("GET", endpoint)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "balance_cents": data.get("balance", 0),
                    "balance_dollars": data.get("balance", 0) / 100,
                    "portfolio_value_cents": data.get("portfolio_value", 0),
                    "portfolio_value_dollars": data.get("portfolio_value", 0) / 100,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_positions(self, ticker: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current positions - READ ONLY, always safe.
        """
        if not self._authenticator:
            return {"success": False, "error": "Not authenticated", "positions": []}

        endpoint = "/portfolio/positions"
        params = {}
        if ticker:
            params["ticker"] = ticker

        try:
            headers = self._authenticator.sign_request("GET", endpoint)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "market_positions": data.get("market_positions", []),
                    "event_positions": data.get("event_positions", []),
                }
        except Exception as e:
            return {"success": False, "error": str(e), "positions": []}

    async def place_order(
        self,
        market_ticker: str,
        side: str,  # "yes" or "no"
        quantity: int,
        price: float,  # Price in cents
    ) -> Dict[str, Any]:
        """
        Place an order on Kalshi.

        SAFETY: In dry-run mode (default), simulates order fill.
        Live trading requires ALL safety gates to pass.
        """
        self._order_counter += 1

        # Always check safety gates first
        if self.dry_run:
            # Simulate immediate fill
            return {
                "success": True,
                "order_id": f"DRY-{self._order_counter:06d}",
                "market_ticker": market_ticker,
                "side": side,
                "quantity": quantity,
                "price": price,
                "filled_quantity": quantity,
                "status": "filled",
                "dry_run": True,
                "timestamp": datetime.now().isoformat(),
            }

        # Check all safety gates
        allowed, reason = self._check_safety_gates()
        if not allowed:
            print(f"[TradingClient] SAFETY GATE BLOCKED: {reason}")
            return {
                "success": False,
                "error": f"Live trading blocked: {reason}",
                "dry_run": False,
                "safety_blocked": True,
            }

        # LIVE TRADING - All gates passed
        print(f"[TradingClient] LIVE ORDER: {side} {quantity}x {market_ticker} @ {price}c")

        endpoint = "/portfolio/orders"
        body = {
            "ticker": market_ticker,
            "side": side,
            "action": "buy",
            "count": quantity,
            "type": "limit",
            "time_in_force": "immediate_or_cancel",  # Safest option
        }

        # Set price based on side
        if side == "yes":
            body["yes_price"] = int(price)
        else:
            body["no_price"] = int(price)

        try:
            body_json = json.dumps(body)
            headers = self._authenticator.sign_request("POST", endpoint, body_json)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    content=body_json
                )

                if response.status_code == 201:
                    order_data = response.json().get("order", {})
                    return {
                        "success": True,
                        "order_id": order_data.get("order_id"),
                        "market_ticker": market_ticker,
                        "side": side,
                        "quantity": quantity,
                        "price": price,
                        "filled_quantity": order_data.get("fill_count", 0),
                        "status": order_data.get("status", "unknown"),
                        "dry_run": False,
                        "timestamp": datetime.now().isoformat(),
                        "taker_fees": order_data.get("taker_fees", 0),
                    }
                else:
                    error_msg = response.text
                    print(f"[TradingClient] Order failed: {response.status_code} - {error_msg}")
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}: {error_msg}",
                        "dry_run": False,
                    }

        except Exception as e:
            print(f"[TradingClient] Order exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "dry_run": False,
            }

    async def close_position(
        self,
        market_ticker: str,
        side: str,
        quantity: int,
        price: float,
    ) -> Dict[str, Any]:
        """Close an existing position by selling."""
        # To close: if we bought YES, we sell YES (action=sell)
        # This is different from placing an opposite order

        if self.dry_run:
            self._order_counter += 1
            return {
                "success": True,
                "order_id": f"DRY-CLOSE-{self._order_counter:06d}",
                "market_ticker": market_ticker,
                "side": side,
                "quantity": quantity,
                "price": price,
                "status": "filled",
                "dry_run": True,
                "timestamp": datetime.now().isoformat(),
            }

        # Live close - same safety gates apply
        allowed, reason = self._check_safety_gates()
        if not allowed:
            return {
                "success": False,
                "error": f"Live trading blocked: {reason}",
                "safety_blocked": True,
            }

        endpoint = "/portfolio/orders"
        body = {
            "ticker": market_ticker,
            "side": side,
            "action": "sell",  # Selling to close
            "count": quantity,
            "type": "limit",
            "time_in_force": "immediate_or_cancel",
        }

        if side == "yes":
            body["yes_price"] = int(price)
        else:
            body["no_price"] = int(price)

        try:
            body_json = json.dumps(body)
            headers = self._authenticator.sign_request("POST", endpoint, body_json)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    content=body_json
                )

                if response.status_code == 201:
                    order_data = response.json().get("order", {})
                    return {
                        "success": True,
                        "order_id": order_data.get("order_id"),
                        "status": order_data.get("status"),
                        "filled_quantity": order_data.get("fill_count", 0),
                        "dry_run": False,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}",
                        "dry_run": False,
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}


class TraderAgent(BaseAgent):
    """
    Executes trades based on arbitrage signals.

    Features:
    - Dry-run mode for paper trading
    - Position management and P&L tracking
    - Risk controls (max positions, position sizing)
    - Trade logging and reporting
    """

    def __init__(
        self,
        event_bus: EventBus,
        dry_run: bool = True,
        max_position_size: float = 100.0,  # Max $ per trade
        max_open_positions: int = 5,
        min_confidence: float = 70.0,
        min_edge: float = 10.0,  # Minimum edge in cents
    ):
        super().__init__("Trader", event_bus)

        self.dry_run = dry_run
        self.max_position_size = max_position_size
        self.max_open_positions = max_open_positions
        self.min_confidence = min_confidence
        self.min_edge = min_edge

        # Trading client
        self.client = KalshiTradingClient(dry_run=dry_run)

        # Position tracking
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.stats = TradingStats()

        # Signal deduplication
        self._recent_signals: Dict[str, datetime] = {}
        self._signal_cooldown = timedelta(minutes=5)

    async def on_start(self) -> None:
        """Subscribe to arbitrage signals"""
        self.subscribe(EventType.ARBITRAGE_SIGNAL, self._handle_signal)

        mode = "DRY-RUN" if self.dry_run else "LIVE"
        print(f"[{self.name}] Started in {mode} mode")
        print(f"[{self.name}] Max position: ${self.max_position_size}")
        print(f"[{self.name}] Max open positions: {self.max_open_positions}")

    async def on_stop(self) -> None:
        """Print final stats and save results"""
        await self._print_summary()
        await self._save_results()

    async def _handle_signal(self, event: BaseEvent) -> None:
        """Handle incoming arbitrage signal"""
        if not isinstance(event, ArbitrageSignalEvent):
            return

        self.stats.signals_received += 1

        # Check if we should trade this signal
        should_trade, reason = self._should_trade(event)

        if not should_trade:
            self.stats.signals_skipped += 1
            print(f"[{self.name}] Skipping signal: {reason}")
            return

        # Execute the trade
        await self._execute_trade(event)

    def _should_trade(self, signal: ArbitrageSignalEvent) -> tuple[bool, str]:
        """Determine if we should trade this signal"""

        # Check confidence threshold
        if signal.confidence < self.min_confidence:
            return False, f"Confidence {signal.confidence}% < {self.min_confidence}%"

        # Check minimum edge
        if signal.spread < self.min_edge:
            return False, f"Edge {signal.spread}c < {self.min_edge}c"

        # Check max open positions
        open_count = len([p for p in self.positions.values() if not p.closed])
        if open_count >= self.max_open_positions:
            return False, f"Max positions reached ({open_count})"

        # Check for duplicate signals (same market)
        signal_key = f"{signal.symbol}_{signal.market_ticker}"
        last_signal = self._recent_signals.get(signal_key)
        if last_signal and datetime.now() - last_signal < self._signal_cooldown:
            return False, "Duplicate signal (cooldown)"

        # Check if we already have a position in this market
        if signal.market_ticker in self.positions:
            existing = self.positions[signal.market_ticker]
            if not existing.closed:
                return False, "Already have position in this market"

        return True, "OK"

    async def _execute_trade(self, signal: ArbitrageSignalEvent) -> None:
        """Execute a trade based on the signal"""

        # Determine side and price
        if signal.direction == "UP":
            side = "yes"
            price = signal.kalshi_yes_price
        else:
            side = "no"
            price = signal.kalshi_no_price

        # Calculate quantity (number of contracts)
        # Each contract pays $1 if correct, costs price in cents
        quantity = int(self.max_position_size / (price / 100))
        quantity = max(1, min(quantity, 100))  # 1-100 contracts

        # Calculate cost
        cost = (price / 100) * quantity

        # Place the order
        result = await self.client.place_order(
            market_ticker=signal.market_ticker,
            side=side,
            quantity=quantity,
            price=price,
        )

        if not result.get("success"):
            print(f"[{self.name}] Order failed: {result.get('error')}")
            return

        # Create position record
        position = Position(
            id=result["order_id"],
            timestamp=datetime.now(),
            market_ticker=signal.market_ticker,
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            current_price=price,
        )

        self.positions[signal.market_ticker] = position
        self.stats.signals_executed += 1
        self.stats.total_cost += cost
        self.stats.total_contracts += quantity

        # Update signal tracking
        signal_key = f"{signal.symbol}_{signal.market_ticker}"
        self._recent_signals[signal_key] = datetime.now()

        # Calculate theoretical win probability and expected value
        # Based on momentum as a proxy for win probability
        win_prob = signal.confidence / 100  # Use confidence as win probability
        expected_payout = win_prob * 100 + (1 - win_prob) * 0  # Binary outcome
        expected_pnl = (expected_payout - price) * quantity / 100

        # Kelly criterion for optimal position sizing (informational)
        # f* = (bp - q) / b where b=odds, p=win prob, q=lose prob
        b = (100 - price) / price  # Odds (potential win / risk)
        kelly_fraction = (b * win_prob - (1 - win_prob)) / b if b > 0 else 0
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%

        # Log the trade
        mode_tag = "[DRY-RUN]" if self.dry_run else "[LIVE]"
        print(f"\n{'='*60}")
        print(f"[{self.name}] {mode_tag} TRADE EXECUTED")
        print(f"{'='*60}")
        print(f"  Order ID:     {position.id}")
        print(f"  Market:       {signal.market_ticker}")
        print(f"  Symbol:       {signal.symbol}")
        print(f"  Side:         {side.upper()}")
        print(f"  Quantity:     {quantity} contracts")
        print(f"  Price:        {price}c")
        print(f"  Cost:         ${cost:.2f}")
        print(f"-" * 60)
        print(f"  Confidence:   {signal.confidence}%")
        print(f"  Expected Edge: {signal.spread}c")
        print(f"  Win Prob:     {win_prob*100:.1f}%")
        print(f"  Expected P&L: ${expected_pnl:.2f}")
        print(f"  Max Win:      ${(100-price)*quantity/100:.2f}")
        print(f"  Max Loss:     -${cost:.2f}")
        print(f"  Kelly %:      {kelly_fraction*100:.1f}%")
        print(f"{'='*60}\n")

        # Publish alert
        alert = AlertEvent(
            level="OPPORTUNITY",
            message=f"Trade executed: {side.upper()} {quantity}x {signal.market_ticker} @ {price}c",
            source_agent=self.name,
            details=position.to_dict(),
        )
        await self.publish(alert)

    async def run(self) -> None:
        """Main loop - update positions and check for exits"""
        # Update P&L for open positions by fetching current prices
        await self._update_positions()
        await asyncio.sleep(5)  # Update every 5 seconds

    async def _update_positions(self) -> None:
        """Fetch current market prices and update position P&L"""
        open_positions = [p for p in self.positions.values() if not p.closed]

        if not open_positions:
            return

        async with httpx.AsyncClient(timeout=15) as client:
            for position in open_positions:
                try:
                    resp = await client.get(
                        f"{config.KALSHI_API_URL}/markets/{position.market_ticker}"
                    )
                    if resp.status_code == 200:
                        market = resp.json().get("market", {})

                        # Get current price based on position side
                        if position.side == "yes":
                            current_price = market.get("yes_bid") or market.get("last_price", position.entry_price)
                        else:
                            current_price = market.get("no_bid") or market.get("last_price", position.entry_price)

                        # Update position
                        old_pnl = position.unrealized_pnl
                        position.update_pnl(float(current_price))

                        # Log significant P&L changes
                        pnl_change = position.unrealized_pnl - old_pnl
                        if abs(pnl_change) >= 1.0:  # $1 or more change
                            pnl_str = f"+${position.unrealized_pnl:.2f}" if position.unrealized_pnl >= 0 else f"-${abs(position.unrealized_pnl):.2f}"
                            print(f"[{self.name}] Position update: {position.market_ticker} | {position.entry_price}c → {current_price}c | P&L: {pnl_str}")

                        # Check if market has resolved
                        status = market.get("status", "")
                        result = market.get("result", "")

                        if status == "finalized" and result:
                            # Market resolved - close position
                            if result == "yes":
                                close_price = 100 if position.side == "yes" else 0
                            else:
                                close_price = 0 if position.side == "yes" else 100

                            await self.close_position(position.market_ticker, close_price, f"market resolved: {result}")

                except Exception as e:
                    # Silently continue on errors
                    pass

    async def close_position(
        self,
        market_ticker: str,
        close_price: float,
        reason: str = "manual",
    ) -> Optional[float]:
        """Close a position and realize P&L"""
        if market_ticker not in self.positions:
            return None

        position = self.positions[market_ticker]
        if position.closed:
            return None

        # Close the position
        pnl = position.close(close_price, datetime.now())
        self.closed_positions.append(position)

        # Update stats
        self.stats.total_trades += 1
        self.stats.total_pnl += pnl
        self.stats.realized_pnl += pnl

        if pnl > 0:
            self.stats.winning_trades += 1
        elif pnl < 0:
            self.stats.losing_trades += 1

        # Track drawdown
        self.stats.peak_pnl = max(self.stats.peak_pnl, self.stats.realized_pnl)
        drawdown = self.stats.peak_pnl - self.stats.realized_pnl
        self.stats.max_drawdown = max(self.stats.max_drawdown, drawdown)

        mode_tag = "[DRY-RUN]" if self.dry_run else "[LIVE]"
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        print(f"[{self.name}] {mode_tag} Position closed: {market_ticker} | P&L: {pnl_str} | Reason: {reason}")

        return pnl

    async def _print_summary(self) -> None:
        """Print trading session summary"""
        stats = self.stats
        open_positions = [p for p in self.positions.values() if not p.closed]

        # Calculate unrealized P&L for open positions
        total_unrealized = sum(p.unrealized_pnl for p in open_positions)
        total_exposure = self.get_total_exposure()

        print(f"\n{'='*60}")
        print(f"  TRADING SESSION SUMMARY")
        print(f"  Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        print(f"{'='*60}")
        print(f"  Signals Received:  {stats.signals_received}")
        print(f"  Signals Executed:  {stats.signals_executed}")
        print(f"  Signals Skipped:   {stats.signals_skipped}")
        print(f"-" * 60)
        print(f"  POSITIONS")
        print(f"  Open Positions:    {len(open_positions)}")
        print(f"  Total Contracts:   {stats.total_contracts}")
        print(f"  Total Cost:        ${stats.total_cost:.2f}")
        print(f"  Current Exposure:  ${total_exposure:.2f}")
        print(f"-" * 60)
        print(f"  CLOSED TRADES")
        print(f"  Total Trades:      {stats.total_trades}")
        print(f"  Winning Trades:    {stats.winning_trades}")
        print(f"  Losing Trades:     {stats.losing_trades}")
        print(f"  Win Rate:          {stats.win_rate:.1f}%")
        print(f"-" * 60)
        print(f"  P&L SUMMARY")
        print(f"  Realized P&L:      ${stats.realized_pnl:.2f}")
        print(f"  Unrealized P&L:    ${total_unrealized:.2f}")
        print(f"  Total P&L:         ${stats.realized_pnl + total_unrealized:.2f}")
        print(f"  Max Drawdown:      ${stats.max_drawdown:.2f}")
        print(f"{'='*60}")

        # Print open positions detail
        if open_positions:
            print(f"\n  OPEN POSITIONS:")
            print(f"  {'-'*56}")
            for p in open_positions:
                pnl_str = f"+${p.unrealized_pnl:.2f}" if p.unrealized_pnl >= 0 else f"-${abs(p.unrealized_pnl):.2f}"
                print(f"  {p.market_ticker}")
                print(f"    {p.side.upper()} {p.quantity}x @ {p.entry_price}c | Current: {p.current_price}c | P&L: {pnl_str}")
            print(f"  {'-'*56}\n")

    async def _save_results(self) -> None:
        """Save trading results to JSON"""
        results = {
            "stats": self.stats.to_dict(),
            "dry_run": self.dry_run,
            "open_positions": [p.to_dict() for p in self.positions.values() if not p.closed],
            "closed_positions": [p.to_dict() for p in self.closed_positions],
        }

        mode = "dryrun" if self.dry_run else "live"
        path = config.LOG_DIR / f"trades_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(results, f, indent=2)

        print(f"[{self.name}] Results saved to {path}")

    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions.values() if not p.closed]

    def get_total_exposure(self) -> float:
        """Get total dollar exposure across all open positions"""
        return sum(
            (p.entry_price / 100) * p.quantity
            for p in self.positions.values()
            if not p.closed
        )
