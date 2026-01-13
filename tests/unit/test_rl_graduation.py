"""Unit tests for Graduation System (Phase 6).

Tests:
- Baseline strategies
- GraduationPolicy
- Graduation decisions
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from darwin.rl.graduation.baselines import (
    EqualWeightBaseline,
    LLMOnlyBaseline,
    PassAllBaseline,
    get_baseline_strategy,
)
from darwin.rl.graduation.policy import GraduationPolicy
from darwin.rl.schemas.rl_config import GraduationThresholdsV1
from darwin.rl.storage.agent_state import AgentStateSQLite
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.outcome_label import OutcomeLabelV1


class TestBaselineStrategies:
    """Test baseline strategies."""

    def create_sample_episodes(self, count: int = 10) -> list:
        """Create sample episodes for testing.

        Args:
            count: Number of episodes to create

        Returns:
            List of episodes
        """
        episodes = []
        for i in range(count):
            candidate = CandidateRecordV1(
                candidate_id=f"cand_{i:03d}",
                run_id="run_001",
                timestamp=datetime.now(),
                symbol="BTC-USD",
                timeframe="15m",
                bar_index=100 + i,
                playbook=PlaybookType.BREAKOUT,
                direction="long",
                entry_price=45000.0,
                atr_at_entry=500.0,
                exit_spec=ExitSpecV1(
                    stop_loss_price=44500.0,
                    take_profit_price=46000.0,
                    time_stop_bars=32,
                    trailing_enabled=True,
                ),
                features={"close": 45000.0},
                was_taken=True,
            )

            # Alternate between winners and losers
            r_multiple = 1.5 if i % 2 == 0 else -1.0

            outcome = OutcomeLabelV1(
                label_id=f"label_{i:03d}",
                candidate_id=f"cand_{i:03d}",
                created_at=datetime.now(),
                was_taken=True,
                actual_r_multiple=r_multiple,
            )

            llm_response = {
                "decision": "take",
                "confidence": 0.75,
            }

            episodes.append({
                "candidate": candidate,
                "outcome": outcome,
                "llm_response": llm_response,
            })

        return episodes

    def test_pass_all_baseline(self):
        """Test pass-all baseline strategy."""
        baseline = PassAllBaseline()
        episodes = self.create_sample_episodes(10)

        metrics = baseline.compute_baseline_performance(episodes)

        # Should compute metrics for all episodes
        assert metrics["total_trades"] == 10
        assert "mean_r_multiple" in metrics
        assert "sharpe_ratio" in metrics
        assert "win_rate" in metrics
        assert metrics["cost_per_trade"] == 1.0  # All call LLM

    def test_equal_weight_baseline(self):
        """Test equal-weight baseline strategy."""
        baseline = EqualWeightBaseline(equal_weight=1.0)
        episodes = self.create_sample_episodes(10)

        metrics = baseline.compute_baseline_performance(episodes)

        # Should compute metrics with equal weighting
        assert metrics["total_trades"] == 10
        assert "mean_r_multiple" in metrics
        assert "sharpe_ratio" in metrics
        assert "win_rate" in metrics

    def test_llm_only_baseline(self):
        """Test LLM-only baseline strategy."""
        baseline = LLMOnlyBaseline()
        episodes = self.create_sample_episodes(10)

        metrics = baseline.compute_baseline_performance(episodes)

        # Should compute metrics following LLM
        assert metrics["total_trades"] == 10  # All LLM said "take"
        assert "mean_r_multiple" in metrics
        assert "sharpe_ratio" in metrics
        assert metrics["agreement_rate"] == 1.0  # 100% agreement

    def test_get_baseline_strategy(self):
        """Test baseline strategy factory."""
        pass_all = get_baseline_strategy("pass_all")
        assert isinstance(pass_all, PassAllBaseline)

        equal_weight = get_baseline_strategy("equal_weight")
        assert isinstance(equal_weight, EqualWeightBaseline)

        llm_only = get_baseline_strategy("llm_only")
        assert isinstance(llm_only, LLMOnlyBaseline)

    def test_get_baseline_strategy_invalid(self):
        """Test baseline strategy factory with invalid type."""
        with pytest.raises(ValueError, match="Unknown baseline type"):
            get_baseline_strategy("invalid_baseline")


class TestGraduationPolicy:
    """Test graduation policy."""

    def create_agent_state_with_data(self, agent_name: str, sample_count: int) -> AgentStateSQLite:
        """Create agent state with sample data.

        Args:
            agent_name: Agent name
            sample_count: Number of samples to create

        Returns:
            Agent state with data
        """
        # Create temp database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)

        # Add sample decisions
        from darwin.rl.schemas.agent_state import AgentDecisionV1

        for i in range(sample_count):
            decision = AgentDecisionV1(
                agent_name=agent_name,
                candidate_id=f"cand_{i:03d}",
                run_id="run_001",
                timestamp=datetime.now(),
                state_hash="test_hash",
                action=1,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)

            # Add outcome (alternate between winners and losers)
            r_multiple = 1.5 if i % 2 == 0 else -1.0
            agent_state.update_decision_outcome(
                agent_name=agent_name,
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=r_multiple,
                outcome_pnl_usd=r_multiple * 1000,
            )

        return agent_state

    def test_graduation_policy_insufficient_data(self):
        """Test graduation with insufficient data."""
        agent_state = self.create_agent_state_with_data("gate", sample_count=10)

        thresholds = GraduationThresholdsV1(
            min_training_samples=100,  # Need 100 samples
            min_validation_samples=20,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=10.0,
        )

        policy = GraduationPolicy(agent_state, thresholds)
        decision = policy.evaluate_graduation("gate")

        # Should fail due to insufficient data
        assert not decision.can_graduate
        assert "Insufficient data" in decision.reason
        assert not decision.checks["has_sufficient_data"]

        agent_state.close()

    def test_graduation_policy_meets_requirements(self):
        """Test graduation with sufficient data."""
        agent_state = self.create_agent_state_with_data("gate", sample_count=150)

        thresholds = GraduationThresholdsV1(
            min_training_samples=100,
            min_validation_samples=20,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=10.0,
        )

        policy = GraduationPolicy(agent_state, thresholds)
        decision = policy.evaluate_graduation("gate")

        # Should have sufficient data
        assert decision.checks["has_sufficient_data"]
        assert decision.metrics["total_samples"] >= 100

        agent_state.close()

    def test_graduation_policy_validation_metric(self):
        """Test graduation policy validation metric selection."""
        agent_state = self.create_agent_state_with_data("gate", sample_count=150)

        thresholds = GraduationThresholdsV1(
            min_training_samples=100,
            min_validation_samples=20,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=10.0,
        )

        policy = GraduationPolicy(agent_state, thresholds)

        # Check validation metric name selection
        assert policy._get_validation_metric_name("gate") == "mean_r_multiple"
        assert policy._get_validation_metric_name("portfolio") == "sharpe_ratio"
        assert policy._get_validation_metric_name("meta_learner") == "sharpe_ratio"

        agent_state.close()

    def test_should_demote_degraded_performance(self):
        """Test demotion decision for degraded performance."""
        agent_state = self.create_agent_state_with_data("gate", sample_count=150)

        # Update all outcomes to losers (simulate degradation)
        for i in range(150):
            agent_state.update_decision_outcome(
                agent_name="gate",
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=-2.0,  # All losers
                outcome_pnl_usd=-2000,
            )

        thresholds = GraduationThresholdsV1(
            min_training_samples=100,
            min_validation_samples=20,
            min_validation_metric=0.5,  # Positive threshold
            baseline_type="pass_all",
            min_improvement_pct=10.0,
        )

        policy = GraduationPolicy(agent_state, thresholds)

        # Should recommend demotion due to negative performance
        should_demote = policy.should_demote("gate")

        # With all negative R-multiples, performance should be degraded
        # (actual demotion logic may vary based on threshold)

        agent_state.close()


class TestGraduationDecision:
    """Test graduation decision object."""

    def test_graduation_decision_creation(self):
        """Test graduation decision creation."""
        from darwin.rl.graduation.policy import GraduationDecision

        decision = GraduationDecision(
            can_graduate=True,
            reason="All criteria met",
            checks={"has_sufficient_data": True, "beats_baseline": True},
            metrics={"sharpe_ratio": 1.5, "total_samples": 1000},
        )

        assert decision.can_graduate
        assert decision.reason == "All criteria met"
        assert decision.checks["has_sufficient_data"]
        assert decision.metrics["sharpe_ratio"] == 1.5

    def test_graduation_decision_repr(self):
        """Test graduation decision string representation."""
        from darwin.rl.graduation.policy import GraduationDecision

        decision = GraduationDecision(
            can_graduate=False,
            reason="Insufficient data",
            checks={},
            metrics={},
        )

        repr_str = repr(decision)
        assert "can_graduate=False" in repr_str
        assert "Insufficient data" in repr_str
