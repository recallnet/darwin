"""Response parsing and validation for LLM outputs.

Extracts, validates, and clamps LLM responses against expected schema.
"""

import json
import re
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from darwin.schemas.llm_response import LLMResponseV1


class ParseResult:
    """
    Result of parsing an LLM response.

    Attributes:
        success: True if parsing succeeded.
        response: Parsed LLMResponseV1 if successful, None otherwise.
        error: Error message if parsing failed, None otherwise.
        raw_json: Raw JSON string extracted from response.
    """

    def __init__(
        self,
        success: bool,
        response: Optional[LLMResponseV1] = None,
        error: Optional[str] = None,
        raw_json: Optional[str] = None,
    ):
        self.success = success
        self.response = response
        self.error = error
        self.raw_json = raw_json

    def __repr__(self) -> str:
        if self.success:
            return f"ParseResult(success=True, response={self.response})"
        else:
            return f"ParseResult(success=False, error={self.error})"


def parse_llm_response(raw_response: str) -> ParseResult:
    """
    Parse and validate LLM response.

    Handles:
    - Extracting JSON from text (finds JSON block in response)
    - Validating against LLMResponseV1 schema
    - Clamping confidence to [0, 1]
    - Graceful handling of malformed responses

    Args:
        raw_response: Raw string response from LLM.

    Returns:
        ParseResult with success flag, parsed response or error.

    Example:
        >>> result = parse_llm_response(llm_output)
        >>> if result.success:
        ...     print(f"Decision: {result.response.decision}")
        ... else:
        ...     print(f"Parse error: {result.error}")
    """
    if not raw_response or not raw_response.strip():
        return ParseResult(
            success=False, error="Empty response from LLM", raw_json=None
        )

    # Extract JSON from response
    json_str, extract_error = _extract_json(raw_response)
    if json_str is None:
        return ParseResult(
            success=False,
            error=f"Could not extract JSON: {extract_error}",
            raw_json=None,
        )

    # Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return ParseResult(
            success=False,
            error=f"Invalid JSON: {str(e)}",
            raw_json=json_str,
        )

    # Validate and fix data before pydantic validation
    data = _preprocess_response_data(data)

    # Validate against schema
    try:
        response = LLMResponseV1(**data)
        return ParseResult(success=True, response=response, raw_json=json_str)
    except ValidationError as e:
        return ParseResult(
            success=False,
            error=f"Schema validation failed: {str(e)}",
            raw_json=json_str,
        )


def _extract_json(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract JSON from text response.

    Handles multiple formats:
    - Pure JSON
    - JSON wrapped in ```json ... ```
    - JSON wrapped in ``` ... ```
    - JSON embedded in text

    Returns:
        (json_string, error_message) tuple. One will be None.
    """
    text = text.strip()

    # Try 1: Pure JSON
    if text.startswith("{") and text.endswith("}"):
        return text, None

    # Try 2: Markdown code block with json tag
    pattern_json = r"```json\s*\n(.*?)\n```"
    match = re.search(pattern_json, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip(), None

    # Try 3: Markdown code block without tag
    pattern_generic = r"```\s*\n(.*?)\n```"
    match = re.search(pattern_generic, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if content.startswith("{") and content.endswith("}"):
            return content, None

    # Try 4: Find JSON object anywhere in text
    # Look for { ... } with balanced braces
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == "{":
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                candidate = text[start_idx : i + 1]
                try:
                    json.loads(candidate)  # Validate it's real JSON
                    return candidate, None
                except json.JSONDecodeError:
                    continue

    return None, "No valid JSON found in response"


def _preprocess_response_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preprocess response data before validation.

    Fixes common issues:
    - Clamps confidence to [0, 1]
    - Normalizes decision to lowercase
    - Ensures risk_flags is a list
    - Handles missing optional fields
    """
    # Clamp confidence
    if "confidence" in data:
        try:
            confidence = float(data["confidence"])
            data["confidence"] = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            data["confidence"] = 0.5  # Default to neutral

    # Normalize decision
    if "decision" in data:
        data["decision"] = str(data["decision"]).lower().strip()

    # Ensure risk_flags is a list
    if "risk_flags" not in data:
        data["risk_flags"] = []
    elif not isinstance(data["risk_flags"], list):
        data["risk_flags"] = []

    # Ensure notes is string or None
    if "notes" in data and data["notes"] is not None:
        data["notes"] = str(data["notes"])

    return data


def create_fallback_response(
    decision: str = "skip", reason: str = "fallback_due_to_error"
) -> LLMResponseV1:
    """
    Create a fallback response when LLM fails.

    Args:
        decision: Decision to use ("skip" or "take"). Default is "skip".
        reason: Reason to include in notes.

    Returns:
        LLMResponseV1 with conservative fallback values.

    Example:
        >>> fallback = create_fallback_response("skip", "LLM timeout")
        >>> assert fallback.decision == "skip"
        >>> assert fallback.confidence == 0.0
    """
    return LLMResponseV1(
        decision=decision,
        setup_quality="C",
        confidence=0.0,
        risk_flags=["fallback_used"],
        notes=f"Fallback response: {reason}",
    )


def validate_response_completeness(response: LLMResponseV1) -> Tuple[bool, Optional[str]]:
    """
    Validate that response has all required fields with reasonable values.

    Args:
        response: Parsed LLMResponseV1 to validate.

    Returns:
        (is_valid, error_message) tuple.

    Example:
        >>> valid, error = validate_response_completeness(response)
        >>> if not valid:
        ...     print(f"Response incomplete: {error}")
    """
    # Check decision
    if response.decision not in ["take", "skip"]:
        return False, f"Invalid decision: {response.decision}"

    # Check setup_quality
    if response.setup_quality not in ["A+", "A", "B", "C"]:
        return False, f"Invalid setup_quality: {response.setup_quality}"

    # Check confidence range
    if not 0.0 <= response.confidence <= 1.0:
        return False, f"Confidence out of range: {response.confidence}"

    # Check risk_flags is list
    if not isinstance(response.risk_flags, list):
        return False, "risk_flags must be a list"

    return True, None
