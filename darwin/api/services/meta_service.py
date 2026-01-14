"""
Meta-analysis service layer for Darwin API.

Provides business logic for:
- Multi-run comparisons
- Equity curve overlays
- Run rankings
- Statistical tests
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from collections import defaultdict

import numpy as np
from scipy import stats

from darwin.api.services.report_service import ReportService
from darwin.api.services.run_service import RunService
from darwin.api.models.meta import (
    RunMetricsComparison,
    ComparisonResponse,
    EquityOverlayResponse,
    EquityOverlayPoint,
    RankingEntry,
    RankingsResponse,
    StatisticalTest,
    StatisticalComparisonResponse,
)


class MetaService:
    """Service for meta-analysis across multiple runs."""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        """
        Initialize meta-analysis service.

        Args:
            artifacts_dir: Artifacts directory (defaults to 'artifacts')
        """
        self.report_service = ReportService(artifacts_dir)
        self.run_service = RunService(artifacts_dir)

    def compare_runs(self, run_ids: List[str]) -> ComparisonResponse:
        """
        Compare multiple runs side-by-side.

        Args:
            run_ids: List of run IDs to compare

        Returns:
            ComparisonResponse with metrics for all runs
        """
        runs_metrics = []
        all_metrics = defaultdict(dict)

        for run_id in run_ids:
            try:
                # Get metrics
                metrics = self.report_service.get_metrics_summary(run_id)

                # Get config for context
                config = self.report_service.load_run_config(run_id)

                # Build comparison entry
                run_comparison = RunMetricsComparison(
                    run_id=run_id,
                    description=config.description,
                    symbols=config.market_scope.symbols,
                    playbooks=[pb.name for pb in config.playbooks],
                    start_date=config.market_scope.start_date,
                    end_date=config.market_scope.end_date,
                    total_return=metrics.total_return,
                    total_return_pct=metrics.total_return_pct,
                    sharpe_ratio=metrics.sharpe_ratio,
                    sortino_ratio=metrics.sortino_ratio,
                    max_drawdown=metrics.max_drawdown,
                    max_drawdown_pct=metrics.max_drawdown_pct,
                    win_rate=metrics.win_rate,
                    win_rate_pct=metrics.win_rate_pct,
                    profit_factor=metrics.profit_factor,
                    total_trades=metrics.total_trades,
                    final_equity=metrics.final_equity,
                )

                runs_metrics.append(run_comparison)

                # Track for best_by_metric
                all_metrics["total_return"][run_id] = metrics.total_return
                all_metrics["sharpe_ratio"][run_id] = metrics.sharpe_ratio
                all_metrics["sortino_ratio"][run_id] = metrics.sortino_ratio
                all_metrics["max_drawdown"][run_id] = metrics.max_drawdown  # Lower is better
                all_metrics["win_rate"][run_id] = metrics.win_rate
                all_metrics["profit_factor"][run_id] = metrics.profit_factor

            except FileNotFoundError:
                # Skip runs that don't have data yet
                continue

        # Find best run for each metric
        best_by_metric = {}

        # Higher is better
        for metric in ["total_return", "sharpe_ratio", "sortino_ratio", "win_rate", "profit_factor"]:
            if all_metrics[metric]:
                best_by_metric[metric] = max(all_metrics[metric], key=all_metrics[metric].get)

        # Lower is better (drawdown)
        if all_metrics["max_drawdown"]:
            best_by_metric["max_drawdown"] = min(
                all_metrics["max_drawdown"], key=all_metrics["max_drawdown"].get
            )

        return ComparisonResponse(
            runs=runs_metrics,
            best_by_metric=best_by_metric,
            generated_at=datetime.utcnow(),
        )

    def overlay_equity_curves(self, run_ids: List[str]) -> EquityOverlayResponse:
        """
        Overlay equity curves from multiple runs.

        Aligns timestamps and interpolates missing data points.

        Args:
            run_ids: List of run IDs

        Returns:
            EquityOverlayResponse with overlaid curves
        """
        # Load equity curves
        equity_curves = {}
        starting_equities = {}
        final_equities = {}

        for run_id in run_ids:
            try:
                equity_data = self.report_service.get_equity_curve(run_id)
                equity_curves[run_id] = equity_data.data_points
                starting_equities[run_id] = equity_data.starting_equity
                final_equities[run_id] = equity_data.final_equity
            except FileNotFoundError:
                # Skip runs without data
                continue

        # Collect all unique timestamps
        all_timestamps = set()
        for points in equity_curves.values():
            for point in points:
                all_timestamps.add(point.timestamp)

        # Sort timestamps
        sorted_timestamps = sorted(all_timestamps)

        # Build overlay points
        overlay_points = []

        for timestamp in sorted_timestamps:
            equities = {}

            for run_id, points in equity_curves.items():
                # Find equity at this timestamp (or closest previous)
                equity_value = starting_equities[run_id]  # Default to starting

                for point in points:
                    if point.timestamp <= timestamp:
                        equity_value = point.equity
                    else:
                        break

                equities[run_id] = equity_value

            overlay_points.append(
                EquityOverlayPoint(
                    timestamp=timestamp,
                    equities=equities,
                )
            )

        return EquityOverlayResponse(
            run_ids=list(equity_curves.keys()),
            starting_equity=starting_equities,
            final_equity=final_equities,
            data_points=overlay_points,
        )

    def rank_runs(
        self,
        run_ids: List[str],
        metric: str = "sharpe_ratio",
    ) -> RankingsResponse:
        """
        Rank runs by a specific metric.

        Args:
            run_ids: List of run IDs
            metric: Metric to rank by (default: 'sharpe_ratio')

        Returns:
            RankingsResponse with ranked runs
        """
        runs_with_metrics = []

        for run_id in run_ids:
            try:
                metrics = self.report_service.get_metrics_summary(run_id)
                config = self.report_service.load_run_config(run_id)

                # Get metric value
                metric_value = getattr(metrics, metric, None)
                if metric_value is None:
                    continue

                runs_with_metrics.append({
                    "run_id": run_id,
                    "description": config.description,
                    "value": float(metric_value),
                    "symbols": config.market_scope.symbols,
                    "playbooks": [pb.name for pb in config.playbooks],
                })

            except (FileNotFoundError, AttributeError):
                # Skip runs without data or invalid metric
                continue

        # Sort by metric (higher is better for most metrics, lower for drawdown)
        if metric == "max_drawdown":
            runs_with_metrics.sort(key=lambda x: x["value"])  # Lower is better
        else:
            runs_with_metrics.sort(key=lambda x: x["value"], reverse=True)  # Higher is better

        # Build rankings
        rankings = [
            RankingEntry(
                rank=idx + 1,
                run_id=run["run_id"],
                description=run["description"],
                value=run["value"],
                symbols=run["symbols"],
                playbooks=run["playbooks"],
            )
            for idx, run in enumerate(runs_with_metrics)
        ]

        return RankingsResponse(
            metric=metric,
            rankings=rankings,
            total_runs=len(rankings),
        )

    def statistical_comparison(
        self,
        run_ids: List[str],
        metric: str = "returns",
    ) -> StatisticalComparisonResponse:
        """
        Perform statistical tests comparing runs.

        Uses t-tests to determine if differences in returns are statistically significant.

        Args:
            run_ids: List of run IDs (min 2)
            metric: Metric to compare (currently only 'returns' supported)

        Returns:
            StatisticalComparisonResponse with test results
        """
        # Load return data for each run
        returns_data = {}

        for run_id in run_ids:
            try:
                ledger = self.report_service.get_position_ledger(run_id)
                positions = ledger.list_positions(run_id=run_id)
                closed_positions = [p for p in positions if not p.is_open and p.pnl_pct is not None]

                # Get returns
                returns = [p.pnl_pct for p in closed_positions]
                returns_data[run_id] = returns

            except FileNotFoundError:
                continue

        # Perform pairwise t-tests
        tests = []

        run_ids_with_data = list(returns_data.keys())
        for i, run_a in enumerate(run_ids_with_data):
            for run_b in run_ids_with_data[i + 1 :]:
                returns_a = np.array(returns_data[run_a])
                returns_b = np.array(returns_data[run_b])

                # Perform t-test
                t_stat, p_value = stats.ttest_ind(returns_a, returns_b)

                # Determine significance
                significant = p_value < 0.05

                # Build interpretation
                mean_a = np.mean(returns_a)
                mean_b = np.mean(returns_b)

                if significant:
                    if mean_a > mean_b:
                        interpretation = f"Run {run_a} significantly outperforms {run_b} (p={p_value:.3f})"
                    else:
                        interpretation = f"Run {run_b} significantly outperforms {run_a} (p={p_value:.3f})"
                else:
                    interpretation = f"No significant difference between {run_a} and {run_b} (p={p_value:.3f})"

                tests.append(
                    StatisticalTest(
                        test_name="t-test",
                        run_a=run_a,
                        run_b=run_b,
                        statistic=float(t_stat),
                        p_value=float(p_value),
                        significant=significant,
                        interpretation=interpretation,
                    )
                )

        return StatisticalComparisonResponse(
            metric=metric,
            tests=tests,
        )

    def export_comparison_csv(self, run_ids: List[str]) -> str:
        """
        Export comparison data to CSV format.

        Args:
            run_ids: List of run IDs

        Returns:
            CSV string
        """
        comparison = self.compare_runs(run_ids)

        # Build CSV
        lines = [
            "run_id,description,symbols,playbooks,total_return_pct,sharpe_ratio,sortino_ratio,max_drawdown_pct,win_rate_pct,profit_factor,total_trades,final_equity"
        ]

        for run in comparison.runs:
            symbols_str = ";".join(run.symbols)
            playbooks_str = ";".join(run.playbooks)

            lines.append(
                f"{run.run_id},{run.description},{symbols_str},{playbooks_str},"
                f"{run.total_return_pct},{run.sharpe_ratio},{run.sortino_ratio},"
                f"{run.max_drawdown_pct},{run.win_rate_pct},{run.profit_factor},"
                f"{run.total_trades},{run.final_equity}"
            )

        return "\n".join(lines)
