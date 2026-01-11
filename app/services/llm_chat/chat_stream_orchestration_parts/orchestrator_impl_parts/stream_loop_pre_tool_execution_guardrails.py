from app.schemas.llm_chat import ChatMessage

from app.services.llm_chat.orchestration_utils import validate_tool_call_protocol_for_execution


def _maybe_apply_pre_tool_execution_guardrails(
    *,
    no_tools_requested: bool,
    is_qa_mode: bool,
    tool_name: str | None,
    full_response: str,
    history_messages: list[ChatMessage],
) -> bool:
    if no_tools_requested:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                    "אסור לבצע TOOL_CALL. החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר, ללא כלים."
                ),
            )
        )
        return True

    if is_qa_mode and tool_name not in {
        "GET_PENSION_PRODUCTS",
        "TRANSFORM_FUNDS_TO_ASSETS",
        "GENERATE_FULL_REPORT",
    }:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: המשתמש ביקש בדיקת מערכת (QA). "
                    "במצב QA אסור להפעיל כלים שמשנים נתונים או עוסקים בתהליכים אחרים. "
                    "כעת עליך לבחור רק אחד מהכלים: GET_PENSION_PRODUCTS, TRANSFORM_FUNDS_TO_ASSETS, GENERATE_FULL_REPORT."
                ),
            )
        )
        return True

    ok, error_msg = validate_tool_call_protocol_for_execution(full_response)
    if not ok:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: אסור לבצע TOOL_CALL כי חסרים שלבי החובה/הפרוטוקול לא תקין. "
                    "כעת החזר רק בלוקים בפורמט: "
                    '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                ),
            )
        )
        return True

    return False
