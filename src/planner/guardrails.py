"""Deterministic guardrails that run outside the model.

These are defence in depth. The primary controls are structural: strict input
schemas, user text passed as JSON data, schema-constrained model output, and a
curated fallback. Pattern matching alone cannot stop prompt injection, so a
match here only *routes away from the model*; it never blocks the plan.
"""

import re
import secrets

_EMAIL = re.compile(r"\b[\w.%+-]+@[\w-]+(?:\.[\w-]+)+\b")
_API_KEY = re.compile(r"\b(?:AIza[\w-]{35}|sk-[A-Za-z0-9]{20,})\b")
# Digit runs with separators; only redacted when they hold 10+ digits, so
# ordinary dates ("12-11-2026") and small amounts survive.
_NUMBER_RUN = re.compile(r"\+?\d[\d\s().-]{8,}\d")
_MIN_PII_DIGITS = 10

_INJECTION = re.compile(
    r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions|prompts|rules)"
    r"|(?:reveal|print|show|repeat)\s+(?:your\s+|the\s+)?"
    r"(?:system\s+prompt|instructions)"
    r"|you\s+are\s+now\s+"
    r"|developer\s+mode"
    r"|jailbreak",
    re.IGNORECASE,
)


def _redact_number(match: re.Match[str]) -> str:
    digits = sum(ch.isdigit() for ch in match.group())
    return "[number]" if digits >= _MIN_PII_DIGITS else match.group()


def redact_sensitive(text: str) -> str:
    """Masks emails, API keys and phone/card-like numbers.

    Applied to free text before it leaves the service (OWASP LLM02), and to
    model output on the way back.
    """
    text = _EMAIL.sub("[email]", text)
    text = _API_KEY.sub("[key]", text)
    return _NUMBER_RUN.sub(_redact_number, text)


def looks_like_injection(text: str) -> bool:
    """Heuristic check for instruction-override attempts (OWASP LLM01)."""
    return _INJECTION.search(text) is not None


def new_canary() -> str:
    """Returns a per-request random marker for system-prompt leak detection."""
    return f"CANARY_{secrets.token_hex(8)}"
