"""Reward shaping utilities for RL agents."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def compute_gate_reward(
    action: int,
    counterfactual_r_multiple: Optional[float] = None,
    llm_decision: Optional[str] = None,
    cost_savings_bonus: float = 0.01,
) -> float:
    """Compute reward for gate agent decision.

    Gate agent reward logic:
    - action=0 (SKIP):
      - If counterfactual R-multiple < 0: +0.1 (correctly skipped loser)
      - If counterfactual R-multiple > 0: -counterfactual_r_multiple (missed opportunity)
      - Plus small cost savings bonus: +0.01
    - action=1 (PASS to LLM):
      - If LLM decided SKIP: -0.02 (wasted LLM call)
      - If LLM decided TAKE: actual R-multiple (trade outcome)

    Args:
        action: Agent action (0=skip, 1=pass)
        counterfactual_r_multiple: What would have happened if taken (for skip action)
        llm_decision: LLM decision if passed ("take" or "skip")
        cost_savings_bonus: Bonus for skipping (default: 0.01)

    Returns:
        Reward value

    Example:
        >>> # Correctly skip a loser
        >>> compute_gate_reward(action=0, counterfactual_r_multiple=-0.5)
        0.11  # +0.1 for correct skip + 0.01 cost savings

        >>> # Miss an opportunity
        >>> compute_gate_reward(action=0, counterfactual_r_multiple=1.5)
        -1.49  # -1.5 penalty + 0.01 cost savings

        >>> # Pass to LLM, but LLM skips
        >>> compute_gate_reward(action=1, llm_decision="skip")
        -0.02  # Wasted LLM call
    """
    SKIP = 0
    PASS = 1

    if action == SKIP:
        # Agent chose to skip
        if counterfactual_r_multiple is None:
            logger.warning("counterfactual_r_multiple is None for SKIP action")
            return 0.0

        if counterfactual_r_multiple < 0:
            # Correctly skipped a loser
            reward = 0.1 + cost_savings_bonus
        else:
            # Missed an opportunity
            reward = -counterfactual_r_multiple + cost_savings_bonus

        return reward

    elif action == PASS:
        # Agent chose to pass to LLM
        if llm_decision == "skip":
            # LLM decided not to take - wasted call
            return -0.02
        elif llm_decision == "take":
            # LLM decided to take - reward comes from actual outcome
            # This will be filled in later with actual R-multiple
            return 0.0  # Placeholder, updated with actual outcome
        else:
            logger.warning(f"Unknown LLM decision: {llm_decision}")
            return 0.0

    else:
        logger.error(f"Invalid action: {action}")
        return 0.0


def compute_portfolio_reward(
    actual_r_multiple: float,
    position_size_fraction: float,
    portfolio_state: dict,
    caused_drawdown: bool = False,
    drawdown_penalty: float = 0.1,
    diversification_bonus: float = 0.05,
    capacity_bonus: float = 0.02,
) -> float:
    """Compute reward for portfolio agent decision.

    Portfolio agent reward logic:
    - Primary: actual R-multiple from trade
    - Drawdown penalty: -0.1 if caused large drawdown
    - Diversification bonus: +0.05 if improved diversification
    - Capacity utilization bonus: +0.02 if used available capacity wisely

    Args:
        actual_r_multiple: Actual R-multiple from trade
        position_size_fraction: Position size chosen (0-1)
        portfolio_state: Portfolio state dict
        caused_drawdown: Whether this trade caused drawdown
        drawdown_penalty: Penalty for causing drawdown (default: 0.1)
        diversification_bonus: Bonus for diversification (default: 0.05)
        capacity_bonus: Bonus for using capacity (default: 0.02)

    Returns:
        Reward value
    """
    # Base reward: R-multiple
    reward = actual_r_multiple

    # Drawdown penalty
    if caused_drawdown:
        reward -= drawdown_penalty

    # Diversification bonus (placeholder - would need portfolio analysis)
    # For now, just reward moderate sizing vs all-in
    if 0.3 <= position_size_fraction <= 0.7:
        reward += diversification_bonus

    # Capacity utilization bonus
    exposure_frac = portfolio_state.get("exposure_frac", 0.0)
    max_exposure_frac = portfolio_state.get("max_exposure_frac", 0.8)

    if exposure_frac < max_exposure_frac and position_size_fraction > 0.5:
        # Good use of available capacity
        reward += capacity_bonus
    elif exposure_frac >= max_exposure_frac and position_size_fraction > 0.3:
        # Oversizing when capacity is low
        reward -= 0.05

    return reward


def compute_meta_learner_reward(
    action: int,
    llm_decision: str,
    actual_r_multiple: Optional[float] = None,
    counterfactual_r_multiple: Optional[float] = None,
    override_penalty: float = 0.05,
) -> float:
    """Compute reward for meta-learner agent decision.

    Meta-learner reward logic:
    - action=0 (AGREE): Follow LLM
      - If LLM said TAKE: reward = actual R-multiple
      - If LLM said SKIP: penalty = -counterfactual_r_multiple * 0.1 (small penalty if missed)
    - action=1 (OVERRIDE_TO_SKIP): Change TAKE → SKIP
      - If counterfactual < 0: reward = -counterfactual (saved from loss)
      - If counterfactual > 0: reward = -counterfactual (missed profit)
      - Plus override penalty: -0.05
    - action=2 (OVERRIDE_TO_TAKE): Change SKIP → TAKE
      - reward = actual R-multiple
      - Plus override penalty: -0.05

    Args:
        action: Agent action (0=agree, 1=override_to_skip, 2=override_to_take)
        llm_decision: Original LLM decision ("take" or "skip")
        actual_r_multiple: Actual R-multiple if taken
        counterfactual_r_multiple: Counterfactual R-multiple if skipped
        override_penalty: Penalty for disagreeing with LLM (default: 0.05)

    Returns:
        Reward value
    """
    AGREE = 0
    OVERRIDE_TO_SKIP = 1
    OVERRIDE_TO_TAKE = 2

    if action == AGREE:
        # Agree with LLM
        if llm_decision == "take":
            if actual_r_multiple is None:
                logger.warning("actual_r_multiple is None for TAKE decision")
                return 0.0
            return actual_r_multiple
        else:  # llm_decision == "skip"
            if counterfactual_r_multiple is None:
                return 0.0
            # Small penalty if missed opportunity
            return -counterfactual_r_multiple * 0.1

    elif action == OVERRIDE_TO_SKIP:
        # Override TAKE → SKIP
        if llm_decision != "take":
            # Invalid action (LLM already said skip)
            return -0.1

        if counterfactual_r_multiple is None:
            logger.warning("counterfactual_r_multiple is None for OVERRIDE_TO_SKIP")
            return -override_penalty

        # Saved from loss (positive) or missed profit (negative)
        reward = -counterfactual_r_multiple - override_penalty
        return reward

    elif action == OVERRIDE_TO_TAKE:
        # Override SKIP → TAKE
        if llm_decision != "skip":
            # Invalid action (LLM already said take)
            return -0.1

        if actual_r_multiple is None:
            logger.warning("actual_r_multiple is None for OVERRIDE_TO_TAKE")
            return -override_penalty

        reward = actual_r_multiple - override_penalty
        return reward

    else:
        logger.error(f"Invalid action: {action}")
        return 0.0


def normalize_reward(reward: float, clip: bool = True, clip_range: float = 5.0) -> float:
    """Normalize and optionally clip reward.

    Args:
        reward: Raw reward value
        clip: Whether to clip reward (default: True)
        clip_range: Clip range [-clip_range, +clip_range] (default: 5.0)

    Returns:
        Normalized/clipped reward
    """
    if clip:
        return max(-clip_range, min(clip_range, reward))
    return reward
