# Darwin LLM Module

This module provides comprehensive LLM integration with production-ready resilience patterns.

## Components

### 1. Rate Limiter (`rate_limiter.py`)

Token bucket algorithm for rate limiting API calls.

```python
from darwin.llm import RateLimiter

# Create rate limiter (30 calls per minute)
limiter = RateLimiter(max_calls_per_minute=30)

# Acquire token (blocks until available)
limiter.acquire()
# Make API call here

# Try to acquire without blocking
if limiter.try_acquire():
    # Make API call
    pass
```

**Features:**
- Thread-safe implementation
- Configurable burst size
- Timeout support
- Token refill based on elapsed time

### 2. Prompt Engineering (`prompts.py`)

Template-based prompt construction with versioning.

```python
from darwin.llm import LLMPromptV1, build_context_from_payload
from darwin.schemas.llm_payload import LLMPayloadV1

# Build context from payload
context = build_context_from_payload(payload)

# Generate prompt
payload = LLMPromptV1.build_payload(context)
# payload = {"system": "...", "user": "..."}

# Or build just user prompt
user_prompt = LLMPromptV1.build_user_prompt(context)
```

**Features:**
- Versioned prompts (v1)
- Structured context formatting
- System and user prompt separation
- Global regime, asset state, candidate setup, policy constraints

### 3. Response Parser (`parser.py`)

Robust parsing and validation of LLM outputs.

```python
from darwin.llm import parse_llm_response, create_fallback_response

# Parse LLM response
result = parse_llm_response(raw_response)

if result.success:
    print(f"Decision: {result.response.decision}")
    print(f"Quality: {result.response.setup_quality}")
    print(f"Confidence: {result.response.confidence}")
else:
    print(f"Parse error: {result.error}")

# Create fallback response on error
fallback = create_fallback_response("skip", "timeout error")
```

**Features:**
- Extracts JSON from text (handles markdown, plain text)
- Schema validation with pydantic
- Confidence clamping to [0, 1]
- Graceful error handling
- Fallback response generation

### 4. Mock LLM (`mock.py`)

Deterministic LLM implementations for testing.

```python
from darwin.llm.mock import MockLLM, RuleBasedMockLLM, PerfectMockLLM

# Static response mock
mock = MockLLM(static_response={
    "decision": "skip",
    "setup_quality": "B",
    "confidence": 0.5,
    "risk_flags": [],
    "notes": "Test response"
})

# Rule-based mock (analyzes payload)
mock = RuleBasedMockLLM()

# Perfect mock (always takes with A+ quality)
mock = PerfectMockLLM()

# Use it
response = mock.query({"user": "test prompt"})
```

**Mock Types:**
- `MockLLM`: Static or custom function responses
- `RuleBasedMockLLM`: Context-aware responses based on rules
- `PerfectMockLLM`: Always takes trades (upper bound testing)
- `PessimisticMockLLM`: Always skips trades

### 5. LLM Harness (`harness.py`)

Production-ready LLM wrapper with retry logic and circuit breaker.

```python
from darwin.llm import LLMHarnessWithRetry, RateLimiter
from darwin.llm.mock import MockLLM

# Create backend
backend = MockLLM()

# Create harness with resilience patterns
harness = LLMHarnessWithRetry(
    backend=backend,
    max_retries=3,
    initial_retry_delay=1.0,
    circuit_breaker_threshold=5,
    circuit_breaker_timeout=60.0,
    fallback_decision="skip",
    rate_limiter=RateLimiter(max_calls_per_minute=30)
)

# Query LLM
result = harness.query({"system": "...", "user": "..."})

if result.success:
    print(f"Decision: {result.response.decision}")
    print(f"Retries: {result.retries}")
    print(f"Latency: {result.latency_ms:.2f}ms")
else:
    print(f"Failed with fallback: {result.error}")
    print(f"Fallback used: {result.fallback_used}")

# Get statistics
stats = harness.get_stats()
print(f"Success rate: {stats['success_rate']:.2%}")
print(f"Circuit breaker state: {stats['circuit_breaker_state']}")
```

**Features:**
- Exponential backoff with jitter
- Circuit breaker (opens after N failures)
- Rate limiting integration
- Fallback decisions on persistent failures
- Comprehensive statistics
- Thread-safe

## Complete Example

```python
from darwin.llm import (
    LLMHarnessWithRetry,
    RateLimiter,
    LLMPromptV1,
    build_context_from_payload
)
from darwin.llm.mock import RuleBasedMockLLM
from darwin.schemas.llm_payload import LLMPayloadV1

# Create LLM payload (from feature pipeline)
payload = LLMPayloadV1(
    global_regime=...,
    asset_state=...,
    candidate_setup=...,
    policy_constraints=...,
    candidate_id="...",
    timestamp="..."
)

# Build context and prompt
context = build_context_from_payload(payload)
prompt_payload = LLMPromptV1.build_payload(context)

# Create harness with mock backend
backend = RuleBasedMockLLM()
rate_limiter = RateLimiter(max_calls_per_minute=30)
harness = LLMHarnessWithRetry(
    backend=backend,
    rate_limiter=rate_limiter,
    max_retries=3
)

# Query LLM
result = harness.query(prompt_payload)

# Process result
if result.success and not result.fallback_used:
    decision = result.response.decision
    quality = result.response.setup_quality
    confidence = result.response.confidence

    print(f"Decision: {decision}")
    print(f"Quality: {quality}")
    print(f"Confidence: {confidence:.2f}")
    print(f"Risk flags: {', '.join(result.response.risk_flags)}")
else:
    print(f"Using fallback decision: {result.response.decision}")
    print(f"Error: {result.error}")
```

## Architecture

### Circuit Breaker States

1. **CLOSED**: Normal operation, all requests processed
2. **OPEN**: Circuit tripped after threshold failures, requests rejected
3. **HALF_OPEN**: Testing if service recovered

The circuit breaker automatically transitions between states based on success/failure patterns.

### Retry Strategy

- **Exponential backoff**: delay = initial_delay * (2 ^ attempt)
- **Jitter**: ±25% randomization to prevent thundering herd
- **Max delay**: Capped at 30 seconds
- **Max retries**: Configurable (default: 3)

### Rate Limiting

Token bucket algorithm:
- Tokens refill at constant rate (calls_per_minute / 60)
- Burst size allows brief spikes above sustained rate
- Thread-safe with lock protection

## Testing

Use mock LLMs for testing without API calls:

```python
from darwin.llm.mock import MockLLM

# Test with static response
mock = MockLLM(static_response={
    "decision": "take",
    "setup_quality": "A",
    "confidence": 0.85,
    "risk_flags": [],
    "notes": "Good setup"
})

# Test with error simulation
mock = MockLLM(simulate_errors=True, error_rate=0.2)

# Test with latency simulation
mock = MockLLM(latency_ms=100.0)
```

## Integration with Darwin

The LLM module integrates with:

- **Feature Pipeline**: Receives context from computed features
- **Decision Events**: Results logged to `decision_events.jsonl`
- **Position Ledger**: Decisions trigger trade execution
- **Candidate Cache**: All candidates and responses cached

See specs in `/Users/michaelsena/code/trademax/LLM_TRADING_SYSTEM_SPECIFICATIONS.md` for complete system architecture.
