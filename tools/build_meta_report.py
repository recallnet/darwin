#!/usr/bin/env python3
"""Build meta report comparing multiple runs.

Usage:
    python tools/build_meta_report.py
    python tools/build_meta_report.py --run-ids run_001 run_002 run_003
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from darwin.evaluation.meta_report import MetaReportBuilder
from darwin.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build meta report comparing multiple Darwin runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare all runs
  python tools/build_meta_report.py

  # Compare specific runs
  python tools/build_meta_report.py --run-ids run_001 run_002 run_003

  # Use custom artifacts directory
  python tools/build_meta_report.py --artifacts-dir /path/to/artifacts
        """,
    )

    parser.add_argument(
        "--run-ids",
        type=str,
        nargs="+",
        default=None,
        help="Specific run IDs to compare (if not specified, compare all runs)",
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
    logger.info("Darwin Meta Report Builder")
    logger.info("=" * 80)
    logger.info(f"Artifacts dir: {args.artifacts_dir}")
    if args.run_ids:
        logger.info(f"Run IDs: {', '.join(args.run_ids)}")
    else:
        logger.info("Run IDs: All available runs")
    logger.info("")

    try:
        # Check that artifacts directory exists
        if not args.artifacts_dir.exists():
            logger.error(f"Artifacts directory not found: {args.artifacts_dir}")
            return 1

        # Build meta report
        builder = MetaReportBuilder(artifacts_dir=args.artifacts_dir)
        meta_report = builder.build_meta_report(run_ids=args.run_ids)

        if not meta_report:
            logger.warning("No runs found to compare")
            return 0

        # Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("Meta Report Summary")
        logger.info("=" * 80)
        logger.info(f"Runs compared: {meta_report['runs_compared']}")

        # Find best run by total return
        if meta_report.get("runs"):
            best_run = max(
                meta_report["runs"],
                key=lambda r: r.get("summary", {}).get("total_return_pct", 0),
            )
            logger.info("")
            logger.info("Best run by total return:")
            logger.info(f"  Run ID: {best_run.get('run_id')}")
            logger.info(
                f"  Total Return: {best_run.get('summary', {}).get('total_return_pct', 0):.2f}%"
            )
            logger.info(
                f"  Sharpe Ratio: {best_run.get('summary', {}).get('sharpe_ratio', 0):.2f}"
            )

        logger.info("=" * 80)

        return 0

    except KeyboardInterrupt:
        logger.warning("\nMeta report building interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Meta report building failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
