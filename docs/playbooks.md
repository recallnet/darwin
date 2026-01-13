# Playbook Specifications

## Overview

Playbooks are deterministic, rule-based systems that identify potential trading opportunities. They consume technical features and output candidate setups without making take/skip decisions (that's the LLM's role).

## Design Philosophy

### Playbook Responsibilities

✅ **What playbooks DO:**
- Pattern detection (breakout, pullback, etc.)
- Entry price determination
- Exit specification (SL, TP, trailing)
- Candidate generation

❌ **What playbooks DON'T do:**
- Take/skip decisions (LLM's job)
- Position sizing (portfolio manager's job)
- Multi-bar state tracking (they're stateless functions)

### Key Principle

> **Playbooks answer "WHAT is an opportunity"**
>
> **LLMs answer "WHETHER to take it"**

## Breakout Playbook

### Concept

Trades breakouts from compression zones with volume confirmation.

### Entry Conditions

1. **Compression Phase**
   - Price range contracting over N bars
   - ATR declining
   - Low volatility regime

2. **Breakout Trigger**
   - Price breaks above/below compression range by ≥ threshold
   - Volume spike (> volume_confirm_threshold × average)
   - Strong directional close

3. **Confirmation**
   - Sustained move (not immediate reversion)
   - Volume expansion continues

### Entry Parameters

```json
{
  "min_compression_bars": 10,        // Minimum bars in compression
  "breakout_threshold_atr": 0.5,     // Breakout size in ATR units
  "volume_confirm_threshold": 1.5    // Volume spike threshold
}
```

### Exit Specification

- **Stop Loss**: 2.0 ATR below entry (long) / above entry (short)
- **Take Profit**: 4.0 ATR above entry (long) / below entry (short)
- **Time Stop**: 32 bars (8 hours @ 15min)
- **Trailing Stop**:
  - Activation: +1.0 ATR profit
  - Distance: 1.2 ATR from highest high

### Implementation

See `darwin/playbooks/breakout.py`

## Pullback Playbook

### Concept

Trades pullbacks in established trends, entering at Fibonacci retracement levels.

### Entry Conditions

1. **Trend Identification**
   - EMAs aligned (20 > 50 > 200 for uptrend)
   - ADX > 25 (strong trend)
   - Higher highs + higher lows (uptrend)

2. **Pullback Phase**
   - Price retraces 38.2% - 61.8% of recent impulse move
   - Momentum (RSI) cools but stays > 40 (uptrend)
   - Volume decreases during pullback

3. **Entry Trigger**
   - Price bounces from support level
   - Momentum turns up (MACD crossover)
   - Volume expansion on reversal

### Entry Parameters

```json
{
  "min_trend_strength": 0.6,      // Minimum trend strength score
  "pullback_depth_min": 0.382,    // Fibonacci 38.2%
  "pullback_depth_max": 0.618     // Fibonacci 61.8%
}
```

### Exit Specification

- **Stop Loss**: 1.5 ATR below recent swing low (long)
- **Take Profit**: 3.0 ATR above entry
- **Time Stop**: 48 bars (12 hours @ 15min)
- **Trailing Stop**:
  - Activation: +0.75 ATR profit
  - Distance: 1.0 ATR from highest high

### Implementation

See `darwin/playbooks/pullback.py`

## Creating Custom Playbooks

### Step 1: Subclass PlaybookBase

```python
from darwin.playbooks.base import PlaybookBase
from darwin.schemas.candidate import CandidateRecordV1

class MyPlaybook(PlaybookBase):
    def evaluate(
        self,
        features: Dict[str, float],
        bar: Dict[str, Any],
        config: PlaybookConfigV1,
    ) -> Optional[CandidateRecordV1]:
        # Your logic here
        pass
```

### Step 2: Implement Detection Logic

```python
def evaluate(self, features, bar, config):
    # Check entry conditions
    if not self._check_conditions(features, config):
        return None

    # Calculate entry and exits
    entry_price = self._calculate_entry(bar, features)
    exit_spec = self._build_exit_spec(entry_price, features, config)

    # Build candidate
    return CandidateRecordV1(
        candidate_id=generate_id(),
        # ... other fields
        playbook="my_playbook",
        entry_price=entry_price,
        exit_spec=exit_spec,
    )
```

### Step 3: Register Playbook

Add to `darwin/playbooks/__init__.py`:

```python
from .my_playbook import MyPlaybook

PLAYBOOK_REGISTRY = {
    "breakout": BreakoutPlaybook,
    "pullback": PullbackPlaybook,
    "my_playbook": MyPlaybook,  # Add here
}
```

### Step 4: Update Configuration Schema

Add to valid playbook names in `run_config.py`:

```python
valid_names = {"breakout", "pullback", "my_playbook"}
```

## Best Practices

### 1. Keep Playbooks Stateless

❌ **Bad**: Store state across bars
```python
class BadPlaybook:
    def __init__(self):
        self.bar_count = 0  # State!
```

✅ **Good**: Pure functions
```python
def evaluate(features, bar, config):
    # All state in features and config
    pass
```

### 2. Use Configuration for Parameters

❌ **Bad**: Hardcoded values
```python
if features['atr'] > 500:  # Magic number
```

✅ **Good**: Configurable
```python
if features['atr'] > config.entry_params['min_atr']:
```

### 3. Comprehensive Validation

```python
def _check_conditions(self, features, config):
    # Check required features exist
    required = ['close', 'ema20', 'atr', 'volume']
    if not all(k in features for k in required):
        return False

    # Check values are valid
    if features['atr'] <= 0:
        return False

    # Your logic
    return True
```

### 4. Clear Exit Specifications

Always provide complete exit specifications:

```python
exit_spec = ExitSpecV1(
    stop_loss_price=entry_price - (2.0 * atr),
    take_profit_price=entry_price + (4.0 * atr),
    time_stop_bars=32,
    trailing_enabled=True,
    trailing_activation_price=entry_price + (1.0 * atr),
    trailing_distance_atr=1.2,
)
```

## Testing Playbooks

### Unit Tests

```python
def test_breakout_triggers_on_pattern():
    # Arrange: Create breakout scenario
    features = create_breakout_features()
    bar = create_breakout_bar()
    config = BreakoutPlaybookConfig()

    # Act
    playbook = BreakoutPlaybook()
    candidate = playbook.evaluate(features, bar, config)

    # Assert
    assert candidate is not None
    assert candidate.direction == "long"
```

### Integration Tests

Use synthetic data generators:

```python
from tests.fixtures.market_data import generate_breakout_scenario

def test_breakout_full_scenario():
    data = generate_breakout_scenario()
    # Run playbook on full scenario
    # Verify candidate at expected bar
```

## Playbook Comparison

| Feature | Breakout | Pullback |
|---------|----------|----------|
| **Best Market** | Volatile, trending | Established trends |
| **Win Rate** | Lower (~40%) | Higher (~55%) |
| **Risk:Reward** | Higher (1:2+) | Moderate (1:1.5) |
| **Holding Time** | Shorter | Longer |
| **Volatility** | Requires expansion | Requires calm |

## Future Playbooks

Potential additions:
- **Range Trading**: Buy support, sell resistance
- **Mean Reversion**: Fade extremes
- **Momentum**: Follow strong moves
- **Statistical Arbitrage**: Price dislocations

## References

- [Architecture Overview](./architecture.md)
- [Feature Documentation](./features.md)
- [Example Configurations](../examples/)
