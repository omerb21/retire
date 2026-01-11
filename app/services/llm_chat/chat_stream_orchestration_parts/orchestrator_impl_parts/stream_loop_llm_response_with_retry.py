from typing import Callable


def _stream_collect_llm_response_with_retry_or_yield_error(
    *,
    collect_llm_response_with_retry: Callable,
    history_messages,
    client_id,
    stream_request_id: str,
    current_step: int,
    logger,
    get_llm_service: Callable,
    get_retry_settings: Callable,
):
    full_response, llm_err = collect_llm_response_with_retry(
        history_messages=history_messages,
        client_id=client_id,
        stream_request_id=stream_request_id,
        current_step=current_step,
        logger=logger,
        get_llm_service=get_llm_service,
        get_retry_settings=get_retry_settings,
    )
    if not isinstance(full_response, str) or not full_response.strip():
        logger.error(
            "Public chat LLM call failed (request_id=%s, client_id=%s, step=%s, error=%s)",
            stream_request_id,
            client_id,
            current_step,
            llm_err,
        )
        yield (
            "שגיאה: לא הצלחתי לקבל תשובה מהמערכת כרגע (כשל זמני). "
            "נסה שוב בעוד רגע. "
            f"(request_id: {stream_request_id})"
        )
        return True, full_response

    return False, full_response
