"""
RL monitoring service layer for Darwin API.

Provides business logic for:
- Agent status and overview
- Performance metrics
- Graduation tracking
- Alert monitoring
- Model version management
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from darwin.rl.storage.agent_state import AgentStateSQLite
from darwin.rl.storage.model_store import ModelStore
from darwin.rl.monitoring.alerts import AgentMonitor, Alert
from darwin.rl.graduation.policy import GraduationPolicy, GraduationDecision
from darwin.rl.graduation.metrics import AgentPerformanceMetrics
from darwin.rl.schemas.rl_config import GraduationThresholdsV1
from darwin.api.models.rl import (
    AgentDecisionResponse,
    PerformanceMetricsResponse,
    PerformanceSnapshotResponse,
    PerformanceHistoryResponse,
    GraduationStatusResponse,
    GraduationRecordResponse,
    GraduationHistoryResponse,
    AlertResponse,
    AlertsResponse,
    ModelVersionResponse,
    ModelVersionsResponse,
    AgentStatusSummary,
    AgentsOverviewResponse,
    AgentDetailResponse,
)


class RLService:
    """Service for RL monitoring and management."""

    # Supported agent names
    AGENT_NAMES = ["gate", "portfolio", "meta_learner"]

    def __init__(
        self,
        artifacts_dir: Optional[Path] = None,
        models_dir: Optional[Path] = None,
    ):
        """
        Initialize RL service.

        Args:
            artifacts_dir: Directory containing agent_state.sqlite (defaults to 'artifacts')
            models_dir: Directory containing model files (defaults to 'models')
        """
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path("artifacts")
        self.models_dir = Path(models_dir) if models_dir else Path("models")

        # Initialize storage backends
        agent_state_path = self.artifacts_dir / "agent_state.sqlite"
        self.agent_state = AgentStateSQLite(agent_state_path)
        self.model_store = ModelStore(self.models_dir)

        # Initialize monitoring and graduation components
        self.monitor = AgentMonitor(self.agent_state)
        self.metrics_tracker = AgentPerformanceMetrics(self.agent_state)

        # Default graduation thresholds (can be overridden)
        self.graduation_thresholds = GraduationThresholdsV1(
            min_training_samples=1000,
            min_validation_samples=100,
            min_validation_metric=0.5,
            min_improvement_pct=10.0,
            baseline_type="random",
        )
        self.graduation_policy = GraduationPolicy(
            self.agent_state, self.graduation_thresholds
        )

    def get_agents_overview(self) -> AgentsOverviewResponse:
        """
        Get overview of all agents.

        Returns:
            AgentsOverviewResponse with status summaries
        """
        agents = []

        for agent_name in self.AGENT_NAMES:
            try:
                # Get current model version
                current_version = self.model_store.get_current_version(agent_name)

                # Get graduation status
                graduation = self.graduation_policy.evaluate_graduation(agent_name)

                # Get recent decisions count (30 days)
                recent_decisions = self.agent_state.get_decision_count(agent_name)

                # Get recent performance metrics
                metrics = self.metrics_tracker.compute_rolling_metrics(
                    agent_name, window_days=30
                )

                # Get alerts
                alerts = self.monitor.check_all(agent_name)

                # Determine current mode (simplified - would need to track in DB)
                # For now, assume observe if can't graduate, active if can
                current_mode = "active" if graduation.can_graduate else "observe"

                agents.append(
                    AgentStatusSummary(
                        agent_name=agent_name,
                        current_mode=current_mode,
                        model_version=current_version,
                        has_active_alerts=len(alerts) > 0,
                        alert_count=len(alerts),
                        can_graduate=graduation.can_graduate,
                        recent_decisions=recent_decisions,
                        recent_mean_r_multiple=(
                            metrics["mean_r_multiple"] if metrics else None
                        ),
                        recent_win_rate=metrics["win_rate"] if metrics else None,
                    )
                )

            except Exception as e:
                # If agent has no data yet, skip or add minimal info
                agents.append(
                    AgentStatusSummary(
                        agent_name=agent_name,
                        current_mode="observe",
                        model_version=None,
                        has_active_alerts=False,
                        alert_count=0,
                        can_graduate=False,
                        recent_decisions=0,
                        recent_mean_r_multiple=None,
                        recent_win_rate=None,
                    )
                )

        return AgentsOverviewResponse(
            agents=agents,
            generated_at=datetime.utcnow(),
        )

    def get_agent_detail(self, agent_name: str) -> AgentDetailResponse:
        """
        Get detailed information for a specific agent.

        Args:
            agent_name: Name of agent

        Returns:
            AgentDetailResponse with full details

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Get current model version
        current_version = self.model_store.get_current_version(agent_name)

        # Get graduation status
        graduation_status = self.get_graduation_status(agent_name)

        # Get performance metrics
        performance_metrics = self.get_performance_metrics(agent_name, window_days=30)

        # Get alerts
        alerts_response = self.get_alerts(agent_name)

        # Get recent decisions count (7 days)
        recent_decisions = self.agent_state.get_decision_count(agent_name)

        # Determine current mode
        current_mode = graduation_status.current_mode

        return AgentDetailResponse(
            agent_name=agent_name,
            current_mode=current_mode,
            model_version=current_version,
            graduation_status=graduation_status,
            performance_metrics=performance_metrics,
            active_alerts=alerts_response.alerts,
            recent_decisions_count=recent_decisions,
        )

    def get_performance_metrics(
        self, agent_name: str, window_days: int = 30
    ) -> PerformanceMetricsResponse:
        """
        Get performance metrics for an agent.

        Args:
            agent_name: Name of agent
            window_days: Window size in days

        Returns:
            PerformanceMetricsResponse

        Raises:
            ValueError: If agent_name invalid or no data
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Get agent-specific metrics
        if agent_name == "gate":
            metrics = self.metrics_tracker.get_gate_agent_metrics(agent_name, window_days)
        elif agent_name == "portfolio":
            metrics = self.metrics_tracker.get_portfolio_agent_metrics(
                agent_name, window_days
            )
        elif agent_name == "meta_learner":
            metrics = self.metrics_tracker.get_meta_learner_metrics(agent_name, window_days)
        else:
            metrics = self.metrics_tracker.compute_rolling_metrics(agent_name, window_days)

        if metrics is None:
            raise ValueError(f"No performance data available for {agent_name}")

        return PerformanceMetricsResponse(
            agent_name=agent_name,
            window_days=metrics["window_days"],
            num_decisions=metrics["num_decisions"],
            mean_r_multiple=metrics["mean_r_multiple"],
            std_r_multiple=metrics["std_r_multiple"],
            sharpe_ratio=metrics["sharpe_ratio"],
            win_rate=metrics["win_rate"],
            max_r_multiple=metrics["max_r_multiple"],
            min_r_multiple=metrics["min_r_multiple"],
            max_drawdown=metrics["max_drawdown"],
            skip_rate=metrics.get("skip_rate"),
            estimated_cost_savings_usd=metrics.get("estimated_cost_savings_usd"),
            miss_rate=metrics.get("miss_rate"),
            avg_position_size=metrics.get("avg_position_size"),
            agreement_rate=metrics.get("agreement_rate"),
            override_rate=metrics.get("override_rate"),
            override_accuracy=metrics.get("override_accuracy"),
        )

    def get_performance_history(
        self, agent_name: str, limit: Optional[int] = None
    ) -> PerformanceHistoryResponse:
        """
        Get performance history (snapshots over time).

        Args:
            agent_name: Name of agent
            limit: Optional limit on number of snapshots

        Returns:
            PerformanceHistoryResponse

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Get snapshots from database
        snapshots = self.agent_state.get_performance_history(agent_name, limit=limit)

        # Convert to response models
        snapshot_responses = [
            PerformanceSnapshotResponse(
                snapshot_date=s.snapshot_date,
                window_size=s.window_size,
                mean_r_multiple=s.mean_r_multiple,
                win_rate=s.win_rate,
                sharpe_ratio=s.sharpe_ratio,
                max_drawdown=s.max_drawdown,
                pass_rate=s.pass_rate,
                override_rate=s.override_rate,
                agreement_rate=s.agreement_rate,
                cost_savings_pct=s.cost_savings_pct,
                llm_calls_avoided=s.llm_calls_avoided,
            )
            for s in snapshots
        ]

        return PerformanceHistoryResponse(
            agent_name=agent_name,
            snapshots=snapshot_responses,
        )

    def get_graduation_status(self, agent_name: str) -> GraduationStatusResponse:
        """
        Get graduation status for an agent.

        Args:
            agent_name: Name of agent

        Returns:
            GraduationStatusResponse

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Evaluate graduation
        decision = self.graduation_policy.evaluate_graduation(agent_name)

        # Get data requirements
        data_req = self.metrics_tracker.get_data_requirements(
            agent_name,
            self.graduation_thresholds.min_training_samples,
            self.graduation_thresholds.min_validation_samples,
        )

        # Calculate progress percentages
        training_progress = min(
            100.0,
            (data_req["total_samples"] / self.graduation_thresholds.min_training_samples)
            * 100,
        )
        validation_progress = min(
            100.0,
            (data_req["recent_samples"] / self.graduation_thresholds.min_validation_samples)
            * 100,
        )

        # Determine current mode (simplified)
        current_mode = "active" if decision.can_graduate else "observe"

        return GraduationStatusResponse(
            agent_name=agent_name,
            current_mode=current_mode,
            can_graduate=decision.can_graduate,
            reason=decision.reason,
            checks=decision.checks,
            metrics=decision.metrics,
            total_samples=data_req["total_samples"],
            recent_samples=data_req["recent_samples"],
            required_training_samples=self.graduation_thresholds.min_training_samples,
            required_validation_samples=self.graduation_thresholds.min_validation_samples,
            training_progress_pct=training_progress,
            validation_progress_pct=validation_progress,
        )

    def get_graduation_history(
        self, agent_name: str, limit: Optional[int] = None
    ) -> GraduationHistoryResponse:
        """
        Get graduation evaluation history.

        Args:
            agent_name: Name of agent
            limit: Optional limit on number of records

        Returns:
            GraduationHistoryResponse

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Get graduation records
        records = self.agent_state.get_graduation_history(agent_name, limit=limit)

        # Convert to response models
        record_responses = [
            GraduationRecordResponse(
                evaluation_date=r.evaluation_date,
                passed=r.passed,
                reason=r.reason,
                metrics=r.metrics,
                baseline_comparison=r.baseline_comparison,
                promoted=r.promoted,
                demoted=r.demoted,
            )
            for r in records
        ]

        return GraduationHistoryResponse(
            agent_name=agent_name,
            records=record_responses,
        )

    def get_alerts(self, agent_name: str) -> AlertsResponse:
        """
        Get active alerts for an agent.

        Args:
            agent_name: Name of agent

        Returns:
            AlertsResponse

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Run all health checks
        alerts = self.monitor.check_all(agent_name)

        # Convert to response models
        alert_responses = [
            AlertResponse(
                alert_type=a.alert_type,
                agent_name=a.agent_name,
                severity=a.severity,
                message=a.message,
                details=a.details,
                timestamp=a.timestamp,
            )
            for a in alerts
        ]

        return AlertsResponse(
            agent_name=agent_name,
            alerts=alert_responses,
        )

    def get_decisions(
        self, agent_name: str, run_id: Optional[str] = None, limit: Optional[int] = 100
    ) -> List[AgentDecisionResponse]:
        """
        Get agent decisions.

        Args:
            agent_name: Name of agent
            run_id: Optional run ID filter
            limit: Optional limit on number of decisions

        Returns:
            List of AgentDecisionResponse

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Get decisions from storage
        decisions = self.agent_state.get_decisions(agent_name, run_id=run_id, limit=limit)

        # Convert to response models
        return [
            AgentDecisionResponse(
                agent_name=d.agent_name,
                candidate_id=d.candidate_id,
                run_id=d.run_id,
                timestamp=d.timestamp,
                state_hash=d.state_hash,
                action=d.action,
                mode=d.mode,
                model_version=d.model_version,
                outcome_r_multiple=d.outcome_r_multiple,
                outcome_pnl_usd=d.outcome_pnl_usd,
            )
            for d in decisions
        ]

    def get_model_versions(self, agent_name: str) -> ModelVersionsResponse:
        """
        Get all model versions for an agent.

        Args:
            agent_name: Name of agent

        Returns:
            ModelVersionsResponse

        Raises:
            ValueError: If agent_name invalid
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Get current version
        current_version = self.model_store.get_current_version(agent_name)

        # Get all versions
        versions_metadata = self.model_store.list_versions(agent_name)

        # Convert to response models
        version_responses = [
            ModelVersionResponse(
                version=v["version"],
                agent_name=v["agent_name"],
                saved_at=datetime.fromisoformat(v["saved_at"]),
                model_path=v["model_path"],
                is_current=(v["version"] == current_version),
                training_steps=v.get("training_steps"),
                training_episodes=v.get("training_episodes"),
                final_mean_reward=v.get("final_mean_reward"),
            )
            for v in versions_metadata
        ]

        return ModelVersionsResponse(
            agent_name=agent_name,
            current_version=current_version,
            versions=version_responses,
        )

    def rollback_model(self, agent_name: str, version: str) -> None:
        """
        Rollback model to a specific version.

        Args:
            agent_name: Name of agent
            version: Version to rollback to

        Raises:
            ValueError: If agent_name invalid or version not found
        """
        if agent_name not in self.AGENT_NAMES:
            raise ValueError(f"Invalid agent name. Must be one of: {self.AGENT_NAMES}")

        # Rollback via model store
        self.model_store.rollback_model(agent_name, version)
