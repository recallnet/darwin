"""Click-based CLI for Darwin.

Provides a unified command-line interface for all Darwin operations.

Usage:
    darwin run config.json
    darwin report run_001
    darwin meta-report
    darwin list-runs
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

import click
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from darwin.evaluation.meta_report import MetaReportBuilder
from darwin.evaluation.run_report import RunReportBuilder
from darwin.runner.experiment import ExperimentRunner
from darwin.schemas.run_config import RunConfigV1
from darwin.storage.position_ledger import PositionLedgerSQLite
from darwin.utils.logging import configure_logging


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Darwin - LLM-Assisted Crypto Trading System.

    A research platform for evaluating LLM-assisted trading strategies
    on cryptocurrency markets.
    """
    pass


@cli.command()
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--mock-llm",
    is_flag=True,
    help="Use mock LLM instead of real API (for testing)",
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume from checkpoint if available",
)
@click.option(
    "--artifacts-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Override artifacts directory from config",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level",
)
def run(
    config_path: Path,
    mock_llm: bool,
    resume: bool,
    artifacts_dir: Optional[Path],
    log_level: str,
):
    """
    Run an experiment with the specified configuration.

    CONFIG_PATH: Path to run configuration JSON file

    Examples:

        \b
        # Run with config file
        darwin run configs/run_001.json

        \b
        # Run with mock LLM (no API calls)
        darwin run configs/run_001.json --mock-llm

        \b
        # Resume from checkpoint
        darwin run configs/run_001.json --resume
    """
    configure_logging(log_level=log_level, console_level=log_level)

    try:
        # Load config
        with open(config_path, "r") as f:
            config_data = json.load(f)
        config = RunConfigV1(**config_data)

        click.echo(f"Running experiment: {config.run_id}")
        if mock_llm:
            click.echo("Using mock LLM (no API calls)")
        if resume:
            click.echo("Resuming from checkpoint if available")

        # Create runner
        runner = ExperimentRunner(
            config=config,
            artifacts_dir=artifacts_dir,
            use_mock_llm=mock_llm,
            resume_from_checkpoint=resume,
        )

        # Run experiment
        runner.run()

        click.secho("Experiment completed successfully!", fg="green")

    except Exception as e:
        click.secho(f"Experiment failed: {e}", fg="red", err=True)
        sys.exit(1)


