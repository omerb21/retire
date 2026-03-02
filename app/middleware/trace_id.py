import json
import logging
import traceback as _tb

from app.services.agent_execution.tool_execution_context import reset_tool_ok_seen
from app.utils.trace_context import generate_trace_id, set_current_trace_id

_logger = logging.getLogger("app.middleware.trace_id")


class TraceIdMiddleware:
    """ASGI middleware.

    NOTE: We intentionally avoid Starlette's BaseHTTPMiddleware because it can
    break ContextVar propagation in streaming responses.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        trace_id = None
        try:
            headers = dict(scope.get("headers") or [])
            incoming = headers.get(b"x-trace-id")
            if incoming is not None:
                try:
                    trace_id = incoming.decode("utf-8", errors="ignore")
                except Exception:
                    trace_id = None
        except Exception:
            trace_id = None

        trace_id = (trace_id or "").strip() or generate_trace_id()
        set_current_trace_id(trace_id)
        try:
            reset_tool_ok_seen()
        except Exception:
            pass

        async def _send_with_trace_id(message):
            if message.get("type") == "http.response.start":
                hdrs = list(message.get("headers") or [])
                hdrs.append((b"x-trace-id", trace_id.encode("utf-8")))
                message["headers"] = hdrs
            await send(message)

        try:
            await self.app(scope, receive, _send_with_trace_id)
        except Exception as exc:
            path = None
            try:
                path = scope.get("path")
            except Exception:
                path = None
            _logger.error(
                "TraceIdMiddleware: unhandled error on %s %s: %s\n%s",
                scope.get("method"),
                path,
                exc,
                _tb.format_exc(),
            )
            try:
                from app.services.agent_trace_logger import emit_trace_error

                emit_trace_error(
                    exc=exc,
                    where=f"middleware:TraceIdMiddleware ({scope.get('method')} {path})",
                    endpoint=str(path or ""),
                )
            except Exception:
                pass

            body = json.dumps(
                {
                    "detail": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "path": str(path or ""),
                },
                ensure_ascii=False,
            ).encode("utf-8")
            await _send_with_trace_id(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"application/json; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": body, "more_body": False})
        finally:
            try:
                set_current_trace_id(None)
            except Exception:
                pass
            try:
                reset_tool_ok_seen()
            except Exception:
                pass
