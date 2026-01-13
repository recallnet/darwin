"""Validation utilities for Darwin."""

import logging
from pathlib import Path
from typing import List, Optional

from darwin.schemas.run_config import RunConfigV1

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_run_preflight(
    config: RunConfigV1,
    data_dir: Optional[Path] = None,
    check_llm: bool = True,
    check_data: bool = True,
) -> None:
    """
    Run pre-flight validation checks before starting experiment.

    Validates:
    1. Config consistency
    2. Data availability (if check_data=True)
    3. LLM connectivity (if check_llm=True)

    Args:
        config: Run configuration to validate
        data_dir: Directory containing OHLCV data (required if check_data=True)
        check_llm: Whether to check LLM connectivity (default: True)
        check_data: Whether to check data availability (default: True)

    Raises:
        ValidationError: If any validation check fails

    Example:
        >>> from darwin.schemas.run_config import RunConfigV1
        >>> config = RunConfigV1(...)
        >>> validate_run_preflight(config, data_dir=Path("data"))
    """
    logger.info("Running pre-flight validation...")

    # 1. Check config consistency
    try:
        check_config_consistency(config)
        logger.info("✓ Config consistency check passed")
    except ValidationError as e:
        logger.error(f"✗ Config consistency check failed: {e}")
        raise

    # 2. Check data availability
    if check_data:
        if data_dir is None:
            raise ValidationError("data_dir is required when check_data=True")
        try:
            check_data_availability(config, data_dir)
            logger.info("✓ Data availability check passed")
        except ValidationError as e:
            logger.error(f"✗ Data availability check failed: {e}")
            raise

    # 3. Check LLM connectivity
    if check_llm:
        try:
            check_llm_connectivity(config)
            logger.info("✓ LLM connectivity check passed")
        except ValidationError as e:
            logger.error(f"✗ LLM connectivity check failed: {e}")
            raise

    logger.info("Pre-flight validation passed ✓")


def check_config_consistency(config: RunConfigV1) -> None:
    """
    Check configuration for internal consistency.

    Validates:
    - At least one playbook is enabled
    - Playbook parameters are valid
    - Portfolio settings are consistent
    - Market scope is valid

    Args:
        config: Run configuration

    Raises:
        ValidationError: If configuration is inconsistent
    """
    # Check that at least one playbook is enabled
    enabled_playbooks = [pb for pb in config.playbooks if pb.enabled]
    if not enabled_playbooks:
        raise ValidationError("No playbooks are enabled. At least one playbook must be enabled.")

    # Check symbols
    if not config.market_scope.symbols:
        raise ValidationError("No symbols specified in market_scope")

    # Check playbook exit specs
    for playbook in config.playbooks:
        if playbook.enabled:
            # TP must be > SL
            if playbook.take_profit_atr <= playbook.stop_loss_atr:
                raise ValidationError(
                    f"Playbook {playbook.name}: take_profit_atr ({playbook.take_profit_atr}) "
                    f"must be > stop_loss_atr ({playbook.stop_loss_atr})"
                )

            # Trailing activation should be between SL and TP
            if playbook.trailing_enabled:
                if playbook.trailing_activation_atr < 0:
                    raise ValidationError(
                        f"Playbook {playbook.name}: trailing_activation_atr must be >= 0"
                    )
                if playbook.trailing_activation_atr > playbook.take_profit_atr:
                    logger.warning(
                        f"Playbook {playbook.name}: trailing_activation_atr "
                        f"({playbook.trailing_activation_atr}) > take_profit_atr "
                        f"({playbook.take_profit_atr}). Trailing may never activate."
                    )

    # Check portfolio settings
    if config.portfolio.max_positions < 1:
        raise ValidationError("max_positions must be >= 1")

    if config.portfolio.max_exposure_fraction > 1.0 and not config.portfolio.allow_leverage:
        raise ValidationError(
            f"max_exposure_fraction ({config.portfolio.max_exposure_fraction}) > 1.0 "
            f"requires allow_leverage=true"
        )

    # Check LLM settings
    if config.llm.max_calls_per_minute < 1:
        raise ValidationError("LLM max_calls_per_minute must be >= 1")

    if config.llm.temperature < 0 or config.llm.temperature > 2:
        raise ValidationError(f"LLM temperature ({config.llm.temperature}) must be in [0, 2]")


def check_data_availability(config: RunConfigV1, data_dir: Path) -> None:
    """
    Check that required data is available.

    For now, this is a stub that checks if data_dir exists.
    When replay-lab is integrated, this will check for specific symbol/timeframe data.

    Args:
        config: Run configuration
        data_dir: Directory containing OHLCV data

    Raises:
        ValidationError: If required data is not available
    """
    if not data_dir.exists():
        raise ValidationError(f"Data directory does not exist: {data_dir}")

    if not data_dir.is_dir():
        raise ValidationError(f"Data path is not a directory: {data_dir}")

    # TODO: When replay-lab is integrated, check for specific data files
    # For now, just check that directory exists and is not empty
    data_files = list(data_dir.glob("*"))
    if not data_files:
        logger.warning(f"Data directory is empty: {data_dir}")

    logger.debug(f"Data directory exists: {data_dir} ({len(data_files)} files)")


def check_llm_connectivity(config: RunConfigV1) -> None:
    """
    Check LLM connectivity.

    For now, this is a stub that validates LLM config.
    When LLM backend is integrated, this will make a test call.

    Args:
        config: Run configuration

    Raises:
        ValidationError: If LLM is not reachable
    """
    # Check that provider is supported
    supported_providers = ["anthropic", "openai", "mock"]
    if config.llm.provider not in supported_providers:
        raise ValidationError(
            f"Unsupported LLM provider: {config.llm.provider}. "
            f"Supported: {supported_providers}"
        )

    # Check that model is specified
    if not config.llm.model:
        raise ValidationError("LLM model must be specified")

    # TODO: When LLM backend is integrated, make a test call
    logger.debug(f"LLM config validated: provider={config.llm.provider}, model={config.llm.model}")


def check_path_writable(path: Path) -> None:
    """
    Check that a path is writable.

    Args:
        path: Path to check

    Raises:
        ValidationError: If path is not writable
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Try to create a temporary file
        test_file = path.parent / ".write_test"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise ValidationError(f"Path is not writable: {path}. Error: {e}")
