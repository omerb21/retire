import os
import hmac
from typing import Callable, Awaitable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


SYSTEM_PASSWORD_MAIN_ENV = "SYSTEM_ACCESS_PASSWORD"
SYSTEM_PASSWORD_DEMO_ENV = "SYSTEM_ACCESS_PASSWORD_DEMO"
SYSTEM_PASSWORD_DISABLED_ENV = "SYSTEM_ACCESS_DISABLED"


def is_protection_enabled() -> bool:
    """Return True unless explicitly disabled via env var."""
    return not bool(os.getenv(SYSTEM_PASSWORD_DISABLED_ENV))


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


class SystemAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        if not is_protection_enabled():
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path or ""

        if not path.startswith("/api/"):
            return await call_next(request)

        if path.startswith("/api/v1/public-chat/") and path != "/api/v1/public-chat/topup":
            return await call_next(request)

        header_password = request.headers.get("X-System-Password")
        expected_passwords = get_expected_passwords()

        if not expected_passwords:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "System access password is not configured (set SYSTEM_ACCESS_PASSWORD or SYSTEM_ACCESS_PASSWORD_DEMO).",
                },
            )

        if not header_password or not any(hmac.compare_digest(header_password, p) for p in expected_passwords):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: invalid or missing system access password"},
            )

        return await call_next(request)
