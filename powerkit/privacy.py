"""Privacy helpers for generated PowerKit evidence."""

from __future__ import annotations

import re
from typing import Any


REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(?i)(?:^|[_-])(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|"
    r"secret|authorization|cookie|credential|private[_-]?key)(?:$|[_-])"
)
_SENSITIVE_COLLAPSED_KEYS = {
    "apikey",
    "accesstoken",
    "authtoken",
    "token",
    "password",
    "passwd",
    "secret",
    "clientsecret",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "privatekey",
}

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?is)-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
            r"-----END [A-Z0-9 ]*PRIVATE KEY-----"
        ),
        REDACTED,
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            r"\b(\s*[:=]\s*)([^\s,;]+)"
        ),
        rf"\1\2{REDACTED}",
    ),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"), f"Bearer {REDACTED}"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"), REDACTED),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), REDACTED),
    (re.compile(r"\bAKIA[A-Z0-9]{16}\b"), REDACTED),
    (
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)"),
        "[REDACTED_PHONE]",
    ),
)


def redact_text(value: object) -> str:
    """Redact common credential forms without reading process environment values."""
    text = str(value)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _sensitive_key(value: object) -> bool:
    text = str(value)
    collapsed = re.sub(r"[^a-z0-9]", "", text.lower())
    return bool(_SENSITIVE_KEY.search(text)) or collapsed in _SENSITIVE_COLLAPSED_KEYS


def redact_value(value: Any) -> Any:
    """Recursively redact strings in JSON-compatible explanatory input."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _sensitive_key(key) else redact_value(item)
            for key, item in value.items()
        }
    return value
