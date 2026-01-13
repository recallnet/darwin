"""Run report generation."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from darwin.evaluation.metrics import calculate_all_metrics, calculate_equity_curve
from darwin.evaluation.plots import generate_all_plots
from darwin.schemas.position import PositionRowV1
from darwin.schemas.run_config import RunConfigV1
from darwin.storage.position_ledger import PositionLedgerSQLite
from darwin.utils.helpers import format_pct, format_usd

logger = logging.getLogger(__name__)


class RunReportBuilder:
    """
    Build run reports from position ledger.

    Generates:
    - report.json: Structured metrics
    - report.md: Human-readable report
    - plots/ directory: Visualization plots
    """

    def __init__(
        self,
        run_id: str,
        run_config: RunConfigV1,
        position_ledger: PositionLedgerSQLite,
        artifacts_dir: Path,
    ):
        """
        Initialize run report builder.

        Args:
            run_id: Run identifier
            run_config: Run configuration
            position_ledger: Position ledger with trade data
            artifacts_dir: Artifacts directory
        """
        self.run_id = run_id
        self.run_config = run_config
        self.position_ledger = position_ledger
        self.artifacts_dir = Path(artifacts_dir)
        self.report_dir = self.artifacts_dir / "reports" / run_id

    def build_report(self, generate_plots: bool = True) -> dict:
        """
        Build complete run report.

        Args:
            generate_plots: Whether to generate plots (default: True)

        Returns:
            Dictionary with report data

        Example:
            >>> builder = RunReportBuilder(...)
            >>> report = builder.build_report()
        """
        logger.info(f"Building run report for {self.run_id}")

        # Create report directory
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Load positions
        positions = self.position_ledger.list_positions(run_id=self.run_id)
        closed_positions = [p for p in positions if not p.is_open]

        logger.info(f"  Total positions: {len(positions)}")
        logger.info(f"  Closed positions: {len(closed_positions)}")

        # Calculate metrics
        starting_equity = self.run_config.portfolio.starting_equity_usd
        metrics = calculate_all_metrics(closed_positions, starting_equity)

        # Build report structure
        report = {
            "run_id": self.run_id,
            "generated_at": datetime.now().isoformat(),
            "summary": self._build_summary(metrics, starting_equity),
            "metrics": metrics,
            "trade_log": self._build_trade_log(closed_positions),
            "config_summary": self._build_config_summary(),
        }

        # Save report.json
        report_json_path = self.report_dir / "report.json"
        with open(report_json_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"  report.json saved: {report_json_path}")

        # Generate report.md
        self._generate_markdown_report(report)

        # Generate plots
        if generate_plots and closed_positions:
            plots_dir = self.report_dir / "plots"
            generate_all_plots(closed_positions, starting_equity, plots_dir)

        logger.info(f"Run report complete: {self.report_dir}")
        return report

    def _build_summary(self, metrics: dict, starting_equity: float) -> dict:
        """Build summary section."""
        return {
            "starting_equity_usd": starting_equity,
            "final_equity_usd": metrics["final_equity"],
            "total_return_pct": metrics["total_return"] * 100,
            "total_trades": metrics["total_trades"],
            "winning_trades": metrics["winning_trades"],
            "losing_trades": metrics["losing_trades"],
            "win_rate_pct": metrics["win_rate"] * 100,
            "sharpe_ratio": metrics["sharpe_ratio"],
            "sortino_ratio": metrics["sortino_ratio"],
            "max_drawdown_pct": metrics["max_drawdown"] * 100,
            "profit_factor": metrics["profit_factor"],
            "avg_win_loss_ratio": metrics["avg_win_loss_ratio"],
        }

    def _build_trade_log(self, positions: List[PositionRowV1]) -> List[dict]:
        """Build trade log."""
        trade_log = []

        for position in sorted(positions, key=lambda p: p.entry_timestamp):
            trade_log.append(
                {
                    "position_id": position.position_id,
                    "symbol": position.symbol,
                    "direction": position.direction,
                    "entry_timestamp": position.entry_timestamp.isoformat()
                    if position.entry_timestamp
                    else None,
                    "exit_timestamp": position.exit_timestamp.isoformat()
                    if position.exit_timestamp
                    else None,
                    "entry_price": position.entry_price,
                    "exit_price": position.exit_price,
                    "size_usd": position.size_usd,
                    "pnl_usd": position.pnl_usd,
                    "pnl_pct": position.pnl_pct * 100 if position.pnl_pct else None,
                    "r_multiple": position.r_multiple,
                    "exit_reason": position.exit_reason.value if position.exit_reason else None,
                    "bars_held": (
                        position.exit_bar_index - position.entry_bar_index
                        if position.exit_bar_index
                        else None
                    ),
                }
            )

        return trade_log

    def _build_config_summary(self) -> dict:
        """Build config summary."""
        return {
            "symbols": self.run_config.market_scope.symbols,
            "timeframe": self.run_config.market_scope.primary_timeframe,
            "max_positions": self.run_config.portfolio.max_positions,
            "playbooks": [pb.name for pb in self.run_config.playbooks if pb.enabled],
            "llm_provider": self.run_config.llm.provider,
            "llm_model": self.run_config.llm.model,
        }

    def _generate_markdown_report(self, report: dict) -> None:
        """Generate markdown report."""
        md_lines = []

        # Header
        md_lines.append(f"# Run Report: {self.run_id}")
        md_lines.append("")
        md_lines.append(f"**Generated:** {report['generated_at']}")
        md_lines.append("")

        # Summary
        summary = report["summary"]
        md_lines.append("## Summary")
        md_lines.append("")
        md_lines.append(f"- **Starting Equity:** {format_usd(summary['starting_equity_usd'])}")
        md_lines.append(f"- **Final Equity:** {format_usd(summary['final_equity_usd'])}")
        md_lines.append(
            f"- **Total Return:** {format_pct(summary['total_return_pct'] / 100, sign=True)}"
        )
        md_lines.append(f"- **Total Trades:** {summary['total_trades']}")
        md_lines.append(f"- **Win Rate:** {summary['win_rate_pct']:.2f}%")
        md_lines.append("")

        # Metrics
        md_lines.append("## Performance Metrics")
        md_lines.append("")
        md_lines.append(f"- **Sharpe Ratio:** {summary['sharpe_ratio']:.2f}")
        md_lines.append(f"- **Sortino Ratio:** {summary['sortino_ratio']:.2f}")
        md_lines.append(f"- **Max Drawdown:** {summary['max_drawdown_pct']:.2f}%")
        md_lines.append(f"- **Profit Factor:** {summary['profit_factor']:.2f}")
        md_lines.append(f"- **Avg Win/Loss Ratio:** {summary['avg_win_loss_ratio']:.2f}")
        md_lines.append("")

        # Trade Breakdown
        md_lines.append("## Trade Breakdown")
        md_lines.append("")
        md_lines.append(f"- **Winning Trades:** {summary['winning_trades']}")
        md_lines.append(f"- **Losing Trades:** {summary['losing_trades']}")
        md_lines.append("")

        # Config
        config = report["config_summary"]
        md_lines.append("## Configuration")
        md_lines.append("")
        md_lines.append(f"- **Symbols:** {', '.join(config['symbols'])}")
        md_lines.append(f"- **Timeframe:** {config['timeframe']}")
        md_lines.append(f"- **Max Positions:** {config['max_positions']}")
        md_lines.append(f"- **Playbooks:** {', '.join(config['playbooks'])}")
        md_lines.append(f"- **LLM:** {config['llm_provider']} / {config['llm_model']}")
        md_lines.append("")

        # Plots
        md_lines.append("## Plots")
        md_lines.append("")
        md_lines.append("- [Equity Curve](plots/equity_curve.html)")
        md_lines.append("- [Drawdown](plots/drawdown.html)")
        md_lines.append("- [Returns Distribution](plots/returns_distribution.html)")
        md_lines.append("- [Trade Timeline](plots/trade_timeline.html)")
        md_lines.append("")

        # Write markdown file
        md_path = self.report_dir / "report.md"
        with open(md_path, "w") as f:
            f.write("\n".join(md_lines))
        logger.info(f"  report.md saved: {md_path}")
