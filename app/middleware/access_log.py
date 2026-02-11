"""
Pure-ASGI request access logger.

NOT based on BaseHTTPMiddleware — operates at the raw ASGI level so it
cannot be silenced by Starlette's internal error handling.

Logs:
  REQ_IN   – method, path, query string, selected headers
  REQ_OUT  – status code, duration (ms)
  REQ_EX   – if an unhandled exception escapes before a response is sent
"""

import logging
import time
from typing import Any, Callable

_log = logging.getLogger("app.access")


def _extract_headers(scope: dict) -> dict[str, str]:
    """Pull a small subset of headers from the ASGI scope."""
    wanted = {
        b"host", b"x-forwarded-for", b"x-forwarded-proto",
        b"x-railway-request-id", b"x-trace-id",
    }
    out: dict[str, str] = {}
    for raw_name, raw_value in (scope.get("headers") or []):
        if raw_name in wanted:
            out[raw_name.decode("latin-1")] = raw_value.decode("latin-1")
    return out


class AccessLogMiddleware:
    """Pure ASGI middleware — wraps the app without BaseHTTPMiddleware."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        qs = (scope.get("query_string") or b"").decode("latin-1")
        hdrs = _extract_headers(scope)

        _log.info(
            "REQ_IN  %s %s%s hdrs=%s",
            method,
            path,
            f"?{qs}" if qs else "",
            hdrs,
        )

        start = time.perf_counter()
        status_code: int | str = "---"

        async def _send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = message.get("status", "---")
            await send(message)

        try:
            await self.app(scope, receive, _send_wrapper)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            _log.exception(
                "REQ_EX  %s %s status=%s %dms exc=%s",
                method, path, status_code, elapsed_ms, exc,
            )
            raise
        else:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            _log.info(
                "REQ_OUT %s %s status=%s %dms",
                method, path, status_code, elapsed_ms,
            )
