# Darwin - LLM-Assisted Crypto Trading Research Platform

Darwin is a replay-first, LLM-assisted crypto trading strategy research system designed to answer questions like:

- When does an LLM add value over deterministic technical analysis?
- Which market regimes or playbooks benefit from LLM judgment?
- Can we learn a gate/budget policy that filters LLM decisions better than rules?
- How do strategy variants evolve over time, not just perform once?

## Philosophy

- **Replay First**: Evaluation comes first; live trading comes much later
- **Reproducible**: Every run must be reproducible and explainable
- **Versioned**: Every artifact must be versioned, schematized, and auditable
- **Learning After Observation**: Learning happens *after* observing outcomes, not inline
- **Comparative**: The system must support many runs and comparisons over time

## Features

- ✅ **Deterministic Playbooks**: Breakout and Pullback strategies with precise entry/exit rules
- ✅ **LLM Evaluation**: Use Claude/GPT to evaluate trade candidates with rich market context
- ✅ **Reinforcement Learning System**: Three RL agents that progressively learn from outcomes
  - **Gate Agent**: Pre-LLM filtering (20-40% API cost reduction)
  - **Portfolio Agent**: Position sizing optimization (Sharpe >1.5)
  - **Meta-Learner Agent**: LLM decision override (+10-15% Sharpe improvement)
- ✅ **Automated Graduation**: Agents start in observe mode and automatically promote when meeting criteria
- ✅ **Comprehensive Feature Pipeline**: 80+ features including price, volatility, trend, momentum, volume
- ✅ **Advanced Exit Logic**: Stop loss, take profit, time stops, and trailing stops
- ✅ **Position Ledger**: Single source of truth for all PnL and trade history
- ✅ **Candidate Cache**: Stores ALL opportunities (taken and skipped) for future learning
- ✅ **Meta Analysis**: Compare multiple runs, generate frontier plots, detect regressions
- ✅ **Error Recovery**: Rate limiting, retry logic, checkpointing for long runs
- ✅ **Production Safety**: Circuit breakers, performance monitoring, automatic fallback
- ✅ **Comprehensive Testing**: 115+ tests including RL agents, 35% RL module coverage

## Target Markets

- **Venue**: Coinbase spot markets (USD pairs)
- **Assets**: BTC-USD, ETH-USD, SOL-USD
- **Primary Timeframe**: 15m (configurable)

## Quick Start

### Installation

```bash
# 1. Clone repositories
git clone https://github.com/recallnet/darwin.git
# Optional: clone replay-lab for real market data
git clone https://github.com/recallnet/replay-lab.git

# 2. Install Darwin dependencies (requires Python 3.11+)
cd darwin
pip install -e ".[dev,ta]"

# 3. Set up Vercel AI Gateway
# Go to https://vercel.com/ai-gateway and create an API key
cp .env.example .env
# Edit .env and set:
#   AI_GATEWAY_API_KEY=your-key-here
#   MODEL_ID=google/gemini-2.0-flash  (or anthropic/claude-sonnet-4-5, deepseek/deepseek-v3.2)

# 4. (Optional) Start replay-lab for real market data
cd ../replay-lab
pnpm install
docker-compose up -d
pnpm db:migrate:sql
pnpm dev --filter replay-lab
# Set REPLAY_LAB_URL=http://localhost:3301 in darwin/.env
```

### Run Your First Experiment

```bash
# Run a simple backtest with mock LLM
darwin run examples/basic_breakout.json --mock-llm

# Run with real LLM
darwin run examples/basic_breakout.json

# View results
darwin report runs/<run_id>

# Compare multiple runs
darwin meta-report
```

### RL Quick Start

To use the reinforcement learning system:

