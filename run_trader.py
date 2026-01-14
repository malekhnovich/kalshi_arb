#!/usr/bin/env python3
"""
Entry point for the arbitrage trading system with dry-run support.

Usage:
    python run_trader.py                    # Dry-run mode (default)
    python run_trader.py --live             # Live trading (requires API key)
    python run_trader.py --max-position 50  # Max $50 per trade
    python run_trader.py --max-positions 3  # Max 3 open positions

Press Ctrl+C to stop gracefully.
"""

import asyncio
import argparse
import signal
import sys
from typing import List, Optional

from events import EventBus
from agents import (
    BaseAgent,
    PriceMonitorAgent,
    KalshiMonitorAgent,
    ArbitrageDetectorAgent,
    SignalAggregatorAgent,
    TraderAgent,
)
import config


class TradingOrchestrator:
    """
    Orchestrator for the trading system with dry-run support.
    """

    def __init__(
        self,
        dry_run: bool = True,
        max_position_size: float = 100.0,
        max_open_positions: int = 5,
        min_confidence: float = 70.0,
        min_edge: float = 10.0,
    ):
        self.event_bus = EventBus()
        self.agents: List[BaseAgent] = []
        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None

        # Trading config
        self.dry_run = dry_run
        self.max_position_size = max_position_size
        self.max_open_positions = max_open_positions
        self.min_confidence = min_confidence
        self.min_edge = min_edge

    def _create_agents(self) -> None:
        """Instantiate all agents including trader"""
        self.agents = [
            PriceMonitorAgent(self.event_bus),
            KalshiMonitorAgent(self.event_bus),
            ArbitrageDetectorAgent(self.event_bus),
            SignalAggregatorAgent(self.event_bus),
            TraderAgent(
                self.event_bus,
                dry_run=self.dry_run,
                max_position_size=self.max_position_size,
                max_open_positions=self.max_open_positions,
                min_confidence=self.min_confidence,
                min_edge=self.min_edge,
            ),
        ]

    async def start(self) -> None:
        """Start the orchestrator and all agents"""
        mode = "DRY-RUN" if self.dry_run else "LIVE"

        print("\n" + "=" * 60)
        print(f"  ARBITRAGE TRADING SYSTEM - {mode} MODE")
        print("  Binance.US <-> Kalshi")
        print("=" * 60)
        print(f"  Max Position Size:   ${self.max_position_size}")
        print(f"  Max Open Positions:  {self.max_open_positions}")
        print(f"  Min Confidence:      {self.min_confidence}%")
        print(f"  Min Edge:            {self.min_edge}c")
        print("=" * 60 + "\n")

        if not self.dry_run:
            print("⚠️  WARNING: LIVE TRADING MODE - Real money at risk!")
            print("    Press Ctrl+C within 5 seconds to cancel...")
            await asyncio.sleep(5)

        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_handler)

        # Initialize event bus
        await self.event_bus.start()
        print("[Orchestrator] Event bus started")

        # Create and start agents
        self._create_agents()
        for agent in self.agents:
            await agent.start()

        # Start health monitoring
        self._health_task = asyncio.create_task(self._health_monitor())

        print(f"\n[Orchestrator] All {len(self.agents)} agents running")
        print("[Orchestrator] Press Ctrl+C to stop\n")

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Stop all agents and cleanup"""
        print("\n[Orchestrator] Initiating shutdown...")

        # Cancel health monitor
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        # Stop agents in reverse order (trader first to close positions)
        for agent in reversed(self.agents):
            await agent.stop()

        # Stop event bus
        await self.event_bus.stop()

        print("[Orchestrator] Shutdown complete")

    def _signal_handler(self) -> None:
        """Handle shutdown signals"""
        self._shutdown_event.set()

    async def _health_monitor(self) -> None:
        """Periodically check agent health"""
        while True:
            try:
                await asyncio.sleep(config.AGENT_HEALTH_CHECK_INTERVAL)

                unhealthy = [
                    agent.name for agent in self.agents
                    if not agent.is_running
                ]

                if unhealthy:
                    print(f"[Orchestrator] WARNING: Unhealthy agents: {unhealthy}")

            except asyncio.CancelledError:
                break

    async def run(self) -> None:
        """Main entry point - start and handle shutdown"""
        try:
            await self.start()
        finally:
            await self.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Run the Binance-Kalshi arbitrage trading system"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading (default: dry-run)"
    )
    parser.add_argument(
        "--max-position",
        type=float,
        default=100.0,
        help="Maximum position size in dollars (default: 100)"
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=5,
        help="Maximum number of open positions (default: 5)"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=70.0,
        help="Minimum confidence threshold (default: 70)"
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=10.0,
        help="Minimum edge in cents (default: 10)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    try:
        orchestrator = TradingOrchestrator(
            dry_run=not args.live,
            max_position_size=args.max_position,
            max_open_positions=args.max_positions,
            min_confidence=args.min_confidence,
            min_edge=args.min_edge,
        )
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
