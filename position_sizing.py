#!/usr/bin/env python3
"""
Position Sizing Module

Implements dynamic position sizing strategies including Kelly criterion.
Allows backtester to size positions based on risk and historical performance.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from math import sqrt

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


@dataclass
class PositionSizing:
    """Position sizing configuration"""
    method: str  # "fixed", "kelly", "fractional_kelly"
    base_position_size: float = 100.0  # Default trade size in dollars
    kelly_fraction: float = 0.25  # Use 1/4 Kelly (safer than full Kelly)
    max_position_size: float = 1000.0  # Cap position size
    min_position_size: float = 10.0  # Floor position size


class KellyCriterion:
    """Calculate optimal position sizes using Kelly criterion"""

    @staticmethod
    def calculate_kelly_fraction(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """Calculate Kelly criterion fraction

        f* = (W*P - L*(1-P)) / L

        Where:
        - W = average win amount (dollars)
        - L = average loss amount (dollars)
        - P = win probability (0-1)

        Returns:
        - Optimal fraction of capital to risk per trade (0-1)
        - Returns 0 if negative Kelly (don't trade)

        Example:
        - Win rate 60%, avg win $100, avg loss $80
        - f* = (100*0.6 - 80*0.4) / 80 = 0.325 → risk 32.5% per trade
        - Fractional Kelly 1/4: risk 8.1% per trade (safer)
        """
        if avg_loss == 0:
            return 0

        kelly = (avg_win * win_rate - avg_loss * (1 - win_rate)) / avg_loss

        # Clamp to [0, 1]
        return max(0, min(kelly, 1))

    @staticmethod
    def position_size_from_kelly(
        account_size: float,
        kelly_fraction: float,
        risk_per_trade: float = 1.0,
    ) -> float:
        """Convert Kelly fraction to position size

        Args:
        - account_size: Total trading capital
        - kelly_fraction: Fraction of Kelly to use (e.g., 0.25 for 1/4 Kelly)
        - risk_per_trade: Risk amount per trade (used to scale down)

        Returns:
        - Position size in dollars
        """
        if kelly_fraction <= 0:
            return 0

        return account_size * kelly_fraction * risk_per_trade

    @staticmethod
    def anti_martingale_sizing(
        current_equity: float,
        initial_equity: float,
        base_size: float,
        multiplier: float = 0.5,
    ) -> float:
        """Increase size as you win (pyramid on success)

        Grow position size proportionally with equity, capped at initial equity growth.
        Conservative: multiplier=0.5 (grow slower than equity)
        Aggressive: multiplier=1.0 (grow with equity)
        """
        if initial_equity <= 0:
            return base_size

        equity_ratio = current_equity / initial_equity
        return base_size * (equity_ratio ** multiplier)

    @staticmethod
    def martingale_sizing(
        current_equity: float,
        initial_equity: float,
        base_size: float,
        loss_threshold: float = 0.9,
    ) -> float:
        """Decrease size as you lose (de-risk on drawdown)

        Reduce position size if equity falls below threshold.
        Helps preserve capital during losing streaks.
        """
        if initial_equity <= 0:
            return base_size

        equity_ratio = current_equity / initial_equity

        if equity_ratio < loss_threshold:
            # De-risk: scale down to preserve remaining capital
            return base_size * equity_ratio

        return base_size


class AdaptivePositionSizer:
    """Dynamically size positions based on recent performance"""

    def __init__(
        self,
        initial_capital: float,
        lookback_trades: int = 50,
        kelly_fraction: float = 0.25,
    ):
        self.initial_capital = initial_capital
        self.lookback_trades = lookback_trades
        self.kelly_fraction = kelly_fraction
        self.trade_history: List[float] = []

    def add_trade_result(self, pnl: float):
        """Record trade result"""
        self.trade_history.append(pnl)

    def get_position_size(self, current_equity: float) -> float:
        """Calculate next position size based on recent performance"""

        if len(self.trade_history) < 5:
            # Not enough history, use base size
            return 100.0

        # Use recent trades only
        recent = self.trade_history[-self.lookback_trades :]

        wins = [p for p in recent if p > 0]
        losses = [abs(p) for p in recent if p < 0]

        if not wins or not losses:
            # Not enough wins/losses, use base size
            return 100.0

        win_rate = len(wins) / len(recent)

        if HAS_NUMPY:
            avg_win = np.mean(wins)
            avg_loss = np.mean(losses)
        else:
            avg_win = sum(wins) / len(wins)
            avg_loss = sum(losses) / len(losses)

        # Calculate Kelly
        kelly = KellyCriterion.calculate_kelly_fraction(
            win_rate, avg_win, avg_loss
        )

        # Apply fractional Kelly
        kelly_to_use = kelly * self.kelly_fraction

        # Convert to position size
        position = KellyCriterion.position_size_from_kelly(
            current_equity, kelly_to_use
        )

        # Cap at reasonable bounds
        position = max(10, min(position, 1000))

        return position


class VolatilityBasedSizer:
    """Size positions inversely to market volatility"""

    @staticmethod
    def size_by_volatility(
        base_size: float,
        recent_volatility: float,
        target_volatility: float = 0.015,
    ) -> float:
        """Reduce position size during high volatility

        When market is volatile, take smaller positions.
        When market is calm, increase position size.

        Args:
        - base_size: Base position size
        - recent_volatility: Recent price volatility (std of returns)
        - target_volatility: Target volatility (use smaller positions above this)
        """
        if target_volatility <= 0:
            return base_size

        # Inverse relationship: higher vol -> smaller size
        vol_ratio = min(target_volatility / recent_volatility, 2.0)

        return base_size * vol_ratio


def calculate_risk_metrics(
    position_size: float,
    entry_price: float,
    stop_loss_pct: float = 2.0,
) -> Dict[str, float]:
    """Calculate risk metrics for a trade

    Args:
    - position_size: Amount risking on trade
    - entry_price: Entry price of the trade
    - stop_loss_pct: Stop loss as % of entry price

    Returns:
    - Dictionary with risk, potential return, risk/reward ratio
    """
    risk_amount = position_size * (stop_loss_pct / 100)

    return {
        "position_size": position_size,
        "entry_price": entry_price,
        "stop_loss_pct": stop_loss_pct,
        "risk_amount": risk_amount,
        "risk_per_contract": risk_amount / (position_size / entry_price) if position_size > 0 else 0,
    }


if __name__ == "__main__":
    # Example: Calculate Kelly-sized position
    print("=" * 60)
    print("KELLY CRITERION EXAMPLE")
    print("=" * 60)

    # Strategy with 60% win rate, $100 avg win, $80 avg loss
    kelly = KellyCriterion.calculate_kelly_fraction(
        win_rate=0.60,
        avg_win=100,
        avg_loss=80,
    )

    print(f"\nStrategy Stats:")
    print(f"  Win Rate: 60%")
    print(f"  Avg Win: $100")
    print(f"  Avg Loss: $80")
    print(f"\nKelly Calculations:")
    print(f"  Full Kelly: {kelly:.1%}")
    print(f"  1/4 Kelly (safer): {kelly/4:.1%}")
    print(f"  1/2 Kelly (moderate): {kelly/2:.1%}")

    # Position sizing with $10k account
    account = 10000
    print(f"\nWith ${account:,} account:")
    print(f"  Full Kelly position: ${account * kelly:,.2f}")
    print(f"  1/4 Kelly position: ${account * kelly / 4:,.2f}")
    print(f"  1/2 Kelly position: ${account * kelly / 2:,.2f}")

    print("\n" + "=" * 60)
    print("ADAPTIVE POSITION SIZER EXAMPLE")
    print("=" * 60)

    sizer = AdaptivePositionSizer(initial_capital=10000, kelly_fraction=0.25)

    # Simulate trade results
    sample_pnls = [50, -20, 75, 30, -10, 100, 20, 40, 60, -5, 80, 25]
    for pnl in sample_pnls:
        sizer.add_trade_result(pnl)

    current_equity = 10000 + sum(sample_pnls)
    next_size = sizer.get_position_size(current_equity)

    print(f"\nAfter {len(sample_pnls)} trades:")
    print(f"  Total P&L: ${sum(sample_pnls):.2f}")
    print(f"  Current Equity: ${current_equity:.2f}")
    print(f"  Recommended Position Size: ${next_size:.2f}")
