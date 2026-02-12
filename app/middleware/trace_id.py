import logging
import traceback as _tb

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.utils.trace_context import generate_trace_id, set_current_trace_id

_logger = logging.getLogger("app.middleware.trace_id")


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-trace-id")
        trace_id = (incoming or "").strip() or generate_trace_id()

        set_current_trace_id(trace_id)

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            _logger.error(
                "TraceIdMiddleware: unhandled error on %s %s: %s\n%s",
                request.method, request.url.path, exc, _tb.format_exc(),
            )
            try:
                from app.services.agent_trace_logger import emit_trace_error
                emit_trace_error(
                    exc=exc,
                    where=f"middleware:TraceIdMiddleware ({request.method} {request.url.path})",
                    endpoint=str(request.url.path),
                )
            except Exception:
                pass
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "path": str(request.url.path),
                },
                headers={"X-Trace-Id": trace_id},
            )
        response.headers["X-Trace-Id"] = trace_id
        return response
