from app.schemas.llm_chat import ChatMessage


def _maybe_append_missing_required_tools_guardrail(
    *,
    required_tools,
    executed_tools,
    is_tax_doc_request,
    history_messages: list[ChatMessage],
):
    missing_tools_after = required_tools.difference(executed_tools)
    if missing_tools_after:
        preferred_order = ["TRANSFORM_FUNDS_TO_ASSETS"]
        if is_tax_doc_request:
            preferred_order.append("GENERATE_TAX_DEDUCTION_DOCUMENTS")
        else:
            preferred_order.append("GENERATE_FULL_REPORT")
        suggested_tool = next(
            (
                name
                for name in preferred_order
                if name in missing_tools_after
            ),
        )
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: נותרו שלבי חובה לבקשה. "
                    f"כעת עליך להפעיל את הכלי: {suggested_tool}. "
                    "החזר רק בלוקים בפורמט: "
                    '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                ),
            )
        )

    return missing_tools_after
