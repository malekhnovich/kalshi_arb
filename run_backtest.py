#!/usr/bin/env python3
"""
Backtest entry point for the arbitrage detection strategy.

Usage:
    python run_backtest.py --symbol BTCUSDT --days 7
    python run_backtest.py --symbol SOLUSDT --start 2026-01-01 --end 2026-01-10

Press Ctrl+C to stop early.
"""

import asyncio
import argparse
from datetime import datetime, timedelta

from events import EventBus
from agents.backtester import BacktestAgent
from agents.arbitrage_detector import ArbitrageDetectorAgent
from agents.signal_aggregator import SignalAggregatorAgent


async def run_backtest(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 10000.0,
    save_results: bool = True,
):
    """Run a backtest with the given parameters"""
    print("\n" + "=" * 60)
    print("  ARBITRAGE STRATEGY BACKTEST")
    print("=" * 60)
    print(f"  Symbol:    {symbol}")
    print(f"  Period:    {start_date.date()} to {end_date.date()}")
    print(f"  Capital:   ${initial_capital:,.2f}")
    print("=" * 60 + "\n")

    # Create event bus
    event_bus = EventBus()
    await event_bus.start()

    # Create agents
    backtester = BacktestAgent(
        event_bus=event_bus,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    # ArbitrageDetector processes events from backtest
    detector = ArbitrageDetectorAgent(event_bus)

    # Optional: SignalAggregator for logging during backtest
    aggregator = SignalAggregatorAgent(event_bus)

    try:
        # Start agents
        await detector.start()
        await aggregator.start()
        await backtester.start()

        # Wait for backtest to complete (the agent runs its own loop)
        while backtester.is_running:
            await asyncio.sleep(0.1)

        # Save results
        if save_results and backtester.result:
            await backtester.save_results()

    except KeyboardInterrupt:
        print("\nBacktest interrupted by user")

    finally:
        # Stop agents
        await backtester.stop()
        await detector.stop()
        await aggregator.stop()
        await event_bus.stop()

    return backtester.result


def parse_date(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD format"""
    return datetime.strptime(date_str, "%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(
        description="Backtest the Binance-Kalshi arbitrage detection strategy"
    )
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        choices=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        help="Trading pair to backtest (default: BTCUSDT)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to backtest (default: 7)",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD). Overrides --days",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD). Defaults to today",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="Initial capital in USD (default: 10000)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file",
    )

    args = parser.parse_args()

    # Determine date range
    if args.end:
        end_date = parse_date(args.end)
    else:
        end_date = datetime.now()

    if args.start:
        start_date = parse_date(args.start)
    else:
        start_date = end_date - timedelta(days=args.days)

    # Run backtest
    result = asyncio.run(
        run_backtest(
            symbol=args.symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=args.capital,
            save_results=not args.no_save,
        )
    )

    # Exit with appropriate code
    if result and result.total_pnl > 0:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
