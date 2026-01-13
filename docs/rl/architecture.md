# RL System Architecture

This document describes the architecture and design of Darwin's reinforcement learning system for automated trading decisions.

## Table of Contents

1. [Overview](#overview)
2. [System Components](#system-components)
3. [Three-Agent Architecture](#three-agent-architecture)
4. [State Representation](#state-representation)
5. [Action Spaces](#action-spaces)
6. [Reward Shaping](#reward-shaping)
7. [Training Pipeline](#training-pipeline)
8. [Graduation System](#graduation-system)
9. [Integration with Runner](#integration-with-runner)
10. [Data Flow](#data-flow)

---

## Overview

Darwin's RL system uses **three specialized agents** that progressively take over trading decisions from the LLM:

1. **Gate Agent**: Filters candidates before LLM evaluation (reduces API costs)
2. **Portfolio Agent**: Optimizes position sizing after LLM approval
3. **Meta-Learner Agent**: Overrides LLM decisions based on learned patterns

### Key Design Principles

- **Observe-First**: Agents start in observe mode, making predictions without affecting decisions
- **Graduation Policies**: Agents automatically promote to active mode when meeting performance criteria
- **Safety Mechanisms**: Circuit breakers, rate limiting, and automatic fallback on degradation
- **Auditability**: Every agent decision is recorded with full state and outcome
- **Offline Learning**: Training happens asynchronously, not during live trading

---

## System Components

### Core Modules

```
darwin/rl/
├── agents/              # Agent implementations
│   ├── base.py          # Base agent interface
│   ├── gate_agent.py    # Pre-LLM filter
│   ├── portfolio_agent.py  # Position sizing
│   └── meta_learner_agent.py  # LLM override
├── envs/                # Gymnasium environments
│   ├── gate_env.py      # Gate agent environment
│   ├── portfolio_env.py # Portfolio agent environment
│   └── meta_learner_env.py  # Meta-learner environment
├── training/            # Training infrastructure
│   ├── offline_batch.py # Offline batch trainer
│   └── hyperparameters.py  # Tuned hyperparameters
├── graduation/          # Graduation system
│   ├── policy.py        # Graduation evaluation
│   ├── baselines.py     # Baseline strategies
│   └── metrics.py       # Performance metrics
├── integration/         # Runner integration
│   └── runner_hooks.py  # RL system hooks
├── storage/             # Persistence
│   ├── agent_state.py   # Decision/outcome storage
│   └── model_store.py   # Model versioning
├── monitoring/          # Production monitoring
│   ├── alerts.py        # Performance alerts
│   └── safety.py        # Circuit breakers
├── schemas/             # Configuration schemas
│   └── rl_config.py     # RL configuration
└── utils/               # Utilities
    ├── state_encoding.py  # State encoders
    └── reward_shaping.py  # Reward functions
```

---

## Three-Agent Architecture

### 1. Gate Agent (Pre-LLM Filter)

**Purpose**: Reduce API costs by filtering low-quality candidates

**Placement**: Before LLM call in decision pipeline

**State**: 34 features
- Price features (close, ATR, volatility)
- Trend indicators (EMAs, ADX)
- Momentum (RSI)
- Range breakout/pullback distances
- Volume indicators
- Portfolio state (open positions, equity)

**Action**: Discrete(2) - `skip` or `pass`

**Reward**:
- +1.0 for correctly skipping a losing trade
- -1.5 for incorrectly skipping a winning trade (opportunity cost)
- -0.1 for passing to LLM (API cost)
- R-multiple scaled reward for correct passes

**Graduation Criteria**:
- 1000+ training samples
- 200+ validation samples
- 20%+ API cost savings vs "pass all" baseline
- <10% miss rate on winning trades

**Expected Impact**: 20-40% reduction in LLM API calls

---

### 2. Portfolio Agent (Position Sizing)

**Purpose**: Optimize position sizing for better risk-adjusted returns

**Placement**: After LLM approval, before position opening

**State**: 30 features
- All candidate features
- LLM confidence and quality scores
- Portfolio context (equity, open positions, exposure)
- Risk specifications (max drawdown, position limits)

**Action**: Continuous[0,1] - position size fraction

**Reward**:
- Base: Actual R-multiple × position size fraction
- Drawdown penalty: -0.5 × drawdown_fraction (if > 20%)
- Diversification bonus: +0.2 × diversification_score

**Graduation Criteria**:
- 500+ training samples
- 100+ validation samples
- Sharpe ratio >1.5 vs equal-weight baseline
- Max drawdown <20%
- 10%+ improvement over baseline

**Expected Impact**: Sharpe ratio improvement from ~1.2 to >1.5

---

### 3. Meta-Learner Agent (LLM Override)

**Purpose**: Learn when to override LLM decisions based on outcome patterns

**Placement**: After LLM decision, before execution

**State**: 38 features
- All candidate features
- LLM decision context (decision, confidence, quality, risk flags)
- LLM historical accuracy (rolling 50-trade window)
- Market regime indicators

**Action**: Discrete(3) - `agree`, `override_to_skip`, `override_to_take`

**Reward**:
- Agree with LLM: +0.1 (slight bonus for deference)
- Override: -0.3 (penalty for disagreeing with expert)
- Correct override: +1.5 (large bonus if override improves outcome)
- Reward = actual R-multiple if override changes outcome

**Graduation Criteria**:
- 2000+ training samples
- 400+ validation samples
- 80-95% agreement rate with LLM
- >60% override accuracy when disagreeing
- +10% Sharpe improvement vs LLM-only baseline

**Expected Impact**: +10-15% Sharpe improvement over LLM-only

---

## State Representation

### State Encoders

Each agent has a dedicated state encoder that converts domain objects to fixed-size numpy arrays:

```python
class GateStateEncoder:
    """Encodes candidate + portfolio state → 34-dim vector"""

    def encode(self, candidate, portfolio_state) -> np.ndarray:
        return np.array([
            # Price features (4)
            candidate.features["close"],
            candidate.features["atr"],
            candidate.features["volatility_20"],
            candidate.features["range_pct"],

            # Trend (6)
            candidate.features["ema_20"],
            candidate.features["ema_50"],
            candidate.features["ema_200"],
            candidate.features["adx"],
            candidate.features["di_plus"],
            candidate.features["di_minus"],

            # Momentum (2)
            candidate.features["rsi_14"],
            candidate.features["returns_20"],

            # Range/Breakout (4)
            candidate.features["breakout_distance_atr"],
            candidate.features["pullback_distance_atr"],
            candidate.features["donchian_mid_pct"],
            candidate.features["days_since_breakout"],

            # Volume (3)
            candidate.features["volume"],
            candidate.features["volume_20ma"],
            candidate.features["volume_ratio"],

            # Playbook context (3)
            1.0 if candidate.playbook == "breakout" else 0.0,
            1.0 if candidate.direction == "long" else 0.0,
            candidate.features.get("setup_strength", 0.5),

            # Portfolio state (12)
            portfolio_state["open_positions"],
            portfolio_state["equity"],
            portfolio_state["total_exposure"],
            portfolio_state["available_capital"],
            portfolio_state["drawdown_from_peak"],
            portfolio_state["winning_streak"],
            portfolio_state["losing_streak"],
            portfolio_state["recent_win_rate"],
            portfolio_state["recent_sharpe"],
            portfolio_state["recent_trades"],
            portfolio_state.get("long_exposure", 0.0),
            portfolio_state.get("short_exposure", 0.0),
        ])
```

**Normalization**: All features are normalized to [-1, 1] or [0, 1] ranges using:
- Min-max scaling for bounded features
- Z-score normalization for unbounded features
- NaN handling with sentinel values (-999.0)

---

## Action Spaces

### Gate Agent: Discrete(2)

```python
SKIP = 0  # Don't call LLM (save cost)
PASS = 1  # Pass to LLM for evaluation
```

### Portfolio Agent: Box[0, 1]

```python
size_fraction = action  # Continuous value in [0, 1]
actual_position_size = base_size * size_fraction
```

Action is clipped to [0, 1] to ensure valid position sizes.

### Meta-Learner Agent: Discrete(3)

```python
AGREE = 0            # Accept LLM decision
OVERRIDE_TO_SKIP = 1 # Override "take" to "skip"
OVERRIDE_TO_TAKE = 2 # Override "skip" to "take"
```

---

## Reward Shaping

### Gate Agent Reward

```python
def compute_gate_reward(action, outcome_r_multiple, llm_decision):
    if action == SKIP:
        if outcome_r_multiple < 0:
            return 1.0  # Correctly skipped loser
        else:
            return -1.5  # Missed winner (opportunity cost)
    else:  # PASS
        llm_cost = -0.1  # API call cost
        if llm_decision == "skip":
            return llm_cost  # LLM decided to skip
        else:
            # LLM took trade, reward based on outcome
            return llm_cost + outcome_r_multiple
```

### Portfolio Agent Reward

```python
def compute_portfolio_reward(size_fraction, outcome_r_multiple, portfolio_state):
    # Base reward: R-multiple scaled by position size
    base_reward = outcome_r_multiple * size_fraction

    # Drawdown penalty
    drawdown_pct = portfolio_state["drawdown_from_peak"]
    if drawdown_pct > 0.2:  # 20% threshold
        penalty = -0.5 * (drawdown_pct - 0.2)
        base_reward += penalty

    # Diversification bonus
    if portfolio_state["position_diversity"] > 0.7:
        bonus = 0.2 * portfolio_state["position_diversity"]
        base_reward += bonus

    return base_reward
```

### Meta-Learner Reward

```python
def compute_meta_learner_reward(action, llm_decision, outcome_r_multiple):
    if action == AGREE:
        # Slight bonus for agreeing with expert
        return 0.1 + outcome_r_multiple

    else:  # Override
        override_penalty = -0.3  # Cost of disagreeing

        # Check if override improved outcome
        llm_would_have = "take" if llm_decision == "take" else "skip"
        agent_chose = "take" if action == OVERRIDE_TO_TAKE else "skip"

        if agent_chose == "take" and llm_would_have == "skip":
            # Override to take: reward if positive outcome
            return override_penalty + max(0, outcome_r_multiple) * 1.5

        elif agent_chose == "skip" and llm_would_have == "take":
            # Override to skip: reward if avoiding loss
            return override_penalty + (1.5 if outcome_r_multiple < 0 else -1.0)

        return override_penalty
```

---

## Training Pipeline

### Offline Batch Training

RL agents train **offline** on historical data:

```
Historical Runs → Candidate Cache → Episode Builder → PPO Training → Model Store
                       ↓
                 Outcome Labels
```

**Training Script**:

```bash
# Train gate agent on historical runs
darwin rl train gate \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --output artifacts/rl_models/gate
```

**Training Process**:

1. **Load Historical Data**: Query candidate cache for specified runs
2. **Build Episodes**: Convert (candidate, outcome) pairs to RL episodes
3. **Create Environment**: Wrap episodes in Gymnasium environment
4. **Train PPO**: Run PPO algorithm for specified timesteps
5. **Evaluate**: Periodic evaluation on held-out validation set
6. **Save Model**: Version and save trained model to storage

**Algorithm**: PPO (Proximal Policy Optimization)
- Actor-critic architecture
- Clipped surrogate objective
- Adaptive KL penalty
- Entropy regularization

**Hyperparameters** (from `darwin/rl/training/hyperparameters.py`):
- Gate: LR=1e-4, clip=0.15, entropy=0.01
- Portfolio: LR=3e-4, clip=0.2, entropy=0.05
- Meta-Learner: LR=5e-5, clip=0.1, entropy=0.001

---

## Graduation System

### Graduation Policy

Agents graduate from observe mode to active mode when meeting all criteria:

**5-Check System**:

1. **Sufficient Data**: Meet minimum training and validation sample requirements
2. **Metrics Available**: Performance metrics computed and valid
3. **Meets Threshold**: Validation metric exceeds minimum threshold
4. **Beats Baseline**: Outperforms baseline strategy by required percentage
5. **Stable Performance**: Consistent performance across multiple time windows

**Baseline Strategies**:
- Gate: "pass_all" (pass everything to LLM)
- Portfolio: "equal_weight" (equal position sizes)
- Meta-Learner: "llm_only" (always agree with LLM)

**Graduation Thresholds** (from `darwin/rl/training/hyperparameters.py`):

| Agent | Min Samples | Validation Metric | Min Improvement | Baseline |
|-------|-------------|-------------------|-----------------|----------|
| Gate | 1000 train, 200 val | mean_r ≥ 0.1 | +20% cost savings | pass_all |
| Portfolio | 500 train, 100 val | Sharpe ≥ 1.5 | +10% Sharpe | equal_weight |
| Meta-Learner | 2000 train, 400 val | Sharpe ≥ 1.0 | +10% Sharpe | llm_only |

**Demotion Triggers**:
- Performance degradation (30%+ drop from baseline)
- Excessive alert volume
- Circuit breaker activations
- Failed safety checks

---

## Integration with Runner

### RL System Lifecycle

```python
# 1. Initialize at runner startup
if config.rl and config.rl.enabled:
    rl_system = RLSystem(config.rl, run_id=run_id)

# 2. Make inline predictions during trading loop
for bar in iterate_bars():
    candidates = evaluate_playbooks(bar)

    for candidate in candidates:
        # Gate hook (pre-LLM)
        if rl_system.gate_hook(candidate, portfolio_state) == "skip":
            continue

        llm_response = llm_harness.call(candidate)

        # Meta-learner hook (post-LLM)
        override = rl_system.meta_learner_hook(
            candidate, llm_response, llm_history, portfolio_state
        )
        if override == "skip":
            continue

        if llm_response.decision == "take":
            # Portfolio hook (position sizing)
            size_fraction = rl_system.portfolio_hook(
                candidate, llm_response, portfolio_state
            )

            open_position(candidate, size=base_size * size_fraction)

# 3. Close at run completion
rl_system.close()
```

### Observe vs Active Mode

**Observe Mode** (default for new agents):
```python
# Agent makes prediction but doesn't affect decision
agent_prediction = agent.predict(state)
rl_system.record_decision(agent_name, candidate, agent_prediction, mode="observe")

# Return default action (don't modify behavior)
return None  # or 1.0 for portfolio agent
```

**Active Mode** (after graduation):
```python
# Agent makes prediction and affects decision
agent_prediction = agent.predict(state)
rl_system.record_decision(agent_name, candidate, agent_prediction, mode="active")

# Return agent's decision
return agent_prediction
```

---

## Data Flow

### Training Data Flow

```
┌─────────────────┐
│ Historical Runs │
│ (runner output) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Candidate Cache │────▶│ Outcome Labels   │
│ (opportunities) │     │ (R-multiples)    │
└────────┬────────┘     └─────────┬────────┘
         │                        │
         └───────────┬────────────┘
                     ▼
         ┌───────────────────────┐
         │ Episode Builder       │
         │ (state, action, reward)│
         └──────────┬────────────┘
                    ▼
         ┌───────────────────────┐
         │ PPO Training          │
         │ (offline, async)      │
         └──────────┬────────────┘
                    ▼
         ┌───────────────────────┐
         │ Model Store           │
         │ (versioned models)    │
         └───────────────────────┘
```

### Inference Data Flow

```
┌─────────────┐
│ Live Bar    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Feature Pipeline│
└──────┬──────────┘
       │
       ▼
┌─────────────────┐     ┌──────────────────┐
│ Playbook Engine │────▶│ Gate Agent       │
│ (candidates)    │     │ (inference ~1ms) │
└─────────────────┘     └────────┬─────────┘
                                 │ skip or pass?
                                 ▼
                      ┌──────────────────┐
                      │ LLM Harness      │
                      │ (~500ms)         │
                      └────────┬─────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Meta-Learner Agent   │
                    │ (inference ~1ms)     │
                    └────────┬─────────────┘
                             │ agree or override?
                             ▼
                  ┌──────────────────────┐
                  │ Portfolio Agent      │
                  │ (inference ~1ms)     │
                  └────────┬─────────────┘
                           │ position size
                           ▼
                ┌──────────────────────┐
                │ Position Manager     │
                │ (open position)      │
                └──────────────────────┘
```

### Decision Recording

All agent decisions are recorded to AgentStateSQLite:

```sql
CREATE TABLE agent_decisions (
    agent_name TEXT,
    candidate_id TEXT,
    run_id TEXT,
    timestamp TEXT,
    state_hash TEXT,
    action INTEGER,
    mode TEXT,  -- 'observe' or 'active'
    model_version TEXT,
    outcome_r_multiple REAL,  -- Updated when outcome known
    outcome_pnl_usd REAL
);
```

This enables:
- Audit trail of all agent decisions
- Graduation evaluation (performance over time)
- Retraining with new data
- Debugging and analysis

---

## Performance Monitoring

### Safety Mechanisms

**Circuit Breakers**:
- Threshold: 5 consecutive failures
- Timeout: 5 minutes before retry
- Automatic reset on success

**Override Rate Limiting**:
- Max override rate: 20% (configurable)
- Window: 60 minutes
- Applies to meta-learner only

**Performance Fallback**:
- Monitor: 7-day rolling performance
- Threshold: mean R-multiple < -0.5
- Action: Auto-demote to observe mode

### Monitoring Alerts

**Alert Types**:
- Performance degradation (30%+ drop)
- Excessive overrides (>20% rate)
- Low decision rate (<1 per day)
- High error rate (>5% failures)

**Alert Response**:
1. Investigate recent decisions
2. Check for market regime changes
3. Evaluate model performance
4. Demote to observe if needed
5. Retrain with recent data

---

## Summary

Darwin's RL system provides a production-ready framework for gradually transitioning from LLM-based to learned trading decisions:

- **Three specialized agents** optimize different parts of the decision pipeline
- **Offline training** on historical data with PPO algorithm
- **Graduation policies** ensure only high-performing agents go active
- **Safety mechanisms** prevent degradation and provide fallback
- **Full auditability** with decision recording and performance tracking

The system is designed for **incremental deployment**: start with all agents in observe mode, collect data, train models, validate performance, and gradually activate agents as they prove their value.