```bash
# 1. Install RL dependencies
pip install -e ".[rl]"

# 2. Run experiments to collect training data (1000+ candidates needed)
darwin run examples/basic_breakout.json
darwin run examples/basic_pullback.json
darwin run examples/multi_playbook.json

# 3. Train RL agents on historical data
python -m darwin.rl.training.offline_batch \
  --agent-name gate \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --output-dir artifacts/rl_models/gate

python -m darwin.rl.training.offline_batch \
  --agent-name portfolio \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --output-dir artifacts/rl_models/portfolio

python -m darwin.rl.training.offline_batch \
  --agent-name meta_learner \
  --run-ids run_001,run_002,run_003 \
  --total-timesteps 100000 \
  --output-dir artifacts/rl_models/meta_learner

# 4. Deploy in observe mode (agents predict but don't affect decisions)
darwin run examples/rl_enabled_run.json

# 5. Check graduation status after validation period
python -m darwin.rl.cli.graduation_status gate \
  --db artifacts/rl_state/agent_state.sqlite

# 6. Activate agents (change "mode": "observe" → "active" in config)
#    Do this gradually: gate → portfolio → meta_learner
#    Monitor performance between each activation

# 7. Monitor and maintain
python -m darwin.rl.cli.evaluate_agent gate \
  --db artifacts/rl_state/agent_state.sqlite \
  --window-days 7
```

**See**: [RL Quick Start Guide](docs/rl/quickstart.md) for detailed instructions

## Architecture

```
Runner → Market Data → Feature Pipeline → Playbook Engine
   ↓                                              ↓
   │                                     ┌────────────────┐
   │                                     │  Gate Agent    │ (RL)
   │                                     │  (pre-filter)  │
   │                                     └───────┬────────┘
   │                                             ↓
   │                                       LLM Harness
   │                                             ↓
   │                                     ┌────────────────┐
   │                                     │ Meta-Learner   │ (RL)
   │                                     │ (override)     │
   │                                     └───────┬────────┘
   │                                             ↓
   │                                       Decision Parser
   │                                             ↓
   │                                     ┌────────────────┐
   │                                     │ Portfolio Agent│ (RL)
   │                                     │ (position size)│
   │                                     └───────┬────────┘
   │                                             ↓
   └─────────────────────────────────> Position Manager
                                                 ↓
                                      Position Ledger (SQLite)
                                                 ↓
                                         Evaluation → Reports
                                                 ↓
                                      Candidate Cache (SQLite)
                                                 ↓
                                           Outcome Labels
                                                 ↓
                                     ┌──────────────────────┐
                                     │  RL Training         │
                                     │  (offline, periodic) │
                                     └──────────────────────┘
                                                 ↓
                                      Model Store (versioned)
                                                 ↓
                                      Graduation & Monitoring
```

### Key Design Principles

1. **Global Runner**: Runner code lives once, globally (not copied into run folders)
2. **Self-Contained Runs**: Every run has its own directory with all decisions auditable
3. **Ledger is Source of Truth**: All PnL, drawdown, exits come from position ledger
4. **Candidate Cache is Learning Substrate**: Every opportunity cached, labels attached later
5. **Schemas are Law**: All artifacts conform to versioned Pydantic schemas

## Integrations

### Vercel AI Gateway (LLM Routing)

Darwin calls **Vercel AI Gateway** directly from Python for unified multi-provider LLM access:

- **Single API Key**: One `AI_GATEWAY_API_KEY` routes to all providers (no per-provider keys needed)
- **Multi-Provider**: Supports Anthropic, OpenAI, Google Gemini, xAI, Mistral, Perplexity, DeepSeek, and more
- **Model Format**: `provider/model-name` (e.g., `anthropic/claude-sonnet-4-5`, `google/gemini-2.0-flash`)
- **Swappable Models**: Each run can specify a different model in its configuration
- **No External Services**: Direct HTTP calls from Python (no Node.js middleware)

```bash
# Set in .env
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
AI_GATEWAY_API_KEY=your-key-from-vercel
MODEL_ID=google/gemini-2.0-flash
```

