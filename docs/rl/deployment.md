# RL System Deployment Checklist

This document provides a comprehensive checklist for deploying the RL system to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Training](#initial-training)
3. [Observe Mode Deployment](#observe-mode-deployment)
4. [Validation](#validation)
5. [Active Mode Deployment](#active-mode-deployment)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- [ ] Python 3.10+ installed
- [ ] All dependencies installed: `pip install -e ".[rl]"`
- [ ] PyTorch with appropriate GPU support (if available)
- [ ] Sufficient disk space for model storage (>1GB recommended)
- [ ] Database storage for agent state (>500MB recommended)

### Data Requirements

Before training agents, ensure you have:

- [ ] **Gate Agent**: 1000+ historical candidates with outcome labels
- [ ] **Portfolio Agent**: 500+ historical trades with outcome labels
- [ ] **Meta-Learner Agent**: 2000+ historical candidates with LLM decisions and outcomes

### Infrastructure Setup

- [ ] Create models directory: `mkdir -p artifacts/rl_models/{gate,portfolio,meta_learner}`
- [ ] Create state database directory: `mkdir -p artifacts/rl_state`
- [ ] Configure log storage: `mkdir -p logs/rl`
- [ ] Set up monitoring dashboards (TensorBoard, custom dashboards)

---

## Initial Training

### 1. Train Gate Agent

```bash
# Train gate agent on historical data
python -m darwin.rl.cli.train_agent gate \
  --run-ids run_001,run_002,run_003 \
  --output-dir artifacts/rl_models/gate \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --tensorboard-log ./tensorboard_logs/gate
```

**Validation**:
- [ ] Training completed without errors
- [ ] Model saved to `artifacts/rl_models/gate/`
- [ ] Training metrics logged to TensorBoard
- [ ] Evaluation metrics show improvement over baseline (pass_all)

### 2. Train Portfolio Agent

```bash
# Train portfolio agent on historical trades
python -m darwin.rl.cli.train_agent portfolio \
  --run-ids run_001,run_002,run_003 \
  --output-dir artifacts/rl_models/portfolio \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --tensorboard-log ./tensorboard_logs/portfolio
```

**Validation**:
- [ ] Training completed without errors
- [ ] Model saved to `artifacts/rl_models/portfolio/`
- [ ] Training metrics logged to TensorBoard
- [ ] Evaluation shows Sharpe ratio improvement over equal-weight baseline

### 3. Train Meta-Learner Agent

```bash
# Train meta-learner agent on historical LLM decisions
python -m darwin.rl.cli.train_agent meta_learner \
  --run-ids run_001,run_002,run_003 \
  --output-dir artifacts/rl_models/meta_learner \
  --total-timesteps 100000 \
  --eval-freq 10000 \
  --tensorboard-log ./tensorboard_logs/meta_learner
```

**Validation**:
- [ ] Training completed without errors
- [ ] Model saved to `artifacts/rl_models/meta_learner/`
- [ ] Training metrics logged to TensorBoard
- [ ] Agent maintains 80-95% agreement with LLM
- [ ] Override accuracy >60% when disagreeing

---

## Observe Mode Deployment

### Configuration

Create or update your run configuration with RL enabled in observe mode:

```json
{
  "rl": {
    "enabled": true,
    "gate_agent": {
      "name": "gate",
      "enabled": true,
      "mode": "observe",
      "model_path": "artifacts/rl_models/gate/current"
    },
    "portfolio_agent": {
      "name": "portfolio",
      "enabled": true,
      "mode": "observe",
      "model_path": "artifacts/rl_models/portfolio/current"
    },
    "meta_learner_agent": {
      "name": "meta_learner",
      "enabled": true,
      "mode": "observe",
      "model_path": "artifacts/rl_models/meta_learner/current"
    },
    "agent_state_db": "artifacts/rl_state/agent_state.sqlite",
    "max_override_rate": 0.2
  }
}
```

### Deployment Steps

1. **Deploy Configuration**:
   - [ ] Copy trained models to production location
   - [ ] Update run config with RL section
   - [ ] Verify all model paths are correct

2. **Start System**:
   ```bash
   darwin run configs/production_rl_observe.json
   ```

3. **Verify Observe Mode**:
   - [ ] All agents initialized successfully
   - [ ] Agents are making predictions (check logs)
   - [ ] Predictions NOT affecting actual decisions
   - [ ] Decisions being recorded to agent state DB

---

## Validation

### Observe Mode Validation Period

Run in observe mode for a minimum validation period:

- **Gate Agent**: 7-14 days (collect 100+ decisions)
- **Portfolio Agent**: 7-14 days (collect 50+ trades)
- **Meta-Learner Agent**: 14-30 days (collect 200+ decisions)

### Validation Checks

#### 1. Performance Monitoring

```bash
# Check graduation status for each agent
python -m darwin.rl.cli.graduation_status gate --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.graduation_status portfolio --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.graduation_status meta_learner --db artifacts/rl_state/agent_state.sqlite
```

**Checklist**:
- [ ] Gate agent shows positive impact (API cost savings)
- [ ] Portfolio agent shows improved Sharpe ratio vs baseline
- [ ] Meta-learner agreement rate 80-95%
- [ ] Meta-learner override accuracy >60%
- [ ] No performance degradation alerts

#### 2. Safety Checks

- [ ] No circuit breaker activations
- [ ] Override rate within limits (<20%)
- [ ] No excessive alert volume
- [ ] System stability (no crashes, errors)

#### 3. Data Quality

```bash
# Verify agent state data
sqlite3 artifacts/rl_state/agent_state.sqlite "SELECT agent_name, COUNT(*) FROM agent_decisions GROUP BY agent_name;"
```

- [ ] All agents have sufficient decisions recorded
- [ ] Outcomes being updated correctly
- [ ] No data gaps or anomalies

---

## Active Mode Deployment

**WARNING**: Only proceed to active mode after successful validation period and all checks passing.

### Pre-Activation Checklist

- [ ] All agents meet graduation criteria
- [ ] Observe mode validation completed (minimum period)
- [ ] Performance metrics show improvement over baselines
- [ ] Safety mechanisms tested and working
- [ ] Rollback procedure documented and tested
- [ ] Team approval obtained

### Gradual Activation Strategy

#### Phase 1: Activate Gate Agent (Lowest Risk)

1. Update configuration:
   ```json
   "gate_agent": {
     "mode": "active",
     ...
   }
   ```

2. Deploy and monitor:
   - [ ] Gate agent blocking low-quality candidates
   - [ ] API cost reduction observed
   - [ ] Miss rate <10% on winning trades
   - [ ] Monitor for 3-7 days

#### Phase 2: Activate Portfolio Agent (Medium Risk)

1. Update configuration:
   ```json
   "portfolio_agent": {
     "mode": "active",
     ...
   }
   ```

2. Deploy and monitor:
   - [ ] Position sizes being adjusted
   - [ ] Sharpe ratio improvement vs baseline
   - [ ] Max drawdown within limits (<20%)
   - [ ] Monitor for 7-14 days

#### Phase 3: Activate Meta-Learner Agent (Highest Risk)

1. Update configuration:
   ```json
   "meta_learner_agent": {
     "mode": "active",
     ...
   }
   ```

2. Deploy and monitor:
   - [ ] LLM decisions being overridden appropriately
   - [ ] Agreement rate 80-95%
   - [ ] Override accuracy >60%
   - [ ] Net Sharpe improvement vs LLM-only
   - [ ] Monitor for 14-30 days

---

## Monitoring and Maintenance

### Daily Monitoring

Run daily health checks:

```bash
# Check agent health
python -m darwin.rl.cli.evaluate_agent gate --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.evaluate_agent portfolio --db artifacts/rl_state/agent_state.sqlite
python -m darwin.rl.cli.evaluate_agent meta_learner --db artifacts/rl_state/agent_state.sqlite
```

**Daily Checklist**:
- [ ] No new alerts in past 24 hours
- [ ] Agent decision rates normal
- [ ] Performance metrics stable
- [ ] Override rates within limits
- [ ] No circuit breaker activations

### Weekly Monitoring

- [ ] Review performance trends (7-day window)
- [ ] Check for performance degradation
- [ ] Validate graduation criteria still met
- [ ] Review and respond to any alerts
- [ ] Check model versions and rollbacks if needed

### Monthly Maintenance

- [ ] Retrain agents with new data
- [ ] Evaluate graduation status
- [ ] Consider promoting/demoting agents
- [ ] Archive old agent state data
- [ ] Review and tune hyperparameters if needed
- [ ] Update documentation

### Alert Response

#### Performance Degradation Alert

1. **Investigate**:
   - Check recent decisions and outcomes
   - Compare to baseline performance
   - Look for market regime changes

2. **Actions**:
   - If temporary: Monitor for 2-3 days
   - If persistent: Consider demotion to observe mode
   - If severe: Rollback to previous model version

#### Excessive Overrides Alert (Meta-Learner)

1. **Investigate**:
   - Check override accuracy
   - Review overridden decisions
   - Look for patterns in overrides

2. **Actions**:
   - If accuracy high: Acceptable (may need to raise limit)
   - If accuracy low: Demote to observe mode, retrain
   - If extreme (>50%): Circuit breaker should activate

#### Low Decision Rate Alert

1. **Investigate**:
   - Check for system issues
   - Verify data pipeline working
   - Look for market conditions (low volatility, etc.)

2. **Actions**:
   - Fix data pipeline if broken
   - If market-driven: Monitor, no action needed
   - If agent issue: Investigate model, consider retraining

---

## Rollback Procedures

### Scenario 1: Agent Performance Degradation

```bash
# Demote agent to observe mode (quick fix)
# Update config:
"gate_agent": {"mode": "observe", ...}

# Or rollback to previous model version
python -m darwin.rl.cli.rollback_model gate --version <previous_version>
```

### Scenario 2: System Instability

```bash
# Disable RL system entirely
# Update config:
"rl": {"enabled": false}
```

### Scenario 3: Critical Issue

```bash
# Emergency disable via environment variable
export DARWIN_RL_DISABLED=1
darwin run configs/production.json
```

---

## Troubleshooting

### Issue: Agent Not Making Predictions

**Symptoms**: Decision count not increasing

**Diagnosis**:
1. Check agent initialization logs
2. Verify model file exists and is valid
3. Check agent enabled and mode set correctly

**Resolution**:
```bash
# Verify model file
ls -lh artifacts/rl_models/gate/current.zip

# Check agent state DB
sqlite3 artifacts/rl_state/agent_state.sqlite ".tables"

# Review logs for errors
tail -f logs/darwin.log | grep RL
```

### Issue: High Override Rate (Meta-Learner)

**Symptoms**: Override rate >20%, safety monitor blocking

**Diagnosis**:
1. Check override accuracy: Are overrides correct?
2. Look for market regime change
3. Check LLM performance (if LLM degraded, overrides expected)

**Resolution**:
- If overrides accurate: Increase max_override_rate limit
- If overrides inaccurate: Demote to observe, retrain
- If LLM issue: Fix LLM, then reassess RL

### Issue: Circuit Breaker Activated

**Symptoms**: Agent can't act, circuit breaker open

**Diagnosis**:
1. Check logs for repeated failures
2. Identify error type (model loading, inference, etc.)
3. Check resource availability (memory, disk)

**Resolution**:
```bash
# Fix underlying issue, then manually reset circuit breaker
# (Circuit breaker auto-resets after timeout, but can force reset by restarting system)

# Restart system
# Circuit breaker will be closed on initialization
```

### Issue: Model Inference Slow

**Symptoms**: High latency, timeout errors

**Diagnosis**:
1. Check CPU/GPU usage
2. Profile model inference time
3. Check model size and complexity

**Resolution**:
- Optimize model (smaller network, quantization)
- Use GPU if available
- Increase timeout limits if necessary

---

## Success Metrics

After full deployment, the system should achieve:

### Gate Agent
- 20-40% reduction in LLM API calls
- <10% miss rate on positive R-multiple trades
- Net cost savings with minimal opportunity loss

### Portfolio Agent
- Sharpe ratio >1.5 (vs baseline equal-weight)
- Max drawdown <20%
- Better capital efficiency

### Meta-Learner Agent
- 80-95% agreement with LLM (mostly defer to expert)
- >60% override accuracy when disagreeing
- +10% net Sharpe improvement vs LLM-only

### Overall System
- Automated graduation working
- All agents observable in production
- Full auditability of decisions
- Smooth handoff from LLM to RL as agents mature

---

## Contact and Support

For issues or questions:

- Review logs: `logs/darwin.log`
- Check TensorBoard: `tensorboard --logdir tensorboard_logs/`
- Review agent state: `sqlite3 artifacts/rl_state/agent_state.sqlite`
- Open GitHub issue: [darwin/issues](https://github.com/your-org/darwin/issues)

---

**Last Updated**: 2026-01-13
**Version**: 1.0.0
