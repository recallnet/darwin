# Darwin RL System

Complete reinforcement learning system for adaptive trading strategy optimization using PPO (Proximal Policy Optimization).

## Overview

The Darwin RL system implements three specialized agents that learn from trading experience to improve decision-making:

1. **Gate Agent**: Filters candidates before sending to LLM (reduces API costs)
2. **Portfolio Agent**: Optimizes position sizing based on setup quality
3. **Meta-Learner Agent**: Learns when to override LLM decisions

**Training Algorithm**: PPO (Proximal Policy Optimization) from stable-baselines3
- True reinforcement learning (not supervised learning)
- Can discover strategies beyond training data
- Learns optimal policies through trial-and-error

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Darwin Backtest Runner                   │
│                                                              │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Gate Agent   │→│  LLM Judge   │→│ Portfolio Agent │  │
│  └───────────────┘  └──────────────┘  └─────────────────┘  │
│                           ↓                                  │
│                  ┌──────────────────┐                        │
│                  │ Meta-Learner     │                        │
│                  │ (Override Logic) │                        │
│                  └──────────────────┘                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
         ┌─────────────────────────────────────┐
         │      Agent State Database           │
         │  (Decisions + Outcomes + States)    │
         └─────────────────────────────────────┘
                           ↓
         ┌─────────────────────────────────────┐
         │      Training Pipeline              │
         │  (Behavioural Cloning + Evaluation) │
         └─────────────────────────────────────┘
                           ↓
         ┌─────────────────────────────────────┐
         │     Graduation & Monitoring         │
         │  (Auto-graduate + Auto-rollback)    │
         └─────────────────────────────────────┘
```

## Agent Lifecycle

Each agent progresses through three modes:

1. **Observe Mode** (Initial State)
   - Agent collects data but doesn't make decisions
   - LLM baseline handles all decisions
   - Records candidate features, LLM responses, and outcomes
   - Transitions to training when minimum data collected

2. **Training Phase**
   - Uses behavioural cloning (supervised learning) on successful past decisions
   - PyTorch neural networks trained on collected data
   - Evaluates performance against graduation thresholds
   - Auto-graduates when performance consistently beats baseline

3. **Active Mode** (Graduated)
   - Agent makes real decisions during backtests
   - Continuously monitored for performance degradation
   - Auto-rolls back to observe mode if performance drops >25%

## Neural Network Architectures

All agents use PPO's MlpPolicy (multi-layer perceptron policy network):

### Gate Agent
- **Input**: 34-dimensional state (candidate features)
- **Output**: Binary action space (0=skip, 1=pass)
- **PPO Network**: Automatic architecture from stable-baselines3
- **Action Type**: Discrete(2)

### Portfolio Agent
- **Input**: 30-dimensional state (candidate + LLM + portfolio context)
- **Output**: Continuous action [0.0, 1.0] for position size
- **PPO Network**: Automatic architecture from stable-baselines3
- **Action Type**: Box(0.0, 1.0, shape=(1,))

### Meta-Learner Agent
- **Input**: 38-dimensional state (candidate + LLM + history + portfolio)
- **Output**: 3-class action space (0=agree, 1=override_skip, 2=override_take)
- **PPO Network**: Automatic architecture from stable-baselines3
- **Action Type**: Discrete(3)

## Training with PPO

### Replay Environments

PPO learns by replaying historical decisions in a custom Gymnasium environment:

```python
# Each decision becomes a step in the environment
observation = decision["state"]  # State features
reward = calculate_reward(decision["action"], decision["r_multiple"])
```

### Reward Functions

**Gate Agent**:
- Pass on winner: +R_multiple (reward actual return)
- Pass on loser: -|R_multiple| (penalize loss)
- Skip winner: -0.5 (missed opportunity)
- Skip loser: +0.1 (avoided loss)

**Portfolio Agent**:
- Reward = position_size * R_multiple
- Encourages large sizes on winners, small sizes on losers
- Small penalty for extreme sizes (>0.9) to encourage diversification

**Meta-Learner**:
- Agree with LLM: -0.1 (small penalty to encourage learning overrides)
- Override to skip on loser: +0.5 (correct override)
- Override to skip on winner: -R_multiple (incorrect)
- Override to take on winner: +R_multiple (correct)
- Override to take on loser: -0.5 (incorrect)

### PPO Hyperparameters
- **Learning Rate**: 3e-4
- **n_steps**: 2048 (rollout buffer size)
- **Batch Size**: 64
- **n_epochs**: 10 (epochs per update)
- **Gamma**: 0.99 (discount factor)
- **GAE Lambda**: 0.95 (advantage estimation)
- **Clip Range**: 0.2 (PPO clipping)
- **Entropy Coef**: 0.01 for discrete actions, 0.0 for continuous
- **Total Timesteps**: min(len(decisions) * 100, 100000)

## Graduation System

Agents must meet strict criteria before graduating to active mode:

### Gate Agent Thresholds
```yaml
min_candidates_seen: 500           # Minimum data samples
min_training_samples: 200          # Samples with outcomes
min_validation_accuracy: 0.55      # Better than random
baseline_improvement_pct: 10       # 10% better than pass-all baseline
stability_windows: 3               # Consistent across 3 time windows
```

### Portfolio Agent Thresholds
```yaml
min_candidates_seen: 300
min_training_samples: 150
min_sharpe_ratio: 0.3              # Minimum Sharpe
baseline_improvement_pct: 15       # 15% better than equal-weight
stability_windows: 3
```

### Meta-Learner Agent Thresholds
```yaml
min_candidates_seen: 400
min_training_samples: 200
min_override_accuracy: 0.60        # Override decisions must be profitable
baseline_improvement_pct: 10       # 10% better than LLM-only
stability_windows: 3
```

## Degradation Monitoring

Active agents are continuously monitored for performance degradation:

```python
# Configuration
lookback_window: 100              # Recent decisions to monitor
degradation_threshold_pct: 25.0   # Performance drop % to trigger rollback
min_samples_for_check: 50         # Minimum samples before checking

