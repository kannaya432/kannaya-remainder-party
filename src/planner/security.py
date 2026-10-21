"""Security middleware (pure ASGI, so no per-request overhead from wrappers)."""

import contextlib
import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
_STATIC_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware:
    """Adds hardening headers and a request id to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Wraps ``send`` to append headers to the response start."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _STATIC_HEADERS.items():
                    headers[name] = value
                headers["X-Request-ID"] = request_id
                if scope["path"].startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _TooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects request bodies above ``max_bytes`` (declared or streamed)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Checks Content-Length, then counts streamed bytes."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                await self._reject(send, 400, "Invalid Content-Length.")
                return
            if too_big:
                await self._reject(send, 413, "Request body too large.")
                return

        received = 0
        exceeded = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise _TooLarge
            return message

        async def tracking_send(message: Message) -> None:
            # Frameworks may turn the read error into their own 400; once the
            # limit is exceeded, replace whatever they send with a 413.
            nonlocal started
            if exceeded:
                if message["type"] == "http.response.start" and not started:
                    started = True
                    await self._reject(send, 413, "Request body too large.")
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        with contextlib.suppress(_TooLarge):
            await self.app(scope, limited_receive, tracking_send)
        if exceeded and not started:
            await self._reject(send, 413, "Request body too large.")

    @staticmethod
    async def _reject(send: Send, status: int, detail: str) -> None:
        body = f'{{"detail":"{detail}"}}'.encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def client_key(request: Request, trust_proxy: bool) -> str:
    """Identifies the caller for rate limiting.

    Behind exactly one trusted proxy (e.g. Cloud Run) the right-most
    ``X-Forwarded-For`` entry is the address the proxy saw; the left-most
    entries are client-controlled and must not be trusted.
    """
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"
