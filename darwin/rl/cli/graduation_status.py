"""CLI tool for checking agent graduation status."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from darwin.rl.graduation.policy import GraduationPolicy
from darwin.rl.schemas.rl_config import GraduationThresholdsV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


def check_graduation_status(
    agent_name: str,
    agent_state_db: str,
    thresholds: GraduationThresholdsV1,
    verbose: bool = False,
) -> int:
    """Check graduation status for an agent.

    Args:
        agent_name: Name of agent to check
        agent_state_db: Path to agent state database
        thresholds: Graduation thresholds
        verbose: Print detailed information

    Returns:
        Exit code (0=can graduate, 1=cannot graduate, 2=error)
    """
    try:
        # Load agent state
        agent_state = AgentStateSQLite(agent_state_db)

        # Create graduation policy
        policy = GraduationPolicy(agent_state, thresholds)

        # Evaluate graduation
        decision = policy.evaluate_graduation(agent_name)

        # Print results
        if verbose:
            print(f"\n{'='*60}")
            print(f"Graduation Status for Agent: {agent_name}")
            print(f"{'='*60}\n")

            print(f"Decision: {'✓ CAN GRADUATE' if decision.can_graduate else '✗ CANNOT GRADUATE'}")
            print(f"Reason: {decision.reason}\n")

            print("Checks:")
            for check_name, passed in decision.checks.items():
                status = "✓" if passed else "✗"
                print(f"  {status} {check_name}")

            print("\nMetrics:")
            for metric_name, value in decision.metrics.items():
                if isinstance(value, float):
                    print(f"  {metric_name}: {value:.4f}")
                else:
                    print(f"  {metric_name}: {value}")

            print(f"\n{'='*60}\n")
        else:
            # Simple output
            if decision.can_graduate:
                print(f"✓ {agent_name}: CAN GRADUATE - {decision.reason}")
            else:
                print(f"✗ {agent_name}: CANNOT GRADUATE - {decision.reason}")

        # Close agent state
        agent_state.close()

        return 0 if decision.can_graduate else 1

    except Exception as e:
        logger.error(f"Error checking graduation status: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check RL agent graduation status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check gate agent with default thresholds
  python -m darwin.rl.cli.graduation_status gate --db artifacts/rl_state/agent_state.sqlite

  # Check with custom thresholds
  python -m darwin.rl.cli.graduation_status portfolio --db artifacts/rl_state/agent_state.sqlite \\
    --min-training 500 --min-validation 100 --min-metric 1.5

  # Verbose output
  python -m darwin.rl.cli.graduation_status meta_learner --db artifacts/rl_state/agent_state.sqlite -v
        """,
    )

    parser.add_argument(
        "agent_name",
        type=str,
        choices=["gate", "portfolio", "meta_learner"],
        help="Name of agent to check",
    )

    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="Path to agent state database",
    )

    # Threshold arguments
    parser.add_argument(
        "--min-training",
        type=int,
        default=1000,
        help="Minimum training samples required (default: 1000)",
    )

    parser.add_argument(
        "--min-validation",
        type=int,
        default=200,
        help="Minimum validation samples required (default: 200)",
    )

    parser.add_argument(
        "--min-metric",
        type=float,
        default=0.1,
        help="Minimum validation metric value (default: 0.1)",
    )

    parser.add_argument(
        "--min-improvement",
        type=float,
        default=10.0,
        help="Minimum improvement percentage over baseline (default: 10.0)",
    )

    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Baseline type (auto-detected if not specified)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed graduation information",
    )

    args = parser.parse_args()

    # Auto-detect baseline type if not specified
    baseline_map = {
        "gate": "pass_all",
        "portfolio": "equal_weight",
        "meta_learner": "llm_only",
    }
    baseline_type = args.baseline or baseline_map[args.agent_name]

    # Create thresholds
    thresholds = GraduationThresholdsV1(
        min_training_samples=args.min_training,
        min_validation_samples=args.min_validation,
        min_validation_metric=args.min_metric,
        baseline_type=baseline_type,
        min_improvement_pct=args.min_improvement,
    )

    # Check graduation status
    exit_code = check_graduation_status(
        args.agent_name,
        args.db,
        thresholds,
        verbose=args.verbose,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