# Automatic Actions
if performance_drop >= 25%:
    agent.mode = "observe"        # Roll back to observe mode
    agent.status = "degraded"     # Mark as degraded
    # Requires retraining and re-graduation
```

Monitoring occurs every 100 bars during backtest execution.

## Model Persistence

Models are saved as stable-baselines3 ZIP archives:

```python
# Save
model.save("path/to/model.zip")

# Load
from stable_baselines3 import PPO
model = PPO.load("path/to/model.zip")

# Predict
action, _states = model.predict(observation, deterministic=True)
```

**Model Directory Structure**:
```
artifacts/
  run_xyz/
    models/
      gate/
        model.zip        # PPO model with policy & value networks
      portfolio/
        model.zip
      meta_learner/
        model.zip
```

## Configuration

Enable RL in your run config:

```yaml
rl:
  enabled: true
  agent_state_db: "artifacts/run_xyz/agent_state.sqlite"
  models_dir: "artifacts/run_xyz/models"

  gate_agent:
    enabled: true
    mode: "observe"  # Start in observe mode
    graduation_thresholds:
      min_candidates_seen: 500
      min_training_samples: 200
      min_validation_accuracy: 0.55
      baseline_type: "pass_all"
      baseline_improvement_pct: 10
      stability_windows: 3

  portfolio_agent:
    enabled: true
    mode: "observe"
    graduation_thresholds:
      min_candidates_seen: 300
      min_training_samples: 150
      min_sharpe_ratio: 0.3
      baseline_type: "equal_weight"
      baseline_improvement_pct: 15
      stability_windows: 3

  meta_learner_agent:
    enabled: true
    mode: "observe"
    graduation_thresholds:
      min_candidates_seen: 400
      min_training_samples: 200
      min_override_accuracy: 0.60
      baseline_type: "llm_only"
      baseline_improvement_pct: 10
      stability_windows: 3
```

## Usage

### Running with RL

```bash
# Run backtest with RL enabled
darwin run path/to/config.yaml

# The runner will:
# 1. Initialize agents in observe mode
# 2. Collect data during backtest
# 3. Check for degradation every 100 bars (if active)
# 4. Save agent state to SQLite database
```

### Training Agents

```bash
# Train specific agent
python -m darwin.rl.training.train_agent \
    --config path/to/config.yaml \
    --agent gate

