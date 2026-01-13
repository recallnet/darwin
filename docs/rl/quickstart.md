# RL System Quick Start Guide

This guide walks you through setting up and deploying Darwin's RL system from scratch.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Phase 1: Data Collection](#phase-1-data-collection)
3. [Phase 2: Train Agents](#phase-2-train-agents)
4. [Phase 3: Deploy in Observe Mode](#phase-3-deploy-in-observe-mode)
5. [Phase 4: Validate Performance](#phase-4-validate-performance)
6. [Phase 5: Activate Agents](#phase-5-activate-agents)
7. [Phase 6: Monitor and Maintain](#phase-6-monitor-and-maintain)

---

## Prerequisites

### System Requirements

```bash
# 1. Install RL dependencies
pip install -e ".[rl]"

# This installs:
# - stable-baselines3[extra]>=2.0.0
# - gymnasium>=0.29.0
# - torch>=2.0.0
# - tensorboard>=2.14.0
```

### Data Requirements

Before training RL agents, you need **historical trading data**:

| Agent | Minimum Data | Recommended |
|-------|-------------|-------------|
| Gate Agent | 1000+ candidates | 2000+ candidates |
| Portfolio Agent | 500+ trades | 1000+ trades |
| Meta-Learner | 2000+ candidates | 3000+ candidates |

**Candidates** = All trading opportunities (taken + skipped)
**Trades** = Executed positions with outcomes

---

## Phase 1: Data Collection

### Step 1.1: Run Initial Experiments

Run Darwin **without RL** to collect baseline data:

```bash
# Run multiple experiments with different configs
darwin run examples/basic_breakout.json
darwin run examples/basic_pullback.json
darwin run examples/multi_playbook.json

# Each run generates:
# - Candidate cache (all opportunities)
# - Outcome labels (trade results)
# - Position ledger (PnL history)
```

### Step 1.2: Verify Data Quality

```bash
# Check candidate counts
sqlite3 artifacts/storage/candidate_cache.sqlite \
  "SELECT COUNT(*) FROM candidates;"

# Check outcome labels
sqlite3 artifacts/storage/outcome_labels.sqlite \
  "SELECT COUNT(*) FROM outcome_labels WHERE actual_r_multiple IS NOT NULL;"

# Should have 1000+ candidates with outcomes before training
```

### Step 1.3: Identify Training Runs

```bash
# List available runs
darwin list-runs

# Note the run_ids for training (e.g., run_001, run_002, run_003)
# Use runs with:
# - Complete outcomes (all trades closed)
# - Good data quality (no missing features)
# - Representative market conditions
```

---

## Phase 2: Train Agents

### Step 2.1: Train Gate Agent

The gate agent learns to filter candidates before LLM evaluation:

```bash
# Train gate agent
python -m darwin.rl.training.offline_batch \
  --agent-name gate \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --output-dir artifacts/rl_models/gate \
  --tensorboard-log ./tensorboard_logs/gate

# Training takes ~10-30 minutes depending on data size
# Monitor progress with TensorBoard:
tensorboard --logdir tensorboard_logs/gate
```

**What to look for during training:**
- Episode reward increasing over time
- Policy loss decreasing
- Value function improving
- Evaluation metrics showing improvement over baseline

### Step 2.2: Train Portfolio Agent

The portfolio agent learns optimal position sizing:

```bash
# Train portfolio agent
python -m darwin.rl.training.offline_batch \
  --agent-name portfolio \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --output-dir artifacts/rl_models/portfolio \
  --tensorboard-log ./tensorboard_logs/portfolio

# Monitor with TensorBoard:
tensorboard --logdir tensorboard_logs/portfolio
```

### Step 2.3: Train Meta-Learner Agent

The meta-learner learns when to override LLM decisions:

```bash
# Train meta-learner agent
python -m darwin.rl.training.offline_batch \
  --agent-name meta_learner \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --output-dir artifacts/rl_models/meta_learner \
  --tensorboard-log ./tensorboard_logs/meta_learner

# Monitor with TensorBoard:
tensorboard --logdir tensorboard_logs/meta_learner
```

### Step 2.4: Verify Model Files

```bash
# Check that models were saved
ls -lh artifacts/rl_models/gate/
ls -lh artifacts/rl_models/portfolio/
ls -lh artifacts/rl_models/meta_learner/

# Each directory should contain:
# - best_model.zip (best performing model)
# - model_metadata.json (training info)
# - training_logs/ (tensorboard logs)
```

---

## Phase 3: Deploy in Observe Mode

### Step 3.1: Create RL-Enabled Configuration

Create a new run configuration with RL enabled:

```json
{
  "run_id": "rl_observe_001",
  "description": "First RL deployment in observe mode",

  // ... (standard config fields) ...

  "rl": {
    "enabled": true,
    "gate_agent": {
      "name": "gate",
      "enabled": true,
      "mode": "observe",  // ← IMPORTANT: Start in observe mode
      "model_path": "artifacts/rl_models/gate/best_model.zip",
      "graduation_thresholds": {
        "min_training_samples": 1000,
        "min_validation_samples": 200,
        "min_validation_metric": 0.1,
        "baseline_type": "pass_all",
        "min_improvement_pct": 20.0
      }
    },
    "portfolio_agent": {
      "name": "portfolio",
      "enabled": true,
      "mode": "observe",  // ← IMPORTANT: Start in observe mode
      "model_path": "artifacts/rl_models/portfolio/best_model.zip",
      "graduation_thresholds": {
        "min_training_samples": 500,
        "min_validation_samples": 100,
        "min_validation_metric": 1.5,
        "baseline_type": "equal_weight",
        "min_improvement_pct": 10.0
      }
    },
    "meta_learner_agent": {
      "name": "meta_learner",
      "enabled": true,
      "mode": "observe",  // ← IMPORTANT: Start in observe mode
      "model_path": "artifacts/rl_models/meta_learner/best_model.zip",
      "graduation_thresholds": {
        "min_training_samples": 2000,
        "min_validation_samples": 400,
        "min_validation_metric": 1.0,
        "baseline_type": "llm_only",
        "min_improvement_pct": 10.0
      }
    },
    "models_dir": "artifacts/rl_models",
    "agent_state_db": "artifacts/rl_state/agent_state.sqlite",
    "max_override_rate": 0.2
  }
}
```

**See**: `examples/rl_enabled_run.json` for a complete example

### Step 3.2: Run with RL in Observe Mode

```bash
# Run experiment with RL agents observing
darwin run configs/rl_observe_001.json

# Agents will:
# - Make predictions for every candidate
# - Record decisions to agent_state.sqlite
# - NOT affect actual trading decisions
# - Accumulate performance data
```

### Step 3.3: Verify Observe Mode

```bash
# Check agent state database
sqlite3 artifacts/rl_state/agent_state.sqlite

# Query decisions
sqlite> SELECT agent_name, COUNT(*), mode
        FROM agent_decisions
        GROUP BY agent_name, mode;

# Expected output:
# gate|150|observe
# portfolio|50|observe
# meta_learner|150|observe

# Verify mode is "observe" for all agents
```

---

## Phase 4: Validate Performance

### Step 4.1: Run Validation Period

Run in observe mode for **minimum validation period**:

- **Gate Agent**: 7-14 days (100+ decisions)
- **Portfolio Agent**: 7-14 days (50+ trades)
- **Meta-Learner**: 14-30 days (200+ decisions)

```bash
# Run multiple experiments over validation period
darwin run configs/rl_observe_001.json  # Day 1
darwin run configs/rl_observe_002.json  # Day 2
# ... continue for validation period
```

### Step 4.2: Check Graduation Status

After validation period, check if agents meet graduation criteria:

```bash
# Check gate agent graduation status
python -m darwin.rl.cli.graduation_status gate \
  --db artifacts/rl_state/agent_state.sqlite \
  --verbose

# Example output:
# ✅ Gate Agent Graduation Status
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Can Graduate: YES
#
# Checks:
#   ✅ Sufficient Data: 1247 training, 256 validation samples
#   ✅ Metrics Available: mean_r=0.23, cost_savings=32.4%
#   ✅ Meets Threshold: 0.23 >= 0.1
#   ✅ Beats Baseline: 32.4% > 20.0% required
#   ✅ Stable Performance: Consistent across 3 windows

# Check all agents
python -m darwin.rl.cli.graduation_status portfolio --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.graduation_status meta_learner --db artifacts/rl_state/agent_state.sqlite
```

### Step 4.3: Evaluate Performance Metrics

```bash
# Evaluate gate agent
python -m darwin.rl.cli.evaluate_agent gate \
  --db artifacts/rl_state/agent_state.sqlite \
  --window-days 30

# Example output:
# Gate Agent Performance (30 days)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Total Decisions: 1,247
# Skip Rate: 34.2%
# Miss Rate: 6.8% (winning trades skipped)
# API Cost Savings: 32.4%
# Mean R-multiple: 0.23
#
# vs Baseline (pass_all):
#   Cost Savings: +32.4%
#   Miss Rate: -6.8% (acceptable)
```

### Step 4.4: Check for Alerts

```bash
# Check for any alerts or issues
python -m darwin.rl.cli.check_alerts \
  --db artifacts/rl_state/agent_state.sqlite

# Should see:
# ✅ No alerts
#
# If alerts exist:
# ⚠️  Gate Agent: Performance degradation detected
#     Recent mean R: 0.05 (baseline: 0.18, -72%)
#     Action: Investigate before activating
```

---

## Phase 5: Activate Agents

**⚠️ WARNING**: Only activate agents after:
- ✅ Successful validation period (minimum days)
- ✅ All graduation criteria met
- ✅ No performance alerts
- ✅ Team approval obtained

### Step 5.1: Gradual Activation Strategy

Activate agents **one at a time** with monitoring between each:

#### Activate Gate Agent (Lowest Risk)

```json
{
  "rl": {
    "gate_agent": {
      "mode": "active",  // ← Changed from "observe"
      // ... rest unchanged
    },
    "portfolio_agent": {
      "mode": "observe",  // ← Still observing
      // ...
    },
    "meta_learner_agent": {
      "mode": "observe",  // ← Still observing
      // ...
    }
  }
}
```

```bash
# Deploy with gate agent active
darwin run configs/rl_active_gate_001.json

# Monitor for 3-7 days:
# - API cost reduction observed?
# - Miss rate acceptable (<10%)?
# - No circuit breaker activations?
```

#### Activate Portfolio Agent (Medium Risk)

After gate agent stable for 3-7 days:

```json
{
  "rl": {
    "gate_agent": {
      "mode": "active",
      // ...
    },
    "portfolio_agent": {
      "mode": "active",  // ← Now active
      // ...
    },
    "meta_learner_agent": {
      "mode": "observe",  // ← Still observing
      // ...
    }
  }
}
```

```bash
# Deploy with portfolio agent active
darwin run configs/rl_active_portfolio_001.json

# Monitor for 7-14 days:
# - Sharpe ratio improvement?
# - Max drawdown within limits?
# - Position sizes reasonable?
```

#### Activate Meta-Learner (Highest Risk)

After portfolio agent stable for 7-14 days:

```json
{
  "rl": {
    "gate_agent": {
      "mode": "active",
      // ...
    },
    "portfolio_agent": {
      "mode": "active",
      // ...
    },
    "meta_learner_agent": {
      "mode": "active",  // ← Now active
      // ...
    }
  }
}
```

```bash
# Deploy with all agents active
darwin run configs/rl_fully_active_001.json

# Monitor for 14-30 days:
# - Override rate 80-95%?
# - Override accuracy >60%?
# - Net Sharpe improvement?
```

### Step 5.2: Rollback if Needed

If any issues occur, immediately rollback:

```bash
# Option 1: Demote specific agent to observe
# Update config: change "mode" back to "observe"

# Option 2: Disable RL entirely
# Update config: "rl": {"enabled": false}

# Option 3: Rollback to previous model version
python -m darwin.rl.cli.rollback_model gate --version previous
```

---

## Phase 6: Monitor and Maintain

### Daily Monitoring

```bash
# Check agent health
python -m darwin.rl.cli.evaluate_agent gate \
  --db artifacts/rl_state/agent_state.sqlite \
  --window-days 1

python -m darwin.rl.cli.evaluate_agent portfolio \
  --db artifacts/rl_state/agent_state.sqlite \
  --window-days 1

python -m darwin.rl.cli.evaluate_agent meta_learner \
  --db artifacts/rl_state/agent_state.sqlite \
  --window-days 1

# Check for alerts
python -m darwin.rl.cli.check_alerts \
  --db artifacts/rl_state/agent_state.sqlite
```

### Weekly Retraining

```bash
# Get recent run IDs
RECENT_RUNS=$(darwin list-runs --since "7 days ago" --format ids)

# Retrain all agents
python -m darwin.rl.training.offline_batch \
  --agent-name gate \
  --run-ids $RECENT_RUNS \
  --output-dir artifacts/rl_models/gate

python -m darwin.rl.training.offline_batch \
  --agent-name portfolio \
  --run-ids $RECENT_RUNS \
  --output-dir artifacts/rl_models/portfolio

python -m darwin.rl.training.offline_batch \
  --agent-name meta_learner \
  --run-ids $RECENT_RUNS \
  --output-dir artifacts/rl_models/meta_learner

# Re-check graduation status
python -m darwin.rl.cli.graduation_status gate --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.graduation_status portfolio --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.graduation_status meta_learner --db artifacts/rl_state/agent_state.sqlite
```

### Alert Response

If alerts are triggered:

```bash
# Investigate performance degradation
python -m darwin.rl.cli.analyze_degradation gate \
  --db artifacts/rl_state/agent_state.sqlite \
  --days 7

# If confirmed degradation:
# 1. Demote agent to observe mode
# 2. Investigate cause (market regime change, model drift, etc.)
# 3. Retrain with recent data
# 4. Re-validate before re-activating
```

---

## Troubleshooting

### Issue: "Insufficient training samples"

**Cause**: Not enough historical data

**Solution**:
```bash
# Run more experiments to collect data
darwin run examples/basic_breakout.json
darwin run examples/basic_pullback.json

# Check sample count
sqlite3 artifacts/storage/candidate_cache.sqlite \
  "SELECT COUNT(*) FROM candidates;"

# Need 1000+ candidates for gate agent
```

### Issue: "Model file not found"

**Cause**: Training didn't complete or output path incorrect

**Solution**:
```bash
# Check training output
ls -la artifacts/rl_models/gate/

# Retrain if needed
python -m darwin.rl.training.offline_batch \
  --agent-name gate \
  --run-ids run_001,run_002,run_003 \
  --output-dir artifacts/rl_models/gate
```

### Issue: "Agent not meeting graduation criteria"

**Cause**: Performance not good enough

**Solution**:
1. Collect more training data (run more experiments)
2. Tune hyperparameters (see `darwin/rl/training/hyperparameters.py`)
3. Adjust graduation thresholds (if too strict)
4. Check data quality (missing features, bad labels, etc.)

### Issue: "High miss rate (gate agent)"

**Cause**: Agent too aggressive in skipping

**Solution**:
```bash
# Adjust reward shaping
# Edit darwin/rl/training/hyperparameters.py:
GATE_AGENT_REWARD_PARAMS = {
    "skip_winner_penalty": -2.0,  # Increase penalty for missing winners
    # ...
}

# Retrain with adjusted rewards
python -m darwin.rl.training.offline_batch --agent-name gate ...
```

### Issue: "Circuit breaker activated"

**Cause**: Repeated agent failures

**Solution**:
```bash
# Check error logs
tail -100 logs/darwin.log | grep "agent failure"

# Common causes:
# - Model file corrupted
# - State encoding errors
# - Resource exhaustion (memory, CPU)

# Fix underlying issue, then restart system
# Circuit breaker will auto-reset after timeout (5 minutes)
```

---

## Next Steps

After successful deployment:

1. **Continuous Monitoring**: Set up automated monitoring and alerts
2. **Periodic Retraining**: Weekly or when significant new data available
3. **Performance Analysis**: Compare RL vs non-RL runs regularly
4. **Hyperparameter Tuning**: Optimize based on production performance
5. **Model Versioning**: Maintain history of model versions and performance

---

## Additional Resources

- [RL Architecture](./architecture.md) - Detailed system architecture
- [Deployment Checklist](./deployment.md) - Production deployment guide
- [Hyperparameters](../../darwin/rl/training/hyperparameters.py) - Tuned hyperparameters
- [Example Config](../../examples/rl_enabled_run.json) - RL-enabled run configuration

---

## Support

For issues or questions:

- 📖 Documentation: `docs/rl/`
- 🐛 Issues: [GitHub Issues](https://github.com/recallnet/darwin/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/recallnet/darwin/discussions)
