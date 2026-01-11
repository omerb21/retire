from app.schemas.llm_chat import ChatMessage, ChatRequest


def _build_allowed_sources_for_numeric_provenance(
    *,
    request: ChatRequest,
    history_messages: list[ChatMessage],
) -> list[str]:
    allowed_sources: list[str] = []
    try:
        for msg in (request.messages or []):
            if getattr(msg, "role", None) == "user":
                allowed_sources.append(getattr(msg, "content", "") or "")
    except Exception:
        pass

    try:
        for msg in (history_messages or []):
            if getattr(msg, "role", None) != "system":
                continue
            content = getattr(msg, "content", "") or ""
            if ("Tool Result (" in content) or ("פלט כלי (" in content):
                allowed_sources.append(content)
    except Exception:
        pass

    return allowed_sources
