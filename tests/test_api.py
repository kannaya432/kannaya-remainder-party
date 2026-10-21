from datetime import date

from fastapi.testclient import TestClient

from helpers import TODAY
from planner.app import create_app
from planner.cache import TTLCache
from planner.config import Settings
from planner.ideas import IdeaService

BODY = {
    "event_type": "birthday",
    "title": "Anu turns 5",
    "event_date": "2026-12-05",
    "guest_count": 25,
    "budget": 30000,
    "honoree_age": 5,
    "dietary": ["vegan"],
    "priorities": ["entertainment"],
}


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {
        "status": "ok",
        "ai_enabled": False,
    }


def test_plan_happy_path(client: TestClient) -> None:
    r = client.post("/api/plan", json=BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["ideas_source"] == "curated"
    assert sum(b["amount"] for b in data["plan"]["budget"]) == 30000
    assert data["plan"]["timeline"][-1]["key"] == "event"


def test_security_headers_on_api_and_static(client: TestClient) -> None:
    for r in (client.post("/api/plan", json=BODY), client.get("/")):
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert "script-src 'self'" in r.headers["content-security-policy"]
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert len(r.headers["x-request-id"]) == 32
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_validation_errors_do_not_echo_input(client: TestClient) -> None:
    secret = "SECRET-MARKER" * 10
    r = client.post("/api/plan", json={**BODY, "title": secret})
    assert r.status_code == 422
    assert "SECRET-MARKER" not in r.text
    r = client.post("/api/plan", json={**BODY, "guest_count": "many"})
    assert r.json()["errors"][0]["field"] == "guest_count"


def test_past_date_is_422(client: TestClient) -> None:
    r = client.post("/api/plan", json={**BODY, "event_date": "2020-01-01"})
    assert r.status_code == 422 and "past" in r.json()["errors"][0]["message"]


def test_malformed_json_is_422(client: TestClient) -> None:
    r = client.post(
        "/api/plan",
        content=b"{oops",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422


def test_body_size_limits() -> None:
    c = TestClient(
        create_app(Settings(max_body_bytes=1024), today=lambda: TODAY)
    )
    big = {
        "content": b"x" * 2000,
        "headers": {"content-type": "application/json"},
    }
    assert c.post("/api/plan", **big).status_code == 413

    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(4):
            yield b" " * 600

    r = c.post(
        "/api/plan",
        content=chunks(),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413
    bad = c.post(
        "/api/plan",
        content=b"{}",
        headers={"content-length": "abc", "content-type": "application/json"},
    )
    assert bad.status_code in (400, 422)


def test_rate_limit_returns_429_with_retry_after() -> None:
    c = TestClient(
        create_app(Settings(rate_limit_per_minute=2), today=lambda: TODAY)
    )
    assert [c.post("/api/plan", json=BODY).status_code for _ in range(2)] == [
        200,
        200,
    ]
    r = c.post("/api/plan", json=BODY)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert c.get("/api/health").status_code == 200  # health is not limited


def test_trusted_proxy_uses_rightmost_forwarded_address() -> None:
    c = TestClient(
        create_app(
            Settings(rate_limit_per_minute=1, trust_proxy=True),
            today=lambda: TODAY,
        )
    )
    first = c.post(
        "/api/plan", json=BODY, headers={"x-forwarded-for": "9.9.9.9, 1.1.1.1"}
    )
    spoof = c.post(
        "/api/plan", json=BODY, headers={"x-forwarded-for": "8.8.8.8, 1.1.1.1"}
    )
    other = c.post(
        "/api/plan", json=BODY, headers={"x-forwarded-for": "9.9.9.9, 2.2.2.2"}
    )
    assert (first.status_code, spoof.status_code, other.status_code) == (
        200,
        429,
        200,
    )


def test_ics_endpoint(client: TestClient) -> None:
    r = client.post("/api/plan.ics", json=BODY)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"]
    assert r.text.startswith("BEGIN:VCALENDAR")


def test_unexpected_error_is_generic() -> None:
    class Boom(IdeaService):
        async def get(self, request, tier):  # type: ignore[no-untyped-def]
            raise RuntimeError("secret internals")

    app = create_app(
        Settings(), idea_service=Boom(None, TTLCache(1, 1)), today=lambda: TODAY
    )
    r = TestClient(app, raise_server_exceptions=False).post(
        "/api/plan", json=BODY
    )
    assert r.status_code == 500 and "secret" not in r.text


def test_static_assets_served_and_no_inline_script(client: TestClient) -> None:
    html = client.get("/").text
    assert "<script>" not in html and 'lang="en"' in html
    assert client.get("/app.js").status_code == 200
    assert client.get("/app.css").status_code == 200
    assert client.get("/nope").status_code == 404
    assert date.today()  # keep import used
