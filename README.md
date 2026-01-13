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
- ✅ **Comprehensive Feature Pipeline**: 80+ features including price, volatility, trend, momentum, volume
- ✅ **Advanced Exit Logic**: Stop loss, take profit, time stops, and trailing stops
- ✅ **Position Ledger**: Single source of truth for all PnL and trade history
- ✅ **Candidate Cache**: Stores ALL opportunities (taken and skipped) for future learning
- ✅ **Meta Analysis**: Compare multiple runs, generate frontier plots, detect regressions
- ✅ **Error Recovery**: Rate limiting, retry logic, checkpointing for long runs
- ✅ **Comprehensive Testing**: 500+ unit tests, integration tests, property-based tests

## Target Markets

- **Venue**: Coinbase spot markets (USD pairs)
- **Assets**: BTC-USD, ETH-USD, SOL-USD
- **Primary Timeframe**: 15m (configurable)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/recallnet/darwin.git
cd darwin

# Install dependencies (requires Python 3.11+)
pip install -e ".[dev,ta]"

# Install nullagent-tutorial and replay-lab
pip install git+https://github.com/recallnet/nullagent-tutorial.git
pip install git+https://github.com/recallnet/replay-lab.git

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
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

## Architecture

```
Runner → Market Data → Feature Pipeline → Playbook Engine → LLM Harness
   ↓                                                              ↓
Position Manager ← Simulator ← Gate/Budget Policies ← Decision Parser
   ↓
Position Ledger (SQLite) → Evaluation → Reports
   ↓
Candidate Cache (SQLite) → Labels → RL Training (future)
```

### Key Design Principles

1. **Global Runner**: Runner code lives once, globally (not copied into run folders)
2. **Self-Contained Runs**: Every run has its own directory with all decisions auditable
3. **Ledger is Source of Truth**: All PnL, drawdown, exits come from position ledger
4. **Candidate Cache is Learning Substrate**: Every opportunity cached, labels attached later
5. **Schemas are Law**: All artifacts conform to versioned Pydantic schemas

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
└── utils/             # Logging, validation, helpers

tools/                 # CLI entry points
tests/                 # Comprehensive test suite
docs/                  # Documentation
examples/              # Example configurations
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Playbook Specifications](docs/playbooks.md)
- [Feature Pipeline](docs/features.md)
- [API Reference](docs/api/)

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

**Current (v0.1.0 - MVP)**:
- ✅ Replay-based evaluation
- ✅ Breakout and Pullback playbooks
- ✅ LLM-assisted decision-making
- ✅ Comprehensive testing and error recovery

**Near Future (v0.2.0)**:
- Reinforcement learning for gate/budget policies
- Supervised learning for LLM decision prediction
- Additional playbooks (mean reversion, momentum)
- Multi-timeframe analysis

**Long Term (v1.0.0+)**:
- Paper trading mode
- Live trading support (with extensive safeguards)
- Auto-promotion of strategies
- Real-time risk management

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
