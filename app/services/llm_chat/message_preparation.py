import logging

from sqlalchemy.orm import Session

from app.schemas.llm_chat import (
    ChatMessage,
    ChatRequest,
    ComputedPensionData,
    PensionPortfolioAccount,
)
from app.services.llm_chat.client_context_builder import build_full_context_for_llm
from app.services.llm_chat.knowledge_snippets import build_knowledge_system_message
from app.services.llm_chat.message_utils import (
    extract_executed_tools_from_history,
    find_last_user_message,
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.prompts import get_global_system_prompt_base
from app.services.llm_chat.state_tools import get_agent_state_json, get_tools_definitions_json
from app.utils.playbook_loader import (
    format_example_as_few_shot,
    get_condensed_workflow_example,
    get_relevant_example,
)

logger = logging.getLogger("app.llm_chat")


MAX_NON_SYSTEM_MESSAGES = 12


def _get_agent_state(client_id: int, db: Session) -> str:
    """
    בונה אובייקט מצב (State) המייצג את הסטטוס הנוכחי של התיק.
    """
    return get_agent_state_json(client_id=client_id, db=db)


def _get_tools_definitions() -> str:
    """
    מחזיר את הגדרות הכלים (Tools) בפורמט JSON Schema.
    """
    return get_tools_definitions_json()


def _build_pension_portfolio_context(
    portfolio: list[PensionPortfolioAccount],
) -> list[str]:
    """
    ממפה את נתוני התיק הפנסיוני מה-UI לפורמט קריא לסוכן.
    מציג רק נתונים גולמיים - הסוכן חייב להריץ חישובים לקבלת קצבה.
    """
    return build_pension_portfolio_context(portfolio)


def _find_last_user_message(messages: list[ChatMessage]) -> str:
    """מוצא את תוכן ההודעה האחרונה שהיא מסוג user."""
    return find_last_user_message(messages)


def _extract_executed_tools_from_history(messages: list[ChatMessage]) -> set[str]:
    """
    מזהה כלים שכבר הופעלו בשיחה הנוכחית לפי הודעות קודמות.
    """
    return extract_executed_tools_from_history(messages)


def prepare_messages_with_context(
    request: ChatRequest, db: Session
) -> tuple[list[ChatMessage], ComputedPensionData | None]:
    """מכין את ההודעות עם הקשר לקוח, מקורות קצבה ותרחישים.

    Returns:
        tuple of (messages, computed_data) where computed_data contains
        pension calculations for direct frontend display.
    """
    messages = list(request.messages)
    computed_pension_data: ComputedPensionData | None = None

    # הנחיית בסיס גלובלית לסוכן (אישיות, שימוש בכלים, פורמט תשובה)
    global_system_prompt = get_global_system_prompt_base()

    workflow_example = get_condensed_workflow_example()
    global_system_prompt += workflow_example

    messages.insert(0, ChatMessage(role="system", content=global_system_prompt))

    last_user_msg = _find_last_user_message(request.messages)
    if last_user_msg:
        relevant_example = get_relevant_example(last_user_msg)
        if relevant_example:
            example_msg = format_example_as_few_shot(relevant_example)
            messages.insert(1, ChatMessage(role="system", content=example_msg))

        knowledge_msg = build_knowledge_system_message(last_user_msg)
        if knowledge_msg:
            insert_idx = 2 if any(m.role == "system" for m in messages[1:2]) else 1
            messages.insert(insert_idx, ChatMessage(role="system", content=knowledge_msg))

    full_context = build_full_context_for_llm(request=request, db=db, messages=messages)
    if full_context:
        user_messages_in_list = [i for i, m in enumerate(messages) if m.role == "user"]
        if user_messages_in_list:
            last_user_idx = user_messages_in_list[-1]
            original_content = messages[last_user_idx].content
            enhanced_content = f"""להלן נתוני הלקוח האמיתיים מהמערכת (חובה להשתמש בהם!):

{full_context}

---
שאלת המשתמש: {original_content}

**חשוב:** ענה רק על בסיס הנתונים האמיתיים למעלה. אל תמציא נתונים!"""
            messages[last_user_idx] = ChatMessage(role="user", content=enhanced_content)
            logger.debug(
                "Enhanced user message with context for client %s: %d chars",
                request.client_id,
                len(enhanced_content),
            )
        else:
            context_msg = ChatMessage(role="system", content=full_context)
            messages = [context_msg, *messages]
            logger.debug(
                "Prepared context for client %s: %d chars",
                request.client_id,
                len(full_context),
            )

    system_messages = [m for m in messages if m.role == "system"]
    non_system_messages = [m for m in messages if m.role != "system"]
    if len(non_system_messages) > MAX_NON_SYSTEM_MESSAGES:
        non_system_messages = non_system_messages[-MAX_NON_SYSTEM_MESSAGES:]
    final_messages = [*system_messages, *non_system_messages]
    return final_messages, computed_pension_data
