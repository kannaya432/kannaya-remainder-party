"""FastAPI application factory."""

import logging
import math
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from planner.budget import classify_tier
from planner.config import Settings
from planner.engine import build_plan
from planner.errors import PlanningError
from planner.ics import build_ics
from planner.ideas import IdeaService, build_idea_service
from planner.models import EventRequest, IdeasResponse, Plan
from planner.ratelimit import SlidingWindowRateLimiter
from planner.security import (
    BodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
    client_key,
)

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


def _errors(items: list[tuple[str, str]]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"errors": [{"field": f, "message": m} for f, m in items]},
    )


def create_app(
    settings: Settings | None = None,
    *,
    idea_service: IdeaService | None = None,
    today: Callable[[], date] | None = None,
) -> FastAPI:
    """Builds the application.

    Args:
        settings: Configuration; defaults to the environment.
        idea_service: Override for tests.
        today: Clock override for tests.

    Returns:
        A configured FastAPI app.
    """
    cfg = settings or Settings.from_env()
    zone = ZoneInfo(cfg.timezone)
    get_today = today or (lambda: datetime.now(zone).date())
    service = idea_service or build_idea_service(cfg)
    limiter = SlidingWindowRateLimiter(cfg.rate_limit_per_minute)

    app = FastAPI(
        title="Celebration & Event Planner",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    # Outermost last: security headers wrap every response, even rejections.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=cfg.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)

    async def enforce_rate_limit(request: Request) -> None:
        retry = limiter.check(client_key(request, cfg.trust_proxy))
        if retry is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment.",
                headers={"Retry-After": str(math.ceil(retry))},
            )

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Deliberately omit the offending input from the response.
        return _errors(
            [
                (
                    ".".join(str(p) for p in e["loc"][1:]) or "body",
                    str(e["msg"]).removeprefix("Value error, "),
                )
                for e in exc.errors()
            ]
        )

    @app.exception_handler(PlanningError)
    async def on_planning_error(_: Request, exc: PlanningError) -> JSONResponse:
        return _errors([("event_date", str(exc))])

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled %s request_id=%s",
            type(exc).__name__,
            request.scope.get("state", {}).get("request_id"),
        )
        return JSONResponse(
            status_code=500, content={"detail": "Something went wrong."}
        )

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {"status": "ok", "ai_enabled": cfg.ai_enabled}

    @app.post(
        "/api/plan",
        response_model=Plan,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def create_plan(body: EventRequest) -> Plan:
        # Deterministic and instant: never waits on the model.
        return build_plan(body, get_today())

    @app.post(
        "/api/ideas",
        response_model=IdeasResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def create_ideas(body: EventRequest) -> IdeasResponse:
        ideas, source = await service.get(body, classify_tier(body))
        return IdeasResponse(
            ideas=ideas, ideas_source=source, generated_at=datetime.now(UTC)
        )

    @app.post("/api/plan.ics", dependencies=[Depends(enforce_rate_limit)])
    async def calendar(body: EventRequest) -> Response:
        plan = build_plan(body, get_today())
        return Response(
            content=build_ics(plan, datetime.now(UTC)),
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="timeline.ics"'
            },
        )

    static_candidates = [
        STATIC_DIR,
        Path.cwd() / "public",
        Path.cwd() / "src" / "planner" / "static",
        Path("/var/task/src/planner/static"),
        Path("/var/task/public"),
    ]
    resolved_static = next((d for d in static_candidates if d.exists()), None)
    if resolved_static is not None:
        app.mount(
            "/",
            StaticFiles(directory=resolved_static, html=True),
            name="static",
        )
    return app
