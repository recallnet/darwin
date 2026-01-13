"""Performance metrics calculation from position ledger.

All metrics are calculated from the position ledger (single source of truth).
"""

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

from darwin.schemas.position import PositionRowV1
from darwin.utils.helpers import safe_div

logger = logging.getLogger(__name__)


def total_return(positions: List[PositionRowV1], starting_equity: float) -> float:
    """
    Calculate total return from positions.

    Args:
        positions: List of closed positions
        starting_equity: Starting equity in USD

    Returns:
        Total return as decimal (e.g., 0.15 for 15% return)

    Example:
        >>> positions = [...]
        >>> total_return(positions, starting_equity=10000.0)
        0.125  # 12.5% return
    """
    total_pnl = sum(p.pnl_usd for p in positions if p.pnl_usd is not None)
    return safe_div(total_pnl, starting_equity)


def sharpe_ratio(
    positions: List[PositionRowV1], risk_free_rate: float = 0.0, periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe ratio from position returns.

    Args:
        positions: List of closed positions
        risk_free_rate: Risk-free rate (annualized, default: 0.0)
        periods_per_year: Number of periods per year (default: 252 for daily)

    Returns:
        Annualized Sharpe ratio

    Example:
        >>> sharpe_ratio(positions)
        1.25
    """
    if not positions:
        return 0.0

    returns = [p.pnl_pct for p in positions if p.pnl_pct is not None]
    if not returns:
        return 0.0

    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate / periods_per_year

    if len(excess_returns) < 2:
        return 0.0

    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess < 1e-9:
        return 0.0

    sharpe = mean_excess / std_excess * np.sqrt(periods_per_year)
    return float(sharpe)


def sortino_ratio(
    positions: List[PositionRowV1],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    target_return: float = 0.0,
) -> float:
    """
    Calculate Sortino ratio from position returns.

    Like Sharpe but only penalizes downside volatility.

    Args:
        positions: List of closed positions
        risk_free_rate: Risk-free rate (annualized, default: 0.0)
        periods_per_year: Number of periods per year (default: 252)
        target_return: Target return for downside calculation (default: 0.0)

    Returns:
        Annualized Sortino ratio

    Example:
        >>> sortino_ratio(positions)
        1.45
    """
    if not positions:
        return 0.0

    returns = [p.pnl_pct for p in positions if p.pnl_pct is not None]
    if not returns:
        return 0.0

    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate / periods_per_year

    if len(excess_returns) < 2:
        return 0.0

    mean_excess = np.mean(excess_returns)

    # Downside deviation: only consider returns below target
    downside_returns = excess_returns - target_return
    downside_returns = downside_returns[downside_returns < 0]

    if len(downside_returns) == 0:
        # No downside, infinite Sortino (cap at 99.0)
        return 99.0

    downside_std = np.std(downside_returns, ddof=1)

    if downside_std < 1e-9:
        return 0.0

    sortino = mean_excess / downside_std * np.sqrt(periods_per_year)
    return float(sortino)


def max_drawdown(equity_curve: List[float]) -> float:
    """
    Calculate maximum drawdown from equity curve.

    Args:
        equity_curve: List of equity values over time

    Returns:
        Maximum drawdown as decimal (e.g., 0.15 for 15% drawdown)

    Example:
        >>> equity_curve = [10000, 10500, 9800, 10200, 11000]
        >>> max_drawdown(equity_curve)
        0.0666...  # 6.67% drawdown
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0

    equity_array = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity_array)
    drawdown = (running_max - equity_array) / running_max

    return float(np.max(drawdown))


def win_rate(positions: List[PositionRowV1]) -> float:
    """
    Calculate win rate from positions.

    Args:
        positions: List of closed positions

    Returns:
        Win rate as decimal (e.g., 0.55 for 55% win rate)

    Example:
        >>> win_rate(positions)
        0.55
    """
    if not positions:
        return 0.0

    winning_trades = sum(1 for p in positions if p.pnl_usd is not None and p.pnl_usd > 0)
    total_trades = len([p for p in positions if p.pnl_usd is not None])

    return safe_div(winning_trades, total_trades)


