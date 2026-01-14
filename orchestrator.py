"""
Orchestrator - Central coordinator for all agents.

Manages agent lifecycle, event bus, and graceful shutdown.
"""

import asyncio
import signal
from typing import List, Optional

from events import EventBus
from agents import (
    BaseAgent,
    PriceMonitorAgent,
    KalshiMonitorAgent,
    ArbitrageDetectorAgent,
    SignalAggregatorAgent,
)
import config


class Orchestrator:
    """
    Central coordinator for the multi-agent system.

    Responsibilities:
    - Initialize the event bus
    - Create and manage agent instances
    - Handle graceful shutdown on SIGINT/SIGTERM
    - Monitor agent health
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.agents: List[BaseAgent] = []
        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None

    def _create_agents(self) -> None:
        """Instantiate all agents"""
        self.agents = [
            PriceMonitorAgent(self.event_bus),
            KalshiMonitorAgent(self.event_bus),
            ArbitrageDetectorAgent(self.event_bus),
            SignalAggregatorAgent(self.event_bus),
        ]

    async def start(self) -> None:
        """Start the orchestrator and all agents"""
        print("\n" + "=" * 60)
        print("  ARBITRAGE DETECTION SYSTEM")
        print("  Binance.US <-> Kalshi")
        print("=" * 60 + "\n")

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

        # Stop agents in reverse order
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


async def main():
    """Entry point for the orchestrator"""
    orchestrator = Orchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
