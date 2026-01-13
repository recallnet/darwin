"""Meta report generation for comparing multiple runs."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MetaReportBuilder:
    """
    Build meta reports comparing multiple runs.

    Generates:
    - meta_report.json: Structured comparison data
    - meta_report.md: Human-readable comparison
    - meta_index.csv: Run metrics table
    - run_configs_index.csv: Config comparison
    """

    def __init__(self, artifacts_dir: Path):
        """
        Initialize meta report builder.

        Args:
            artifacts_dir: Artifacts directory containing runs
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.reports_dir = self.artifacts_dir / "reports"
        self.meta_reports_dir = self.artifacts_dir / "meta_reports"

    def build_meta_report(self, run_ids: Optional[List[str]] = None) -> dict:
        """
        Build meta report comparing multiple runs.

        Args:
            run_ids: List of run IDs to include (if None, include all runs)

        Returns:
            Dictionary with meta report data

        Example:
            >>> builder = MetaReportBuilder(Path("artifacts"))
            >>> meta_report = builder.build_meta_report()
        """
        logger.info("Building meta report")

        # Create meta reports directory
        self.meta_reports_dir.mkdir(parents=True, exist_ok=True)

        # Discover runs
        if run_ids is None:
            run_ids = self._discover_runs()

        logger.info(f"  Found {len(run_ids)} runs")

        # Load reports
        run_data = []
        for run_id in run_ids:
            report = self._load_run_report(run_id)
            if report:
                run_data.append(report)

        if not run_data:
            logger.warning("No run reports found")
            return {}

        # Build comparison
        meta_report = {
            "generated_at": datetime.now().isoformat(),
            "runs_compared": len(run_data),
            "runs": run_data,
        }

        # Save meta_report.json
        meta_json_path = self.meta_reports_dir / "meta_report.json"
        with open(meta_json_path, "w") as f:
            json.dump(meta_report, f, indent=2)
        logger.info(f"  meta_report.json saved: {meta_json_path}")

        # Generate CSV indexes
        self._generate_meta_index_csv(run_data)

        # Generate markdown report
        self._generate_meta_markdown(meta_report)

        logger.info(f"Meta report complete: {self.meta_reports_dir}")
        return meta_report

    def _discover_runs(self) -> List[str]:
        """Discover all completed runs."""
        if not self.reports_dir.exists():
            return []

        run_ids = []
        for run_dir in self.reports_dir.iterdir():
            if run_dir.is_dir() and (run_dir / "report.json").exists():
                run_ids.append(run_dir.name)

        return sorted(run_ids)

    def _load_run_report(self, run_id: str) -> Optional[dict]:
        """Load a run report."""
        report_path = self.reports_dir / run_id / "report.json"
        if not report_path.exists():
            logger.warning(f"Report not found: {report_path}")
            return None

        try:
            with open(report_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load report {run_id}: {e}")
            return None

    def _generate_meta_index_csv(self, run_data: List[dict]) -> None:
        """Generate meta index CSV with key metrics."""
        rows = []

        for report in run_data:
            summary = report.get("summary", {})
            config = report.get("config_summary", {})

            rows.append(
                {
                    "run_id": report.get("run_id"),
                    "symbols": ", ".join(config.get("symbols", [])),
                    "playbooks": ", ".join(config.get("playbooks", [])),
                    "total_return_pct": summary.get("total_return_pct"),
                    "sharpe_ratio": summary.get("sharpe_ratio"),
                    "sortino_ratio": summary.get("sortino_ratio"),
                    "max_drawdown_pct": summary.get("max_drawdown_pct"),
                    "win_rate_pct": summary.get("win_rate_pct"),
                    "profit_factor": summary.get("profit_factor"),
                    "total_trades": summary.get("total_trades"),
                    "winning_trades": summary.get("winning_trades"),
                    "losing_trades": summary.get("losing_trades"),
                    "final_equity_usd": summary.get("final_equity_usd"),
                }
            )

        df = pd.DataFrame(rows)

        # Sort by total return
        if "total_return_pct" in df.columns:
            df = df.sort_values("total_return_pct", ascending=False)

        # Save CSV
        csv_path = self.meta_reports_dir / "meta_index.csv"
        df.to_csv(csv_path, index=False, float_format="%.2f")
        logger.info(f"  meta_index.csv saved: {csv_path}")

    def _generate_meta_markdown(self, meta_report: dict) -> None:
        """Generate markdown meta report."""
        md_lines = []

        # Header
        md_lines.append("# Meta Report: Run Comparison")
        md_lines.append("")
        md_lines.append(f"**Generated:** {meta_report['generated_at']}")
        md_lines.append(f"**Runs Compared:** {meta_report['runs_compared']}")
        md_lines.append("")

        # Summary table
        md_lines.append("## Summary Table")
        md_lines.append("")
        md_lines.append(
            "| Run ID | Total Return | Sharpe | Max DD | Win Rate | Trades |"
        )
        md_lines.append(
            "|--------|--------------|--------|--------|----------|--------|"
        )

        for report in meta_report["runs"]:
            summary = report.get("summary", {})
            run_id = report.get("run_id", "unknown")
            total_return = summary.get("total_return_pct", 0)
            sharpe = summary.get("sharpe_ratio", 0)
            max_dd = summary.get("max_drawdown_pct", 0)
            win_rate = summary.get("win_rate_pct", 0)
            trades = summary.get("total_trades", 0)

            md_lines.append(
                f"| {run_id} | {total_return:.2f}% | {sharpe:.2f} | "
                f"{max_dd:.2f}% | {win_rate:.2f}% | {trades} |"
            )

        md_lines.append("")

        # Top performers
        md_lines.append("## Top Performers")
        md_lines.append("")

        # Sort by total return
        sorted_runs = sorted(
            meta_report["runs"],
            key=lambda r: r.get("summary", {}).get("total_return_pct", 0),
            reverse=True,
        )

        if sorted_runs:
            md_lines.append("### By Total Return")
            md_lines.append("")
            for i, report in enumerate(sorted_runs[:5], 1):
                run_id = report.get("run_id", "unknown")
                total_return = report.get("summary", {}).get("total_return_pct", 0)
                md_lines.append(f"{i}. **{run_id}**: {total_return:.2f}%")
            md_lines.append("")

        # Sort by Sharpe
        sorted_by_sharpe = sorted(
            meta_report["runs"],
            key=lambda r: r.get("summary", {}).get("sharpe_ratio", 0),
            reverse=True,
        )

        if sorted_by_sharpe:
            md_lines.append("### By Sharpe Ratio")
            md_lines.append("")
            for i, report in enumerate(sorted_by_sharpe[:5], 1):
                run_id = report.get("run_id", "unknown")
                sharpe = report.get("summary", {}).get("sharpe_ratio", 0)
                md_lines.append(f"{i}. **{run_id}**: {sharpe:.2f}")
            md_lines.append("")

        # Links to individual reports
        md_lines.append("## Individual Reports")
        md_lines.append("")
        for report in meta_report["runs"]:
            run_id = report.get("run_id", "unknown")
            md_lines.append(f"- [{run_id}](../reports/{run_id}/report.md)")
        md_lines.append("")

        # Write markdown file
        md_path = self.meta_reports_dir / "meta_report.md"
        with open(md_path, "w") as f:
            f.write("\n".join(md_lines))
        logger.info(f"  meta_report.md saved: {md_path}")