# Will:
# 1. Load collected data from agent_state.sqlite
# 2. Train neural network using behavioural cloning
# 3. Evaluate against graduation thresholds
# 4. Save model if graduated
# 5. Update agent status in config
```

### Monitoring Status

```python
from darwin.rl.storage.agent_state import AgentStateSQLite

# Check agent status
db = AgentStateSQLite("artifacts/run_xyz/agent_state.sqlite")

# View decision counts
gate_decisions = db.get_decision_count("gate")
portfolio_decisions = db.get_decision_count("portfolio")

# View decisions with outcomes (for training)
gate_training_data = db.get_decisions_with_outcomes("gate")
```

## File Structure

```
darwin/rl/
├── agents/
│   ├── base.py                    # Base agent class with PPO model loading
│   ├── gate_agent.py              # Gate agent implementation
│   ├── portfolio_agent.py         # Portfolio agent implementation
│   └── meta_learner_agent.py      # Meta-learner agent implementation
├── training/
│   ├── environments.py            # Gymnasium replay environments for PPO
│   ├── algorithms.py              # PPO training algorithms
│   ├── train_agent.py             # Training pipeline and CLI
│   └── hyperparameters.py         # Training hyperparameter configs
├── graduation/
│   ├── evaluator.py               # Graduation evaluation logic
│   ├── policy.py                  # Graduation policy enforcement
│   ├── metrics.py                 # Metric calculations
│   └── baselines.py               # Baseline implementations
├── monitoring/
│   └── degradation.py             # Degradation detection and rollback
├── storage/
│   └── agent_state.py             # SQLite database for agent state
├── integration/
│   └── runner_hooks.py            # Runner integration hooks
├── utils/
│   └── state_encoding.py          # State encoders for each agent
└── schemas/
    └── rl_config.py               # Configuration schemas
```

## Key Implementation Details

### State Encoding

Each agent encodes different information:

**Gate Agent** (34 dimensions):
- Candidate features (playbook, direction, confidence, etc.)
- Technical indicators
- Market context

**Portfolio Agent** (30 dimensions):
- Candidate features
- LLM confidence and reasoning quality
- Portfolio exposure and risk metrics
- Position correlation

**Meta-Learner Agent** (38 dimensions):
- Candidate features
- LLM decision and confidence
- Rolling LLM performance history (30-day)
- Portfolio state

### Decision Recording

Every agent decision is recorded with:
```python
{
    "candidate_id": "ABC_20240101_LONG",
    "timestamp": 1704067200,
    "state": [0.1, 0.5, ...],          # Encoded state vector
    "action": 1,                        # Agent action
    "r_multiple": 2.5,                  # Outcome (if available)
    "exit_reason": "target",            # Trade result
    "agent_mode": "observe"             # Mode at decision time
}
```

### Performance Metrics

**Gate Agent**:
- Pass rate (% candidates passed to LLM)
- Profitable pass rate (% passed candidates that won)
- Cost savings (% reduction in LLM calls)

**Portfolio Agent**:
- Sharpe ratio (risk-adjusted returns)
- Mean R-multiple
- Position size distribution

**Meta-Learner**:
- Override rate (% times LLM overridden)
- Override accuracy (% correct overrides)
- Impact on overall performance

## Safety Mechanisms

### Circuit Breakers
- Agents automatically roll back if performance degrades >25%
- Minimum sample requirements prevent premature graduation
- Stability windows ensure consistent performance

### Fallback Strategy
- If agent fails to load, system falls back to LLM-only baseline
- Graceful degradation ensures trading continues

### Monitoring
- Continuous performance tracking
- Alert generation for degradation
- Detailed logging of all decisions and outcomes

## Development Workflow

### Adding a New Agent

1. **Create Network Architecture** (`models/networks.py`)
```python
class NewAgentNetwork(nn.Module):
    def __init__(self, state_dim: int, hidden_dims: list):
        # Define layers
        pass
```

2. **Create Training Algorithm** (`training/algorithms.py`)
```python
class NewAgentTraining(AgentTrainingAlgorithm):
    def prepare_data(self, decisions):
        # Prepare training data
        pass

    def train(self, decisions):
        # Training loop
        pass
