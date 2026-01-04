from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.trace_context import generate_trace_id, set_current_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-trace-id")
        trace_id = (incoming or "").strip() or generate_trace_id()

        set_current_trace_id(trace_id)

        response: Response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
