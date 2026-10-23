import json
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from helpers import TODAY, make
from planner.cache import TTLCache
from planner.config import Settings
from planner.engine import build_plan
from planner.ics import _fold, build_ics
from planner.ratelimit import SlidingWindowRateLimiter


def test_vercel_entrypoint_starts_from_bundled_api_package() -> None:
    """The serverless entrypoint must work without the development source path."""
    root = Path(__file__).parents[1]
    code = """
import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient

entrypoint = Path('api/index.py').resolve()
spec = importlib.util.spec_from_file_location('vercel_entry', entrypoint)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
response = TestClient(module.app).get('/api/health')
assert response.status_code == 200
assert response.json()['status'] == 'ok'
"""
    result = subprocess.run(  # noqa: S603 - executable is this test's Python.
        [sys.executable, "-c", code],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_vercel_api_bundle_excludes_duplicate_static_assets() -> None:
    """Vercel requires unique extensionless paths in the API function bundle."""
    api_static = Path(__file__).parents[1] / "api" / "planner" / "static"
    assert not (api_static / "app.css").exists()
    assert not (api_static / "app.js").exists()
    assert not (api_static / "index.html").exists()


def test_pyproject_declares_runtime_dependencies_for_vercel() -> None:
    """Vercel resolves Python dependencies from pyproject.toml."""
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    dependencies = config["project"]["dependencies"]

    assert any(
        dependency.startswith("fastapi==") for dependency in dependencies
    )


def test_vercel_does_not_rewrite_fastapi_routes_to_entrypoint() -> None:
    """The FastAPI preset keeps the original request path for route matching."""
    vercel_json = Path(__file__).parents[1] / "vercel.json"
    config = json.loads(vercel_json.read_text(encoding="utf-8"))

    assert "rewrites" not in config


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_cache_expiry_and_lru() -> None:
    clock = Clock()
    cache: TTLCache[str, int] = TTLCache(2, 10, clock)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # refresh a
    cache.set("c", 3)  # evicts b
    assert cache.get("b") is None and len(cache) == 2
    clock.now = 11
    assert cache.get("a") is None


def test_cache_disabled_with_zero_ttl() -> None:
    cache: TTLCache[str, int] = TTLCache(2, 0)
    cache.set("a", 1)
    assert cache.get("a") is None


def test_rate_limiter_window_and_eviction() -> None:
    clock = Clock()
    rl = SlidingWindowRateLimiter(2, 60, max_keys=2, clock=clock)
    assert rl.check("x") is None and rl.check("x") is None
    wait = rl.check("x")
    assert wait is not None and 0 < wait <= 60
    assert rl.check("y") is None  # other keys unaffected
    clock.now = 61
    assert rl.check("x") is None
    rl.check("z")
    rl.check("w")  # exceeds max_keys, oldest evicted
    assert len(rl._hits) <= 2


def test_settings_defaults_and_overrides() -> None:
    s = Settings.from_env({})
    assert not s.ai_enabled and s.rate_limit_per_minute == 30
    s = Settings.from_env(
        {
            "GOOGLE_API_KEY": " k ",
            "TRUST_PROXY": "TRUE",
            "AI_TIMEOUT_SECONDS": "5",
        }
    )
    assert s.ai_enabled and s.trust_proxy and s.ai_timeout_seconds == 5


@pytest.mark.parametrize(
    "env", [{"AI_TIMEOUT_SECONDS": "abc"}, {"AI_TIMEOUT_SECONDS": "0"}]
)
def test_settings_reject_bad_numbers(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="AI_TIMEOUT_SECONDS"):
        Settings.from_env(env)


def test_ics_is_valid_and_escaped() -> None:
    plan = build_plan(make(title="Priya, Arjun; \\ 💍 " + "x" * 55), TODAY)
    text = build_ics(plan, datetime(2026, 10, 20, tzinfo=UTC))
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith(
        "END:VCALENDAR\r\n"
    )
    assert text.count("BEGIN:VEVENT") == len(plan.timeline)
    assert "\\," in text and "\\;" in text
    for line in text.split("\r\n"):
        assert len(line.encode()) <= 75


def test_fold_never_splits_multibyte_characters() -> None:
    folded = _fold("SUMMARY:" + "క" * 60)
    assert "".join(folded.split("\r\n ")) == "SUMMARY:" + "క" * 60
