from app.models.client import Client
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.message_utils import find_last_user_message


from ..chat_helpers import _user_requested_target_pension_plan


def _maybe_apply_non_tool_response_guardrails(
    *,
    full_response: str,
    request: ChatRequest,
    db,
    history_messages: list[ChatMessage],
    is_qa_mode: bool,
    no_tools_requested: bool,
    required_tools: set[str],
    executed_tools: set[str],
    is_tax_doc_request: bool,
    qa_summary_required: bool,
    is_cashflow_request: bool,
    is_comparison_request: bool,
    is_net_request: bool,
    is_doc_request: bool,
) -> tuple[bool, bool]:
    lowered = (full_response or "").lower()
    has_pass_fail = ("pass" in lowered) or ("fail" in lowered)

    user_msg_for_default_date = find_last_user_message(request.messages) or ""

    if is_qa_mode and no_tools_requested and not has_pass_fail:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                    "אסור להחזיר TOOL_CALL. כעת החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר."
                ),
            )
        )
        return True, has_pass_fail

    missing_tools = required_tools.difference(executed_tools)

    if missing_tools and not no_tools_requested:
        preferred_order = ["TRANSFORM_FUNDS_TO_ASSETS"]
        if is_tax_doc_request:
            preferred_order.append("GENERATE_TAX_DEDUCTION_DOCUMENTS")
        else:
            preferred_order.append("GENERATE_FULL_REPORT")
        suggested_tool = next(
            (name for name in preferred_order if name in missing_tools),
            next(iter(missing_tools)),
        )
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: טרם הושלמו שלבי החובה לבקשה. "
                    f"כעת עליך להפעיל את הכלי: {suggested_tool}. "
                    "החזר רק בלוקים בפורמט: "
                    '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                ),
            )
        )
        return True, has_pass_fail

    if qa_summary_required and not has_pass_fail:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: במצב QA חובה לסיים בתשובת PASS/FAIL וסיכום קצר. "
                    "החזר כעת תשובת PASS או FAIL בלבד + 3-6 שורות סיכום + open_path של הדוח."
                ),
            )
        )
        return True, has_pass_fail

    has_tool_results = any(
        (m.role == "system")
        and (
            ("Tool Result (" in (m.content or ""))
            or ("פלט כלי (" in (m.content or ""))
        )
        for m in history_messages
    )

    if is_cashflow_request and (not no_tools_requested) and (not has_tool_results):
        if _user_requested_target_pension_plan(user_msg_for_default_date):
            warning_msg = (
                "אזהרה: המשתמש ביקש מתווה/תכנית ליעד קצבה עם מספר. אסור לענות ללא הרצת הכלי הייעודי. "
                "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "BUILD_TARGET_PENSION_PLAN", "arguments": {"target_monthly_pension": 28000}} ללא טקסט נוסף.'
            )
            history_messages.append(ChatMessage(role="system", content=warning_msg))
            return True, has_pass_fail

    if is_comparison_request and (not no_tools_requested):
        cashflow_results = sum(
            1
            for m in history_messages
            if (m.role == "system")
            and ("Tool Result (RUN_RETIREMENT_CASHFLOW_ANALYSIS" in m.content)
        )
        if cashflow_results < 2:
            return False, has_pass_fail

    if is_net_request and (not no_tools_requested) and not has_tool_results:
        return False, has_pass_fail

    if is_doc_request and not has_tool_results:
        doc_tool = "GENERATE_TAX_DEDUCTION_DOCUMENTS" if is_tax_doc_request else "GENERATE_FULL_REPORT"
        warning_msg = (
            "אזהרה: המשתמש ביקש דוח/מסמך להורדה. אסור לך להשיב טקסט חופשי או לטעון שהופק מסמך ללא הפעלת כלי GENERATE_* "
            "והחזרת download_url או open_path. התשובה האחרונה שלך בוטלה. "
            "כעת עליך להחזיר רק בלוק יחיד בפורמט "
            f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "{doc_tool}", "arguments": {{}}}} ללא טקסט נוסף.'
        )
        history_messages.append(ChatMessage(role="system", content=warning_msg))
        return True, has_pass_fail

    return False, has_pass_fail