def profit_factor(positions: List[PositionRowV1]) -> float:
    """
    Calculate profit factor (gross profit / gross loss).

    Args:
        positions: List of closed positions

    Returns:
        Profit factor (> 1.0 is profitable)

    Example:
        >>> profit_factor(positions)
        1.35
    """
    if not positions:
        return 0.0

    gross_profit = sum(p.pnl_usd for p in positions if p.pnl_usd is not None and p.pnl_usd > 0)
    gross_loss = abs(sum(p.pnl_usd for p in positions if p.pnl_usd is not None and p.pnl_usd < 0))

    return safe_div(gross_profit, gross_loss)


def avg_win_loss_ratio(positions: List[PositionRowV1]) -> float:
    """
    Calculate average win / average loss ratio.

    Args:
        positions: List of closed positions

    Returns:
        Average win/loss ratio

    Example:
        >>> avg_win_loss_ratio(positions)
        1.8
    """
    if not positions:
        return 0.0

    wins = [p.pnl_usd for p in positions if p.pnl_usd is not None and p.pnl_usd > 0]
    losses = [abs(p.pnl_usd) for p in positions if p.pnl_usd is not None and p.pnl_usd < 0]

    if not wins or not losses:
        return 0.0

    avg_win = np.mean(wins)
    avg_loss = np.mean(losses)

    return safe_div(avg_win, avg_loss)


def calculate_equity_curve(
    positions: List[PositionRowV1], starting_equity: float
) -> List[dict]:
    """
    Calculate equity curve from positions.

    Args:
        positions: List of closed positions (should be sorted by exit_timestamp)
        starting_equity: Starting equity in USD

    Returns:
        List of dicts with: timestamp, equity, pnl, cumulative_pnl

    Example:
        >>> curve = calculate_equity_curve(positions, 10000.0)
        >>> curve[0]
        {'timestamp': '2024-01-01T00:00:00', 'equity': 10150.0, 'pnl': 150.0, ...}
    """
    equity_curve = []
    cumulative_pnl = 0.0

    for position in sorted(positions, key=lambda p: p.exit_timestamp or ""):
        if position.pnl_usd is None or position.exit_timestamp is None:
            continue

        cumulative_pnl += position.pnl_usd
        equity = starting_equity + cumulative_pnl

        equity_curve.append(
            {
                "timestamp": position.exit_timestamp,
                "equity": equity,
                "pnl": position.pnl_usd,
                "cumulative_pnl": cumulative_pnl,
                "position_id": position.position_id,
            }
        )

    return equity_curve


def calculate_all_metrics(
    positions: List[PositionRowV1], starting_equity: float
) -> dict:
    """
    Calculate all metrics from positions.

    Args:
        positions: List of closed positions
        starting_equity: Starting equity in USD

    Returns:
        Dictionary with all calculated metrics

    Example:
        >>> metrics = calculate_all_metrics(positions, 10000.0)
        >>> metrics["total_return"]
        0.125
        >>> metrics["sharpe_ratio"]
        1.25
    """
    closed_positions = [p for p in positions if not p.is_open and p.pnl_usd is not None]

    # Calculate equity curve
    equity_curve_data = calculate_equity_curve(closed_positions, starting_equity)
    equity_values = [starting_equity] + [e["equity"] for e in equity_curve_data]

    return {
        "total_return": total_return(closed_positions, starting_equity),
        "sharpe_ratio": sharpe_ratio(closed_positions),
        "sortino_ratio": sortino_ratio(closed_positions),
        "max_drawdown": max_drawdown(equity_values),
        "win_rate": win_rate(closed_positions),
        "profit_factor": profit_factor(closed_positions),
        "avg_win_loss_ratio": avg_win_loss_ratio(closed_positions),
        "total_trades": len(closed_positions),
        "winning_trades": sum(1 for p in closed_positions if p.pnl_usd > 0),
        "losing_trades": sum(1 for p in closed_positions if p.pnl_usd < 0),
        "final_equity": equity_values[-1] if equity_values else starting_equity,
    }