**Supported Models:** Darwin supports **ALL 17+ models** available through Vercel AI Gateway with 100% test pass rate:
- **Anthropic**: Claude Sonnet/Opus/Haiku 4.5
- **OpenAI**: GPT-4o, GPT-4o Mini, o1 (reasoning)
- **Google**: Gemini 2.0/2.5 Flash, Gemini 2.5 Pro, Gemini 3 Pro (reasoning)
- **DeepSeek**: DeepSeek v3.2, DeepSeek Reasoner
- **xAI**: Grok 2 Vision, Grok 4 Fast Reasoning
- **Mistral**: Pixtral Large, Ministral 8B
- **Perplexity**: Sonar Pro

**Recommended Models:**
- Production: `anthropic/claude-sonnet-4-5` (best quality)
- Default: `google/gemini-2.0-flash` (fast, cheap, good performance)
- High-volume: `deepseek/deepseek-v3.2` (very cheap)
- Reasoning: `openai/o1`, `google/gemini-3-pro-preview` (automatic 4x token boost)

**Auto-Optimization:** Reasoning models automatically get 4000 max_tokens (vs 1000 for standard models)

See [SUPPORTED_MODELS.md](./SUPPORTED_MODELS.md) for full details and test results.

### Replay-Lab (Market Data)

