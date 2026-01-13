"""Run configuration schema with comprehensive validation."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DecisionTiming(str, Enum):
    """When trading decisions are made."""

    ON_CLOSE = "on_close"  # Evaluate signal at bar close


class FillTiming(str, Enum):
    """When orders are filled."""

    NEXT_OPEN = "next_open"  # Fill at next bar's open price


class PriceSource(str, Enum):
    """Source of price data."""

    OHLCV = "ohlcv"  # Open, High, Low, Close, Volume


class SlippageModel(str, Enum):
    """Slippage estimation model."""

    STATIC_SPREAD = "static_spread"  # Constant spread per asset
    VOLATILITY_ADJUSTED = "volatility_adjusted"  # Spread + volatility component


class FeatureMode(str, Enum):
    """Feature computation mode."""

    FULL = "full"  # All features including derivatives
    NO_DERIVS = "no_derivs"  # Spot data only


class MarketScopeV1(BaseModel):
    """Market scope configuration."""

    venue: str = Field(default="coinbase", description="Trading venue")
    symbols: List[str] = Field(..., description="List of trading symbols (e.g., ['BTC-USD'])")
    primary_timeframe: str = Field(default="15m", description="Primary timeframe for analysis")
    additional_timeframes: List[str] = Field(
        default_factory=lambda: ["1h", "4h"],
        description="Additional timeframes for context"
    )
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD) or null for all")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD) or null for latest")
    warmup_bars: int = Field(default=400, description="Number of warmup bars required")

    @field_validator("symbols")
    @classmethod
    def symbols_must_be_nonempty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("symbols must not be empty")
        if any(not s.strip() for s in v):
            raise ValueError("symbols must not contain empty strings")
        return v

    @field_validator("warmup_bars")
    @classmethod
    def warmup_bars_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("warmup_bars must be > 0")
        return v


class FeesConfigV1(BaseModel):
    """Fee configuration."""

    maker_bps: float = Field(default=6.0, description="Maker fee in basis points")
    taker_bps: float = Field(default=12.5, description="Taker fee in basis points")

    @field_validator("maker_bps", "taker_bps")
    @classmethod
    def fees_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("fees must be non-negative")
        return v


class PortfolioConfigV1(BaseModel):
    """Portfolio and risk configuration."""

    starting_equity_usd: float = Field(default=10000.0, description="Starting equity in USD")
    max_positions: int = Field(default=3, description="Maximum concurrent positions")
    max_exposure_fraction: float = Field(
        default=1.0, description="Maximum exposure as fraction of equity"
    )
    allow_leverage: bool = Field(default=False, description="Whether leverage is allowed")
    position_size_method: Literal["equal_weight", "risk_parity"] = Field(
        default="equal_weight", description="Position sizing method"
    )
    risk_per_trade_fraction: float = Field(
        default=0.02, description="Risk per trade as fraction of equity (for risk_parity)"
    )

    @field_validator("starting_equity_usd")
    @classmethod
    def starting_equity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("starting_equity_usd must be > 0")
        return v

    @field_validator("max_positions")
    @classmethod
    def max_positions_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_positions must be > 0")
        return v

    @field_validator("max_exposure_fraction")
    @classmethod
    def max_exposure_fraction_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("max_exposure_fraction must be > 0")
        return v

    @field_validator("risk_per_trade_fraction")
    @classmethod
    def risk_per_trade_fraction_must_be_valid(cls, v: float) -> float:
        if v <= 0 or v > 0.5:
            raise ValueError("risk_per_trade_fraction must be between 0 and 0.5")
        return v

    @model_validator(mode="after")
    def validate_exposure_and_leverage(self) -> "PortfolioConfigV1":
        if self.max_exposure_fraction > 1.0 and not self.allow_leverage:
            raise ValueError(
                f"max_exposure_fraction={self.max_exposure_fraction} > 1.0 "
                f"requires allow_leverage=true"
            )
        return self


class LLMConfigV1(BaseModel):
    """LLM configuration."""

    provider: str = Field(default="anthropic", description="LLM provider (e.g., 'anthropic', 'openai')")
    model: str = Field(default="claude-3-sonnet-20240229", description="Model name")
    temperature: float = Field(default=0.0, description="Sampling temperature")
    max_tokens: int = Field(default=500, description="Maximum tokens in response")
    max_calls_per_minute: int = Field(default=50, description="Rate limit for LLM calls")
    max_retries: int = Field(default=3, description="Maximum retry attempts on failure")
    initial_retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    circuit_breaker_threshold: int = Field(
        default=5, description="Consecutive failures before circuit breaker opens"
    )
    fallback_decision: Literal["skip", "take"] = Field(
        default="skip", description="Fallback decision when LLM fails"
    )

    @field_validator("temperature")
    @classmethod
    def temperature_must_be_valid(cls, v: float) -> float:
        if v < 0 or v > 2:
            raise ValueError("temperature must be between 0 and 2")
        return v

    @field_validator("max_tokens")
    @classmethod
    def max_tokens_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_tokens must be > 0")
        return v

    @field_validator("max_calls_per_minute")
    @classmethod
    def max_calls_per_minute_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_calls_per_minute must be > 0")
        return v


class PlaybookConfigV1(BaseModel):
    """Playbook configuration."""

    name: str = Field(..., description="Playbook name ('breakout' or 'pullback')")
    enabled: bool = Field(default=True, description="Whether playbook is enabled")

    # Entry parameters (playbook-specific)
    entry_params: dict = Field(default_factory=dict, description="Entry parameters")

    # Exit parameters
    stop_loss_atr: float = Field(..., description="Stop loss distance in ATR units")
    take_profit_atr: float = Field(..., description="Take profit distance in ATR units")
    time_stop_bars: int = Field(..., description="Time stop in number of bars")
    trailing_enabled: bool = Field(default=True, description="Whether trailing stop is enabled")
    trailing_activation_atr: float = Field(..., description="Profit level to activate trailing (ATR units)")
    trailing_distance_atr: float = Field(..., description="Trailing stop distance in ATR units")

    @field_validator("stop_loss_atr", "take_profit_atr", "trailing_activation_atr", "trailing_distance_atr")
    @classmethod
    def atr_values_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("ATR-based values must be > 0")
        return v

    @field_validator("time_stop_bars")
    @classmethod
    def time_stop_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("time_stop_bars must be > 0")
        return v

    @model_validator(mode="after")
    def validate_exit_params(self) -> "PlaybookConfigV1":
        if self.take_profit_atr <= self.stop_loss_atr:
            raise ValueError(
                f"take_profit_atr ({self.take_profit_atr}) must be > stop_loss_atr ({self.stop_loss_atr})"
            )
        return self


class RunConfigV1(BaseModel):
    """
    Complete run configuration with comprehensive validation.

    This is the only mutable input to a run. It is:
    - Validated before execution
    - Snapshotted into run folder
    - Never mutated after start
    """

    run_id: str = Field(..., description="Unique run identifier")
    description: str = Field(default="", description="Human-readable description")

    # Market scope
    market_scope: MarketScopeV1 = Field(..., description="Market scope configuration")

    # Fees
    fees: FeesConfigV1 = Field(default_factory=FeesConfigV1, description="Fee configuration")

    # Portfolio
    portfolio: PortfolioConfigV1 = Field(
        default_factory=PortfolioConfigV1, description="Portfolio configuration"
    )

    # LLM
    llm: LLMConfigV1 = Field(default_factory=LLMConfigV1, description="LLM configuration")

    # RL (optional)
    rl: Optional["RLConfigV1"] = Field(default=None, description="RL system configuration (optional)")

    # Playbooks
    playbooks: List[PlaybookConfigV1] = Field(..., description="List of playbook configurations")

    # Simulation semantics (locked)
    decision_timing: DecisionTiming = Field(
        default=DecisionTiming.ON_CLOSE, description="Decision timing"
    )
    fill_timing: FillTiming = Field(default=FillTiming.NEXT_OPEN, description="Fill timing")
    price_source: PriceSource = Field(default=PriceSource.OHLCV, description="Price source")
    slippage_model: SlippageModel = Field(
        default=SlippageModel.STATIC_SPREAD, description="Slippage model"
    )

    # Features
    feature_mode: FeatureMode = Field(default=FeatureMode.FULL, description="Feature mode")

    # Paths
    artifacts_dir: str = Field(default="artifacts", description="Artifacts directory")

    # Evaluation flags
    generate_plots: bool = Field(default=True, description="Generate plots in reports")
    save_payloads: bool = Field(default=True, description="Save LLM payloads")
    save_responses: bool = Field(default=True, description="Save LLM responses")

    @field_validator("playbooks")
    @classmethod
    def playbooks_must_not_be_empty(cls, v: List[PlaybookConfigV1]) -> List[PlaybookConfigV1]:
        if not v:
            raise ValueError("playbooks must not be empty")
        return v

    @model_validator(mode="after")
    def validate_playbook_names(self) -> "RunConfigV1":
        """Ensure playbook names are valid."""
        valid_names = {"breakout", "pullback"}
        for playbook in self.playbooks:
            if playbook.name not in valid_names:
                raise ValueError(
                    f"Invalid playbook name: {playbook.name}. Must be one of {valid_names}"
                )
        return self

    class Config:
        use_enum_values = True
