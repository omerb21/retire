from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.orchestration_utils import build_tax_result_system_message_for_stream


def _stream_maybe_emit_tax_autochain_result(
    *,
    logger,
    req_id: str,
    gross_for_tax,
    tax_result,
    request: ChatRequest,
    history_messages: list[ChatMessage],
):
    if tax_result is not None:
        logger.info(
            "🔗 Force Chaining (Stream): Running GET_TAX_PROJECTION with gross=%s",
            gross_for_tax,
        )
        yield (
            "\n\n🔧 **פלט כלי (הערכת מס - שרשור אוטומטי):**\n"
            f"{tax_result}"
        )
        history_messages.append(
            ChatMessage(
                role="system",
                content=build_tax_result_system_message_for_stream(
                    tax_result
                ),
            )
        )