@cli.command()
@click.argument("run_id", type=str)
@click.option(
    "--no-plots",
    is_flag=True,
    help="Skip plot generation (faster)",
)
@click.option(
    "--artifacts-dir",
    type=click.Path(path_type=Path),
    default=Path("artifacts"),
    help="Artifacts directory",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level",
)
def report(
    run_id: str,
    no_plots: bool,
    artifacts_dir: Path,
    log_level: str,
):
    """
    Build evaluation report for a run.

    RUN_ID: Run identifier to build report for

    Examples:

        \b
        # Build report with plots
        darwin report run_001

        \b
        # Build report without plots (faster)
        darwin report run_001 --no-plots
    """
    configure_logging(log_level=log_level, console_level=log_level)

    try:
        # Check that run directory exists
        run_dir = artifacts_dir / "runs" / run_id
        if not run_dir.exists():
            click.secho(f"Run directory not found: {run_dir}", fg="red", err=True)
            sys.exit(1)

        # Load run config
        config_path = run_dir / "run_config.json"
        with open(config_path, "r") as f:
            config_data = json.load(f)
        run_config = RunConfigV1(**config_data)

        # Initialize position ledger
        ledger_path = artifacts_dir / "ledger" / "positions.sqlite"
        if not ledger_path.exists():
            click.secho(f"Position ledger not found: {ledger_path}", fg="red", err=True)
            sys.exit(1)

        position_ledger = PositionLedgerSQLite(ledger_path)

        try:
            # Build report
            click.echo(f"Building report for {run_id}...")
            builder = RunReportBuilder(
                run_id=run_id,
                run_config=run_config,
                position_ledger=position_ledger,
                artifacts_dir=artifacts_dir,
            )

            report = builder.build_report(generate_plots=not no_plots)

            # Print summary
            click.echo("")
            click.secho("Report Summary", fg="green", bold=True)
            click.echo("=" * 60)
            summary = report["summary"]
            click.echo(f"Total Return:    {summary['total_return_pct']:>8.2f}%")
            click.echo(f"Sharpe Ratio:    {summary['sharpe_ratio']:>8.2f}")
            click.echo(f"Max Drawdown:    {summary['max_drawdown_pct']:>8.2f}%")
            click.echo(f"Win Rate:        {summary['win_rate_pct']:>8.2f}%")
            click.echo(f"Total Trades:    {summary['total_trades']:>8}")
            click.echo("=" * 60)

            report_path = artifacts_dir / "reports" / run_id / "report.md"
            click.secho(f"\nReport saved: {report_path}", fg="green")

        finally:
            position_ledger.close()

    except Exception as e:
        click.secho(f"Report building failed: {e}", fg="red", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--run-ids",
    multiple=True,
    help="Specific run IDs to compare (can be specified multiple times)",
)
@click.option(
    "--artifacts-dir",
    type=click.Path(path_type=Path),
    default=Path("artifacts"),
    help="Artifacts directory",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level",
)
def meta_report(
    run_ids: tuple,
    artifacts_dir: Path,
    log_level: str,
):
    """
    Build meta report comparing multiple runs.

    Examples:

        \b
        # Compare all runs
        darwin meta-report

        \b
        # Compare specific runs
        darwin meta-report --run-ids run_001 --run-ids run_002 --run-ids run_003
    """
    configure_logging(log_level=log_level, console_level=log_level)

    try:
        # Check that artifacts directory exists
        if not artifacts_dir.exists():
            click.secho(f"Artifacts directory not found: {artifacts_dir}", fg="red", err=True)
            sys.exit(1)

        # Convert tuple to list or None
        run_ids_list = list(run_ids) if run_ids else None

        # Build meta report
        click.echo("Building meta report...")
        builder = MetaReportBuilder(artifacts_dir=artifacts_dir)
        meta_report = builder.build_meta_report(run_ids=run_ids_list)

        if not meta_report:
            click.secho("No runs found to compare", fg="yellow")
            return

        # Print summary
        click.echo("")
        click.secho("Meta Report Summary", fg="green", bold=True)
        click.echo("=" * 60)
        click.echo(f"Runs compared: {meta_report['runs_compared']}")

        # Find best run by total return
        if meta_report.get("runs"):
            best_run = max(
                meta_report["runs"],
                key=lambda r: r.get("summary", {}).get("total_return_pct", 0),
            )
            click.echo("")
            click.echo("Best run by total return:")
            click.echo(f"  Run ID:       {best_run.get('run_id')}")
            click.echo(
                f"  Total Return: {best_run.get('summary', {}).get('total_return_pct', 0):.2f}%"
            )
            click.echo(
                f"  Sharpe Ratio: {best_run.get('summary', {}).get('sharpe_ratio', 0):.2f}"
            )

        click.echo("=" * 60)

        report_path = artifacts_dir / "meta_reports" / "meta_report.md"
        click.secho(f"\nMeta report saved: {report_path}", fg="green")

    except Exception as e:
        click.secho(f"Meta report building failed: {e}", fg="red", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--artifacts-dir",
    type=click.Path(path_type=Path),
    default=Path("artifacts"),
    help="Artifacts directory",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information",
)
def list_runs(artifacts_dir: Path, verbose: bool):
    """
    List all available runs.

    Examples:

        \b
        # List runs
        darwin list-runs

        \b
        # List runs with details
        darwin list-runs --verbose
    """
    runs_dir = artifacts_dir / "runs"

    if not runs_dir.exists():
        click.secho(f"No runs directory found: {runs_dir}", fg="yellow")
        return

    # Discover runs
    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]

    if not run_dirs:
        click.secho("No runs found", fg="yellow")
        return

    click.secho(f"Found {len(run_dirs)} runs:", fg="green", bold=True)
    click.echo("")

    for run_dir in sorted(run_dirs):
        run_id = run_dir.name

        # Check for manifest
        manifest_path = run_dir / "manifest.json"
        has_manifest = manifest_path.exists()

        # Load manifest if available
        status = "unknown"
        if has_manifest:
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    status = manifest.get("status", "unknown")
            except Exception:
                pass

        # Color-code by status
        if status == "completed":
            status_color = "green"
        elif status == "running":
            status_color = "yellow"
        elif status == "failed":
            status_color = "red"
        else:
            status_color = "white"

        click.echo(f"  {run_id:<30} ", nl=False)
        click.secho(f"[{status}]", fg=status_color)

        if verbose:
            # Load config if available
            config_path = run_dir / "run_config.json"
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        config_data = json.load(f)
                    symbols = config_data.get("market_scope", {}).get("symbols", [])
                    playbooks = [
                        pb["name"]
                        for pb in config_data.get("playbooks", [])
                        if pb.get("enabled")
                    ]
                    click.echo(f"    Symbols: {', '.join(symbols)}")
                    click.echo(f"    Playbooks: {', '.join(playbooks)}")
                except Exception:
                    pass
            click.echo("")


