"""The authentication layer: token checking and origin validation.

Every request must carry a token — the one published to the connection file at startup
— and arrive from a same-origin context. Two defenses:

1. The token keeps arbitrary processes from talking to the service. Loopback is not
   enough: a browser can reach 127.0.0.1 freely, which would let any page the user
   visits move files into the library or read it back out.

2. Origin checks keep web contexts from reaching the service even when they somehow
   have the token. A legitimate client is either not a browser (the VSCode extension,
   say) or a page we served ourselves; both are allowed, and everything else is not.

The token is rotated on every startup, so one read from a previous run does not grant
access forever.
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from fileseek.api.models import error_response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response

logger = logging.getLogger(__name__)

TOKEN_HEADER = "X-FileSeek-Token"  # noqa: S105 - a header name, not a password

# Unauthenticated: it reports only whether the service is running.
HEALTH_PATH = "/health"

# Mirrors app.py's INTERNAL_ERROR_MESSAGE: BaseHTTPMiddleware runs call_next in its own
# task, so an exception raised past app.exception_handler(Exception) surfaces here
# instead of at the ASGI boundary. Without this catch it would escape this dispatch
# as a raw exception rather than becoming a 500 response.
INTERNAL_ERROR_MESSAGE = "the request could not be completed; see the service log for details"


def is_same_origin_request(request: Request) -> bool:
    """Whether the request came from our own origin or a non-browser client.

    Browser requests carry Origin (for CORS-triggering methods) or Sec-Fetch-Site (for
    same-origin navigations). If either is present we check it; if both are absent the
    client is not a browser, which is fine — the VSCode extension does not set them.

    A request from a different site gets "cross-site" or an origin that is not ours. A
    request from our own page gets "same-origin" / "same-site" or our own origin. A
    top-level navigation (typing the URL into the address bar) gets "none", which we
    allow since it is a real user action rather than a script.
    """
    origin = request.headers.get("Origin")
    if origin is not None:
        # The origin matches if it is exactly our base URL. We serve on 127.0.0.1,
        # which is distinct from localhost — the browser treats them as separate
        # origins — so the check is literal.
        expected = f"http://{request.url.hostname}:{request.url.port}"
        return origin == expected

    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site is not None:
        # "same-origin" for our own page, "none" for a top-level navigation, both fine.
        # "cross-site" and "same-site" (a different site under the same registrable
        # domain, which does not apply to 127.0.0.1 anyway) are not.
        return fetch_site in {"same-origin", "none"}

    # No browser headers at all: the client is not a browser. That is the extension or
    # the UI hitting us directly, which is what we want.
    return True


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that lack the token or arrive from a foreign origin.

    Every request except the health check must carry the token in X-FileSeek-Token.
    Browser requests must come from the same origin; non-browser requests (the
    extension, the standalone UI) do not carry origin headers and are allowed.

    The middleware runs before routing, so it can protect the entire app in one place
    rather than being scattered across handler decorators.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        expected_token: str,
        health_path: str = HEALTH_PATH,
    ) -> None:
        super().__init__(app)
        self.expected_token = expected_token
        self.health_path = health_path

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # The health check is public — it tells monitoring whether the service is up,
        # which does not need a secret. Everything else requires the token.
        if request.url.path == self.health_path:
            return await call_next(request)

        provided = request.headers.get(TOKEN_HEADER)
        # Constant-time: a plain != returns sooner on an early-differing byte, which
        # leaks the token's prefix to a caller willing to measure.
        if provided is None or not secrets.compare_digest(provided, self.expected_token):
            return JSONResponse(
                error_response("authentication required"),
                status_code=401,
            )

        if not is_same_origin_request(request):
            return JSONResponse(
                error_response("cross-origin requests are not allowed"),
                status_code=403,
            )

        try:
            return await call_next(request)
        except Exception:
            # call_next runs the rest of the app in its own task; an exception that
            # reaches here already escaped app.exception_handler(Exception), so this
            # is the last chance to turn it into a 500 instead of a raw ASGI failure.
            logger.exception(
                "unhandled error serving %s %s", request.method, request.url.path
            )
            return JSONResponse(
                error_response(INTERNAL_ERROR_MESSAGE),
                status_code=500,
            )
