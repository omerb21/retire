import os
import hmac
from typing import Callable, Awaitable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


SYSTEM_PASSWORD_ENV = "SYSTEM_ACCESS_PASSWORD"


def is_protection_enabled() -> bool:
    password = os.getenv(SYSTEM_PASSWORD_ENV)
    return bool(password)


def get_expected_password() -> str:
    return os.getenv(SYSTEM_PASSWORD_ENV, "")


class SystemAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        if not is_protection_enabled():
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path or ""

        if not path.startswith("/api/"):
            return await call_next(request)

        header_password = request.headers.get("X-System-Password")
        expected = get_expected_password()

        if not header_password or not hmac.compare_digest(header_password, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: invalid or missing system access password"},
            )

        return await call_next(request)
