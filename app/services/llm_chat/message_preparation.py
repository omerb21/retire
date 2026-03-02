import logging

from sqlalchemy.orm import Session

from app.schemas.llm_chat import (
    ChatMessage,
    ChatRequest,
    ComputedPensionData,
    PensionPortfolioAccount,
)
from app.services.agent_execution.tool_execution_context import (
    get_current_tool_execution_policy_decision,
)
from app.services.knowledge_base.rag_prompt import build_rag_system_message
from app.services.llm_chat.client_context_builder import build_full_context_for_llm
from app.services.llm_chat.knowledge_snippets import build_knowledge_system_message
from app.services.llm_chat.message_utils import (
    extract_executed_tools_from_history,
    find_last_user_message,
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.prompts import get_global_system_prompt_base
from app.services.llm_chat.state_tools import get_agent_state_json
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

    last_user_msg = _find_last_user_message(request.messages)

    policy_decision = get_current_tool_execution_policy_decision()
    tools_allowed = True
    if policy_decision is not None:
        tools_allowed = bool(getattr(policy_decision, "tools_allowed", True))
    inject_rag = not tools_allowed

    if inject_rag:
        rag_msg = build_rag_system_message(user_message=last_user_msg or "")
        if not rag_msg:
            rag_msg = (
                "ידע מערכת שנשלף מה-Knowledge Base (חובה להשתמש בו):\n"
                "(לא נמצאו מקורות רלוונטיים או שהאינדקס לא זמין)\n\n"
                "הנחיות:\n"
                "- לפני כל שימוש בנתוני לקוח או הפעלת כלי, חובה להצליב את הפעולה מול ידע המערכת (RAG) ולצטט את המקור הרלוונטי.\n"
                "- אסור להסתמך על ידע כללי שסותר את המסמכים; אם אין מקורות, ציין זאת במפורש.\n"
                "- אם אתה עומד לבצע TOOL_CALL שמשנה נתונים/מצב, בקש הבהרה/מקור נוסף לפני ביצוע.\n"
            )

        messages.insert(0, ChatMessage(role="system", content=rag_msg))

    # הנחיית בסיס גלובלית לסוכן (אישיות, שימוש בכלים, פורמט תשובה)
    global_system_prompt = get_global_system_prompt_base()

    workflow_example = get_condensed_workflow_example()
    global_system_prompt += workflow_example

    global_system_prompt_insertion_idx = 1 if inject_rag else 0
    messages.insert(
        global_system_prompt_insertion_idx,
        ChatMessage(role="system", content=global_system_prompt),
    )

    if last_user_msg:
        insertion_idx = global_system_prompt_insertion_idx + 1

        relevant_example = get_relevant_example(last_user_msg)
        if relevant_example:
            example_msg = format_example_as_few_shot(relevant_example)
            messages.insert(
                insertion_idx, ChatMessage(role="system", content=example_msg)
            )
            insertion_idx += 1

        if inject_rag:
            knowledge_msg = build_knowledge_system_message(last_user_msg)
            if knowledge_msg:
                messages.insert(
                    insertion_idx, ChatMessage(role="system", content=knowledge_msg)
                )

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

**חשוב:**
1) ענה רק על בסיס הנתונים האמיתיים למעלה. אל תמציא נתונים!
2) לפני כל שימוש בנתוני לקוח או הפעלת כלי, חובה להצליב את הפעולה מול ידע המערכת (RAG) ולצטט את המקור הרלוונטי."""
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
