"""
Reports router for Darwin API.

Provides endpoints for:
- Performance metrics
- Equity curves
- Trade logs
- Trade details
- Candidate analysis
- Data export
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session

from darwin.api.db import get_db
from darwin.api.middleware.auth import get_auth_context, AuthContext
from darwin.api.models.report import (
    MetricsSummaryResponse,
    EquityCurveResponse,
    TradeListResponse,
    TradeDetailResponse,
    CandidateStats,
    FullReportResponse,
)
from darwin.api.services.report_service import ReportService
from darwin.api.services.run_service import RunService

router = APIRouter()

# Initialize services
report_service = ReportService()
run_service = RunService()


@router.get("/{run_id}", response_model=FullReportResponse)
async def get_full_report(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get complete run report with metrics, candidate stats, and config summary.

    All team members can view reports.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        FullReportResponse: Complete report

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        report = report_service.get_full_report(run_id)
        return report
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report data not found for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/metrics", response_model=MetricsSummaryResponse)
async def get_metrics(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get performance metrics summary.

    All team members can view metrics.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        MetricsSummaryResponse: Performance metrics

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        metrics = report_service.get_metrics_summary(run_id)
        return metrics
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metrics not available for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/equity", response_model=EquityCurveResponse)
async def get_equity_curve(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get equity curve data for visualization.

    All team members can view equity curves.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        EquityCurveResponse: Equity curve data points

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        equity_curve = report_service.get_equity_curve(run_id)
        return equity_curve
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equity curve not available for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/trades", response_model=TradeListResponse)
async def list_trades(
    run_id: str,
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    direction: Optional[str] = Query(None, description="Filter by direction (long/short)"),
    playbook: Optional[str] = Query(None, description="Filter by playbook"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    List trades with pagination and filtering.

    All team members can view trades.

    Args:
        run_id: Run ID
        page: Page number (0-indexed)
        page_size: Page size (max 100)
        symbol: Optional symbol filter
        direction: Optional direction filter
        playbook: Optional playbook filter
        auth: Authentication context
        db: Database session

    Returns:
        TradeListResponse: Paginated trade list

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        trades, total = report_service.list_trades(
            run_id=run_id,
            page=page,
            page_size=page_size,
            symbol_filter=symbol,
            direction_filter=direction,
            playbook_filter=playbook,
        )

        return TradeListResponse(
            run_id=run_id,
            trades=trades,
            total=total,
            page=page,
            page_size=page_size,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade data not available for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/trades/{position_id}", response_model=TradeDetailResponse)
async def get_trade_detail(
    run_id: str,
    position_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get detailed trade information.

    All team members can view trade details.

    Args:
        run_id: Run ID
        position_id: Position ID
        auth: Authentication context
        db: Database session

    Returns:
        TradeDetailResponse: Detailed trade data

    Raises:
        HTTPException: If run or trade not found
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        trade_detail = report_service.get_trade_detail(run_id, position_id)
        if trade_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trade '{position_id}' not found in run '{run_id}'",
            )
        return trade_detail
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade data not available for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/candidates", response_model=CandidateStats)
async def get_candidate_stats(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get candidate statistics (taken vs skipped analysis).

    All team members can view candidate stats.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        CandidateStats: Candidate statistics

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        candidate_stats = report_service.get_candidate_stats(run_id)
        return candidate_stats
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate data not available for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/export/trades.csv")
async def export_trades_csv(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Export trades to CSV format.

    All team members can export data.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        CSV file content

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        csv_content = report_service.export_trades_csv(run_id)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={run_id}_trades.csv"
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade data not available for run '{run_id}'. Run may not have completed.",
        )


@router.get("/{run_id}/export/report.json")
async def export_report_json(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Export full report to JSON format.

    All team members can export data.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        JSON file content

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    try:
        json_data = report_service.export_metrics_json(run_id)
        return Response(
            content=json.dumps(json_data, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={run_id}_report.json"
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report data not available for run '{run_id}'. Run may not have completed.",
        )
