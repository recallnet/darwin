#!/usr/bin/env python3
"""Build evaluation report for a run.

Usage:
    python tools/build_report.py run_001
    python tools/build_report.py run_001 --no-plots
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from darwin.evaluation.run_report import RunReportBuilder
from darwin.schemas.run_config import RunConfigV1
from darwin.storage.position_ledger import PositionLedgerSQLite
from darwin.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build evaluation report for a Darwin run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build report with plots
  python tools/build_report.py run_001

  # Build report without plots (faster)
  python tools/build_report.py run_001 --no-plots

  # Use custom artifacts directory
  python tools/build_report.py run_001 --artifacts-dir /path/to/artifacts
        """,
    )

    parser.add_argument(
        "run_id",
        type=str,
        help="Run ID to build report for",
    )

    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip plot generation (faster)",
    )

    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("artifacts"),
        help="Artifacts directory (default: artifacts)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def load_run_config(run_dir: Path) -> RunConfigV1:
    """
    Load run configuration.

    Args:
        run_dir: Run directory

    Returns:
        RunConfigV1 instance

    Raises:
        SystemExit: If config not found or invalid
    """
    config_path = run_dir / "run_config.json"
    if not config_path.exists():
        logger.error(f"Run config not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)
        return RunConfigV1(**config_data)
    except Exception as e:
        logger.error(f"Failed to load run config: {e}")
        sys.exit(1)


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_args()

    # Configure logging
    configure_logging(log_level=args.log_level, console_level=args.log_level)

    logger.info("=" * 80)
    logger.info("Darwin Report Builder")
    logger.info("=" * 80)
    logger.info(f"Run ID: {args.run_id}")
    logger.info(f"Artifacts dir: {args.artifacts_dir}")
    logger.info(f"Generate plots: {not args.no_plots}")
    logger.info("")

    try:
        # Check that run directory exists
        run_dir = args.artifacts_dir / "runs" / args.run_id
        if not run_dir.exists():
            logger.error(f"Run directory not found: {run_dir}")
            return 1

        # Load run config
        run_config = load_run_config(run_dir)

        # Initialize position ledger
        ledger_path = args.artifacts_dir / "ledger" / "positions.sqlite"
        if not ledger_path.exists():
            logger.error(f"Position ledger not found: {ledger_path}")
            return 1

        position_ledger = PositionLedgerSQLite(ledger_path)

        try:
            # Build report
            builder = RunReportBuilder(
                run_id=args.run_id,
                run_config=run_config,
                position_ledger=position_ledger,
                artifacts_dir=args.artifacts_dir,
            )

            report = builder.build_report(generate_plots=not args.no_plots)

            # Print summary
            logger.info("")
            logger.info("=" * 80)
            logger.info("Report Summary")
            logger.info("=" * 80)
            summary = report["summary"]
            logger.info(f"Total Return: {summary['total_return_pct']:.2f}%")
            logger.info(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
            logger.info(f"Max Drawdown: {summary['max_drawdown_pct']:.2f}%")
            logger.info(f"Win Rate: {summary['win_rate_pct']:.2f}%")
            logger.info(f"Total Trades: {summary['total_trades']}")
            logger.info("=" * 80)

            return 0

        finally:
            position_ledger.close()

    except KeyboardInterrupt:
        logger.warning("\nReport building interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Report building failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
