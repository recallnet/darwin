# Darwin System Architecture

## Overview

Darwin is a research platform for evaluating LLM-assisted trading strategies using historical market data. The system implements a clean separation between opportunity detection (playbooks), decision-making (LLM), execution simulation, and performance analysis.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER / CLI                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   GLOBAL RUNNER                              │
│  • Config validation & snapshotting                         │
│  • Bar iteration loop                                        │
│  • Playbook orchestration                                    │
│  • LLM decision pipeline                                     │
│  • Simulation execution                                      │
└───┬──────────┬──────────┬──────────┬──────────┬────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│  Data  │ │Feature │ │Playbook│ │  LLM   │ │ Simulator  │
│ Source │ │Pipeline│ │Engine  │ │Harness │ │  Engine    │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
    │          │          │          │          │
    └──────────┴──────────┴──────────┴──────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                             │
│  • CandidateCache (all opportunities)                       │
│  • PositionLedger (single source of truth for PnL)          │
│  • OutcomeLabels (post-hoc learning substrate)              │
│  • Artifacts (configs, events, payloads)                    │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Runner (`darwin/runner/`)

The global runner orchestrates the entire backtest:

- **experiment.py**: Main execution loop
  - Loads configuration and validates
  - Iterates through historical bars
  - Coordinates playbook evaluation
  - Manages LLM calls
  - Updates positions

- **progress.py**: Real-time progress tracking
  - Bar processing progress
  - Candidate generation stats
  - LLM call tracking

- **checkpointing.py**: State persistence for resumability
  - Saves state every N bars
  - Allows resuming from checkpoint

### 2. Playbooks (`darwin/playbooks/`)

Playbooks are deterministic rule-based systems that identify trading opportunities:

- **base.py**: Abstract base class
- **breakout.py**: Breakout pattern detection
- **pullback.py**: Pullback/retracement detection

Each playbook:
- Consumes features
- Returns candidate setups (entry price, exit spec)
- Does NOT make take/skip decisions (that's LLM's job)

### 3. Feature Pipeline (`darwin/features/`)

Computes technical indicators and market features:

- **pipeline.py**: Main feature computation orchestrator
- **indicators.py**: Technical indicators (EMA, ATR, RSI, etc.)
- **bucketing.py**: Converts features to LLM-friendly buckets

Key optimization: Incremental updates instead of recomputation.

### 4. LLM Integration (`darwin/llm/`)

- **harness.py**: Wraps LLM API calls
- **rate_limiter.py**: Enforces rate limits
- **prompts.py**: Prompt templates (versioned)
- **parser.py**: Response parsing and validation
- **mock.py**: Mock LLM for testing

Features:
- Exponential backoff retry logic
- Circuit breaker for persistent failures
- Payload/response caching

### 5. Simulator (`darwin/simulator/`)

Simulates position execution with realistic constraints:

- **position.py**: Tracks individual positions
- **exits.py**: Exit condition checking
- **position_manager.py**: Manages multiple open positions

Exit Logic Priority:
1. Stop loss (highest priority)
2. Trailing stop
3. Take profit
4. Time stop

### 6. Storage Layer (`darwin/storage/`)

All storage uses SQLite for simplicity:

- **candidate_cache.py**: Stores ALL candidates (taken + skipped)
- **position_ledger.py**: **Single source of truth** for PnL
- **outcome_labels.py**: Post-hoc outcome labeling

### 7. Evaluation (`darwin/evaluation/`)

- **run_report.py**: Per-run analysis
- **meta_report.py**: Cross-run comparison
- **metrics.py**: Performance metrics (Sharpe, Sortino, etc.)
- **plots.py**: Visualization generation

## Data Flow

### Single Bar Processing

```
1. Load bar[t]
   ↓
2. Compute features
   ↓
3. Check open positions for exits
   ↓
4. For each playbook:
   a. Evaluate if candidate
   b. If yes → Build LLM payload
   c. Call LLM
   d. Parse decision
   e. Store in candidate cache
   f. If TAKE → Open position
   ↓
5. Store decision events
   ↓
6. Continue to bar[t+1]
```

## Key Design Principles

### 1. Immutability

- Configs are snapshotted at run start
- Artifacts include version headers
- No mutation after creation

### 2. Single Source of Truth

- Position ledger is authoritative for PnL
- All metrics derived from ledger
- No cached derived values

### 3. Separation of Concerns

- **Playbooks**: WHAT is an opportunity
- **LLM**: WHETHER to take it
- **Simulator**: HOW it performs
- **Evaluator**: DID it work

### 4. Learning Substrate

- Candidate cache stores ALL opportunities
- Enables supervised learning (predict LLM quality)
- Enables RL (optimize policies)
- Enables counterfactual analysis

### 5. Reproducibility

- Config snapshots
- Deterministic execution
- Content hashes in manifests

## File Structure

```
darwin/
├── __init__.py
├── schemas/          # Pydantic models
├── storage/          # SQLite storage
├── features/         # Feature computation
├── playbooks/        # Trading playbooks
├── simulator/        # Position simulation
├── llm/              # LLM integration
├── runner/           # Main orchestrator
├── evaluation/       # Performance analysis
└── utils/            # Utilities

tools/                # CLI entry points
tests/                # Test suite
examples/             # Example configs
docs/                 # Documentation
```

## Artifacts Structure

```
artifacts/
├── runs/
│   └── run_001/
│       ├── config.json           # Snapshotted config
│       ├── decision_events.jsonl # Event stream
│       ├── payloads/             # LLM payloads
│       ├── responses/            # LLM responses
│       ├── report.json           # Performance report
│       ├── report.md             # Human-readable report
│       ├── plots/                # Visualizations
│       └── manifest.json         # Run manifest
├── ledger/
│   └── positions.db              # Position ledger (SQLite)
├── candidate_cache/
│   └── candidates.db             # Candidate cache (SQLite)
├── labels/
│   └── labels.db                 # Outcome labels (SQLite)
└── meta_reports/
    └── meta_report.md            # Cross-run analysis
```

## Extension Points

### Adding a New Playbook

1. Subclass `PlaybookBase`
2. Implement `evaluate(features, bar)` method
3. Register in `playbooks/__init__.py`
4. Add config schema to `PlaybookConfigV1`

### Adding New Features

1. Add indicator to `features/indicators.py`
2. Update `FeaturePipelineV1.compute_features()`
3. Add bucketing logic if needed
4. Update LLM payload schema

### Adding New Storage Backend

1. Implement storage interface from `storage/interface.py`
2. Register in factory pattern
3. Update configuration schema

## Performance Considerations

### Feature Computation

- **Problem**: Computing 80+ features per bar is slow
- **Solution**: Incremental updates (EMA state, rolling windows)
- **Speedup**: 10-100x over naive implementation

### LLM Rate Limiting

- **Problem**: API rate limits
- **Solution**: Rate limiter + retry logic + circuit breaker
- **Benefit**: Graceful handling of bursts

### Database Writes

- **Problem**: SQLite doesn't handle concurrent writes well
- **Solution**: Abstract storage interface for future backends
- **Future**: Can swap to Postgres for parallelization

## Testing Strategy

- **Unit tests**: Individual components
- **Integration tests**: End-to-end runs with mock LLM
- **Property-based tests**: Invariant checking (Hypothesis)
- **Synthetic data**: Fast, reproducible test data

See `tests/` directory for comprehensive test suite.

## References

- [System Audit Document](../../../trademax/SYSTEM_AUDIT_AND_IMPROVEMENTS.md)
- [Playbook Specifications](./playbooks.md)
- [Feature Documentation](./features.md)
- [API Documentation](./api/README.md)
