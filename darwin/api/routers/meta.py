"""
Meta-analysis router for Darwin API.

Provides endpoints for:
- Multi-run comparisons
- Equity curve overlays
- Run rankings
- Statistical tests
- Comparison exports
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session

from darwin.api.db import get_db
from darwin.api.middleware.auth import get_auth_context, AuthContext
from darwin.api.models.meta import (
    CompareRunsRequest,
    ComparisonResponse,
    EquityOverlayResponse,
    RankingsResponse,
    StatisticalComparisonResponse,
)
from darwin.api.services.meta_service import MetaService
from darwin.api.services.run_service import RunService

router = APIRouter()

# Initialize services
meta_service = MetaService()
run_service = RunService()


@router.post("/compare", response_model=ComparisonResponse)
async def compare_runs(
    request: CompareRunsRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Compare multiple runs side-by-side.

    Returns metrics for all runs with indicators of best/worst performance.
    All team members can compare runs.

    Args:
        request: List of run IDs to compare
        auth: Authentication context
        db: Database session

    Returns:
        ComparisonResponse: Comparison data

    Raises:
        HTTPException: If runs not found or not owned by team
    """
    # Verify all runs belong to team
    for run_id in request.run_ids:
        run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found or not accessible",
            )

    try:
        comparison = meta_service.compare_runs(request.run_ids)

        if not comparison.runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed runs found with available data",
            )

        return comparison

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing runs: {str(e)}",
        )


@router.get("/compare/{run_a}/{run_b}", response_model=ComparisonResponse)
async def compare_two_runs(
    run_a: str,
    run_b: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Compare two runs (convenience endpoint).

    All team members can compare runs.

    Args:
        run_a: First run ID
        run_b: Second run ID
        auth: Authentication context
        db: Database session

    Returns:
        ComparisonResponse: Comparison data

    Raises:
        HTTPException: If runs not found or not owned by team
    """
    # Verify runs belong to team
    for run_id in [run_a, run_b]:
        run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found or not accessible",
            )

    try:
        comparison = meta_service.compare_runs([run_a, run_b])

        if not comparison.runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed runs found with available data",
            )

        return comparison

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing runs: {str(e)}",
        )


@router.post("/overlay", response_model=EquityOverlayResponse)
async def overlay_equity_curves(
    request: CompareRunsRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Overlay equity curves from multiple runs for visualization.

    Aligns timestamps and provides synchronized data points for charting.
    All team members can overlay equity curves.

    Args:
        request: List of run IDs
        auth: Authentication context
        db: Database session

    Returns:
        EquityOverlayResponse: Overlaid equity curve data

    Raises:
        HTTPException: If runs not found or not owned by team
    """
    # Verify all runs belong to team
    for run_id in request.run_ids:
        run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found or not accessible",
            )

    try:
        overlay = meta_service.overlay_equity_curves(request.run_ids)

        if not overlay.run_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed runs found with equity curve data",
            )

        return overlay

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error overlaying equity curves: {str(e)}",
        )


@router.get("/rankings", response_model=RankingsResponse)
async def get_rankings(
    metric: str = Query("sharpe_ratio", description="Metric to rank by"),
    run_ids: List[str] = Query(..., description="List of run IDs to rank"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Rank runs by a specific metric.

    Supported metrics:
    - total_return
    - sharpe_ratio
    - sortino_ratio
    - max_drawdown (lower is better)
    - win_rate
    - profit_factor

    All team members can view rankings.

    Args:
        metric: Metric to rank by
        run_ids: List of run IDs
        auth: Authentication context
        db: Database session

    Returns:
        RankingsResponse: Ranked runs

    Raises:
        HTTPException: If runs not found or metric invalid
    """
    # Verify all runs belong to team
    for run_id in run_ids:
        run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found or not accessible",
            )

    # Validate metric
    valid_metrics = [
        "total_return",
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown",
        "win_rate",
        "profit_factor",
    ]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric. Must be one of: {', '.join(valid_metrics)}",
        )

    try:
        rankings = meta_service.rank_runs(run_ids, metric=metric)

        if not rankings.rankings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed runs found with available data",
            )

        return rankings

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ranking runs: {str(e)}",
        )


@router.post("/statistical-comparison", response_model=StatisticalComparisonResponse)
async def statistical_comparison(
    request: CompareRunsRequest,
    metric: str = Query("returns", description="Metric to compare (currently only 'returns')"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Perform statistical tests comparing runs.

    Uses t-tests to determine if differences in returns are statistically significant.
    All team members can run statistical tests.

    Args:
        request: List of run IDs (min 2)
        metric: Metric to compare (currently only 'returns' supported)
        auth: Authentication context
        db: Database session

    Returns:
        StatisticalComparisonResponse: Statistical test results

    Raises:
        HTTPException: If runs not found or insufficient data
    """
    if len(request.run_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 2 runs for statistical comparison",
        )

    # Verify all runs belong to team
    for run_id in request.run_ids:
        run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found or not accessible",
            )

    try:
        comparison = meta_service.statistical_comparison(request.run_ids, metric=metric)

        if not comparison.tests:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed runs found with sufficient data for statistical tests",
            )

        return comparison

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error performing statistical comparison: {str(e)}",
        )


@router.post("/export/comparison.csv")
async def export_comparison_csv(
    request: CompareRunsRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Export comparison data to CSV format.

    All team members can export comparisons.

    Args:
        request: List of run IDs
        auth: Authentication context
        db: Database session

    Returns:
        CSV file content

    Raises:
        HTTPException: If runs not found or not owned by team
    """
    # Verify all runs belong to team
    for run_id in request.run_ids:
        run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found or not accessible",
            )

    try:
        csv_content = meta_service.export_comparison_csv(request.run_ids)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=comparison.csv"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting comparison: {str(e)}",
        )
