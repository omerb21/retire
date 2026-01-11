from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.chat_orchestration_helpers import build_forced_document_reply
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text


def _stream_maybe_emit_forced_document_reply(
    *,
    tool_name: str,
    tool_result: str,
    history_messages: list[ChatMessage],
):
    forced_document_reply = build_forced_document_reply(
        tool_name=tool_name,
        tool_result=tool_result,
    )

    if forced_document_reply:
        yield "\n\n" + sanitize_user_visible_text(forced_document_reply)
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "המסמך הופק בהצלחה (UI_ACTION כבר נשלח למשתמש). "
                    "כעת עליך להמשיך ולספק תשובת סיכום טקסטואלית מלאה בהתאם לבקשה (למשל QA / PASS/FAIL), "
                    "ולהזכיר בבירור את open_path או קישור הדוח."
                ),
            )
        )
