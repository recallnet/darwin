"""Logging configuration for Darwin."""

import logging
import sys
from pathlib import Path
from typing import Optional


def configure_logging(
    log_file: Optional[Path] = None,
    log_level: str = "INFO",
    console_level: str = "INFO",
) -> None:
    """
    Configure logging for Darwin.

    Sets up both file and console logging with structured format.

    Args:
        log_file: Path to log file. If None, logs to console only.
        log_level: Logging level for file output (default: INFO)
        console_level: Logging level for console output (default: INFO)

    Example:
        >>> from pathlib import Path
        >>> configure_logging(
        ...     log_file=Path("artifacts/runs/run_001/run.log"),
        ...     log_level="DEBUG",
        ...     console_level="INFO"
        ... )
    """
    # Parse log levels
    file_log_level = getattr(logging, log_level.upper(), logging.INFO)
    console_log_level = getattr(logging, console_level.upper(), logging.INFO)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything at root level

    # Clear existing handlers
    root_logger.handlers.clear()

    # Structured format with timestamp, level, module, and message
    log_format = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log_file provided)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(f"Logging configured: file={log_file}, level={log_level}")
    else:
        root_logger.info(f"Logging configured: console only, level={console_level}")

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