```

3. **Create Agent Class** (`agents/new_agent.py`)
```python
class NewAgent(RLAgent):
    def predict(self, *args):
        # Prediction logic
        pass
```

4. **Add State Encoder** (`utils/state_encoding.py`)
```python
class NewAgentStateEncoder:
    def encode(self, candidate, context):
        # Encode state
        pass
```

5. **Add Configuration** (`schemas/rl_config.py`)
```python
new_agent: Optional[AgentConfigV1] = None
```

## Testing

```bash
# Run unit tests
pytest darwin/rl/tests/

# Test specific components
pytest darwin/rl/tests/test_agents.py
pytest darwin/rl/tests/test_training.py
pytest darwin/rl/tests/test_graduation.py
```

## Performance Tuning

### Network Architecture
- Adjust hidden layer sizes for model capacity
- Tune dropout rate to prevent overfitting
- Experiment with activation functions

### Training Parameters
- Increase epochs for more complex patterns
- Adjust batch size based on data volume
- Tune learning rate for convergence

### Graduation Thresholds
- Relax thresholds for faster deployment
- Tighten thresholds for higher quality
- Adjust stability windows for reliability

## Troubleshooting

### Agent Not Graduating
- Check if minimum data requirements met
- Review graduation metrics in training logs
- Lower graduation thresholds if too strict

### Performance Degradation
- Review recent decisions in agent_state.sqlite
- Check for market regime changes
- Retrain with more recent data

### Model Not Loading
- Verify PyTorch is installed: `pip install torch`
- Check model file exists at specified path
- Verify model architecture matches saved checkpoint

## Dependencies

```bash
# Install RL dependencies
pip install 'darwin[rl]'

# Or manually:
pip install stable-baselines3[extra]>=2.0.0
pip install gymnasium>=0.29.0
pip install torch>=2.0.0
pip install tensorboard>=2.14.0

# Already in Darwin
# - pydantic (for config schemas)
# - sqlalchemy (for storage)
# - numpy (for arrays)
```

## Future Enhancements

- [ ] Add ensemble methods (combine multiple PPO models)
- [ ] Implement online learning (continue training during backtests)
- [ ] Add model versioning and A/B testing
- [ ] Experiment with other RL algorithms (SAC, TD3 for continuous actions)
- [ ] Add explainability (attention mechanisms, SHAP values)
- [ ] Implement multi-agent coordination (agents learn to cooperate)
- [ ] Add transfer learning across symbols/timeframes
- [ ] Implement prioritized experience replay
- [ ] Add curriculum learning (gradually increase difficulty)

## Documentation

### Quick Start Guides

- **[FULL_LOOP_CHECKLIST.md](FULL_LOOP_CHECKLIST.md)** - Complete end-to-end workflow walkthrough
  - Data collection in observe mode
  - Training with PPO
  - Graduation evaluation
  - Deployment to active mode
  - Monitoring and auto-rollback
  - Multi-run training
  - Verification checklists

- **[TRAINING_BEST_PRACTICES.md](TRAINING_BEST_PRACTICES.md)** - ⭐ Essential reading for training agents
  - Single-run vs multi-run training decision matrix
  - When to retrain on same data vs diverse data
  - Overfitting risks and mitigation strategies
  - Data diversity requirements
  - Recommended 4-phase workflow
  - Common mistakes to avoid
  - Quick command reference

### Module Documentation

See individual module docstrings for detailed API documentation:
- `agents/` - Agent implementations (gate, portfolio, meta-learner)
- `training/` - Training algorithms (PPO, multi-run training)
- `graduation/` - Graduation evaluation logic
- `monitoring/` - Performance tracking and alerts
- `storage/` - SQLite storage for decisions and states
- `utils/` - State encoding, config updates, helpers

## References

- **PPO**: Proximal Policy Optimization (Schulman et al., 2017)
- **stable-baselines3**: High-quality RL implementations
- **Gymnasium**: Standard RL environment API
- **Reward Shaping**: Designing reward functions for RL
- **State Encoding**: Feature engineering for RL

## License

Part of the Darwin trading system.
