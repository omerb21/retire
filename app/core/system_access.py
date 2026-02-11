import logging
import os
import hmac
import traceback
from typing import Callable, Awaitable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_logger = logging.getLogger("app.middleware.system_access")

SYSTEM_PASSWORD_MAIN_ENV = "SYSTEM_ACCESS_PASSWORD"
SYSTEM_PASSWORD_DEMO_ENV = "SYSTEM_ACCESS_PASSWORD_DEMO"
SYSTEM_PASSWORD_DISABLED_ENV = "SYSTEM_ACCESS_DISABLED"


def is_protection_enabled() -> bool:
    """Return True when system access protection is configured and enabled."""
    if bool(os.getenv(SYSTEM_PASSWORD_DISABLED_ENV)):
        return False
    return bool(get_expected_passwords())


def get_expected_passwords():
    """Return list of all configured valid passwords (main and demo)."""
    passwords = []
    main_password = os.getenv(SYSTEM_PASSWORD_MAIN_ENV)
    demo_password = os.getenv(SYSTEM_PASSWORD_DEMO_ENV)
    if main_password:
        passwords.append(main_password)
    if demo_password:
        passwords.append(demo_password)
    return passwords


def _safe_digest_eq(a: str, b: str) -> bool:
    """Constant-time string comparison via UTF-8 bytes.
    Falls back to False on any encoding / type error so we never crash."""
    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except Exception:
        return False


class SystemAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        try:
            return await self._dispatch_inner(request, call_next)
        except Exception as exc:
            _logger.error(
                "SystemAccessMiddleware unhandled error on %s %s: %s\n%s",
                request.method,
                request.url.path,
                exc,
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"Internal server error: {type(exc).__name__}: {str(exc)[:500]}",
                    "path": str(request.url.path),
                },
            )

    async def _dispatch_inner(self, request: Request, call_next: Callable[[Request], Awaitable]):
        if not is_protection_enabled():
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path or ""

        if not path.startswith("/api/"):
            return await call_next(request)

        if path.startswith("/api/v1/reports/") and path.endswith("/download"):
            return await call_next(request)

        if path.startswith("/api/v1/documents/") and path.endswith("/download"):
            return await call_next(request)

        if path.startswith("/api/v1/fixation/") and path.endswith("/package"):
            return await call_next(request)

        if path.startswith("/api/v1/files"):
            return await call_next(request)

        if path.startswith("/api/v1/public-chat/") and path != "/api/v1/public-chat/topup":
            return await call_next(request)

        try:
            header_password = request.headers.get("X-System-Password")
            expected_passwords = get_expected_passwords()

            if not expected_passwords:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": "System access password is not configured (set SYSTEM_ACCESS_PASSWORD or SYSTEM_ACCESS_PASSWORD_DEMO).",
                    },
                )

            if (not header_password) or (not any(_safe_digest_eq(header_password, p) for p in expected_passwords)):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: invalid or missing system access password"},
                )
        except Exception as pwd_exc:
            _logger.error(
                "SystemAccessMiddleware password check error on %s %s: %s",
                request.method, request.url.path, pwd_exc,
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: password validation failed"},
            )

        return await call_next(request)
