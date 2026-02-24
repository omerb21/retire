import logging
import time
from typing import Any

logger = logging.getLogger("app.llm_chat")


_TARGET_PATH = "/api/v1/llm/pension-chat-stream"


class StreamTraceLoggerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path") or ""
        if path != _TARGET_PATH:
            return await self.app(scope, receive, send)

        method = scope.get("method") or ""

        trace_id = "unknown"
        railway_request_id = "unknown"
        try:
            headers_list = list(scope.get("headers") or [])
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in headers_list
            }
            trace_id = (headers.get("x-trace-id") or "").strip() or "unknown"
            railway_request_id = (
                headers.get("x-railway-request-id") or ""
            ).strip() or "unknown"
        except Exception:
            pass

        start_ts = time.perf_counter()

        logger.info(
            "pension_chat_stream request_start trace_id=%s railway_request_id=%s method=%s path=%s",
            trace_id,
            railway_request_id,
            method,
            path,
        )

        response_status_code: int | str = "unknown"
        end_logged = False

        async def wrapped_send(message: dict[str, Any]):
            nonlocal response_status_code, end_logged

            if message.get("type") == "http.response.start":
                response_status_code = message.get("status") or "unknown"

            if message.get("type") == "http.response.body":
                more = bool(message.get("more_body"))
                if (not more) and (not end_logged):
                    end_logged = True
                    duration_ms = int((time.perf_counter() - start_ts) * 1000)
                    logger.info(
                        "pension_chat_stream request_end trace_id=%s railway_request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
                        trace_id,
                        railway_request_id,
                        method,
                        path,
                        response_status_code,
                        duration_ms,
                    )

            await send(message)

        try:
            return await self.app(scope, receive, wrapped_send)
        except Exception:
            if not end_logged:
                end_logged = True
                duration_ms = int((time.perf_counter() - start_ts) * 1000)
                logger.info(
                    "pension_chat_stream request_end trace_id=%s railway_request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
                    trace_id,
                    railway_request_id,
                    method,
                    path,
                    response_status_code,
                    duration_ms,
                )
            raise