Darwin integrates with [replay-lab](https://github.com/recallnet/replay-lab) for real market data:

- **Architecture**: REST API client calls replay-lab's OHLCV endpoints
- **Fallbacks**: Gracefully falls back to CSV files or synthetic data
- **Symbol Mapping**: Converts `BTC-USD` → `COINBASE_SPOT_BTC_USD`
- **Data Quality**: Validates all OHLCV data before use

```bash
# Start replay-lab locally
cd replay-lab
pnpm dev --filter replay-lab

# Set in .env
REPLAY_LAB_URL=http://localhost:3301
```

**Data Priority**:
1. Replay-Lab API (if `REPLAY_LAB_URL` set and reachable)
2. CSV files in data directory (if `--data-dir` specified)
3. Synthetic data (GBM-based price generation for testing)

## Playbooks

### Breakout Playbook
- **Entry**: Price breaks 32-bar range with ADX ≥ 18, volume confirmation, trend alignment
- **Stop Loss**: 1.2 × ATR
- **Take Profit**: 2.4 × ATR (~2R)
- **Time Stop**: 32 bars (8 hours on 15m)
- **Trailing**: Activates at +1.0R, trails at 1.2 × ATR

### Pullback Playbook
- **Entry**: Price tags EMA20 and reclaims in uptrend (EMA50 > EMA200, ADX ≥ 16)
- **Stop Loss**: 1.0 × ATR
- **Take Profit**: 1.8 × ATR (~1.8R)
- **Time Stop**: 48 bars (12 hours on 15m)
- **Trailing**: Activates at +0.8R, trails at 1.0 × ATR

## Feature Pipeline

Darwin computes 80+ features per candidate across multiple categories:

- **Price/Returns**: Close, returns over multiple horizons, range
- **Volatility**: ATR, realized volatility, volatility z-scores
- **Trend/Regime**: EMAs (20/50/200), ADX, directional indicators
- **Momentum**: RSI, MACD, Stochastic (optional)
- **Range/Levels**: Donchian channels, Bollinger Bands, breakout/pullback distances
- **Volume**: Turnover, ADV, volume ratios and z-scores
- **Microstructure**: Spread estimates, slippage models
- **Portfolio State**: Open positions, exposure, drawdown
- **Derivatives** (optional): Funding rates, open interest

## LLM Integration

Darwin sends structured JSON payloads to LLMs with:
- Global market regime (BTC 4h context)
- Asset-specific state (15m + 1h)
- Candidate setup details (playbook-specific)
- Policy constraints

LLMs return decisions with:
- `decision`: "take" or "skip"
- `setup_quality`: "A+", "A", "B", or "C"
- `confidence`: 0.0 to 1.0
- `risk_flags`: Array of concerns
- `notes`: Brief explanation

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/property/

# Run with coverage
pytest --cov=darwin --cov-report=html

# Run property-based tests
pytest tests/property/test_simulator_invariants.py
```

## Project Structure

```
darwin/
├── schemas/           # Pydantic models with validation
├── storage/           # SQLite stores with abstract interfaces
├── features/          # Incremental feature pipeline
├── playbooks/         # Breakout and Pullback implementations
├── simulator/         # Position management and exit logic
├── llm/               # LLM harness with rate limiting
├── runner/            # Global runner with error recovery
├── evaluation/        # Ledger-driven evaluation and reporting
├── rl/                # Reinforcement learning system
│   ├── agents/        #   Three RL agents (gate, portfolio, meta-learner)
│   ├── envs/          #   Gymnasium environments
│   ├── training/      #   Offline training and hyperparameters
│   ├── graduation/    #   Automated graduation policies
│   ├── integration/   #   Runner integration hooks
│   ├── storage/       #   Model store and agent state
│   ├── monitoring/    #   Alerts and safety mechanisms
│   └── utils/         #   State encoding and reward shaping
└── utils/             # Logging, validation, helpers

tools/                 # CLI entry points
tests/                 # Comprehensive test suite (115+ tests)
docs/                  # Documentation
examples/              # Example configurations
```

## Documentation

### Core System
- [Architecture Overview](docs/architecture.md)
- [Playbook Specifications](docs/playbooks.md)
- [Feature Pipeline](docs/features.md)
- [API Reference](docs/api/)

### Reinforcement Learning
- [RL System Architecture](docs/rl/architecture.md) - Detailed RL system design
- [RL Quick Start Guide](docs/rl/quickstart.md) - Step-by-step setup and deployment
- [Deployment Checklist](docs/rl/deployment.md) - Production deployment procedures
- [Example RL Config](examples/rl_enabled_run.json) - Complete RL configuration

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Run linters
black darwin/ tests/
ruff check darwin/ tests/
mypy darwin/

# Format code
black darwin/ tests/
```

## Roadmap

**Current (v0.2.0 - RL System)**:
- ✅ Replay-based evaluation
- ✅ Breakout and Pullback playbooks
- ✅ LLM-assisted decision-making
- ✅ Comprehensive testing and error recovery
- ✅ **Three-agent RL system** (gate, portfolio, meta-learner)
- ✅ **Automated graduation policies** (observe → active promotion)
- ✅ **Production safety mechanisms** (circuit breakers, monitoring, fallback)
- ✅ **Offline training pipeline** with PPO algorithm
- ✅ **115+ comprehensive tests** including end-to-end RL workflow

**Near Future (v0.3.0)**:
- Supervised learning for LLM decision prediction
- Additional playbooks (mean reversion, momentum)
- Multi-timeframe analysis
- Hyperparameter optimization (grid search, Bayesian)
- Real-time performance dashboards

**Long Term (v1.0.0+)**:
- Paper trading mode
- Live trading support (with extensive safeguards)
- Multi-agent coordination strategies
- Real-time risk management
- Auto-scaling position sizes based on account growth

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Citation

If you use Darwin in your research, please cite:

```bibtex
@software{darwin2024,
  title={Darwin: LLM-Assisted Crypto Trading Research Platform},
  author={Recall Net},
  year={2024},
  url={https://github.com/recallnet/darwin}
}
```

## Acknowledgments

- Built on [nullagent-tutorial](https://github.com/recallnet/nullagent-tutorial) for LLM harness
- Uses [replay-lab](https://github.com/recallnet/replay-lab) for market data
- Inspired by research in LLM-assisted trading and reinforcement learning

## Support

- 📖 Documentation: [docs/](docs/)
- 🐛 Issues: [GitHub Issues](https://github.com/recallnet/darwin/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/recallnet/darwin/discussions)
