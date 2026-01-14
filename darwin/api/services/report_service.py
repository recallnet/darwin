"""
Report service layer for Darwin API.

Provides business logic for:
- Performance metrics calculation
- Equity curve generation
- Trade log queries
- Candidate analysis
- Data export functionality
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from darwin.evaluation.metrics import calculate_all_metrics, calculate_equity_curve
from darwin.schemas.position import PositionRowV1
from darwin.schemas.run_config import RunConfigV1
from darwin.storage.position_ledger import PositionLedgerSQLite
from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.api.models.report import (
    MetricsSummaryResponse,
    EquityCurveResponse,
    EquityCurvePoint,
    TradeListItem,
    TradeDetailResponse,
    CandidateStats,
    FullReportResponse,
)


class ReportService:
    """Service for generating run reports."""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        """
        Initialize report service.

        Args:
            artifacts_dir: Artifacts directory (defaults to 'artifacts')
        """
        if artifacts_dir is None:
            artifacts_dir = Path("artifacts")
        self.artifacts_dir = Path(artifacts_dir)
        self.runs_dir = self.artifacts_dir / "runs"

    def get_position_ledger(self, run_id: str) -> PositionLedgerSQLite:
        """
        Get position ledger for a run.

        Args:
            run_id: Run ID

        Returns:
            PositionLedgerSQLite instance
        """
        ledger_path = self.runs_dir / run_id / "positions.sqlite"
        return PositionLedgerSQLite(ledger_path)

    def get_candidate_cache(self, run_id: str) -> CandidateCacheSQLite:
        """
        Get candidate cache for a run.

        Args:
            run_id: Run ID

        Returns:
            CandidateCacheSQLite instance
        """
        cache_path = self.runs_dir / run_id / "candidates.sqlite"
        return CandidateCacheSQLite(cache_path)

    def load_run_config(self, run_id: str) -> RunConfigV1:
        """
        Load run configuration.

        Args:
            run_id: Run ID

        Returns:
            RunConfigV1 instance
        """
        config_path = self.runs_dir / run_id / "run_config.json"
        with open(config_path, "r") as f:
            config_data = json.load(f)
        return RunConfigV1(**config_data)

    def get_metrics_summary(self, run_id: str) -> MetricsSummaryResponse:
        """
        Get performance metrics summary.

        Args:
            run_id: Run ID

        Returns:
            MetricsSummaryResponse with calculated metrics
        """
        # Load data
        ledger = self.get_position_ledger(run_id)
        config = self.load_run_config(run_id)

        # Get closed positions
        positions = ledger.list_positions(run_id=run_id)
        closed_positions = [p for p in positions if not p.is_open and p.pnl_usd is not None]

        # Calculate metrics
        starting_equity = config.portfolio.starting_equity_usd
        metrics = calculate_all_metrics(closed_positions, starting_equity)

        # Build response with percentages
        return MetricsSummaryResponse(
            total_return=metrics["total_return"],
            total_return_pct=metrics["total_return"] * 100,
            sharpe_ratio=metrics["sharpe_ratio"],
            sortino_ratio=metrics["sortino_ratio"],
            max_drawdown=metrics["max_drawdown"],
            max_drawdown_pct=metrics["max_drawdown"] * 100,
            total_trades=metrics["total_trades"],
            winning_trades=metrics["winning_trades"],
            losing_trades=metrics["losing_trades"],
            win_rate=metrics["win_rate"],
            win_rate_pct=metrics["win_rate"] * 100,
            profit_factor=metrics["profit_factor"],
            avg_win_loss_ratio=metrics["avg_win_loss_ratio"],
            starting_equity=starting_equity,
            final_equity=metrics["final_equity"],
        )

    def get_equity_curve(self, run_id: str) -> EquityCurveResponse:
        """
        Get equity curve data.

        Args:
            run_id: Run ID

        Returns:
            EquityCurveResponse with equity curve points
        """
        # Load data
        ledger = self.get_position_ledger(run_id)
        config = self.load_run_config(run_id)

        # Get closed positions
        positions = ledger.list_positions(run_id=run_id)
        closed_positions = [p for p in positions if not p.is_open and p.pnl_usd is not None]

        # Calculate equity curve
        starting_equity = config.portfolio.starting_equity_usd
        equity_data = calculate_equity_curve(closed_positions, starting_equity)

        # Build response
        data_points = [
            EquityCurvePoint(
                timestamp=point["timestamp"],
                equity=point["equity"],
                cumulative_pnl=point["cumulative_pnl"],
                cumulative_return=point["cumulative_return"],
            )
            for point in equity_data
        ]

        final_equity = equity_data[-1]["equity"] if equity_data else starting_equity

        return EquityCurveResponse(
            run_id=run_id,
            starting_equity=starting_equity,
            final_equity=final_equity,
            data_points=data_points,
        )

    def list_trades(
        self,
        run_id: str,
        page: int = 0,
        page_size: int = 20,
        symbol_filter: Optional[str] = None,
        direction_filter: Optional[str] = None,
        playbook_filter: Optional[str] = None,
    ) -> Tuple[List[TradeListItem], int]:
        """
        List trades with pagination and filtering.

        Args:
            run_id: Run ID
            page: Page number (0-indexed)
            page_size: Page size
            symbol_filter: Optional symbol filter
            direction_filter: Optional direction filter ('long' or 'short')
            playbook_filter: Optional playbook filter

        Returns:
            Tuple of (list of TradeListItem, total count)
        """
        # Load positions
        ledger = self.get_position_ledger(run_id)
        positions = ledger.list_positions(run_id=run_id)
        closed_positions = [p for p in positions if not p.is_open]

        # Apply filters
        filtered_positions = closed_positions

        if symbol_filter:
            filtered_positions = [p for p in filtered_positions if p.symbol == symbol_filter]

        if direction_filter:
            filtered_positions = [p for p in filtered_positions if p.direction == direction_filter]

        if playbook_filter:
            filtered_positions = [p for p in filtered_positions if p.playbook == playbook_filter]

        # Get total count
        total = len(filtered_positions)

        # Sort by entry timestamp (most recent first)
        filtered_positions.sort(key=lambda p: p.entry_timestamp, reverse=True)

        # Paginate
        start_idx = page * page_size
        end_idx = start_idx + page_size
        page_positions = filtered_positions[start_idx:end_idx]

        # Build list items
        items = [
            TradeListItem(
                position_id=p.position_id,
                symbol=p.symbol,
                direction=p.direction,
                playbook=p.playbook,
                entry_timestamp=p.entry_timestamp,
                entry_price=p.entry_price,
                exit_timestamp=p.exit_timestamp,
                exit_price=p.exit_price,
                exit_reason=p.exit_reason.value if p.exit_reason else None,
                size_usd=p.size_usd,
                size_units=p.size_units,
                pnl_usd=p.pnl_usd,
                pnl_pct=p.pnl_pct,
                r_multiple=p.r_multiple,
                bars_held=p.bars_held,
            )
            for p in page_positions
        ]

        return items, total

    def get_trade_detail(self, run_id: str, position_id: str) -> Optional[TradeDetailResponse]:
        """
        Get detailed trade information.

        Args:
            run_id: Run ID
            position_id: Position ID

        Returns:
            TradeDetailResponse if found, None otherwise
        """
        ledger = self.get_position_ledger(run_id)
        position = ledger.get_position(position_id)

        if position is None:
            return None

        return TradeDetailResponse(
            position=position.model_dump(),
        )

    def get_candidate_stats(self, run_id: str) -> CandidateStats:
        """
        Get candidate statistics.

        Args:
            run_id: Run ID

        Returns:
            CandidateStats with candidate analysis
        """
        cache = self.get_candidate_cache(run_id)
        candidates = cache.list_candidates(run_id=run_id)

        # Count taken vs skipped
        taken = sum(1 for c in candidates if c.decision == "TAKE")
        skipped = sum(1 for c in candidates if c.decision == "SKIP")
        total = len(candidates)

        # Breakdown by playbook
        by_playbook: Dict[str, Dict[str, int]] = {}

        for candidate in candidates:
            playbook = candidate.playbook.value
            if playbook not in by_playbook:
                by_playbook[playbook] = {"total": 0, "taken": 0, "skipped": 0}

            by_playbook[playbook]["total"] += 1
            if candidate.decision == "TAKE":
                by_playbook[playbook]["taken"] += 1
            else:
                by_playbook[playbook]["skipped"] += 1

        take_rate = taken / total if total > 0 else 0.0

        return CandidateStats(
            total_candidates=total,
            taken=taken,
            skipped=skipped,
            take_rate=take_rate,
            take_rate_pct=take_rate * 100,
            by_playbook=by_playbook,
        )

    def get_full_report(self, run_id: str) -> FullReportResponse:
        """
        Get complete run report.

        Args:
            run_id: Run ID

        Returns:
            FullReportResponse with all report data
        """
        # Get metrics
        metrics = self.get_metrics_summary(run_id)

        # Get candidate stats
        candidate_stats = self.get_candidate_stats(run_id)

        # Get config summary
        config = self.load_run_config(run_id)
        config_summary = {
            "symbols": config.market_scope.symbols,
            "timeframe": config.market_scope.primary_timeframe,
            "start_date": config.market_scope.start_date,
            "end_date": config.market_scope.end_date,
            "playbooks": [pb.name for pb in config.playbooks],
            "starting_equity": config.portfolio.starting_equity_usd,
            "max_positions": config.portfolio.max_positions,
        }

        return FullReportResponse(
            run_id=run_id,
            generated_at=datetime.utcnow(),
            metrics=metrics,
            candidate_stats=candidate_stats,
            config_summary=config_summary,
        )

    def export_trades_csv(self, run_id: str) -> str:
        """
        Export trades to CSV format.

        Args:
            run_id: Run ID

        Returns:
            CSV string
        """
        # Get all trades
        ledger = self.get_position_ledger(run_id)
        positions = ledger.list_positions(run_id=run_id)
        closed_positions = [p for p in positions if not p.is_open]

        # Build CSV
        lines = [
            "position_id,symbol,direction,playbook,entry_timestamp,entry_price,exit_timestamp,exit_price,exit_reason,size_usd,size_units,pnl_usd,pnl_pct,r_multiple,bars_held"
        ]

        for p in closed_positions:
            lines.append(
                f"{p.position_id},{p.symbol},{p.direction},{p.playbook},"
                f"{p.entry_timestamp.isoformat()},{p.entry_price},"
                f"{p.exit_timestamp.isoformat() if p.exit_timestamp else ''},"
                f"{p.exit_price if p.exit_price else ''},"
                f"{p.exit_reason.value if p.exit_reason else ''},"
                f"{p.size_usd},{p.size_units},"
                f"{p.pnl_usd if p.pnl_usd else ''},"
                f"{p.pnl_pct if p.pnl_pct else ''},"
                f"{p.r_multiple if p.r_multiple else ''},"
                f"{p.bars_held}"
            )

        return "\n".join(lines)

    def export_metrics_json(self, run_id: str) -> dict:
        """
        Export metrics to JSON format.

        Args:
            run_id: Run ID

        Returns:
            Dictionary with metrics
        """
        report = self.get_full_report(run_id)
        return report.model_dump()
