#!/usr/bin/env python3
"""Main CLI entry point for running experiments.

Usage:
    python tools/run_experiment.py config.json
    python tools/run_experiment.py config.json --mock-llm
    python tools/run_experiment.py config.json --resume
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from darwin.runner.experiment import ExperimentRunner
from darwin.schemas.run_config import RunConfigV1
from darwin.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Darwin experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with config file
  python tools/run_experiment.py configs/run_001.json

  # Run with mock LLM (no API calls)
  python tools/run_experiment.py configs/run_001.json --mock-llm

  # Resume from checkpoint
  python tools/run_experiment.py configs/run_001.json --resume

  # Override artifacts directory
  python tools/run_experiment.py configs/run_001.json --artifacts-dir /path/to/artifacts
        """,
    )

    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to run configuration JSON file",
    )

    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Use mock LLM instead of real API (for testing)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available",
    )

    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Override artifacts directory from config",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def load_config(config_path: Path) -> RunConfigV1:
    """
    Load run configuration from JSON file.

    Args:
        config_path: Path to config file

    Returns:
        Validated RunConfigV1 instance

    Raises:
        SystemExit: If config is invalid
    """
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)

        config = RunConfigV1(**config_data)
        logger.info(f"Config loaded: {config_path}")
        return config

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_args()

    # Configure logging (console only for now, file logging happens in runner)
    configure_logging(log_level=args.log_level, console_level=args.log_level)

    logger.info("=" * 80)
    logger.info("Darwin Experiment Runner")
    logger.info("=" * 80)
    logger.info(f"Config: {args.config_path}")
    logger.info(f"Mock LLM: {args.mock_llm}")
    logger.info(f"Resume: {args.resume}")
    if args.artifacts_dir:
        logger.info(f"Artifacts dir: {args.artifacts_dir}")
    logger.info("")

    try:
        # Load config
        config = load_config(args.config_path)

        # Create runner
        runner = ExperimentRunner(
            config=config,
            artifacts_dir=args.artifacts_dir,
            use_mock_llm=args.mock_llm,
            resume_from_checkpoint=args.resume,
        )

        # Run experiment
        runner.run()

        logger.info("=" * 80)
        logger.info("Experiment completed successfully")
        logger.info("=" * 80)
        return 0

    except KeyboardInterrupt:
        logger.warning("\nExperiment interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Experiment failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
