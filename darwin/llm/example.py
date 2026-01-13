"""Example usage of the darwin.llm module.

This demonstrates the complete flow from building prompts to making decisions.
Run this file to test the LLM module with mock backends.
"""

from darwin.llm import (
    LLMHarnessWithRetry,
    LLMPromptV1,
    RateLimiter,
    build_context_from_payload,
)
from darwin.llm.mock import MockLLM, RuleBasedMockLLM
from darwin.schemas.llm_payload import (
    AssetStateV1,
    CandidateSetupV1,
    GlobalRegimeV1,
    LLMPayloadV1,
    PolicyConstraintsV1,
    TrendInfo,
    VolatilityInfo,
    VolumeInfo,
)


def create_example_payload() -> LLMPayloadV1:
    """Create an example LLM payload for testing."""
    global_regime = GlobalRegimeV1(
        risk_mode="risk_on",
        risk_budget=0.5,
        trend_mode="up",
        trend_strength_pct=75.0,
        vol_mode="normal",
        vol_pct=50.0,
        drawdown_bucket="none",
    )

    asset_state = AssetStateV1(
        symbol="BTC-USD",
        price_location_1h="above_key_ma",
        trend_1h=TrendInfo(direction="up", strength_pct=70.0),
        momentum_15m="strong_up",
        volatility=VolatilityInfo(
            atr_pct_15m=2.5, atr_pct_1h=3.0, vol_regime_15m="normal"
        ),
        volume=VolumeInfo(regime_15m="high", zscore_15m=1.5),
        range_state_15m="normal",
        chop_score="low",
        recent_events=["vol_expansion_3bars"],
    )

    candidate_setup = CandidateSetupV1(
        playbook="breakout",
        direction="long",
        setup_stage="ok",
        trigger_type="range_break_with_volume",
        stop_atr=1.2,
        expected_rr_bucket="2-3",
        distance_to_structure="near",
        quality_indicators={
            "compression_present": True,
            "vol_expansion": True,
            "volume_confirm": True,
            "prior_false_breakouts_24h": 0,
        },
    )

    policy_constraints = PolicyConstraintsV1(
        required_quality="A",
        max_risk_budget=0.5,
        notes="Risk-on regime, favor quality breakouts",
    )

    return LLMPayloadV1(
        global_regime=global_regime,
        asset_state=asset_state,
        candidate_setup=candidate_setup,
        policy_constraints=policy_constraints,
        candidate_id="test_candidate_001",
        timestamp="2024-01-13T09:00:00Z",
    )


def example_basic_usage():
    """Example 1: Basic usage with mock LLM."""
    print("=" * 80)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 80)

    # Create payload
    payload = create_example_payload()

    # Build prompt
    context = build_context_from_payload(payload)
    prompt_payload = LLMPromptV1.build_payload(context)

    print("\nSystem Prompt (first 200 chars):")
    print(prompt_payload["system"][:200] + "...")

    print("\nUser Prompt (first 500 chars):")
    print(prompt_payload["user"][:500] + "...")

    # Create mock LLM backend
    backend = MockLLM(
        static_response={
            "decision": "take",
            "setup_quality": "A",
            "confidence": 0.85,
            "risk_flags": [],
            "notes": "Strong breakout with volume confirmation",
        }
    )

    # Create harness
    harness = LLMHarnessWithRetry(backend=backend, max_retries=2)

    # Query
    result = harness.query(prompt_payload)

    print(f"\n{'Success!' if result.success else 'Failed!'}")
    print(f"Decision: {result.response.decision}")
    print(f"Quality: {result.response.setup_quality}")
    print(f"Confidence: {result.response.confidence:.2f}")
    print(f"Notes: {result.response.notes}")
    print(f"Retries: {result.retries}")
    print(f"Latency: {result.latency_ms:.2f}ms")


def example_rule_based_mock():
    """Example 2: Rule-based mock LLM."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Rule-Based Mock")
    print("=" * 80)

    # Create payload
    payload = create_example_payload()
    context = build_context_from_payload(payload)
    prompt_payload = LLMPromptV1.build_payload(context)

    # Use rule-based mock (analyzes prompt content)
    backend = RuleBasedMockLLM()
    harness = LLMHarnessWithRetry(backend=backend)

    result = harness.query(prompt_payload)

    print(f"\n{'Success!' if result.success else 'Failed!'}")
    print(f"Decision: {result.response.decision}")
    print(f"Quality: {result.response.setup_quality}")
    print(f"Confidence: {result.response.confidence:.2f}")
    print(f"Risk Flags: {', '.join(result.response.risk_flags) or 'None'}")
    print(f"Notes: {result.response.notes}")


def example_with_rate_limiting():
    """Example 3: With rate limiting."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Rate Limiting")
    print("=" * 80)

    # Create payload
    payload = create_example_payload()
    context = build_context_from_payload(payload)
    prompt_payload = LLMPromptV1.build_payload(context)

    # Create rate limiter (60 calls per minute)
    rate_limiter = RateLimiter(max_calls_per_minute=60)

    # Create harness with rate limiting
    backend = RuleBasedMockLLM()
    harness = LLMHarnessWithRetry(backend=backend, rate_limiter=rate_limiter)

    print("\nMaking 3 rapid queries...")
    for i in range(3):
        result = harness.query(prompt_payload)
        print(f"Query {i+1}: {result.response.decision} ({result.latency_ms:.2f}ms)")

    # Get statistics
    stats = harness.get_stats()
    print(f"\nHarness Statistics:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Avg retries: {stats['avg_retries_per_call']:.2f}")
    print(f"  Circuit breaker: {stats['circuit_breaker_state']}")


def example_retry_with_failures():
    """Example 4: Retry logic with simulated failures."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Retry Logic")
    print("=" * 80)

    # Create payload
    payload = create_example_payload()
    context = build_context_from_payload(payload)
    prompt_payload = LLMPromptV1.build_payload(context)

    # Mock with 50% error rate
    backend = MockLLM(simulate_errors=True, error_rate=0.5)

    harness = LLMHarnessWithRetry(
        backend=backend, max_retries=3, initial_retry_delay=0.1  # Fast retries for demo
    )

    print("\nTrying 3 queries with 50% error rate...")
    for i in range(3):
        result = harness.query(prompt_payload)
        status = "SUCCESS" if result.success else "FALLBACK"
        print(
            f"Query {i+1}: {status} (retries: {result.retries}, latency: {result.latency_ms:.0f}ms)"
        )
        if not result.success:
            print(f"  Error: {result.error}")

    # Statistics
    stats = harness.get_stats()
    print(f"\nFinal Statistics:")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Failed calls: {stats['failed_calls']}")
    print(f"  Total retries: {stats['total_retries']}")


if __name__ == "__main__":
    # Run all examples
    example_basic_usage()
    example_rule_based_mock()
    example_with_rate_limiting()
    example_retry_with_failures()

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)
