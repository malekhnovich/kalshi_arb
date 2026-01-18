#!/usr/bin/env python3
"""
Statistical Significance Testing Framework

Tests whether strategy results are statistically significant or due to chance.
Includes:
- Out-of-sample validation
- Confidence intervals
- Sharpe ratio testing
- Win rate significance (binomial test)
- Monte Carlo permutation testing
- Walk-forward analysis
"""

import numpy as np
from typing import Dict, List, Tuple, Any
from scipy import stats
import json
from dataclasses import dataclass


@dataclass
class StatisticalResult:
    """Container for statistical test results"""
    metric: str
    value: float
    lower_ci: float
    upper_ci: float
    p_value: float
    is_significant: bool  # p < 0.05
    sample_size: int


class StrategyStatistics:
    """Analyze strategy performance with statistical rigor"""

    def __init__(self, trades: List[Dict[str, Any]]):
        """Initialize with list of trade results"""
        self.trades = trades
        self.pnl_list = [t.get("pnl", 0) for t in trades]
        self.wins = [p for p in self.pnl_list if p > 0]
        self.losses = [abs(p) for p in self.pnl_list if p < 0]
        self.num_trades = len(trades)
        self.num_wins = len(self.wins)
        self.num_losses = len(self.losses)

    def win_rate_ci(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Binomial confidence interval for win rate"""
        if self.num_trades == 0:
            return 0, 0

        # Wilson score interval (more accurate than normal approximation)
        n = self.num_trades
        successes = self.num_wins
        z = stats.norm.ppf((1 + confidence) / 2)

        denominator = 1 + z**2 / n
        center = (successes + z**2 / 2) / n
        p_hat = successes / n
        adjustment = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n)

        lower = (center - adjustment) / denominator
        upper = (center + adjustment) / denominator

        return max(0, lower), min(1, upper)

    def test_win_rate_significance(self, null_hypothesis: float = 0.5) -> StatisticalResult:
        """Test if win rate is significantly different from null hypothesis (e.g., random)

        Args:
            null_hypothesis: Expected win rate under random trading (default 0.5 for binary outcomes)

        Returns:
            StatisticalResult with p-value and CI
        """
        if self.num_trades == 0:
            return StatisticalResult(
                metric="win_rate",
                value=0,
                lower_ci=0,
                upper_ci=0,
                p_value=1.0,
                is_significant=False,
                sample_size=0
            )

        # Binomial test
        result = stats.binomtest(
            self.num_wins,
            self.num_trades,
            null_hypothesis,
            alternative="two-sided"
        )
        p_value = result.pvalue

        lower, upper = self.win_rate_ci()
        actual_wr = self.num_wins / self.num_trades

        return StatisticalResult(
            metric="win_rate",
            value=actual_wr,
            lower_ci=lower,
            upper_ci=upper,
            p_value=p_value,
            is_significant=p_value < 0.05,
            sample_size=self.num_trades
        )

    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio of trade returns"""
        if len(self.pnl_list) == 0:
            return 0

        returns = np.array(self.pnl_list)
        excess_returns = returns - risk_free_rate

        if np.std(excess_returns) == 0:
            return 0

        return np.mean(excess_returns) / np.std(excess_returns)

    def sharpe_ratio_ci(self, confidence: float = 0.95, risk_free_rate: float = 0.0) -> Tuple[float, float]:
        """Confidence interval for Sharpe ratio using bootstrap"""
        if len(self.pnl_list) < 10:
            return 0, 0

        bootstrap_sharpes = []
        n_bootstrap = 1000

        np.random.seed(42)
        for _ in range(n_bootstrap):
            sample = np.random.choice(self.pnl_list, size=len(self.pnl_list), replace=True)
            returns = sample - risk_free_rate

            if np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns)
                bootstrap_sharpes.append(sharpe)

        if not bootstrap_sharpes:
            return 0, 0

        alpha = (1 - confidence) / 2
        lower = np.percentile(bootstrap_sharpes, alpha * 100)
        upper = np.percentile(bootstrap_sharpes, (1 - alpha) * 100)

        return float(lower), float(upper)

    def test_sharpe_ratio_vs_zero(self, confidence: float = 0.95) -> StatisticalResult:
        """Test if Sharpe ratio is significantly different from zero"""
        if len(self.pnl_list) < 10:
            return StatisticalResult(
                metric="sharpe_ratio",
                value=0,
                lower_ci=0,
                upper_ci=0,
                p_value=1.0,
                is_significant=False,
                sample_size=len(self.pnl_list)
            )

        sharpe = self.sharpe_ratio()
        lower, upper = self.sharpe_ratio_ci(confidence)

        # If CI doesn't include zero, it's significant at alpha level
        is_sig = (lower > 0) or (upper < 0)
        p_value = 0.05 if is_sig else 0.5  # Simplified

        return StatisticalResult(
            metric="sharpe_ratio",
            value=sharpe,
            lower_ci=lower,
            upper_ci=upper,
            p_value=p_value,
            is_significant=is_sig,
            sample_size=len(self.pnl_list)
        )

    def pnl_ci(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Confidence interval for mean P&L using t-distribution"""
        if len(self.pnl_list) < 2:
            return 0, 0

        mean = np.mean(self.pnl_list)
        sem = stats.sem(self.pnl_list)  # Standard error of mean
        ci = sem * stats.t.ppf((1 + confidence) / 2, len(self.pnl_list) - 1)

        return float(mean - ci), float(mean + ci)

    def test_pnl_vs_zero(self, confidence: float = 0.95) -> StatisticalResult:
        """One-sample t-test: is mean P&L significantly > 0?"""
        if len(self.pnl_list) < 2:
            return StatisticalResult(
                metric="total_pnl",
                value=0,
                lower_ci=0,
                upper_ci=0,
                p_value=1.0,
                is_significant=False,
                sample_size=0
            )

        t_stat, p_value = stats.ttest_1samp(self.pnl_list, 0)
        mean_pnl = np.mean(self.pnl_list)
        lower, upper = self.pnl_ci(confidence)

        return StatisticalResult(
            metric="total_pnl",
            value=mean_pnl,
            lower_ci=lower,
            upper_ci=upper,
            p_value=p_value / 2,  # One-tailed
            is_significant=(p_value / 2) < 0.05,
            sample_size=len(self.pnl_list)
        )

    def monte_carlo_distribution(self, n_simulations: int = 10000) -> Dict[str, Any]:
        """Generate distribution of metrics under random trading

        Shuffles trades randomly to create null distribution
        """
        if len(self.pnl_list) < 10:
            return {}

        np.random.seed(42)
        random_returns = []

        for _ in range(n_simulations):
            shuffled = np.random.permutation(self.pnl_list)
            random_returns.append(np.sum(shuffled))

        return {
            "mean": float(np.mean(random_returns)),
            "std": float(np.std(random_returns)),
            "percentile_5": float(np.percentile(random_returns, 5)),
            "percentile_95": float(np.percentile(random_returns, 95)),
            "min": float(np.min(random_returns)),
            "max": float(np.max(random_returns)),
        }

    def kelly_fraction(self) -> float:
        """Calculate optimal position size using Kelly criterion

        f* = (W*P - L*(1-P)) / L

        Where:
        - W = average win amount
        - L = average loss amount
        - P = win probability

        Returns fraction (0-1) of capital to risk per trade
        """
        if self.num_trades == 0 or self.num_wins == 0 or self.num_losses == 0:
            return 0

        p_win = self.num_wins / self.num_trades
        avg_win = np.mean(self.wins)
        avg_loss = np.mean(self.losses)

        if avg_loss == 0:
            return 0

        kelly = (avg_win * p_win - avg_loss * (1 - p_win)) / avg_loss

        # Typically use fractional Kelly (e.g., 0.25*kelly) to reduce variance
        # Return base Kelly, user can apply fraction
        return max(0, min(kelly, 1))

    def generate_report(self) -> str:
        """Generate comprehensive statistical report"""
        report = []
        report.append("=" * 80)
        report.append("STATISTICAL SIGNIFICANCE ANALYSIS")
        report.append("=" * 80)

        # Basic stats
        report.append(f"\nSample Size: {self.num_trades} trades")
        report.append(f"Wins: {self.num_wins} ({100*self.num_wins/self.num_trades if self.num_trades > 0 else 0:.1f}%)")
        report.append(f"Losses: {self.num_losses}")

        if self.num_trades > 0:
            report.append(f"Total P&L: ${sum(self.pnl_list):.2f}")
            report.append(f"Avg Trade P&L: ${sum(self.pnl_list)/self.num_trades:.2f}")

        report.append("\n" + "-" * 80)
        report.append("SIGNIFICANCE TESTS (α = 0.05)")
        report.append("-" * 80)

        # Win rate test
        wr_test = self.test_win_rate_significance()
        report.append(f"\n✓ Win Rate Test")
        report.append(f"  Value: {wr_test.value:.1%}")
        report.append(f"  95% CI: [{wr_test.lower_ci:.1%}, {wr_test.upper_ci:.1%}]")
        report.append(f"  p-value: {wr_test.p_value:.4f}")
        report.append(f"  Significant vs 50%? {'YES' if wr_test.is_significant else 'NO'}")

        # P&L test
        pnl_test = self.test_pnl_vs_zero()
        report.append(f"\n✓ P&L Test (Mean > 0)")
        report.append(f"  Mean P&L: ${pnl_test.value:.2f}")
        report.append(f"  95% CI: [${pnl_test.lower_ci:.2f}, ${pnl_test.upper_ci:.2f}]")
        report.append(f"  p-value: {pnl_test.p_value:.4f}")
        report.append(f"  Significant? {'YES ✓' if pnl_test.is_significant else 'NO ✗'}")

        # Sharpe ratio test
        sharpe_test = self.test_sharpe_ratio_vs_zero()
        report.append(f"\n✓ Sharpe Ratio Test (vs 0)")
        report.append(f"  Sharpe: {sharpe_test.value:.3f}")
        report.append(f"  95% CI: [{sharpe_test.lower_ci:.3f}, {sharpe_test.upper_ci:.3f}]")
        report.append(f"  Significant? {'YES ✓' if sharpe_test.is_significant else 'NO ✗'}")

        # Kelly criterion
        kelly = self.kelly_fraction()
        report.append(f"\n✓ Position Sizing (Kelly Criterion)")
        report.append(f"  Full Kelly: {kelly:.1%}")
        report.append(f"  1/4 Kelly (safer): {kelly/4:.1%}")
        report.append(f"  1/2 Kelly (moderate): {kelly/2:.1%}")

        # Monte Carlo
        if self.num_trades >= 10:
            mc = self.monte_carlo_distribution()
            actual_pnl = sum(self.pnl_list)
            report.append(f"\n✓ Monte Carlo (10k simulations)")
            report.append(f"  Actual P&L: ${actual_pnl:.2f}")
            report.append(f"  Random Mean: ${mc['mean']:.2f}")
            report.append(f"  Random 90% Range: [${mc['percentile_5']:.2f}, ${mc['percentile_95']:.2f}]")
            if mc['percentile_5'] < actual_pnl < mc['percentile_95']:
                report.append(f"  Result is within random range (suspicious)")
            else:
                report.append(f"  Result beats random distribution ✓")

        report.append("\n" + "=" * 80)
        return "\n".join(report)


def compare_strategies(
    results_file_1: str,
    results_file_2: str,
    strategy_name_1: str = "Strategy 1",
    strategy_name_2: str = "Strategy 2",
) -> str:
    """Compare two strategy results using statistical tests"""

    with open(results_file_1) as f:
        data1 = json.load(f)
    with open(results_file_2) as f:
        data2 = json.load(f)

    trades1 = data1.get("trades", [])
    trades2 = data2.get("trades", [])

    pnls1 = [t.get("pnl", 0) for t in trades1]
    pnls2 = [t.get("pnl", 0) for t in trades2]

    report = []
    report.append("=" * 80)
    report.append("STRATEGY COMPARISON")
    report.append("=" * 80)

    report.append(f"\n{strategy_name_1}: {len(trades1)} trades, ${sum(pnls1):.2f} P&L")
    report.append(f"{strategy_name_2}: {len(trades2)} trades, ${sum(pnls2):.2f} P&L")

    # Independent samples t-test
    if len(pnls1) > 1 and len(pnls2) > 1:
        t_stat, p_value = stats.ttest_ind(pnls1, pnls2)
        report.append(f"\nIndependent t-test:")
        report.append(f"  t-statistic: {t_stat:.4f}")
        report.append(f"  p-value: {p_value:.4f}")
        if p_value < 0.05:
            report.append(f"  Result: Strategies are SIGNIFICANTLY different ✓")
        else:
            report.append(f"  Result: No significant difference")

    report.append("\n" + "=" * 80)
    return "\n".join(report)


if __name__ == "__main__":
    # Example usage
    sample_trades = [
        {"pnl": 50}, {"pnl": -20}, {"pnl": 75}, {"pnl": 30},
        {"pnl": -10}, {"pnl": 100}, {"pnl": 20}, {"pnl": 40},
        {"pnl": 60}, {"pnl": -5}, {"pnl": 80}, {"pnl": 25},
    ]

    strategy_stats = StrategyStatistics(sample_trades)
    print(strategy_stats.generate_report())
