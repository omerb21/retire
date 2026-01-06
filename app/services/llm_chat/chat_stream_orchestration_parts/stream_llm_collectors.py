import queue
import threading
import time
from typing import Any, Optional


def _collect_llm_response_once(
    timeout_seconds: float,
    *,
    history_messages,
    client_id,
    stream_request_id: str,
    current_step: int,
    logger,
    get_llm_service,
) -> tuple[Optional[str], Optional[str]]:
    out_q: "queue.Queue[tuple[str, Any]]" = queue.Queue(maxsize=1)

    started = time.monotonic()

    def _runner() -> None:
        try:
            buf: list[str] = []
            llm_service = get_llm_service()
            for chunk in llm_service.chat_stream(history_messages, client_id):
                if chunk:
                    buf.append(str(chunk))
            out_q.put(("ok", "".join(buf)))
        except Exception as e:
            out_q.put(("err", e))

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout_seconds)
    elapsed = time.monotonic() - started
    if t.is_alive():
        logger.warning(
            "Public chat LLM call timed out (request_id=%s, client_id=%s, step=%s, elapsed=%.3fs, timeout=%.1fs, stream=%s)",
            stream_request_id,
            client_id,
            current_step,
            elapsed,
            timeout_seconds,
            True,
        )
        return None, f"timeout_after_{timeout_seconds}s"
    try:
        status, payload = out_q.get_nowait()
    except Exception:
        logger.warning(
            "Public chat LLM call returned no result (request_id=%s, client_id=%s, step=%s, elapsed=%.3fs, timeout=%.1fs, stream=%s)",
            stream_request_id,
            client_id,
            current_step,
            elapsed,
            timeout_seconds,
            True,
        )
        return None, "no_result"
    if status == "err":
        try:
            logger.warning(
                "Public chat LLM call failed (request_id=%s, client_id=%s, step=%s, elapsed=%.3fs, timeout=%.1fs, stream=%s, error=%s)",
                stream_request_id,
                client_id,
                current_step,
                elapsed,
                timeout_seconds,
                True,
                str(payload) or "llm_error",
            )
            return None, str(payload) or "llm_error"
        except Exception:
            return None, "llm_error"
    try:
        logger.info(
            "Public chat LLM call succeeded (request_id=%s, client_id=%s, step=%s, elapsed=%.3fs, timeout=%.1fs, stream=%s)",
            stream_request_id,
            client_id,
            current_step,
            elapsed,
            timeout_seconds,
            True,
        )
        return str(payload), None
    except Exception:
        return None, "invalid_response"



def _collect_llm_response_with_retry(
    *,
    history_messages,
    client_id,
    stream_request_id: str,
    current_step: int,
    logger,
    get_llm_service,
    get_retry_settings,
) -> tuple[Optional[str], Optional[str]]:
    last_err: Optional[str] = None
    retries, timeout, backoffs = get_retry_settings()
    for attempt in range(max(1, retries)):
        resp, err = _collect_llm_response_once(
            timeout_seconds=timeout,
            history_messages=history_messages,
            client_id=client_id,
            stream_request_id=stream_request_id,
            current_step=current_step,
            logger=logger,
            get_llm_service=get_llm_service,
        )
        if isinstance(resp, str) and resp.strip():
            return resp, None
        last_err = err or "empty_reply"
        if err and ("timeout_after_" in err or err in {"no_result", "llm_error"}):
            try:
                get_llm_service().set_provider("ollama", None)
            except Exception:
                pass
        if attempt < (retries - 1):
            try:
                delay = float(backoffs[attempt]) if attempt < len(backoffs) else float(backoffs[-1])
            except Exception:
                delay = 1.0
            time.sleep(max(0.0, delay))
    return None, last_err
