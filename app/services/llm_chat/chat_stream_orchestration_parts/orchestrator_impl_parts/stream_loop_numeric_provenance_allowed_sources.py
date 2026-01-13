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
            if (
                ("Tool Result (" in content)
                or ("פלט כלי (" in content)
                or ("🔧 **פלט כלי" in content)
                or ("תיק פנסיוני (נתונים גולמיים" in content)
                or ("📂 **תיק פנסיוני" in content)
                or ("סיכום נתונים גולמיים" in content)
                or ("סיכום מהיר" in content)
                or ("סה\"כ יתרות" in content)
                or ("תרחישי פרישה" in content)
                or ("📋 **פרטי הלקוח**" in content)
                or ("💰 **סיכום פיננסי**" in content)
                or ("📜 **קיבוע זכויות**" in content)
                or ("פיצויים צבורים" in content)
                or ("יתרת הון פטורה" in content)
                or ("אחוז קצבה פטורה" in content)
                or ("🎯 **תרחישי פרישה" in content)
                or ("📈 **סיכום תרחישים**" in content)
                or ("להלן נתוני הלקוח האמיתיים" in content)
            ):
                allowed_sources.append(content)
    except Exception:
        pass

    return allowed_sources
