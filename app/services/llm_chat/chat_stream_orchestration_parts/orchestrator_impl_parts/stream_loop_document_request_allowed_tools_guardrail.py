from app.schemas.llm_chat import ChatMessage


def _maybe_guardrail_document_request_allowed_tools(
    *,
    is_doc_request: bool,
    is_qa_mode: bool,
    is_tax_doc_request: bool,
    current_pension_portfolio,
    tool_name: str | None,
    history_messages: list[ChatMessage],
) -> bool:
    if is_doc_request and not is_qa_mode:
        allowed_doc_tools = {"GENERATE_FULL_REPORT"}
        if isinstance(current_pension_portfolio, list) and current_pension_portfolio:
            allowed_doc_tools.add("TRANSFORM_FUNDS_TO_ASSETS")

        if is_tax_doc_request:
            allowed_doc_tools = {"GENERATE_TAX_DEDUCTION_DOCUMENTS"}
            if (
                isinstance(current_pension_portfolio, list)
                and current_pension_portfolio
            ):
                allowed_doc_tools.add("TRANSFORM_FUNDS_TO_ASSETS")

        if tool_name not in allowed_doc_tools:
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש דוח/מסמך להורדה (ללא QA). "
                        "אסור לבצע פעולות שמשנות נתונים או תהליכים אחרים. "
                        "כעת עליך לבחור רק אחד מהכלים המותרים: "
                        + ", ".join(sorted(allowed_doc_tools))
                        + "."
                    ),
                )
            )
            return True

    return False
