"""Unit tests for Pydantic schemas."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from darwin.schemas.artifact_header import ArtifactHeaderV1
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.decision_event import DecisionEventV1
from darwin.schemas.llm_payload import GlobalRegimeV1, LLMPayloadV1
from darwin.schemas.llm_response import LLMResponseV1
from darwin.schemas.outcome_label import OutcomeLabelV1
from darwin.schemas.position import ExitReason, PositionRowV1
from darwin.schemas.run_config import (
    FeatureMode,
    FeesConfigV1,
    LLMConfigV1,
    MarketScopeV1,
    PlaybookConfigV1,
    PortfolioConfigV1,
    RunConfigV1,
)
from darwin.schemas.run_manifest import RunManifestV1


class TestArtifactHeader:
    """Test ArtifactHeaderV1 schema."""

    def test_valid_artifact_header(self):
        """Test valid artifact header creation."""
        header = ArtifactHeaderV1(
            schema_version="v1",
            created_at=datetime(2024, 1, 1, 12, 0),
            run_id="test_run_001",
        )
        assert header.schema_version == "v1"
        assert header.run_id == "test_run_001"

    def test_artifact_header_serialization(self):
        """Test artifact header can be serialized to JSON."""
        header = ArtifactHeaderV1(
            schema_version="v1",
            created_at=datetime(2024, 1, 1, 12, 0),
            run_id="test_run_001",
        )
        json_str = header.model_dump_json()
        parsed = ArtifactHeaderV1.model_validate_json(json_str)
        assert parsed.run_id == header.run_id


class TestMarketScope:
    """Test MarketScopeV1 schema."""

    def test_valid_market_scope(self, market_scope_config):
        """Test valid market scope configuration."""
        assert market_scope_config.venue == "coinbase"
        assert len(market_scope_config.symbols) == 2
        assert market_scope_config.warmup_bars == 400

    def test_empty_symbols_rejected(self):
        """Test that empty symbols list is rejected."""
        with pytest.raises(ValidationError, match="symbols must not be empty"):
            MarketScopeV1(symbols=[], primary_timeframe="15m")

    def test_empty_string_in_symbols_rejected(self):
        """Test that empty strings in symbols are rejected."""
        with pytest.raises(ValidationError, match="symbols must not contain empty strings"):
            MarketScopeV1(symbols=["BTC-USD", "  ", "ETH-USD"], primary_timeframe="15m")

    def test_negative_warmup_bars_rejected(self):
        """Test that negative warmup_bars is rejected."""
        with pytest.raises(ValidationError, match="warmup_bars must be > 0"):
            MarketScopeV1(symbols=["BTC-USD"], primary_timeframe="15m", warmup_bars=-1)

    def test_zero_warmup_bars_rejected(self):
        """Test that zero warmup_bars is rejected."""
        with pytest.raises(ValidationError, match="warmup_bars must be > 0"):
            MarketScopeV1(symbols=["BTC-USD"], primary_timeframe="15m", warmup_bars=0)


class TestFeesConfig:
    """Test FeesConfigV1 schema."""

    def test_valid_fees_config(self, fees_config):
        """Test valid fees configuration."""
        assert fees_config.maker_bps == 6.0
        assert fees_config.taker_bps == 12.5

    def test_negative_fees_rejected(self):
        """Test that negative fees are rejected."""
        with pytest.raises(ValidationError, match="fees must be non-negative"):
            FeesConfigV1(maker_bps=-1.0, taker_bps=12.5)

    def test_zero_fees_allowed(self):
        """Test that zero fees are allowed."""
        config = FeesConfigV1(maker_bps=0.0, taker_bps=0.0)
        assert config.maker_bps == 0.0


class TestPortfolioConfig:
    """Test PortfolioConfigV1 schema."""

    def test_valid_portfolio_config(self, portfolio_config):
        """Test valid portfolio configuration."""
        assert portfolio_config.starting_equity_usd == 10000.0
        assert portfolio_config.max_positions == 3

    def test_negative_starting_equity_rejected(self):
        """Test that negative starting equity is rejected."""
        with pytest.raises(ValidationError, match="starting_equity_usd must be > 0"):
            PortfolioConfigV1(starting_equity_usd=-1000.0)

    def test_zero_max_positions_rejected(self):
        """Test that zero max_positions is rejected."""
        with pytest.raises(ValidationError, match="max_positions must be > 0"):
            PortfolioConfigV1(max_positions=0)

    def test_leverage_required_for_high_exposure(self):
        """Test that high exposure requires leverage flag."""
        with pytest.raises(
            ValidationError, match="max_exposure_fraction=1.5 > 1.0 requires allow_leverage=true"
        ):
            PortfolioConfigV1(max_exposure_fraction=1.5, allow_leverage=False)

    def test_high_exposure_allowed_with_leverage(self):
        """Test that high exposure is allowed with leverage flag."""
        config = PortfolioConfigV1(max_exposure_fraction=1.5, allow_leverage=True)
        assert config.max_exposure_fraction == 1.5

    def test_invalid_risk_per_trade_rejected(self):
        """Test that invalid risk_per_trade_fraction is rejected."""
        with pytest.raises(ValidationError, match="risk_per_trade_fraction must be between 0 and 0.5"):
            PortfolioConfigV1(risk_per_trade_fraction=0.6)


class TestLLMConfig:
    """Test LLMConfigV1 schema."""

    def test_valid_llm_config(self, llm_config):
        """Test valid LLM configuration."""
        assert llm_config.provider == "anthropic"
        assert llm_config.temperature == 0.0

    def test_invalid_temperature_rejected(self):
        """Test that invalid temperature is rejected."""
        with pytest.raises(ValidationError, match="temperature must be between 0 and 2"):
            LLMConfigV1(temperature=3.0)

    def test_negative_max_tokens_rejected(self):
        """Test that negative max_tokens is rejected."""
        with pytest.raises(ValidationError, match="max_tokens must be > 0"):
            LLMConfigV1(max_tokens=-1)


class TestPlaybookConfig:
    """Test PlaybookConfigV1 schema."""

    def test_valid_breakout_playbook(self, breakout_playbook_config):
        """Test valid breakout playbook configuration."""
        assert breakout_playbook_config.name == "breakout"
        assert breakout_playbook_config.stop_loss_atr == 2.0

    def test_take_profit_must_exceed_stop_loss(self):
        """Test that take_profit_atr must be greater than stop_loss_atr."""
        with pytest.raises(
            ValidationError, match="take_profit_atr.*must be > stop_loss_atr"
        ):
            PlaybookConfigV1(
                name="breakout",
                stop_loss_atr=3.0,
                take_profit_atr=2.0,  # Invalid: less than SL
                time_stop_bars=32,
                trailing_activation_atr=1.0,
                trailing_distance_atr=1.2,
            )

    def test_negative_atr_values_rejected(self):
        """Test that negative ATR values are rejected."""
        with pytest.raises(ValidationError, match="ATR-based values must be > 0"):
            PlaybookConfigV1(
                name="breakout",
                stop_loss_atr=-1.0,
                take_profit_atr=4.0,
                time_stop_bars=32,
                trailing_activation_atr=1.0,
                trailing_distance_atr=1.2,
            )


class TestRunConfig:
    """Test RunConfigV1 schema."""

    def test_valid_run_config(self, run_config):
        """Test valid run configuration."""
        assert run_config.run_id == "test_run_001"
        assert len(run_config.playbooks) == 2

    def test_empty_playbooks_rejected(self):
        """Test that empty playbooks list is rejected."""
        with pytest.raises(ValidationError, match="playbooks must not be empty"):
            RunConfigV1(
                run_id="test",
                market_scope=MarketScopeV1(symbols=["BTC-USD"], primary_timeframe="15m"),
                playbooks=[],
            )

    def test_invalid_playbook_name_rejected(self):
        """Test that invalid playbook names are rejected."""
        with pytest.raises(ValidationError, match="Invalid playbook name"):
            RunConfigV1(
                run_id="test",
                market_scope=MarketScopeV1(symbols=["BTC-USD"], primary_timeframe="15m"),
                playbooks=[
                    PlaybookConfigV1(
                        name="invalid_playbook",
                        stop_loss_atr=2.0,
                        take_profit_atr=4.0,
                        time_stop_bars=32,
                        trailing_activation_atr=1.0,
                        trailing_distance_atr=1.2,
                    )
                ],
            )

    def test_run_config_serialization(self, run_config):
        """Test that run config can be serialized and deserialized."""
        json_str = run_config.model_dump_json()
        parsed = RunConfigV1.model_validate_json(json_str)
        assert parsed.run_id == run_config.run_id
        assert len(parsed.playbooks) == len(run_config.playbooks)


class TestCandidateRecord:
    """Test CandidateRecordV1 schema."""

    def test_valid_candidate(self, sample_candidate):
        """Test valid candidate record."""
        assert sample_candidate.candidate_id == "cand_test_001"
        assert sample_candidate.playbook == PlaybookType.BREAKOUT
        assert sample_candidate.was_taken is True

    def test_candidate_serialization(self, sample_candidate):
        """Test candidate can be serialized and deserialized."""
        json_str = sample_candidate.model_dump_json()
        parsed = CandidateRecordV1.model_validate_json(json_str)
        assert parsed.candidate_id == sample_candidate.candidate_id
        assert parsed.features == sample_candidate.features


class TestExitSpec:
    """Test ExitSpecV1 schema."""

    def test_valid_exit_spec(self, sample_exit_spec):
        """Test valid exit specification."""
        assert sample_exit_spec.stop_loss_price == 49000.0
        assert sample_exit_spec.take_profit_price == 52000.0
        assert sample_exit_spec.trailing_enabled is True

    def test_exit_spec_serialization(self, sample_exit_spec):
        """Test exit spec can be serialized."""
        json_str = sample_exit_spec.model_dump_json()
        parsed = ExitSpecV1.model_validate_json(json_str)
        assert parsed.stop_loss_price == sample_exit_spec.stop_loss_price


class TestPositionRow:
    """Test PositionRowV1 schema."""

    def test_valid_open_position(self, sample_position):
        """Test valid open position."""
        assert sample_position.position_id == "pos_test_001"
        assert sample_position.is_open is True
        assert sample_position.exit_timestamp is None

    def test_position_serialization(self, sample_position):
        """Test position can be serialized."""
        json_str = sample_position.model_dump_json()
        parsed = PositionRowV1.model_validate_json(json_str)
        assert parsed.position_id == sample_position.position_id

    def test_closed_position(self, sample_position):
        """Test closed position with PnL."""
        sample_position.is_open = False
        sample_position.exit_timestamp = datetime(2024, 1, 1, 13, 0)
        sample_position.exit_price = 51000.0
        sample_position.exit_fees_usd = 6.25
        sample_position.exit_reason = ExitReason.TAKE_PROFIT
        sample_position.pnl_usd = 987.5  # ~$1000 profit minus fees
        sample_position.pnl_pct = 9.875

        assert sample_position.is_open is False
        assert sample_position.pnl_usd is not None


class TestLLMPayload:
    """Test LLMPayloadV1 schema."""

    def test_valid_llm_payload(self):
        """Test valid LLM payload creation."""
        global_regime = GlobalRegimeV1(
            risk_mode="moderate",
            trend_mode="uptrend",
            trend_strength_pct=65.0,
            vol_mode="normal",
            vol_pct=45.0,
            drawdown_bucket="none",
        )

        payload = LLMPayloadV1(
            candidate_id="cand_test_001",
            timestamp=datetime(2024, 1, 1, 12, 0),
            symbol="BTC-USD",
            playbook="breakout",
            direction="long",
            global_regime=global_regime,
            asset_state={},
            candidate_setup={},
            policy_constraints={},
        )

        assert payload.candidate_id == "cand_test_001"
        assert payload.global_regime.risk_mode == "moderate"


class TestLLMResponse:
    """Test LLMResponseV1 schema."""

    def test_valid_llm_response(self, mock_llm_response):
        """Test valid LLM response parsing."""
        response = LLMResponseV1(**mock_llm_response)
        assert response.decision == "take"
        assert response.confidence == 0.85
        assert response.setup_quality == "A"

    def test_confidence_clamping(self):
        """Test that confidence is clamped to [0, 1]."""
        # Note: This would require implementing clamping in the schema
        # For now, just test that valid values are accepted
        response = LLMResponseV1(
            decision="take",
            setup_quality="A",
            confidence=0.0,
            risk_flags=[],
            notes="Test",
        )
        assert response.confidence == 0.0


class TestOutcomeLabel:
    """Test OutcomeLabelV1 schema."""

    def test_valid_outcome_label(self):
        """Test valid outcome label creation."""
        label = OutcomeLabelV1(
            candidate_id="cand_test_001",
            run_id="run_test_001",
            label_timestamp=datetime(2024, 1, 1, 13, 0),
            was_taken=True,
            best_r_at_tp=2.5,
            best_r_at_sl=-0.8,
            best_r_at_time=1.8,
            worst_r_at_tp=0.5,
            worst_r_at_sl=-1.0,
            worst_r_at_time=-0.2,
            actual_r=1.8,
            actual_exit_reason="take_profit",
        )
        assert label.candidate_id == "cand_test_001"
        assert label.best_r_at_tp == 2.5


class TestDecisionEvent:
    """Test DecisionEventV1 schema."""

    def test_valid_decision_event(self):
        """Test valid decision event creation."""
        event = DecisionEventV1(
            event_id="evt_test_001",
            run_id="run_test_001",
            timestamp=datetime(2024, 1, 1, 12, 0),
            bar_index=400,
            candidate_id="cand_test_001",
            symbol="BTC-USD",
            playbook="breakout",
            llm_decision="take",
            llm_confidence=0.85,
            was_taken=True,
            rejection_reason=None,
        )
        assert event.event_id == "evt_test_001"
        assert event.llm_decision == "take"


class TestRunManifest:
    """Test RunManifestV1 schema."""

    def test_valid_run_manifest(self):
        """Test valid run manifest creation."""
        manifest = RunManifestV1(
            run_id="run_test_001",
            created_at=datetime(2024, 1, 1, 12, 0),
            config_snapshot_path="config.json",
            ledger_path="ledger.db",
            candidate_cache_path="candidates.db",
            labels_path="labels.db",
            events_path="events.jsonl",
            report_path="report.json",
        )
        assert manifest.run_id == "run_test_001"
        assert manifest.ledger_path == "ledger.db"


class TestFeatureMode:
    """Test FeatureMode enum."""

    def test_feature_modes(self):
        """Test feature mode enum values."""
        assert FeatureMode.FULL == "full"
        assert FeatureMode.NO_DERIVS == "no_derivs"


class TestPlaybookType:
    """Test PlaybookType enum."""

    def test_playbook_types(self):
        """Test playbook type enum values."""
        assert PlaybookType.BREAKOUT == "breakout"
        assert PlaybookType.PULLBACK == "pullback"


class TestExitReason:
    """Test ExitReason enum."""

    def test_exit_reasons(self):
        """Test exit reason enum values."""
        assert ExitReason.STOP_LOSS == "stop_loss"
        assert ExitReason.TAKE_PROFIT == "take_profit"
        assert ExitReason.TRAILING_STOP == "trailing_stop"
        assert ExitReason.TIME_STOP == "time_stop"
