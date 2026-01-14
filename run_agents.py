#!/usr/bin/env python3
"""
Entry point for the arbitrage detection agent system.

Usage:
    python run_agents.py [--debug]

Press Ctrl+C to stop gracefully.
"""

import asyncio
import argparse
import sys

from orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Run the Binance-Kalshi arbitrage detection agents"
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
        orchestrator = Orchestrator()
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
