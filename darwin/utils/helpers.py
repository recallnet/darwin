"""Helper utilities for Darwin."""

import hashlib
import json
from typing import Any, Dict, Union


def compute_hash(data: Union[str, Dict[str, Any]]) -> str:
    """
    Compute SHA256 hash of data.

    Args:
        data: String or dictionary to hash. Dictionaries are JSON-serialized first.

    Returns:
        Hexadecimal hash string

    Example:
        >>> compute_hash("hello world")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
        >>> compute_hash({"foo": "bar"})
        '7a38bf81f383f69433ad6e900d35b3e2385593f76a7b7ab5d4355b8ba41ee24b'
    """
    if isinstance(data, dict):
        # Sort keys for deterministic serialization
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    else:
        serialized = str(data)

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is near zero.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if division is unsafe (default: 0.0)

    Returns:
        numerator / denominator if safe, else default

    Example:
        >>> safe_div(10, 2)
        5.0
        >>> safe_div(10, 0)
        0.0
        >>> safe_div(10, 1e-15, default=-999)
        -999
    """
    if abs(denominator) > 1e-12:
        return numerator / denominator
    return default


def bps(value: float) -> float:
    """
    Convert decimal fraction to basis points.

    Args:
        value: Decimal value (e.g., 0.0125 for 1.25%)

    Returns:
        Value in basis points (e.g., 125.0)

    Example:
        >>> bps(0.0125)
        125.0
        >>> bps(0.005)
        50.0
    """
    return value * 10000.0


def pct(value: float) -> float:
    """
    Convert decimal fraction to percentage.

    Args:
        value: Decimal value (e.g., 0.125 for 12.5%)

    Returns:
        Value in percentage (e.g., 12.5)

    Example:
        >>> pct(0.125)
        12.5
        >>> pct(0.025)
        2.5
    """
    return value * 100.0


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Clamp value to range [min_value, max_value].

    Args:
        value: Value to clamp
        min_value: Minimum bound
        max_value: Maximum bound

    Returns:
        Clamped value

    Example:
        >>> clamp(5, 0, 10)
        5
        >>> clamp(-5, 0, 10)
        0
        >>> clamp(15, 0, 10)
        10
    """
    return max(min_value, min(max_value, value))


def format_usd(value: float, decimals: int = 2) -> str:
    """
    Format value as USD string.

    Args:
        value: Dollar value
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted string (e.g., "$1,234.56")

    Example:
        >>> format_usd(1234.5678)
        '$1,234.57'
        >>> format_usd(-999.99)
        '-$999.99'
    """
    if value < 0:
        return f"-${abs(value):,.{decimals}f}"
    return f"${value:,.{decimals}f}"


def format_pct(value: float, decimals: int = 2, sign: bool = False) -> str:
    """
    Format value as percentage string.

    Args:
        value: Decimal value (e.g., 0.125 for 12.5%)
        decimals: Number of decimal places (default: 2)
        sign: Whether to always show sign (default: False)

    Returns:
        Formatted string (e.g., "12.50%")

    Example:
        >>> format_pct(0.125)
        '12.50%'
        >>> format_pct(0.125, sign=True)
        '+12.50%'
        >>> format_pct(-0.025, decimals=1)
        '-2.5%'
    """
    pct_value = pct(value)
    if sign and pct_value >= 0:
        return f"+{pct_value:.{decimals}f}%"
    return f"{pct_value:.{decimals}f}%"
