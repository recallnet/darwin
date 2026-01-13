"""Plot generation for evaluation reports."""

import logging
from pathlib import Path
from typing import List, Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from darwin.schemas.position import PositionRowV1

logger = logging.getLogger(__name__)


def equity_curve(
    positions: List[PositionRowV1],
    starting_equity: float,
    output_path: Optional[Path] = None,
    title: str = "Equity Curve",
) -> go.Figure:
    """
    Generate equity curve plot.

    Args:
        positions: List of closed positions
        starting_equity: Starting equity in USD
        output_path: Path to save plot (if None, just return figure)
        title: Plot title

    Returns:
        Plotly figure

    Example:
        >>> fig = equity_curve(positions, 10000.0, output_path=Path("equity.html"))
    """
    # Calculate equity curve
    timestamps = []
    equity_values = [starting_equity]
    cumulative_pnl = 0.0

    sorted_positions = sorted(
        [p for p in positions if p.exit_timestamp and p.pnl_usd is not None],
        key=lambda p: p.exit_timestamp,
    )

    for position in sorted_positions:
        cumulative_pnl += position.pnl_usd
        timestamps.append(position.exit_timestamp)
        equity_values.append(starting_equity + cumulative_pnl)

    # Create figure
    fig = go.Figure()

    # Add equity curve
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=equity_values[1:],
            mode="lines",
            name="Equity",
            line=dict(color="blue", width=2),
        )
    )

    # Add starting equity line
    if timestamps:
        fig.add_hline(
            y=starting_equity,
            line_dash="dash",
            line_color="gray",
            annotation_text="Starting Equity",
            annotation_position="right",
        )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Equity (USD)",
        hovermode="x unified",
        template="plotly_white",
    )

    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))
        logger.info(f"Equity curve saved: {output_path}")

    return fig


def drawdown_chart(
    positions: List[PositionRowV1],
    starting_equity: float,
    output_path: Optional[Path] = None,
    title: str = "Drawdown",
) -> go.Figure:
    """
    Generate drawdown chart.

    Args:
        positions: List of closed positions
        starting_equity: Starting equity in USD
        output_path: Path to save plot (if None, just return figure)
        title: Plot title

    Returns:
        Plotly figure

    Example:
        >>> fig = drawdown_chart(positions, 10000.0, output_path=Path("drawdown.html"))
    """
    # Calculate equity curve and drawdown
    timestamps = []
    equity_values = [starting_equity]
    cumulative_pnl = 0.0

    sorted_positions = sorted(
        [p for p in positions if p.exit_timestamp and p.pnl_usd is not None],
        key=lambda p: p.exit_timestamp,
    )

    for position in sorted_positions:
        cumulative_pnl += position.pnl_usd
        timestamps.append(position.exit_timestamp)
        equity_values.append(starting_equity + cumulative_pnl)

    # Calculate drawdown
    running_max = [equity_values[0]]
    for equity in equity_values[1:]:
        running_max.append(max(running_max[-1], equity))

    drawdown = [(running_max[i] - equity_values[i]) / running_max[i] * 100 for i in range(len(equity_values))]

    # Create figure
    fig = go.Figure()

    # Add drawdown area
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=drawdown[1:],
            mode="lines",
            name="Drawdown",
            fill="tozeroy",
            line=dict(color="red", width=2),
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        hovermode="x unified",
        template="plotly_white",
        yaxis=dict(autorange="reversed"),  # Drawdown goes down
    )

    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))
        logger.info(f"Drawdown chart saved: {output_path}")

    return fig


def returns_distribution(
    positions: List[PositionRowV1],
    output_path: Optional[Path] = None,
    title: str = "Returns Distribution",
) -> go.Figure:
    """
    Generate returns distribution histogram.

    Args:
        positions: List of closed positions
        output_path: Path to save plot (if None, just return figure)
        title: Plot title

    Returns:
        Plotly figure

    Example:
        >>> fig = returns_distribution(positions, output_path=Path("returns.html"))
    """
    returns = [p.pnl_pct * 100 for p in positions if p.pnl_pct is not None]

    if not returns:
        logger.warning("No returns data available for distribution plot")
        return go.Figure()

    fig = go.Figure()

    # Add histogram
    fig.add_trace(
        go.Histogram(
            x=returns,
            nbinsx=30,
            name="Returns",
            marker=dict(color="blue", line=dict(color="white", width=1)),
        )
    )

    # Add vertical line at 0
    fig.add_vline(x=0, line_dash="dash", line_color="gray", annotation_text="Break-even")

    fig.update_layout(
        title=title,
        xaxis_title="Return (%)",
        yaxis_title="Frequency",
        template="plotly_white",
        showlegend=False,
    )

    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))
        logger.info(f"Returns distribution saved: {output_path}")

    return fig


def trade_timeline(
    positions: List[PositionRowV1],
    output_path: Optional[Path] = None,
    title: str = "Trade Timeline",
) -> go.Figure:
    """
    Generate trade timeline showing wins/losses over time.

    Args:
        positions: List of closed positions
        output_path: Path to save plot (if None, just return figure)
        title: Plot title

    Returns:
        Plotly figure

    Example:
        >>> fig = trade_timeline(positions, output_path=Path("timeline.html"))
    """
    sorted_positions = sorted(
        [p for p in positions if p.exit_timestamp and p.pnl_usd is not None],
        key=lambda p: p.exit_timestamp,
    )

    if not sorted_positions:
        logger.warning("No positions data available for timeline plot")
        return go.Figure()

    # Separate wins and losses
    win_timestamps = []
    win_pnl = []
    loss_timestamps = []
    loss_pnl = []

    for position in sorted_positions:
        if position.pnl_usd > 0:
            win_timestamps.append(position.exit_timestamp)
            win_pnl.append(position.pnl_usd)
        else:
            loss_timestamps.append(position.exit_timestamp)
            loss_pnl.append(position.pnl_usd)

    fig = go.Figure()

    # Add winning trades
    if win_timestamps:
        fig.add_trace(
            go.Scatter(
                x=win_timestamps,
                y=win_pnl,
                mode="markers",
                name="Winning Trades",
                marker=dict(color="green", size=8, symbol="triangle-up"),
            )
        )

    # Add losing trades
    if loss_timestamps:
        fig.add_trace(
            go.Scatter(
                x=loss_timestamps,
                y=loss_pnl,
                mode="markers",
                name="Losing Trades",
                marker=dict(color="red", size=8, symbol="triangle-down"),
            )
        )

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="PnL (USD)",
        hovermode="closest",
        template="plotly_white",
    )

    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))
        logger.info(f"Trade timeline saved: {output_path}")

    return fig


def generate_all_plots(
    positions: List[PositionRowV1],
    starting_equity: float,
    plots_dir: Path,
) -> None:
    """
    Generate all evaluation plots.

    Args:
        positions: List of closed positions
        starting_equity: Starting equity in USD
        plots_dir: Directory to save plots

    Example:
        >>> generate_all_plots(positions, 10000.0, Path("artifacts/reports/run_001/plots"))
    """
    plots_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating plots in {plots_dir}")

    equity_curve(positions, starting_equity, output_path=plots_dir / "equity_curve.html")
    drawdown_chart(positions, starting_equity, output_path=plots_dir / "drawdown.html")
    returns_distribution(positions, output_path=plots_dir / "returns_distribution.html")
    trade_timeline(positions, output_path=plots_dir / "trade_timeline.html")

    logger.info("All plots generated")
