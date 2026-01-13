"""Pytest configuration and shared fixtures for Darwin tests."""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from darwin.schemas.artifact_header import ArtifactHeaderV1
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.position import PositionRowV1
from darwin.schemas.run_config import (
    FeesConfigV1,
    LLMConfigV1,
    MarketScopeV1,
    PlaybookConfigV1,
    PortfolioConfigV1,
    RunConfigV1,
)
from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.storage.position_ledger import PositionLedgerSQLite


# ============================================================================
# Basic Data Fixtures
# ============================================================================


@pytest.fixture
def sample_bar() -> Dict[str, Any]:
    """Generate a sample OHLCV bar."""
    return {
        "timestamp": datetime(2024, 1, 1, 12, 0),
        "open": 50000.0,
        "high": 50500.0,
        "low": 49500.0,
        "close": 50250.0,
        "volume": 1000000.0,
    }


@pytest.fixture
def sample_bar_series() -> pd.DataFrame:
    """Generate a series of sample OHLCV bars."""
    base_time = datetime(2024, 1, 1)
    bars = []
    base_price = 50000.0

    for i in range(100):
        timestamp = base_time + timedelta(minutes=15 * i)
        # Simple random walk
        price_change = np.random.randn() * 100
        close = base_price + price_change
        open_price = base_price
        high = max(open_price, close) + abs(np.random.randn() * 50)
        low = min(open_price, close) - abs(np.random.randn() * 50)
        volume = 1000000.0 + np.random.randn() * 100000

        bars.append(
            {
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
        base_price = close

    return pd.DataFrame(bars)


@pytest.fixture
def sample_features() -> Dict[str, float]:
    """Generate sample feature dictionary."""
    return {
        # Price features
        "close": 50000.0,
        "ema20": 49800.0,
        "ema50": 49500.0,
        "ema200": 48000.0,
        # Volatility
        "atr": 500.0,
        "atr_pct": 1.0,
        # Momentum
        "rsi": 55.0,
        "macd": 100.0,
        "macd_signal": 80.0,
        # Volume
        "volume": 1000000.0,
        "volume_sma20": 900000.0,
        "volume_ratio": 1.11,
        # Trend
        "adx": 25.0,
        "plus_di": 22.0,
        "minus_di": 18.0,
        # Structure
        "swing_high": 51000.0,
        "swing_low": 48000.0,
    }


@pytest.fixture
def sample_exit_spec() -> ExitSpecV1:
    """Generate sample exit specification."""
    return ExitSpecV1(
        stop_loss_price=49000.0,
        take_profit_price=52000.0,
        time_stop_bars=32,
        trailing_enabled=True,
        trailing_activation_price=51000.0,
        trailing_distance_atr=1.2,
    )


@pytest.fixture
def sample_candidate(sample_features: Dict[str, float], sample_exit_spec: ExitSpecV1) -> CandidateRecordV1:
    """Generate sample candidate record."""
    return CandidateRecordV1(
        candidate_id="cand_test_001",
        run_id="run_test_001",
        timestamp=datetime(2024, 1, 1, 12, 0),
        symbol="BTC-USD",
        timeframe="15m",
        bar_index=400,
        playbook=PlaybookType.BREAKOUT,
        direction="long",
        entry_price=50000.0,
        atr_at_entry=500.0,
        exit_spec=sample_exit_spec,
        features=sample_features,
        llm_decision="take",
        llm_confidence=0.85,
        llm_setup_quality="A",
        payload_ref="payloads/cand_test_001.json",
        response_ref="responses/cand_test_001.json",
        was_taken=True,
        rejection_reason=None,
        position_id="pos_test_001",
    )


@pytest.fixture
def sample_position() -> PositionRowV1:
    """Generate sample position record."""
    return PositionRowV1(
        position_id="pos_test_001",
        run_id="run_test_001",
        candidate_id="cand_test_001",
        symbol="BTC-USD",
        direction="long",
        entry_timestamp=datetime(2024, 1, 1, 12, 15),
        entry_bar_index=401,
        entry_price=50000.0,
        entry_fees_usd=6.25,
        size_usd=1000.0,
        size_units=0.02,
        exit_timestamp=None,
        exit_bar_index=None,
        exit_price=None,
        exit_fees_usd=None,
        exit_reason=None,
        pnl_usd=None,
        pnl_pct=None,
        r_multiple=None,
        stop_loss_price=49000.0,
        take_profit_price=52000.0,
        time_stop_bars=32,
        trailing_enabled=True,
        trailing_activated=False,
        highest_price=None,
        lowest_price=None,
        is_open=True,
    )


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def market_scope_config() -> MarketScopeV1:
    """Generate sample market scope configuration."""
    return MarketScopeV1(
        venue="coinbase",
        symbols=["BTC-USD", "ETH-USD"],
        primary_timeframe="15m",
        additional_timeframes=["1h", "4h"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        warmup_bars=400,
    )


@pytest.fixture
def fees_config() -> FeesConfigV1:
    """Generate sample fees configuration."""
    return FeesConfigV1(maker_bps=6.0, taker_bps=12.5)


@pytest.fixture
def portfolio_config() -> PortfolioConfigV1:
    """Generate sample portfolio configuration."""
    return PortfolioConfigV1(
        starting_equity_usd=10000.0,
        max_positions=3,
        max_exposure_fraction=0.9,
        allow_leverage=False,
        position_size_method="equal_weight",
        risk_per_trade_fraction=0.02,
    )


@pytest.fixture
def llm_config() -> LLMConfigV1:
    """Generate sample LLM configuration."""
    return LLMConfigV1(
        provider="anthropic",
        model="claude-3-sonnet-20240229",
        temperature=0.0,
        max_tokens=500,
        max_calls_per_minute=50,
        max_retries=3,
        initial_retry_delay=1.0,
        circuit_breaker_threshold=5,
        fallback_decision="skip",
    )


@pytest.fixture
def breakout_playbook_config() -> PlaybookConfigV1:
    """Generate sample breakout playbook configuration."""
    return PlaybookConfigV1(
        name="breakout",
        enabled=True,
        entry_params={
            "min_compression_bars": 10,
            "breakout_threshold_atr": 0.5,
            "volume_confirm_threshold": 1.5,
        },
        stop_loss_atr=2.0,
        take_profit_atr=4.0,
        time_stop_bars=32,
        trailing_enabled=True,
        trailing_activation_atr=1.0,
        trailing_distance_atr=1.2,
    )


@pytest.fixture
def pullback_playbook_config() -> PlaybookConfigV1:
    """Generate sample pullback playbook configuration."""
    return PlaybookConfigV1(
        name="pullback",
        enabled=True,
        entry_params={
            "min_trend_strength": 0.6,
            "pullback_depth_min": 0.382,
            "pullback_depth_max": 0.618,
        },
        stop_loss_atr=1.5,
        take_profit_atr=3.0,
        time_stop_bars=48,
        trailing_enabled=True,
        trailing_activation_atr=0.75,
        trailing_distance_atr=1.0,
    )


@pytest.fixture
def run_config(
    market_scope_config: MarketScopeV1,
    fees_config: FeesConfigV1,
    portfolio_config: PortfolioConfigV1,
    llm_config: LLMConfigV1,
    breakout_playbook_config: PlaybookConfigV1,
    pullback_playbook_config: PlaybookConfigV1,
) -> RunConfigV1:
    """Generate complete run configuration."""
    return RunConfigV1(
        run_id="test_run_001",
        description="Test run configuration",
        market_scope=market_scope_config,
        fees=fees_config,
        portfolio=portfolio_config,
        llm=llm_config,
        playbooks=[breakout_playbook_config, pullback_playbook_config],
        artifacts_dir="artifacts",
        generate_plots=True,
        save_payloads=True,
        save_responses=True,
    )


# ============================================================================
# Storage Fixtures
# ============================================================================


@pytest.fixture
def temp_db() -> sqlite3.Connection:
    """Create temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_db_path() -> str:
    """Create temporary database path (without opening connection)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def candidate_cache(temp_db_path: str) -> CandidateCacheSQLite:
    """Create candidate cache with temporary database."""
    cache = CandidateCacheSQLite(temp_db_path)
    yield cache
    cache.close()


@pytest.fixture
def position_ledger(temp_db_path: str) -> PositionLedgerSQLite:
    """Create position ledger with temporary database."""
    ledger = PositionLedgerSQLite(temp_db_path)
    yield ledger
    ledger.close()


# ============================================================================
# Mock LLM Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Generate mock LLM response."""
    return {
        "decision": "take",
        "setup_quality": "A",
        "confidence": 0.85,
        "risk_flags": [],
        "notes": "Strong breakout setup with volume confirmation.",
    }


@pytest.fixture
def mock_llm_harness(mock_llm_response: Dict[str, Any]) -> Mock:
    """Create mock LLM harness that returns predefined responses."""
    mock = Mock()
    mock.call.return_value = mock_llm_response
    mock.health_check.return_value = True
    return mock


@pytest.fixture
def mock_llm_harness_always_skip() -> Mock:
    """Create mock LLM harness that always skips."""
    mock = Mock()
    mock.call.return_value = {
        "decision": "skip",
        "setup_quality": "C",
        "confidence": 0.3,
        "risk_flags": ["high_volatility"],
        "notes": "Risk too high.",
    }
    mock.health_check.return_value = True
    return mock


@pytest.fixture
def mock_llm_harness_failing() -> Mock:
    """Create mock LLM harness that fails."""
    mock = Mock()
    mock.call.side_effect = Exception("LLM API error")
    mock.health_check.return_value = False
    return mock


# ============================================================================
# Directory Fixtures
# ============================================================================


@pytest.fixture
def temp_artifacts_dir() -> Path:
    """Create temporary artifacts directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir) / "artifacts"
        artifacts_dir.mkdir()

        # Create subdirectories
        (artifacts_dir / "runs").mkdir()
        (artifacts_dir / "payloads").mkdir()
        (artifacts_dir / "responses").mkdir()
        (artifacts_dir / "reports").mkdir()
        (artifacts_dir / "meta_reports").mkdir()

        yield artifacts_dir


# ============================================================================
# Helper Functions
# ============================================================================


def create_sample_bar_with_price(
    price: float,
    timestamp: datetime | None = None,
    volatility: float = 0.01,
) -> Dict[str, Any]:
    """Create a sample bar with specified price."""
    if timestamp is None:
        timestamp = datetime(2024, 1, 1, 12, 0)

    price_range = price * volatility
    return {
        "timestamp": timestamp,
        "open": price,
        "high": price + price_range,
        "low": price - price_range,
        "close": price,
        "volume": 1000000.0,
    }


def create_trending_bars(
    num_bars: int,
    start_price: float,
    trend: float,
    volatility: float = 0.01,
    start_time: datetime | None = None,
) -> pd.DataFrame:
    """
    Create a series of bars with a consistent trend.

    Args:
        num_bars: Number of bars to generate
        start_price: Starting price
        trend: Price change per bar (positive = uptrend, negative = downtrend)
        volatility: Volatility as fraction of price
        start_time: Starting timestamp

    Returns:
        DataFrame with OHLCV data
    """
    if start_time is None:
        start_time = datetime(2024, 1, 1)

    bars = []
    current_price = start_price

    for i in range(num_bars):
        timestamp = start_time + timedelta(minutes=15 * i)

        # Add trend + noise
        noise = np.random.randn() * (current_price * volatility)
        close = current_price + trend + noise
        open_price = current_price

        high = max(open_price, close) * (1 + abs(np.random.randn() * volatility / 2))
        low = min(open_price, close) * (1 - abs(np.random.randn() * volatility / 2))
        volume = 1000000.0 * (1 + np.random.randn() * 0.2)

        bars.append(
            {
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": max(volume, 0),
            }
        )

        current_price = close

    return pd.DataFrame(bars)


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config: Any) -> None:
    """Configure pytest."""
    # Add custom markers
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "property: marks property-based tests")


# Set random seed for reproducibility in tests
np.random.seed(42)