@cli.command()
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.argument("agent_name", type=click.Choice(["gate", "portfolio", "meta_learner"]))
@click.option(
    "--no-activate",
    is_flag=True,
    help="Don't automatically activate agent after graduation (manual config update required)",
)
def train_agent(config_path: Path, agent_name: str, no_activate: bool):
    """
    Train an RL agent and evaluate graduation readiness.

    \b
    CONFIG_PATH: Path to run configuration YAML/JSON file
    AGENT_NAME: Agent to train (gate, portfolio, or meta_learner)

    \b
    Examples:
        darwin train-agent config.yaml gate
        darwin train-agent config.yaml portfolio
        darwin train-agent config.yaml meta_learner --no-activate

    \b
    This command:
    1. Reads collected data from agent_state.sqlite
    2. Trains the agent with PPO
    3. Evaluates against graduation thresholds
    4. Auto-activates agent in config if graduated (unless --no-activate)
    5. Creates backup of config before updating

    \b
    After graduation, the agent will be active on the next run.
    """
    from darwin.rl.training.train_agent import train_agent_from_config_file

    configure_logging(console_only=True, level="INFO")

    click.echo(f"\n{'='*80}")
    click.echo(f"Training RL Agent: {agent_name}")
    click.echo(f"{'='*80}\n")

    try:
        graduated = train_agent_from_config_file(
            str(config_path),
            agent_name,
            auto_activate=not no_activate
        )

        if graduated:
            click.echo(f"\n🎓 SUCCESS! Agent '{agent_name}' has GRADUATED!")
            if not no_activate:
                click.echo("   ✅ Agent automatically activated in config")
                click.echo("   🚀 Ready to use on next run!")
            else:
                click.echo("   📝 Manual config update required (--no-activate was used)")
        else:
            click.echo(f"\n📚 Agent '{agent_name}' needs more training.")
            click.echo("   Continue running backtests to collect more data.")

    except Exception as e:
        click.echo(f"\n❌ Error training agent: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("agent_name", type=click.Choice(["gate", "portfolio", "meta_learner"]))
@click.option(
    "--db-paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Paths to agent_state.sqlite databases (can be specified multiple times)",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output path for trained model (e.g., artifacts/models/gate/model.zip)",
)
@click.option(
    "--timesteps",
    default=100000,
    type=int,
    help="Total training timesteps (default: 100000)",
)
@click.option(
    "--tensorboard-log",
    type=click.Path(path_type=Path),
    default=None,
    help="Tensorboard log directory (optional)",
)
def train_multi_run(
    agent_name: str,
    db_paths: tuple,
    output: Path,
    timesteps: int,
    tensorboard_log: Optional[Path],
):
    """
    Train an RL agent on data from multiple runs.

    \b
    AGENT_NAME: Agent to train (gate, portfolio, or meta_learner)

    \b
    Examples:
        # Train on data from 3 runs
        darwin train-multi-run gate \\
            --db-paths artifacts/run_001/agent_state.sqlite \\
            --db-paths artifacts/run_002/agent_state.sqlite \\
            --db-paths artifacts/run_003/agent_state.sqlite \\
            --output artifacts/models/gate/model.zip

        \b
        # With tensorboard logging
        darwin train-multi-run portfolio \\
            --db-paths run_001/agent_state.sqlite \\
            --db-paths run_002/agent_state.sqlite \\
            --output models/portfolio/model.zip \\
            --tensorboard-log artifacts/tensorboard

        \b
        # With custom timesteps
        darwin train-multi-run meta_learner \\
            --db-paths run_*/agent_state.sqlite \\
            --output models/meta_learner/model.zip \\
            --timesteps 200000

    \b
    This command:
    1. Loads decision data from all specified databases
    2. Combines data from multiple runs
    3. Trains agent with PPO on combined dataset
    4. Saves trained model to output path

    \b
    Benefits of multi-run training:
    - More diverse training data (different market conditions)
    - Larger dataset (better generalization)
    - Reduced overfitting to single run
    - Better performance on unseen data
    """
    from darwin.rl.training.multi_run_training import train_agent_multi_run

    configure_logging(console_only=True, level="INFO")

    click.echo(f"\n{'='*80}")
    click.echo(f"MULTI-RUN TRAINING: {agent_name}")
    click.echo(f"{'='*80}\n")

    # Convert tuple to list
    db_paths_list = list(db_paths)

    click.echo(f"Training on {len(db_paths_list)} runs:")
    for i, path in enumerate(db_paths_list, 1):
        click.echo(f"  {i}. {path}")
    click.echo(f"\nOutput: {output}")
    click.echo(f"Timesteps: {timesteps}")
    if tensorboard_log:
        click.echo(f"Tensorboard: {tensorboard_log}")
    click.echo()

    try:
        success = train_agent_multi_run(
            agent_state_db_paths=db_paths_list,
            agent_name=agent_name,
            output_model_path=str(output),
            total_timesteps=timesteps,
            tensorboard_log=str(tensorboard_log) if tensorboard_log else None,
        )

        if success:
            click.secho(f"\n✅ SUCCESS! Multi-run training completed!", fg="green")
            click.echo(f"   Model saved to: {output}")
            if tensorboard_log:
                click.echo(f"   View training with: tensorboard --logdir {tensorboard_log}")
        else:
            click.secho(f"\n❌ Multi-run training failed", fg="red")
            sys.exit(1)

    except Exception as e:
        click.secho(f"\n❌ Error during multi-run training: {e}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
