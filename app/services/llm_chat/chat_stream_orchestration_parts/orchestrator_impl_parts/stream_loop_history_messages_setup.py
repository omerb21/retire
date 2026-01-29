from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.intent_classifier import ChatIntent, get_stream_base_system_prompt, get_stream_system_prompt_for_intent
from app.services.llm_chat.execution_only_guard import get_execution_only_system_prompt
from app.services.llm_chat.prompts_stream_retirement_kb import get_stream_professional_system_prompt
 


def _build_history_messages_for_stream(
    *,
    messages: list[ChatMessage],
    exec_only_active: bool,
    resolved_intent,
    tools_disabled_reason: str | None,
    wants_ignore_blocked: bool,
    load_stream_intents_playbook_text,
    get_retirement_kb_for_stream,
):
    history_messages: list[ChatMessage] = list(messages)

    insertion_idx = next(
        (i for i, m in enumerate(history_messages) if getattr(m, "role", None) != "system"),
        len(history_messages),
    )

    if exec_only_active and resolved_intent != ChatIntent.REPORT:
        try:
            if not (
                history_messages
                and getattr(history_messages[0], "role", None) == "system"
                and "מצב: EXECUTION_ONLY" in (getattr(history_messages[0], "content", "") or "")
            ):
                history_messages.insert(
                    0,
                    ChatMessage(role="system", content=get_execution_only_system_prompt()),
                )
        except Exception:
            pass

        insertion_idx = next(
            (
                i
                for i, m in enumerate(history_messages)
                if getattr(m, "role", None) != "system"
            ),
            len(history_messages),
        )

    if resolved_intent in (ChatIntent.NO_TOOLS, ChatIntent.ANALYSIS) or (
        exec_only_active and resolved_intent != ChatIntent.REPORT
    ):
        try:
            kb_text = get_retirement_kb_for_stream()
            if kb_text:
                history_messages.insert(
                    insertion_idx, ChatMessage(role="system", content=kb_text)
                )
                insertion_idx += 1
        except Exception:
            pass

    history_messages.insert(
        insertion_idx,
        ChatMessage(role="system", content=get_stream_base_system_prompt()),
    )
    insertion_idx += 1

    if resolved_intent in (ChatIntent.NO_TOOLS, ChatIntent.ANALYSIS) or (
        exec_only_active and resolved_intent != ChatIntent.REPORT
    ):
        try:
            prof_prompt = get_stream_professional_system_prompt()
            if prof_prompt:
                history_messages.insert(
                    insertion_idx, ChatMessage(role="system", content=prof_prompt)
                )
                insertion_idx += 1
        except Exception:
            pass

    playbook_text = load_stream_intents_playbook_text()
    if playbook_text:
        history_messages.insert(
            insertion_idx, ChatMessage(role="system", content=playbook_text)
        )
        insertion_idx += 1

    if resolved_intent in (ChatIntent.NO_TOOLS, ChatIntent.ANALYSIS):
        intent_system_prompt = get_stream_system_prompt_for_intent(resolved_intent)
        if intent_system_prompt:
            history_messages.insert(
                insertion_idx,
                ChatMessage(role="system", content=intent_system_prompt),
            )
            insertion_idx += 1

    try:
        if (
            (not exec_only_active)
            and (resolved_intent != ChatIntent.REPORT)
            and (tools_disabled_reason == "conceptual")
        ):
            history_messages.insert(
                insertion_idx,
                ChatMessage(
                    role="system",
                    content=(
                        "ענה רק על השאלה האחרונה של המשתמש. "
                        "אל תסכם נושאים אחרים מה־KB. "
                        "ציין במפורש את מונח המפתח שמופיע בשאלה."
                    ),
                ),
            )
            insertion_idx += 1
    except Exception:
        pass

    if wants_ignore_blocked:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                    "אל תשאל שוב לאישור על זה. אל תבצע עזיבת עבודה בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                ),
            )
        )

    return history_messages
