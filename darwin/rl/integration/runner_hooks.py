"""RL system integration for Darwin runner."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from darwin.rl.agents.gate_agent import GateAgent
from darwin.rl.agents.portfolio_agent import PortfolioAgent
from darwin.rl.schemas.rl_config import AgentConfigV1, RLConfigV1
from darwin.rl.storage.agent_state import AgentStateSQLite
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class RLSystem:
    """Manages RL agents and their integration with the runner.

    Responsibilities:
    - Load trained agents from disk
    - Manage agent modes (observe vs active)
    - Track agent decisions
    - Provide hooks for runner integration
    """

    def __init__(self, config: RLConfigV1, run_id: str):
        """Initialize RL system.

        Args:
            config: RL configuration
            run_id: Current run ID
        """
        self.config = config
        self.run_id = run_id

        # Initialize agent state storage
        self.agent_state = AgentStateSQLite(config.agent_state_db)

        # Initialize agents
        self.gate_agent: Optional[GateAgent] = None
        self.portfolio_agent: Optional[PortfolioAgent] = None
        self.meta_learner_agent = None  # TODO: Implement in Phase 5

        # Load agents if enabled
        if config.gate_agent and config.gate_agent.enabled:
            self._load_gate_agent(config.gate_agent)

        if config.portfolio_agent and config.portfolio_agent.enabled:
            self._load_portfolio_agent(config.portfolio_agent)

        logger.info(
            f"Initialized RL system for run {run_id} with "
            f"gate_agent={config.gate_agent.enabled if config.gate_agent else False}, "
            f"portfolio_agent={config.portfolio_agent.enabled if config.portfolio_agent else False}"
        )

    def _load_gate_agent(self, config: AgentConfigV1) -> None:
        """Load gate agent from disk.

        Args:
            config: Gate agent configuration
        """
        try:
            self.gate_agent = GateAgent()

            if config.model_path:
                model_path = Path(config.model_path)
                if model_path.exists():
                    self.gate_agent.load_model(str(model_path))
                    logger.info(
                        f"Loaded gate agent model from {model_path} "
                        f"(mode: {config.mode})"
                    )
                else:
                    logger.warning(
                        f"Gate agent model not found at {model_path}. "
                        f"Agent will remain in {config.mode} mode without predictions."
                    )
            else:
                logger.info(
                    f"Gate agent initialized without model (mode: {config.mode})"
                )

        except Exception as e:
            logger.error(f"Failed to load gate agent: {e}")
            self.gate_agent = None

    def _load_portfolio_agent(self, config: AgentConfigV1) -> None:
        """Load portfolio agent from disk.

        Args:
            config: Portfolio agent configuration
        """
        try:
            self.portfolio_agent = PortfolioAgent()

            if config.model_path:
                model_path = Path(config.model_path)
                if model_path.exists():
                    self.portfolio_agent.load_model(str(model_path))
                    logger.info(
                        f"Loaded portfolio agent model from {model_path} "
                        f"(mode: {config.mode})"
                    )
                else:
                    logger.warning(
                        f"Portfolio agent model not found at {model_path}. "
                        f"Agent will remain in {config.mode} mode without predictions."
                    )
            else:
                logger.info(
                    f"Portfolio agent initialized without model (mode: {config.mode})"
                )

        except Exception as e:
            logger.error(f"Failed to load portfolio agent: {e}")
            self.portfolio_agent = None

    def gate_agent_active(self) -> bool:
        """Check if gate agent is active and can make decisions.

        Returns:
            True if gate agent is in active mode and loaded
        """
        if not self.config.gate_agent:
            return False

        if not self.config.gate_agent.enabled:
            return False

        if self.config.gate_agent.mode != "active":
            return False

        if not self.gate_agent or not self.gate_agent.is_loaded():
            return False

        return True

    def gate_hook(
        self, candidate: CandidateRecordV1, portfolio_state: Dict
    ) -> Optional[str]:
        """Gate agent hook: decide whether to skip or pass candidate to LLM.

        Args:
            candidate: Candidate to evaluate
            portfolio_state: Current portfolio state

        Returns:
            "skip" if agent decides to skip, None if pass (or observe mode)
        """
        if not self.config.gate_agent or not self.config.gate_agent.enabled:
            return None

        if not self.gate_agent or not self.gate_agent.is_loaded():
            return None

        try:
            # Make prediction
            action = self.gate_agent.predict(candidate, portfolio_state)
            is_skip = action == 0

            # Record decision
            from darwin.rl.schemas.agent_state import AgentDecisionV1
            from datetime import datetime

            state = self.gate_agent.encoder.encode(candidate, portfolio_state)
            decision = AgentDecisionV1(
                agent_name="gate",
                candidate_id=candidate.candidate_id,
                run_id=self.run_id,
                timestamp=datetime.now(),
                state_hash=AgentStateSQLite.hash_state(state),
                action=action,
                mode=self.config.gate_agent.mode,
                model_version=self.config.gate_agent.model_version,
            )
            self.agent_state.record_decision(decision)

            # In observe mode, log but don't affect decisions
            if self.config.gate_agent.mode == "observe":
                logger.debug(
                    f"Gate agent (observe): candidate {candidate.candidate_id} "
                    f"-> {'SKIP' if is_skip else 'PASS'}"
                )
                return None

            # In active mode, return skip decision
            if is_skip:
                logger.debug(
                    f"Gate agent (active): skipping candidate {candidate.candidate_id}"
                )
                return "skip"

            return None

        except Exception as e:
            logger.error(f"Gate agent hook error: {e}")
            return None

    def portfolio_agent_active(self) -> bool:
        """Check if portfolio agent is active.

        Returns:
            True if portfolio agent is in active mode and loaded
        """
        if not self.config.portfolio_agent:
            return False

        if not self.config.portfolio_agent.enabled:
            return False

        if self.config.portfolio_agent.mode != "active":
            return False

        if not self.portfolio_agent or not self.portfolio_agent.is_loaded():
            return False

        return True

    def portfolio_hook(
        self, candidate: CandidateRecordV1, llm_response: Dict[str, Any], portfolio_state: Dict
    ) -> float:
        """Portfolio agent hook: determine position size fraction.

        Args:
            candidate: Candidate that was approved by LLM
            llm_response: LLM response with decision context
            portfolio_state: Current portfolio state

        Returns:
            Position size fraction (0.0 to 1.0)
        """
        if not self.config.portfolio_agent or not self.config.portfolio_agent.enabled:
            return 1.0  # Default: full size

        if not self.portfolio_agent or not self.portfolio_agent.is_loaded():
            return 1.0

        try:
            # Make prediction
            position_size = self.portfolio_agent.predict(
                candidate, llm_response, portfolio_state
            )

            # Record decision
            from darwin.rl.schemas.agent_state import AgentDecisionV1
            from datetime import datetime

            state = self.portfolio_agent.encoder.encode(
                candidate, llm_response, portfolio_state
            )
            decision = AgentDecisionV1(
                agent_name="portfolio",
                candidate_id=candidate.candidate_id,
                run_id=self.run_id,
                timestamp=datetime.now(),
                state_hash=AgentStateSQLite.hash_state(state),
                action=position_size,  # Store continuous action
                mode=self.config.portfolio_agent.mode,
                model_version=self.config.portfolio_agent.model_version,
            )
            self.agent_state.record_decision(decision)

            # In observe mode, log but don't affect sizing
            if self.config.portfolio_agent.mode == "observe":
                logger.debug(
                    f"Portfolio agent (observe): candidate {candidate.candidate_id} "
                    f"-> size fraction {position_size:.2f}"
                )
                return 1.0  # Default size in observe mode

            # In active mode, return predicted size
            logger.debug(
                f"Portfolio agent (active): candidate {candidate.candidate_id} "
                f"-> size fraction {position_size:.2f}"
            )
            return position_size

        except Exception as e:
            logger.error(f"Portfolio agent hook error: {e}")
            return 1.0  # Default: full size on error

    def meta_learner_agent_active(self) -> bool:
        """Check if meta-learner agent is active.

        Returns:
            True if meta-learner agent is in active mode and loaded
        """
        # TODO: Implement in Phase 5
        return False

    def meta_learner_hook(
        self, candidate: CandidateRecordV1, llm_decision: str, portfolio_state: Dict
    ) -> Optional[str]:
        """Meta-learner agent hook: override LLM decision if needed.

        Args:
            candidate: Candidate evaluated by LLM
            llm_decision: LLM's decision ("skip" or "take")
            portfolio_state: Current portfolio state

        Returns:
            Override decision ("skip", "take") or None to agree with LLM
        """
        # TODO: Implement in Phase 5
        return None  # Default: agree with LLM

    def update_decision_outcome(
        self, candidate_id: str, r_multiple: Optional[float], pnl_usd: Optional[float]
    ) -> None:
        """Update outcome for a recorded decision.

        Args:
            candidate_id: Candidate ID
            r_multiple: R-multiple outcome
            pnl_usd: PnL in USD
        """
        try:
            # Update outcomes for all active agents
            if self.config.gate_agent and self.config.gate_agent.enabled:
                self.agent_state.update_decision_outcome(
                    agent_name="gate", candidate_id=candidate_id,
                    r_multiple=r_multiple, pnl_usd=pnl_usd
                )

            if self.config.portfolio_agent and self.config.portfolio_agent.enabled:
                self.agent_state.update_decision_outcome(
                    agent_name="portfolio", candidate_id=candidate_id,
                    r_multiple=r_multiple, pnl_usd=pnl_usd
                )
        except Exception as e:
            logger.error(f"Failed to update decision outcome: {e}")

    def close(self) -> None:
        """Close RL system and release resources."""
        if self.agent_state:
            self.agent_state.close()
        logger.info(f"Closed RL system for run {self.run_id}")
