"""Prompt engineering as code with versioning.

Template-based prompt construction for LLM decision-making.
"""

from typing import Any, Dict

from darwin.schemas.llm_payload import (
    AssetStateV1,
    CandidateSetupV1,
    GlobalRegimeV1,
    LLMPayloadV1,
    PolicyConstraintsV1,
)


class LLMPromptV1:
    """
    Version 1 of the LLM prompt template.

    Formats context from features into structured prompts for trade evaluation.
    Includes global regime, asset state, candidate setup, and policy constraints.
    """

    VERSION = "v1"

    # System prompt (constant)
    SYSTEM_PROMPT = """You are a professional crypto trading system evaluating candidate trade setups.

Your role is to:
1. Assess the quality of a trade setup according to the specified playbook
2. Identify risk factors that could invalidate the setup
3. Make a binary decision: TAKE or SKIP
4. Provide a confidence score reflecting your conviction

You MUST output valid JSON only, with no additional text or explanation.

Output schema:
{
  "decision": "take" or "skip",
  "setup_quality": "A+" | "A" | "B" | "C",
  "confidence": 0.0 to 1.0,
  "risk_flags": ["flag1", "flag2", ...],
  "notes": "Brief reasoning (1-2 sentences max)"
}

Quality grades:
- A+: Textbook setup, all conditions ideal, rare opportunity
- A: Strong setup, meets all key criteria, good risk/reward
- B: Acceptable setup, some conditions met, marginal risk/reward
- C: Weak setup, few conditions met, poor risk/reward

Risk flags can include:
- crowded_longs, crowded_shorts
- late_entry, extended_move
- high_chop, weak_setup
- no_volume_confirm, low_liquidity
- regime_mismatch

Be selective. Only take A+ or A grade setups in favorable conditions.
When in doubt, skip. Capital preservation is paramount."""

    @classmethod
    def build_user_prompt(cls, context: Dict[str, Any]) -> str:
        """
        Build user prompt from context dictionary.

        Args:
            context: Dictionary containing:
                - global_regime: GlobalRegimeV1 instance or dict
                - asset_state: AssetStateV1 instance or dict
                - candidate_setup: CandidateSetupV1 instance or dict
                - policy_constraints: PolicyConstraintsV1 instance or dict
                - derivatives (optional): Derivatives data dict

        Returns:
            Formatted user prompt string.

        Example:
            >>> context = {
            ...     "global_regime": global_regime_obj,
            ...     "asset_state": asset_state_obj,
            ...     "candidate_setup": setup_obj,
            ...     "policy_constraints": policy_obj
            ... }
            >>> prompt = LLMPromptV1.build_user_prompt(context)
        """
        # Extract objects (handle both pydantic models and dicts)
        global_regime = cls._to_dict(context.get("global_regime"))
        asset_state = cls._to_dict(context.get("asset_state"))
        candidate_setup = cls._to_dict(context.get("candidate_setup"))
        policy_constraints = cls._to_dict(context.get("policy_constraints"))
        derivatives = context.get("derivatives")

        # Build prompt sections
        sections = []

        # Global regime section
        sections.append("# GLOBAL MARKET REGIME (BTC 4h context)")
        sections.append(f"Risk Mode: {global_regime.get('risk_mode', 'unknown')}")
        sections.append(f"Risk Budget: {global_regime.get('risk_budget', 0.0):.2f}")
        sections.append(f"Trend: {global_regime.get('trend_mode', 'unknown')} (strength: {global_regime.get('trend_strength_pct', 0):.0f}%)")
        sections.append(f"Volatility: {global_regime.get('vol_mode', 'unknown')} ({global_regime.get('vol_pct', 0):.0f}%)")
        sections.append(f"Drawdown: {global_regime.get('drawdown_bucket', 'unknown')}")
        sections.append("")

        # Asset state section
        sections.append(f"# ASSET STATE: {asset_state.get('symbol', 'UNKNOWN')}")
        sections.append(f"Price Location (1h): {asset_state.get('price_location_1h', 'unknown')}")

        trend_1h = asset_state.get('trend_1h', {})
        sections.append(f"Trend (1h): {trend_1h.get('direction', 'unknown')} (strength: {trend_1h.get('strength_pct', 0):.0f}%)")
        sections.append(f"Momentum (15m): {asset_state.get('momentum_15m', 'unknown')}")

        vol_info = asset_state.get('volatility', {})
        sections.append(f"Volatility (15m): {vol_info.get('vol_regime_15m', 'unknown')} (ATR: {vol_info.get('atr_pct_15m', 0):.2f}%)")

        vol_data = asset_state.get('volume', {})
        sections.append(f"Volume (15m): {vol_data.get('regime_15m', 'unknown')} (z-score: {vol_data.get('zscore_15m', 0):.2f})")

        sections.append(f"Range State (15m): {asset_state.get('range_state_15m', 'unknown')}")
        sections.append(f"Chop Score: {asset_state.get('chop_score', 'unknown')}")

        recent_events = asset_state.get('recent_events', [])
        if recent_events:
            sections.append(f"Recent Events: {', '.join(recent_events)}")
        else:
            sections.append("Recent Events: None")
        sections.append("")

        # Candidate setup section
        sections.append("# CANDIDATE SETUP")
        sections.append(f"Playbook: {candidate_setup.get('playbook', 'unknown').upper()}")
        sections.append(f"Direction: {candidate_setup.get('direction', 'unknown').upper()}")
        sections.append(f"Setup Stage: {candidate_setup.get('setup_stage', 'unknown')}")
        sections.append(f"Trigger: {candidate_setup.get('trigger_type', 'unknown')}")
        sections.append(f"Stop Loss: {candidate_setup.get('stop_atr', 0):.2f} ATR")
        sections.append(f"Expected R:R: {candidate_setup.get('expected_rr_bucket', 'unknown')}")
        sections.append(f"Distance to Structure: {candidate_setup.get('distance_to_structure', 'unknown')}")

        quality_indicators = candidate_setup.get('quality_indicators', {})
        if quality_indicators:
            sections.append("\nQuality Indicators:")
            for key, value in quality_indicators.items():
                sections.append(f"  - {key}: {value}")
        sections.append("")

        # Derivatives data (if available)
        if derivatives:
            sections.append("# DERIVATIVES DATA")
            for key, value in derivatives.items():
                sections.append(f"{key}: {value}")
            sections.append("")

        # Policy constraints section
        sections.append("# POLICY CONSTRAINTS")
        sections.append(f"Required Quality: {policy_constraints.get('required_quality', 'unknown')} or better")
        sections.append(f"Max Risk Budget: {policy_constraints.get('max_risk_budget', 0):.2f}")
        policy_notes = policy_constraints.get('notes', '')
        if policy_notes:
            sections.append(f"Notes: {policy_notes}")
        sections.append("")

        # Decision prompt
        sections.append("# YOUR DECISION")
        sections.append("Evaluate this setup and output your decision as JSON.")

        return "\n".join(sections)

    @classmethod
    def build_payload(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build complete LLM payload with system and user prompts.

        Args:
            context: Context dictionary (same as build_user_prompt)

        Returns:
            Dictionary with 'system' and 'user' keys containing prompts.

        Example:
            >>> payload = LLMPromptV1.build_payload(context)
            >>> # payload = {"system": "...", "user": "..."}
        """
        return {
            "system": cls.SYSTEM_PROMPT,
            "user": cls.build_user_prompt(context),
        }

    @staticmethod
    def _to_dict(obj: Any) -> Dict[str, Any]:
        """Convert pydantic model to dict, or return dict as-is."""
        if obj is None:
            return {}
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj
        return {}


def build_context_from_payload(payload: LLMPayloadV1) -> Dict[str, Any]:
    """
    Build context dictionary from LLMPayloadV1 for prompt construction.

    Args:
        payload: LLMPayloadV1 instance containing all context.

    Returns:
        Context dictionary suitable for LLMPromptV1.build_user_prompt().

    Example:
        >>> payload = LLMPayloadV1(...)
        >>> context = build_context_from_payload(payload)
        >>> prompt = LLMPromptV1.build_user_prompt(context)
    """
    return {
        "global_regime": payload.global_regime,
        "asset_state": payload.asset_state,
        "candidate_setup": payload.candidate_setup,
        "policy_constraints": payload.policy_constraints,
        "derivatives": payload.derivatives,
    }
