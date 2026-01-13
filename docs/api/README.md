# Darwin API Documentation

## Overview

This directory contains API documentation for Darwin's key modules and interfaces.

## Module Reference

### Schemas (`darwin.schemas`)

Pydantic models for data validation:

- **run_config.py**: Run configuration with validation
- **candidate.py**: Candidate record schema
- **position.py**: Position record schema
- **llm_payload.py**: LLM input schema
- **llm_response.py**: LLM output schema
- **outcome_label.py**: Outcome labeling schema

See schema files for detailed field documentation.

### Storage (`darwin.storage`)

Storage layer interfaces:

- **candidate_cache.py**: CRUD for candidates
- **position_ledger.py**: CRUD for positions
- **outcome_labels.py**: CRUD for labels

#### CandidateCache API

```python
from darwin.storage.candidate_cache import CandidateCacheSQLite

# Initialize
cache = CandidateCacheSQLite("path/to/db")

# Store candidate
cache.put(candidate_record)

# Retrieve candidate
candidate = cache.get(candidate_id)

# Query candidates
candidates = cache.query(
    run_id="run_001",
    symbol="BTC-USD",
    playbook="breakout",
    taken_only=True
)
```

#### PositionLedger API

```python
from darwin.storage.position_ledger import PositionLedgerSQLite

# Initialize
ledger = PositionLedgerSQLite("path/to/db")

# Open position
ledger.open_position(position_row)

# Update position (e.g., trailing stop)
ledger.update_position(position_id, {"highest_price": 52000.0})

# Close position
ledger.close_position(position_id, exit_info)

# Get open positions
open_positions = ledger.get_open_positions()

# Get all positions for run
all_positions = ledger.get_all(run_id="run_001")
```

### Playbooks (`darwin.playbooks`)

Playbook base interface:

```python
from darwin.playbooks.base import PlaybookBase

class CustomPlaybook(PlaybookBase):
    def evaluate(
        self,
        features: Dict[str, float],
        bar: Dict[str, Any],
        config: PlaybookConfigV1,
    ) -> Optional[CandidateRecordV1]:
        """
        Evaluate if current bar presents a candidate.

        Args:
            features: Computed technical features
            bar: Current OHLCV bar
            config: Playbook configuration

        Returns:
            CandidateRecordV1 if candidate found, None otherwise
        """
        pass
```

### Simulator (`darwin.simulator`)

Position simulation:

```python
from darwin.simulator.position import Position

# Create position
position = Position(
    position_id="pos_001",
    symbol="BTC-USD",
    direction="long",
    entry_price=50000.0,
    entry_bar_index=100,
    entry_timestamp=datetime.now(),
    size_usd=1000.0,
    size_units=0.02,
    entry_fees_usd=6.25,
    atr_at_entry=500.0,
    exit_spec=exit_spec,
)

# Update with new bar
exit_result = position.update_bar(
    high=51000.0,
    low=49500.0,
    close=50500.0,
    bar_index=101,
    timestamp=datetime.now(),
)

if exit_result is not None:
    print(f"Position exited: {exit_result.reason}")
```

### Features (`darwin.features`)

Feature pipeline:

```python
from darwin.features.pipeline import FeaturePipelineV1

# Initialize
pipeline = FeaturePipelineV1(
    symbol="BTC-USD",
    warmup_bars=400,
    feature_mode="full"
)

# Process bar
features = pipeline.on_bar(bar)

if features is not None:
    # Features available after warmup
    print(features['rsi'])
    print(features['atr'])
```

### LLM (`darwin.llm`)

LLM integration:

```python
from darwin.llm.harness import LLMHarness

# Initialize with retry logic
harness = LLMHarness(
    provider="anthropic",
    model="claude-3-sonnet-20240229",
    max_calls_per_minute=50,
    max_retries=3,
)

# Make call
response = harness.call(payload)
```

### Runner (`darwin.runner`)

Main experiment runner:

```python
from darwin.runner.experiment import run_experiment
from darwin.schemas.run_config import RunConfigV1

# Load config
config = RunConfigV1.model_validate_json(config_json)

# Run experiment
run_experiment(config)
```

### Evaluation (`darwin.evaluation`)

Performance analysis:

```python
from darwin.evaluation.run_report import generate_run_report

# Generate report
report = generate_run_report(
    run_id="run_001",
    ledger=position_ledger,
    candidate_cache=candidate_cache,
)

# Save report
report.save("artifacts/runs/run_001/report.json")
```

## CLI Usage

Darwin provides a command-line interface:

```bash
# Run experiment
darwin run examples/basic_breakout.json

# Generate report
darwin report run_001

# Generate meta report (cross-run comparison)
darwin meta-report

# List runs
darwin list

# Compare two runs
darwin compare run_001 run_002
```

## Configuration Reference

See example configurations in `examples/` directory:

- `basic_breakout.json`: Simple breakout strategy
- `basic_pullback.json`: Simple pullback strategy
- `multi_playbook.json`: Multiple playbooks
- `conservative.json`: Low-risk settings
- `aggressive.json`: High-risk settings

## Error Handling

All API functions may raise:

- `ValueError`: Invalid input parameters
- `FileNotFoundError`: Missing required files
- `pydantic.ValidationError`: Schema validation failures
- `sqlite3.Error`: Database errors

Use try-except blocks appropriately:

```python
from pydantic import ValidationError

try:
    config = RunConfigV1.model_validate_json(json_str)
except ValidationError as e:
    print(f"Invalid config: {e}")
```

## Type Hints

All Darwin modules use type hints. Enable mypy for type checking:

```bash
mypy darwin --strict
```

## Further Reading

- [Architecture Overview](../architecture.md)
- [Playbook Specifications](../playbooks.md)
- [Feature Documentation](../features.md)
