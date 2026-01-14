# RL Training Best Practices - Quick Reference

## TL;DR

- **Development**: Train on same run as data accumulates (fast iteration)
- **Production**: Use multi-run training with 5+ diverse runs (robust models)
- **After Degradation**: Retrain with old + new data (prevents forgetting)

## Core Principle: PPO Trains From Scratch

⚠️ **IMPORTANT**: Each training run creates a **NEW model from scratch**. Training does NOT continue from previous models - it starts fresh with the data you provide.

## The Overfitting Problem

Training on a single run repeatedly can cause:
- 🔴 **Market regime overfitting** (e.g., only works in bull markets)
- 🔴 **Symbol-specific memorization** (works on BTC, fails on others)
- 🔴 **Playbook-specific patterns** (learns tricks for one strategy)
- 🔴 **Poor generalization** to unseen conditions

**Example:**
```
Train on: BTC Jan-Mar 2024 (bull market)
Agent learns: Be aggressive, high pass rate
Market shifts: Consolidation in April 2024
Result: Still too aggressive → Poor performance → Degradation → Rollback
```

## Decision Matrix

### ✅ Train on Same Run Multiple Times When:

- Early in development (testing the pipeline)
- Accumulating data in long continuous backtest
- Haven't met graduation thresholds yet
- Iterating quickly on config/playbook

**Example:**
```bash
# Collect data progressively
darwin run config.yaml           # 200 decisions
darwin train-agent config.yaml gate

# More data
darwin run config.yaml --resume  # 500 decisions
darwin train-agent config.yaml gate  # Retrain with more data
```

### ✅ Use Multi-Run Training When:

- Deploying to production/active mode
- Have 5+ diverse backtests completed
- Want robust performance across conditions
- Agent degraded and needs retraining
- Market conditions changed significantly

**Example:**
```bash
# Diverse backtests
darwin run config_btc_2023.yaml
darwin run config_eth_2024.yaml
darwin run config_highvol.yaml

# Multi-run training
darwin train-multi-run gate \
    --db-paths artifacts/*/agent_state.sqlite \
    --output models/gate/production_v1.zip \
    --timesteps 200000
```

## Data Diversity Requirements

Ensure diversity across:

| Dimension | Examples | Why It Matters |
|-----------|----------|----------------|
| **Market Regime** | Bull, bear, consolidation, high/low volatility | Adapts to changing conditions |
| **Time Periods** | 2023 vs 2024, Q1 vs Q3 | Market dynamics evolve |
| **Symbols** | BTC, ETH, SOL | Asset-specific behavior differs |
| **Playbooks** | Different entry strategies | Strategy-agnostic learning |
| **Sample Size** | 500+ decisions per run | Statistical significance |

## Recommended Workflow

### Phase 1: Development (0-2 weeks)
```bash
# Quick iteration
darwin run config.yaml
darwin train-agent config.yaml gate
# Iterate on config, test graduation
```
**Goal:** Get comfortable with the pipeline, tune thresholds

### Phase 2: Diversification (2-4 weeks)
```bash
# Run diverse backtests
darwin run config_btc.yaml      # Different symbol
darwin run config_2023.yaml     # Different period
darwin run config_highvol.yaml  # Different regime
```
**Goal:** Collect diverse training data

### Phase 3: Production Training (Week 4+)
```bash
# Multi-run training for production
darwin train-multi-run gate \
    --db-paths artifacts/run_*/agent_state.sqlite \
    --output models/gate/production_v1.zip \
    --timesteps 200000
```
**Goal:** Train robust, production-ready agent

### Phase 4: Maintenance (Ongoing)
```bash
# After degradation
darwin train-multi-run gate \
    --db-paths artifacts/new_data/agent_state.sqlite \
    --db-paths artifacts/old_run_*/agent_state.sqlite \
    --output models/gate/recovery_v2.zip
```
**Goal:** Adapt to new conditions while retaining knowledge

