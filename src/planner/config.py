"""Runtime configuration, read once from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = frozenset({"1", "true", "yes", "on"})
DEFAULT_MODEL = "gemini-3.1-flash-lite"


def _int(
    env: Mapping[str, str], key: str, default: int, low: int, high: int
) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings."""

    gemini_api_key: str | None = None
    gemini_model: str = DEFAULT_MODEL
    ai_timeout_seconds: int = 12
    rate_limit_per_minute: int = 20
    max_body_bytes: int = 16_384
    trust_proxy: bool = False
    cache_ttl_seconds: int = 3600
    cache_max_entries: int = 256
    timezone: str = "UTC"
    log_level: str = "INFO"

    @property
    def ai_enabled(self) -> bool:
        """True when a Gemini API key is configured."""
        return bool(self.gemini_api_key)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        """Builds settings from environment variables.

        Args:
            env: Mapping to read; defaults to ``os.environ``.

        Returns:
            Validated settings.

        Raises:
            ValueError: If a numeric variable is malformed or out of range.
        """
        e = os.environ if env is None else env
        key = (e.get("GEMINI_API_KEY") or e.get("GOOGLE_API_KEY") or "").strip()
        return cls(
            gemini_api_key=key or None,
            gemini_model=(e.get("GEMINI_MODEL") or DEFAULT_MODEL).strip(),
            ai_timeout_seconds=_int(e, "AI_TIMEOUT_SECONDS", 12, 1, 60),
            rate_limit_per_minute=_int(e, "RATE_LIMIT_PER_MINUTE", 20, 1, 6000),
            max_body_bytes=_int(e, "MAX_BODY_BYTES", 16_384, 1024, 1_048_576),
            trust_proxy=e.get("TRUST_PROXY", "false").strip().lower() in _TRUE,
            cache_ttl_seconds=_int(e, "CACHE_TTL_SECONDS", 3600, 0, 86_400),
            cache_max_entries=_int(e, "CACHE_MAX_ENTRIES", 256, 1, 100_000),
            timezone=e.get("APP_TIMEZONE", "UTC").strip() or "UTC",
            log_level=e.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
