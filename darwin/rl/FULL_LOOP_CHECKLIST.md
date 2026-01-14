# Darwin RL System - Full Loop Checklist

This document walks through the complete end-to-end RL workflow to verify everything is functional.

## Complete RL Loop Overview

```
1. COLLECT DATA (Observe Mode)
   ↓
2. TRAIN WITH PPO
   ↓
3. EVALUATE GRADUATION
   ↓
4. DEPLOY (Active Mode)
   ↓
5. MONITOR PERFORMANCE
   ↓
6. AUTO-ROLLBACK IF DEGRADED
   ↓
   (Return to step 1)
```

## Prerequisites

```bash
# Install RL dependencies
pip install 'darwin[rl]'

# Verify installation
python3 -c "import stable_baselines3; import gymnasium; print('✓ RL dependencies installed')"
```

## Phase 1: Data Collection (Observe Mode)

### Step 1.1: Create Run Config

Create `config.yaml` with RL enabled:

```yaml
rl:
  enabled: true
  agent_state_db: "artifacts/my_run/agent_state.sqlite"
  models_dir: "artifacts/my_run/models"

  gate_agent:
    enabled: true
    mode: "observe"  # Start in observe mode
    model_path: null  # No model yet
    current_status: "training"
    model_version: "v1"
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
    model_path: null
    current_status: "training"
    model_version: "v1"
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
    model_path: null
    current_status: "training"
    model_version: "v1"
    graduation_thresholds:
      min_candidates_seen: 400
      min_training_samples: 200
      min_override_accuracy: 0.60
      baseline_type: "llm_only"
      baseline_improvement_pct: 10
      stability_windows: 3
```

### Step 1.2: Run Backtest in Observe Mode

```bash
# Run backtest - agents collect data but don't make decisions
darwin run config.yaml
```