## Common Mistakes

### ❌ Mistake 1: Training on Identical Data
```bash
# Bad: All runs same period, same symbol, same config
darwin run config_btc_jan.yaml
darwin run config_btc_jan.yaml  # Same data!
darwin run config_btc_jan.yaml  # Still same data!

darwin train-multi-run gate --db-paths artifacts/*/agent_state.sqlite
# Result: No diversity benefit, still overfitted
```

### ❌ Mistake 2: Deploying Single-Run Models to Production
```bash
# Bad: Only trained on one market condition
darwin run config_btc_bull.yaml
darwin train-agent config.yaml gate
# Set mode = "active" and deploy
# Result: Degrades quickly when market shifts
```

### ❌ Mistake 3: Not Including Old Data After Degradation
```bash
# Bad: Only train on new data after degradation
darwin train-agent new_config.yaml gate
# Result: Agent "forgets" what it learned before
```

### ✅ Fix: Always Include Historical Data
```bash
# Good: Combine old successful data + new data
darwin train-multi-run gate \
    --db-paths artifacts/new_run/agent_state.sqlite \
    --db-paths artifacts/old_run_1/agent_state.sqlite \
    --db-paths artifacts/old_run_2/agent_state.sqlite \
    --output models/gate/recovery.zip
```

## Data Quality Checklist

Before training, verify your data has:

- [ ] **Sufficient volume**: 500+ decisions per run (gate), 300+ (portfolio), 400+ (meta-learner)
- [ ] **High outcome ratio**: >50% decisions have outcomes (trades closed)
- [ ] **Market diversity**: Bull, bear, consolidation periods represented
- [ ] **Time diversity**: Spans multiple months/quarters
- [ ] **Symbol diversity**: Multiple assets (if multi-asset strategy)
- [ ] **Win rate variety**: Mix of winning and losing periods (not just wins)

## Quick Commands Reference

```bash
# Single-run training (development)
darwin train-agent config.yaml gate

# Single-run training without auto-activation
darwin train-agent config.yaml gate --no-activate

# Multi-run training (production)
darwin train-multi-run gate \
    --db-paths run_1/agent_state.sqlite \
    --db-paths run_2/agent_state.sqlite \
    --db-paths run_3/agent_state.sqlite \
    --output models/gate/model.zip \
    --timesteps 200000 \
    --tensorboard-log artifacts/tensorboard

# With glob pattern (shell expansion)
darwin train-multi-run portfolio \
    --db-paths artifacts/run_*/agent_state.sqlite \
    --output models/portfolio/model.zip
```

## Performance Expectations

### Single-Run Trained Model
- ✅ Good performance on similar conditions
- ⚠️ May degrade when conditions change
- ⚠️ Narrower applicability
- ⏱️ Faster to collect data and train

### Multi-Run Trained Model
- ✅ Robust across market regimes
- ✅ Better generalization
- ✅ More stable performance
- ⏱️ Requires more data collection time
- 🎯 **Recommended for production**

## When to Retrain

Retrain agents when:

1. **After degradation** (auto-rollback triggered)
2. **Market regime change** (bull → bear, low vol → high vol)
3. **New symbols added** (if trading new assets)
4. **Playbook updated** (strategy logic changed)
5. **Periodic refresh** (every 3-6 months recommended)
6. **Performance plateau** (graduation metrics not improving)

## Key Takeaway

> **The multi-run training feature exists specifically to solve the overfitting problem.**
>
> Use it for any model that will make real decisions in active mode. Single-run training is fine for development, but production agents should ALWAYS be trained on diverse data.

## Need Help?

- Full documentation: `darwin/rl/FULL_LOOP_CHECKLIST.md`
- Training algorithms: `darwin/rl/training/algorithms.py`
- Multi-run training: `darwin/rl/training/multi_run_training.py`
- CLI reference: `darwin train-agent --help` or `darwin train-multi-run --help`
