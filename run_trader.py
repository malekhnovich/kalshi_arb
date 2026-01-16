#!/usr/bin/env python3
"""
Entry point for the arbitrage trading system with dry-run support.

Usage:
    python run_trader.py                    # Dry-run mode (default)
    python run_trader.py --live             # Live trading (requires safety gates)
    python run_trader.py --max-position 50  # Max $50 per trade
    python run_trader.py --max-positions 3  # Max 3 open positions

SAFETY: Live trading requires ALL of these:
    1. KALSHI_ENABLE_LIVE_TRADING=true environment variable
    2. ./ENABLE_LIVE_TRADING file must exist
    3. --live flag passed
    4. Type "CONFIRM" at interactive prompt

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


def check_live_trading_safety() -> tuple[bool, List[str]]:
    """
    Check all safety gates for live trading.

    Returns:
        (all_passed, list_of_issues)
    """
    issues = []
    status = config.get_live_trading_status()

    if not status["env_var_set"]:
        issues.append("KALSHI_ENABLE_LIVE_TRADING environment variable not set to 'true'")

    if not status["enable_file_exists"]:
        issues.append("./ENABLE_LIVE_TRADING file does not exist (create with: touch ./ENABLE_LIVE_TRADING)")

    if not status["not_in_ci"]:
        issues.append("Running in CI/automated environment (CI or GITHUB_ACTIONS env var detected)")

    if not status["no_kill_switch"]:
        issues.append("Kill switch active (./STOP_TRADING file exists)")

    if not config.KALSHI_API_KEY:
        issues.append("KALSHI_API_KEY not configured")

    if not config.KALSHI_PRIVATE_KEY_PATH:
        issues.append("KALSHI_PRIVATE_KEY_PATH not configured")

    return (len(issues) == 0, issues)


def confirm_live_trading() -> bool:
    """
    Interactive confirmation for live trading.

    Returns True only if user explicitly types "CONFIRM".
    """
    print("\n" + "=" * 60)
    print("  ⚠️  LIVE TRADING MODE CONFIRMATION  ⚠️")
    print("=" * 60)
    print()
    print("  You are about to enable LIVE TRADING with real money.")
    print("  This will execute actual orders on Kalshi.")
    print()
    print("  Safety status:")
    status = config.get_live_trading_status()
    print(f"    ✓ Environment variable: {'SET' if status['env_var_set'] else 'NOT SET'}")
    print(f"    ✓ Enable file exists:   {'YES' if status['enable_file_exists'] else 'NO'}")
    print(f"    ✓ Not in CI:            {'YES' if status['not_in_ci'] else 'NO'}")
    print(f"    ✓ No kill switch:       {'YES' if status['no_kill_switch'] else 'ACTIVE'}")
    print()
    print("=" * 60)
    print()

    try:
        response = input("  Type 'CONFIRM' to proceed with live trading: ")
        return response.strip() == "CONFIRM"
    except (EOFError, KeyboardInterrupt):
        return False


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
        help="Enable live trading (requires safety gates - see docs)"
    )
    parser.add_argument(
        "--max-position",
        type=float,
        default=config.MAX_POSITION_SIZE,
        help=f"Maximum position size in dollars (default: {config.MAX_POSITION_SIZE})"
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=config.MAX_OPEN_POSITIONS,
        help=f"Maximum number of open positions (default: {config.MAX_OPEN_POSITIONS})"
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
    parser.add_argument(
        "--check-safety",
        action="store_true",
        help="Check safety gates and exit (useful for debugging)"
    )

    args = parser.parse_args()

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    # Check safety gates status
    if args.check_safety:
        print("\n" + "=" * 60)
        print("  LIVE TRADING SAFETY GATE STATUS")
        print("=" * 60)
        passed, issues = check_live_trading_safety()
        status = config.get_live_trading_status()

        print(f"\n  Environment variable (KALSHI_ENABLE_LIVE_TRADING): ", end="")
        print("✓ SET" if status["env_var_set"] else "✗ NOT SET")

        print(f"  Enable file (./ENABLE_LIVE_TRADING):               ", end="")
        print("✓ EXISTS" if status["enable_file_exists"] else "✗ MISSING")

        print(f"  Not in CI environment:                             ", end="")
        print("✓ OK" if status["not_in_ci"] else "✗ CI DETECTED")

        print(f"  Kill switch (./STOP_TRADING):                      ", end="")
        print("✓ INACTIVE" if status["no_kill_switch"] else "✗ ACTIVE")

        print(f"  API Key configured:                                ", end="")
        print("✓ SET" if config.KALSHI_API_KEY else "✗ NOT SET")

        print(f"  Private Key Path configured:                       ", end="")
        print("✓ SET" if config.KALSHI_PRIVATE_KEY_PATH else "✗ NOT SET")

        print(f"\n  Overall Status: ", end="")
        if passed:
            print("✓ ALL GATES PASSED - Live trading can be enabled")
        else:
            print("✗ BLOCKED")
            print("\n  Issues to resolve:")
            for issue in issues:
                print(f"    - {issue}")

        print("=" * 60 + "\n")
        sys.exit(0 if passed else 1)

    # Handle --live flag with safety checks
    if args.live:
        # Check all safety gates
        passed, issues = check_live_trading_safety()

        if not passed:
            print("\n" + "=" * 60)
            print("  ✗ LIVE TRADING BLOCKED - Safety gates not passed")
            print("=" * 60)
            print("\n  The following issues must be resolved:\n")
            for issue in issues:
                print(f"    ✗ {issue}")
            print("\n  Run with --check-safety to see detailed status.")
            print("  Running in DRY-RUN mode instead.\n")
            print("=" * 60 + "\n")

            # Fall back to dry-run
            args.live = False

        else:
            # All gates passed - require interactive confirmation
            if not confirm_live_trading():
                print("\n  Confirmation not received. Exiting.")
                sys.exit(0)

            print("\n  ✓ Live trading confirmed. Starting...\n")

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