**What happens**:
- ✅ Agents initialized in observe mode
- ✅ All candidates sent to LLM (gate agent observes but doesn't filter)
- ✅ All positions use default sizing (portfolio agent observes but doesn't adjust)
- ✅ LLM decisions are final (meta-learner observes but doesn't override)
- ✅ All decisions + outcomes recorded to `agent_state.sqlite`

**Verify data collection**:

```python
from darwin.rl.storage.agent_state import AgentStateSQLite

db = AgentStateSQLite("artifacts/my_run/agent_state.sqlite")
print(f"Gate decisions: {db.get_decision_count('gate')}")
print(f"Portfolio decisions: {db.get_decision_count('portfolio')}")
print(f"Meta-learner decisions: {db.get_decision_count('meta_learner')}")
```

**Expected output**:
```
Gate decisions: 523
Portfolio decisions: 156
Meta-learner decisions: 156
```

## Phase 2: Training with PPO

### Step 2.1: Train Gate Agent

```bash
# Train gate agent
python -m darwin.rl.training.train_agent \
    --config config.yaml \
    --agent gate
```

**What happens**:
1. ✅ Loads historical decisions from `agent_state.sqlite`
2. ✅ Checks minimum data requirements (500 candidates, 200 with outcomes)
3. ✅ Creates PPO replay environment
4. ✅ Trains PPO model (learns optimal skip/pass policy)
5. ✅ Evaluates graduation criteria
6. ✅ Saves model to `artifacts/my_run/models/gate/model.zip`
7. ✅ Updates `model_path` in config (in-memory)
8. ✅ Updates status to "graduated" if criteria met

**Expected output**:
```
Training gate agent with PPO...
  Training samples: 234
  Total timesteps: 23400
Starting PPO training...
  Step 2048: mean_reward=-5.42
  Step 4096: mean_reward=-2.15
  ...
PPO training completed!

GRADUATION EVALUATION RESULTS
================================================================================
✅ Checks Passed:
   Minimum candidates seen: 523 >= 500
   Minimum training samples: 234 >= 200
   Validation accuracy: 0.58 >= 0.55
   Baseline improvement: 12.3% >= 10%
   Stability check: passed (3/3 windows)

🎓 Agent 'gate' is READY TO GRADUATE!

✅ Next steps:
   1. Model saved to: artifacts/my_run/models/gate/model.zip
   2. Agent status: graduated
   3. To activate agent, update config:
      rl.gate_agent.mode = 'active'
```

### Step 2.2: Update Config for Activation

After graduation, update `config.yaml` to activate the agent:

```yaml
gate_agent:
  enabled: true
  mode: "active"  # Changed from "observe"
  model_path: "artifacts/my_run/models/gate/model.zip"  # Set by training
  current_status: "graduated"
```

### Step 2.3: Train Other Agents

Repeat for portfolio and meta-learner:

```bash
python -m darwin.rl.training.train_agent --config config.yaml --agent portfolio
python -m darwin.rl.training.train_agent --config config.yaml --agent meta_learner
```

## Phase 3: Deploy Active Agents

### Step 3.1: Run Backtest with Active Agents

```bash
# Run with active agents
darwin run config.yaml
```

**What happens**:
- ✅ Gate agent loads from `model.zip`
- ✅ Gate agent filters candidates (some skipped before LLM)
- ✅ Portfolio agent adjusts position sizes
- ✅ Meta-learner overrides LLM decisions when confident
- ✅ Degradation monitoring checks every 100 bars
- ✅ Decisions continue to be recorded

**Verify active agents**:

Check logs for:
```
INFO:darwin.rl.integration.runner_hooks:Loaded gate agent model from artifacts/my_run/models/gate/model.zip (mode: active)
DEBUG:darwin.rl.integration.runner_hooks:Gate agent (active): skipping candidate BTC_20240115_LONG
DEBUG:darwin.rl.integration.runner_hooks:Portfolio agent (active): candidate BTC_20240116_LONG -> size fraction 0.65
```

## Phase 4: Performance Monitoring

### Step 4.1: Automatic Degradation Detection

**What happens automatically**:
- Every 100 bars, degradation monitor checks active agents
- Compares recent performance (last 100 decisions) to graduation baseline
- If performance drops >25%, triggers auto-rollback

**Degradation detection**:
```python
# In experiment.py, called every 100 bars
if bars_processed % 100 == 0:
    self._check_agent_degradation()
```

**What you'll see if degradation detected**:
```
ERROR:darwin.runner.experiment:⚠️  DEGRADATION DETECTED for agent 'gate'
ERROR:darwin.runner.experiment:   Performance dropped 27.5% (graduation: 0.580 → current: 0.420)
ERROR:darwin.runner.experiment:   AUTOMATICALLY ROLLING BACK TO OBSERVE MODE
WARNING:darwin.rl.monitoring.degradation:🔙 Rolling back agent 'gate' to observe mode
WARNING:darwin.rl.monitoring.degradation:   Status: active → observe
WARNING:darwin.rl.monitoring.degradation:   Agent status: graduated → degraded
```

### Step 4.2: Manual Performance Checks

Query agent performance:

```python
from darwin.rl.storage.agent_state import AgentStateSQLite

db = AgentStateSQLite("artifacts/my_run/agent_state.sqlite")

# Get recent decisions with outcomes
gate_decisions = db.get_decisions_with_outcomes("gate")[-100:]

# Calculate win rate
wins = sum(1 for d in gate_decisions if d["r_multiple"] > 0)
win_rate = wins / len(gate_decisions)
print(f"Gate agent win rate (last 100): {win_rate:.2%}")
```

## Phase 5: Continuous Improvement Loop

### Step 5.1: Retrain After Degradation

If an agent degrades and rolls back to observe mode:

1. **Collect more data** (agent continues in observe mode)
2. **Retrain with updated data**:
   ```bash
   python -m darwin.rl.training.train_agent --config config.yaml --agent gate
   ```
3. **Evaluate graduation again**
4. **Reactivate if graduated**

### Step 5.2: Periodic Retraining

Even if agents aren't degrading, retrain periodically with new data:

```bash
# Every N runs or every M days
python -m darwin.rl.training.train_agent --config config.yaml --agent gate
python -m darwin.rl.training.train_agent --config config.yaml --agent portfolio
python -m darwin.rl.training.train_agent --config config.yaml --agent meta_learner
```

This keeps agents adapted to current market conditions.

### Step 5.3: Multi-Run Training

For better generalization, train agents on data from multiple runs:

```bash
# Train on data from multiple backtests
darwin train-multi-run gate \
    --db-paths artifacts/run_001/agent_state.sqlite \
    --db-paths artifacts/run_002/agent_state.sqlite \
    --db-paths artifacts/run_003/agent_state.sqlite \
    --output artifacts/models/gate/model_multi.zip \
    --tensorboard-log artifacts/tensorboard

# Or use glob patterns (shell expansion)
darwin train-multi-run portfolio \
    --db-paths artifacts/run_*/agent_state.sqlite \
    --output artifacts/models/portfolio/model_multi.zip
```

**Benefits of multi-run training**:
- **More diverse data**: Learns from different market conditions, symbols, timeframes
- **Larger dataset**: More samples for better generalization
- **Reduced overfitting**: Less likely to memorize single run's patterns
- **Better performance**: Improved accuracy on unseen data

**When to use multi-run training**:
- After collecting data from 5+ backtest runs
- When single-run performance plateaus
- Before deploying to production
- When market conditions change significantly

**Example workflow**:
```bash
# 1. Run multiple backtests with different configs
darwin run config_btc.yaml     # BTC only
darwin run config_eth.yaml     # ETH only
darwin run config_mixed.yaml   # Mixed portfolio
darwin run config_2023.yaml    # 2023 data
darwin run config_2024.yaml    # 2024 data

# 2. Train on combined data from all runs
darwin train-multi-run gate \
    --db-paths artifacts/*/agent_state.sqlite \
    --output artifacts/models/gate/model_v2.zip \
    --timesteps 200000

# 3. Update config with new model
# Edit config.yaml:
#   rl.gate_agent.model_path = "artifacts/models/gate/model_v2.zip"
#   rl.gate_agent.model_version = "v2"

# 4. Run with new model
darwin run config.yaml
```

### Step 5.4: Training Best Practices - Single Run vs Multi-Run

**IMPORTANT**: Understanding when to train on the same run multiple times vs using multi-run training is critical for building robust agents.

#### Key Concept: PPO Trains From Scratch

Each time you call `train-agent` or `train-multi-run`, it creates a **NEW model from scratch**. The training doesn't continue from a previous model - it starts fresh with the data in the database(s).

#### Approach 1: Train on Same Run Multiple Times

**Use this approach during development/iteration:**

```bash
# Run backtest, accumulate data in one database
darwin run config.yaml  # 100 bars, 50 decisions
# ... collect more data ...
darwin run config.yaml --resume  # 100 more bars, 100 total decisions
# ... collect more data ...
darwin run config.yaml --resume  # 100 more bars, 150 total decisions

# Train once when you have enough data (500+ decisions)
darwin train-agent config.yaml gate
```

**When to use:**
- ✅ Early development and rapid iteration
- ✅ Long continuous backtests (accumulating data over time)
- ✅ Haven't reached graduation thresholds yet
- ✅ Testing the training pipeline

**Risks:**
- ❌ **Overfitting to specific market regime** (e.g., 2024 bull market only)
- ❌ **Symbol-specific memorization** (works on BTC, fails on ETH)
- ❌ **Playbook-specific patterns** (learns tricks for one strategy only)
- ❌ **LLM quirks** (adapts to biases in LLM's decisions during that period)
- ❌ **Poor generalization** to unseen market conditions

**Example of overfitting:**
```
Scenario: You train gate agent on BTC data from Jan-Mar 2024 (bull market)
Result: Agent learns to be aggressive (high pass rate) because most trades won
Problem: When market shifts to consolidation/bear, agent still passes too many
Outcome: Performance degrades, auto-rollback triggers, back to observe mode
```

#### Approach 2: Multi-Run Training (Recommended for Production)

**Use this approach for production-quality models:**

```bash
# Run diverse backtests with different characteristics
darwin run config_btc_2023.yaml      # BTC, 2023 (bear/recovery)
darwin run config_btc_2024.yaml      # BTC, 2024 (bull market)
darwin run config_eth_2023.yaml      # ETH, 2023 (different asset)
darwin run config_mixed_2024.yaml    # Mixed portfolio
darwin run config_highvol.yaml       # High volatility period

# Train on combined data from all runs
darwin train-multi-run gate \
    --db-paths artifacts/run_*/agent_state.sqlite \
    --output models/gate/production_v1.zip \
    --timesteps 200000
```

**When to use:**
- ✅ Deploying agents to production/active mode
- ✅ Have 5+ completed backtests with diverse conditions
- ✅ Want robust performance across market regimes
- ✅ After agent degradation (retrain with old + new data)
- ✅ Adapting to new market conditions

**Benefits:**
- ✅ **Diverse training data** from different market conditions
- ✅ **Better generalization** to unseen scenarios
- ✅ **Reduced overfitting** to specific patterns
- ✅ **More robust** to market regime changes
- ✅ **Larger dataset** improves learning quality

#### Recommended Workflow

**Phase 1: Development (0-2 weeks)**
```bash
# Quick iteration with same config
darwin run config.yaml           # Run 1: 200 decisions
darwin train-agent config.yaml gate  # Quick test

# Collect more data
darwin run config.yaml --resume  # Run 1 continued: 500 decisions
darwin train-agent config.yaml gate  # Train again with more data

# Test graduation thresholds, tune hyperparameters
```

**Phase 2: Diversification (2-4 weeks)**
```bash
# Run diverse backtests
darwin run config_btc.yaml       # Run 2: Different symbol
darwin run config_2023.yaml      # Run 3: Different period
darwin run config_highvol.yaml   # Run 4: Different market regime

# Each run collects its own data in separate agent_state.sqlite
```

**Phase 3: Production Training (Week 4+)**
```bash
# Multi-run training for production model
darwin train-multi-run gate \
    --db-paths artifacts/run_1/agent_state.sqlite \
    --db-paths artifacts/run_2/agent_state.sqlite \
    --db-paths artifacts/run_3/agent_state.sqlite \
    --db-paths artifacts/run_4/agent_state.sqlite \
    --output models/gate/production_v1.zip \
    --timesteps 200000

# Update config to use production model
# Edit config.yaml:
#   rl.gate_agent.model_path = "models/gate/production_v1.zip"
#   rl.gate_agent.model_version = "production_v1"
#   rl.gate_agent.mode = "active"

# Deploy to active mode
darwin run config.yaml
```

**Phase 4: Maintenance (Ongoing)**
```bash
# If agent degrades or market conditions change significantly:
# 1. Collect new data (agent auto-rolled back to observe)
darwin run config.yaml  # Collects data in degraded conditions

# 2. Retrain with old + new data (prevents forgetting)
darwin train-multi-run gate \
    --db-paths artifacts/degraded_run/agent_state.sqlite \
    --db-paths artifacts/old_run_*/agent_state.sqlite \
    --output models/gate/recovery_v2.zip

# 3. Redeploy
```

#### Data Diversity Checklist

When collecting data for multi-run training, ensure diversity across:

- **Market Regimes**: Bull, bear, consolidation, high volatility, low volatility
- **Time Periods**: Different months/quarters/years
- **Symbols**: BTC, ETH, SOL, and other assets (if applicable)
- **Playbooks**: Different entry strategies (if using multiple)
- **LLM Decisions**: Data should span multiple LLM "moods" or decision patterns

**Bad example (low diversity):**
```bash
# All runs from same 2-week period, same symbol, same market condition
darwin run config_btc_week1.yaml
darwin run config_btc_week2.yaml
darwin run config_btc_week3.yaml
# Result: Model still overfits to that specific market regime
```

**Good example (high diversity):**
```bash
# Diverse conditions
darwin run config_btc_jan2023.yaml   # Bear market recovery
darwin run config_btc_jul2023.yaml   # Consolidation
darwin run config_btc_jan2024.yaml   # Bull market
darwin run config_eth_2024.yaml      # Different asset
darwin run config_mixed_2024.yaml    # Multi-asset portfolio
# Result: Model generalizes well to new conditions
```

#### Summary: When to Use Each Approach

| Scenario | Recommended Approach | Rationale |
|----------|---------------------|-----------|
| **Early development** | Train on same run | Fast iteration, testing pipeline |
| **Reaching graduation** | Train on same run | Need enough data to meet thresholds |
| **Production deployment** | Multi-run training | Robust, generalizable agents |
| **After degradation** | Multi-run training (old + new) | Adapt while retaining knowledge |
| **Market regime change** | Multi-run training (diverse periods) | Learn new patterns without forgetting |
| **Testing new playbook** | Train on same run | Validate playbook effectiveness |
| **Production model update** | Multi-run training (all history) | Best possible generalization |

#### Key Takeaway

**The multi-run training feature exists specifically to solve the overfitting problem.** Use it for any model that will make real decisions in active mode. Single-run training is fine for development, but production agents should always be trained on diverse data.

## Verification Checklist

Use this checklist to verify each component:

### Data Collection ✓
- [ ] Config has `rl.enabled: true`
- [ ] Agents enabled with `mode: "observe"`
- [ ] Backtest runs successfully
- [ ] `agent_state.sqlite` created
- [ ] Decisions recorded (check with SQL query)
- [ ] Outcomes updated after trades close

### Training ✓
- [ ] PPO dependencies installed (`stable-baselines3`, `gymnasium`)
- [ ] Training command runs without errors
- [ ] Minimum data requirements met
- [ ] Model saved to `models/{agent_name}/model.zip`
- [ ] Graduation criteria evaluated
- [ ] Model path updated in config

### Deployment ✓
- [ ] Config updated with `mode: "active"`
- [ ] `model_path` points to trained model
- [ ] Agent loads successfully (check logs)
- [ ] Agent makes predictions (check debug logs)
- [ ] Predictions affect backtest behavior

### Monitoring ✓
- [ ] Degradation monitor initialized
- [ ] Checks run every 100 bars
- [ ] Performance metrics calculated correctly
- [ ] Rollback triggers when performance drops >25%
- [ ] Agent mode changes to "observe" after rollback
- [ ] Agent status changes to "degraded"

### Full Loop ✓
- [ ] Can run multiple cycles: observe → train → deploy → monitor → rollback → retrain
- [ ] Data accumulates across runs
- [ ] Agents improve over time
- [ ] System recovers from degradation automatically

## Troubleshooting

### Issue: "Not enough training samples"

**Cause**: Not enough decisions with outcomes recorded

**Solution**:
- Run more backtests in observe mode
- Lower `min_training_samples` threshold
- Check that outcomes are being recorded correctly

### Issue: "Agent doesn't graduate"

**Cause**: Performance doesn't meet thresholds

**Solutions**:
- Review graduation criteria (may be too strict)
- Check baseline calculation
- Examine training data quality
- Try different PPO hyperparameters
- Collect more diverse data

### Issue: "Model not found"

**Cause**: `model_path` not set or incorrect

**Solution**:
- Verify model file exists at path
- Update config with correct path
- Retrain if model was deleted

### Issue: "Agent degrades immediately"

**Cause**: Overfitting to training data or distribution shift

**Solutions**:
- Collect more diverse training data
- Adjust PPO hyperparameters (reduce overfitting)
- Implement regularization
- Use larger lookback window for degradation detection

### Issue: "Agents not making decisions in active mode"

**Cause**: Mode not set to "active" or model not loaded

**Solution**:
- Check config: `mode: "active"`
- Verify model loads (check logs)
- Ensure `is_loaded()` returns True

## Performance Expectations

After graduation, you should see:

### Gate Agent
- **Cost Savings**: 20-40% reduction in LLM API calls
- **Filtering Accuracy**: 55-65% (better than random 50%)
- **False Negatives**: <20% (missing good opportunities)

### Portfolio Agent
- **Sharpe Improvement**: +15-30% vs equal weight
- **Drawdown Reduction**: -10-20%
- **Size Distribution**: Larger sizes on high-confidence setups

### Meta-Learner
- **Override Rate**: 5-15% of LLM decisions
- **Override Accuracy**: 60-70% (overrides should be right more often than wrong)
- **Net Impact**: +5-15% improvement in overall performance

## Next Steps

1. **Run the Test Script**:
   ```bash
   python test_ppo_training.py
   ```
   Verify all components work with mock data.

2. **Run Your First Observe-Mode Backtest**:
   ```bash
   darwin run config.yaml
   ```
   Collect initial data.

3. **Train When Ready**:
   Once you have enough data (check thresholds), train your first agent.

4. **Activate and Monitor**:
   Deploy the graduated agent and watch the monitoring system.

5. **Iterate**:
   Continue the loop, gradually improving agent performance.

## Summary

The Darwin RL system is now **fully functional** with:

✅ **Data Collection** - Observe mode records all decisions
✅ **PPO Training** - True reinforcement learning with exploration
✅ **Graduation System** - Multi-threshold evaluation with baselines
✅ **Deployment** - Active mode for real decision-making
✅ **Degradation Monitoring** - Automatic performance tracking
✅ **Auto-Rollback** - Safety mechanism for degraded agents
✅ **Continuous Loop** - Self-improving system

Everything is in place for a production RL system!
