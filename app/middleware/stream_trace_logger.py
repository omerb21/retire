import json
import logging
import time
from typing import Any, Callable, Awaitable

from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    is_no_tools_request,
)
from app.utils.trace_context import generate_trace_id


logger = logging.getLogger("app.llm_chat")


_TARGET_PATH = "/api/v1/llm/pension-chat-stream"


def _safe_parse_json_body(raw_body: bytes) -> dict[str, Any] | None:
    if not raw_body:
        return None
    try:
        parsed = json.loads(raw_body)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _extract_last_user_message(body_json: dict[str, Any] | None) -> str | None:
    if not isinstance(body_json, dict):
        return None

    messages = body_json.get("messages")
    if not isinstance(messages, list):
        return None

    last_user: str | None = None
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str) and content.strip():
            last_user = content

    return last_user


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

        headers_list = list(scope.get("headers") or [])
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in headers_list}

        incoming_trace_id = (headers.get("x-trace-id") or "").strip()
        railway_request_id = (headers.get("x-railway-request-id") or "").strip()

        if not incoming_trace_id:
            incoming_trace_id = generate_trace_id()
            try:
                headers_list.append((b"x-trace-id", incoming_trace_id.encode("utf-8")))
                scope["headers"] = headers_list
            except Exception:
                pass

        raw_body_parts: list[bytes] = []
        buffered_messages: list[dict[str, Any]] = []

        more_body = True
        while more_body:
            message = await receive()
            buffered_messages.append(message)
            if message.get("type") != "http.request":
                break
            body = message.get("body") or b""
            if body:
                raw_body_parts.append(body)
            more_body = bool(message.get("more_body"))

        raw_body = b"".join(raw_body_parts)
        body_json = _safe_parse_json_body(raw_body)

        client_id: str | int = "unknown"
        prompt_variant: str = "unknown"
        no_tools_requested: str | bool = "unknown"

        if isinstance(body_json, dict):
            maybe_client_id = body_json.get("client_id")
            if isinstance(maybe_client_id, int):
                client_id = maybe_client_id
            elif isinstance(maybe_client_id, str) and maybe_client_id.strip().isdigit():
                client_id = maybe_client_id.strip()

            maybe_prompt_variant = body_json.get("prompt_variant")
            if isinstance(maybe_prompt_variant, str) and maybe_prompt_variant.strip():
                prompt_variant = maybe_prompt_variant.strip()

            last_user_msg = _extract_last_user_message(body_json)
            if isinstance(last_user_msg, str):
                try:
                    no_tools_requested = is_no_tools_request(last_user_msg)
                except Exception:
                    no_tools_requested = "unknown"

        start_ts = time.perf_counter()

        logger.info(
            "pension_chat_stream request_start trace_id=%s railway_request_id=%s method=%s path=%s client_id=%s no_tools_requested=%s prompt_variant=%s",
            incoming_trace_id or "unknown",
            railway_request_id or "unknown",
            method,
            path,
            client_id,
            no_tools_requested,
            prompt_variant,
        )

        response_status_code: int | str = "unknown"
        response_trace_id: str = ""

        async def replay_receive() -> dict[str, Any]:
            if buffered_messages:
                return buffered_messages.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        async def wrapped_send(message: dict[str, Any]):
            nonlocal response_status_code, response_trace_id

            if message.get("type") == "http.response.start":
                response_status_code = message.get("status") or "unknown"
                resp_headers_list = message.get("headers") or []
                try:
                    resp_headers = {
                        k.decode("latin-1").lower(): v.decode("latin-1")
                        for k, v in resp_headers_list
                    }
                    response_trace_id = (resp_headers.get("x-trace-id") or "").strip()
                except Exception:
                    response_trace_id = ""

            if message.get("type") == "http.response.body":
                more = bool(message.get("more_body"))
                if not more:
                    duration_ms = int((time.perf_counter() - start_ts) * 1000)
                    trace_id = incoming_trace_id or response_trace_id or "unknown"
                    logger.info(
                        "pension_chat_stream request_end trace_id=%s railway_request_id=%s method=%s path=%s status_code=%s duration_ms=%s client_id=%s no_tools_requested=%s prompt_variant=%s",
                        trace_id,
                        railway_request_id or "unknown",
                        method,
                        path,
                        response_status_code,
                        duration_ms,
                        client_id,
                        no_tools_requested,
                        prompt_variant,
                    )

            await send(message)

        return await self.app(scope, replay_receive, wrapped_send)
