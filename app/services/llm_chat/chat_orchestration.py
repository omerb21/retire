import json
import logging
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatMessage, ChatRequest, ChatResponse
from app.services.llm_chat.chat_orchestration_helpers import (
    build_forced_document_reply,
    build_pension_portfolio_update_after_transform,
    get_gross_for_tax_chaining,
    maybe_clear_pension_portfolio_after_transform,
    run_tax_projection_autochain,
)
from app.services.llm_chat.chat_stream_orchestration import (
    run_pension_chat_stream as run_pension_chat_stream_impl,
)
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import find_last_user_message
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot_models
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_chat,
    build_tool_call_message_content,
    build_tool_result_system_message_for_chat,
    is_document_request,
    is_no_tools_request,
    is_qa_request,
    is_transform_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_portfolio_breakdown_request,
    parse_tool_call_from_reply,
)
from app.services.llm_chat.tool_execution import execute_tool_call
from app.services.llm_pension_agent_service import pension_llm_service
from app.utils.llm_chat_log import generate_request_id, log_llm_event

logger = logging.getLogger("app.llm_chat")


def _execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
    force_max_exemption: bool = False,
) -> str:
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)
    return execute_tool_call(
        tool_name=tool_name,
        args=args,
        client_id=client_id,
        db=db,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
    )


def run_pension_chat(request: ChatRequest, db: Session) -> ChatResponse:
    request_id = generate_request_id()

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    if request.client_id is not None:
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded

    messages, computed_data = prepare_messages_with_context(request, db)
    original_user_msg = find_last_user_message(request.messages)
    if is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        breakdown = (
            "\n".join(
                build_pension_portfolio_context(
                    portfolio,
                    user_message=original_user_msg,
                    snapshot_at=effective_snapshot_at,
                )
            ).strip()
            if portfolio
            else ""
        )
        if breakdown:
            return ChatResponse(reply=breakdown, computed_data=computed_data)
    is_doc_request = is_document_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = is_no_tools_request(original_user_msg)
    force_max_exemption = is_max_exemption_request(original_user_msg)
    is_net_request = is_net_pension_request(original_user_msg)

    current_pension_portfolio = effective_portfolio

    log_llm_event(
        request_id=request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
    )

    max_steps = 5
    current_step = 0
    final_reply = ""
    forced_user_prefix: str = ""
    qa_summary_required = False
    report_open_path: str | None = None

    while current_step < max_steps:
        logger.info(
            "🔄 Agent Loop Step %d/%d for client %s",
            current_step + 1,
            max_steps,
            request.client_id,
        )

        raw_reply = pension_llm_service.chat(messages, request.client_id)

        lowered = (raw_reply or "").lower()
        has_pass_fail = ("pass" in lowered) or ("fail" in lowered)

        if is_qa_mode and no_tools_requested and not has_pass_fail and "###TOOL_CALL###" not in raw_reply:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                        "אסור להחזיר TOOL_CALL. כעת החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר."
                    ),
                )
            )
            current_step += 1
            continue

        if qa_summary_required and not has_pass_fail and "###TOOL_CALL###" not in raw_reply:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: במצב QA חובה לסיים בתשובת PASS/FAIL וסיכום קצר. "
                        "החזר כעת תשובת PASS או FAIL בלבד + 3-6 שורות סיכום + open_path של הדוח."
                    ),
                )
            )
            current_step += 1
            continue

        if "###TOOL_CALL###" in raw_reply:
            tool_part_for_log = raw_reply.split("###TOOL_CALL###", 1)[1].strip()

            try:
                parsed = parse_tool_call_from_reply(raw_reply)
                if parsed is None:
                    break

                text_part, tool_call_data = parsed
                tool_name = tool_call_data.get("name")
                tool_args = tool_call_data.get("arguments", {})

                if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
                    explicit_transform = is_transform_request(original_user_msg)
                    if (not is_doc_request) and (not is_qa_mode) and (not explicit_transform):
                        messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: אסור לבצע TRANSFORM_FUNDS_TO_ASSETS ללא בקשה מפורשת להמרה, "
                                    "או במסגרת בקשת דוח/QA. כעת המשך ללא TOOL_CALL ותן תשובה טקסטואלית בלבד "
                                    "או בחר כלי אחר שמתאים לבקשה."
                                ),
                            )
                        )
                        current_step += 1
                        continue

                    if (
                        (not isinstance(tool_args, dict))
                        or (not isinstance(tool_args.get("accounts"), list))
                        or (not tool_args.get("accounts"))
                    ):
                        derived_accounts = build_transform_accounts_from_portfolio(
                            current_pension_portfolio
                        )
                        if derived_accounts:
                            tool_args["accounts"] = derived_accounts
                        else:
                            messages.append(
                                ChatMessage(
                                    role="system",
                                    content=(
                                        "אזהרה: TRANSFORM_FUNDS_TO_ASSETS דורש רשימת accounts תקינה. "
                                        "אין accounts ואין pension_portfolio שממנו ניתן לגזור accounts. "
                                        "כעת אל תחזיר TOOL_CALL."
                                    ),
                                )
                            )
                            current_step += 1
                            continue

                if no_tools_requested:
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                                "אסור לבצע TOOL_CALL. החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר, ללא כלים."
                            ),
                        )
                    )
                    current_step += 1
                    continue

                if is_doc_request and not is_qa_mode:
                    allowed_doc_tools = {"GENERATE_FULL_REPORT"}
                    if (
                        isinstance(current_pension_portfolio, list)
                        and current_pension_portfolio
                    ):
                        allowed_doc_tools.add("TRANSFORM_FUNDS_TO_ASSETS")

                    if tool_name not in allowed_doc_tools:
                        messages.append(
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
                        current_step += 1
                        continue

                if is_qa_mode and tool_name not in {
                    "GET_PENSION_PRODUCTS",
                    "TRANSFORM_FUNDS_TO_ASSETS",
                    "GENERATE_FULL_REPORT",
                }:
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש בדיקת מערכת (QA). "
                                "במצב QA אסור להפעיל כלים שמשנים נתונים או עוסקים בתהליכים אחרים. "
                                "כעת עליך לבחור רק אחד מהכלים: GET_PENSION_PRODUCTS, TRANSFORM_FUNDS_TO_ASSETS, GENERATE_FULL_REPORT."
                            ),
                        )
                    )
                    current_step += 1
                    continue

                log_llm_event(
                    request_id=request_id,
                    event_type="tool_call",
                    payload={"name": tool_name, "arguments": tool_args},
                    client_id=request.client_id,
                )

                apply_max_exemption_if_requested(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    force_max_exemption=force_max_exemption,
                )

                if text_part:
                    messages.append(ChatMessage(role="assistant", content=text_part))

                tool_msg_content = build_tool_call_message_content(
                    tool_call_data, ensure_ascii=True
                )
                messages.append(ChatMessage(role="assistant", content=tool_msg_content))

                tool_result = _execute_tool_call(
                    tool_name,
                    tool_args,
                    request.client_id,
                    db,
                    pension_portfolio=current_pension_portfolio,
                    force_max_exemption=force_max_exemption,
                )

                portfolio_update_marker = build_pension_portfolio_update_after_transform(
                    tool_name=tool_name,
                    tool_result=tool_result,
                    tool_args=tool_args,
                    current_pension_portfolio=current_pension_portfolio,
                )
                if portfolio_update_marker:
                    forced_user_prefix += portfolio_update_marker

                if is_qa_mode and tool_name == "GENERATE_FULL_REPORT":
                    qa_summary_required = True
                    try:
                        parsed_tool = json.loads(tool_result)
                        report_open_path = parsed_tool.get("open_path")
                    except Exception:
                        report_open_path = report_open_path

                current_pension_portfolio = maybe_clear_pension_portfolio_after_transform(
                    tool_name=tool_name,
                    tool_result=tool_result,
                    current_pension_portfolio=current_pension_portfolio,
                )

                log_llm_event(
                    request_id=request_id,
                    event_type="tool_result",
                    payload={"tool_name": tool_name, "result": tool_result},
                    client_id=request.client_id,
                )

                forced_document_reply = build_forced_document_reply(
                    tool_name=tool_name,
                    tool_result=tool_result,
                )

                if forced_document_reply:
                    if is_doc_request and not is_qa_mode:
                        final_reply = forced_document_reply
                        break

                    forced_user_prefix += forced_document_reply.strip() + "\n\n"
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "המסמך הופק בהצלחה (UI_ACTION כבר נשלח למשתמש). "
                                "כעת עליך להמשיך ולספק תשובת סיכום טקסטואלית מלאה בהתאם לבקשה (למשל QA / PASS/FAIL), "
                                "ולהזכיר בבירור את open_path או קישור הדוח."
                            ),
                        )
                    )

                result_msg = build_tool_result_system_message_for_chat(tool_name, tool_result)
                messages.append(ChatMessage(role="system", content=result_msg))

                original_user_msg = find_last_user_message(request.messages)
                is_net = is_net_pension_request(original_user_msg)

                gross_for_tax = get_gross_for_tax_chaining(
                    is_net=is_net,
                    tool_name=tool_name,
                    tool_result=tool_result,
                )

                logger.info(
                    "🔗 Checking Force Chaining: Tool=%s, IsNet=%s, GrossForTax=%s, Msg='%s'",
                    tool_name,
                    is_net,
                    gross_for_tax,
                    original_user_msg[:50],
                )

                tax_result = run_tax_projection_autochain(
                    gross_for_tax=gross_for_tax,
                    execute_tool_call_fn=lambda name, args: _execute_tool_call(
                        name,
                        args,
                        request.client_id,
                        db,
                        pension_portfolio=current_pension_portfolio,
                        force_max_exemption=force_max_exemption,
                    ),
                )
                if tax_result is not None:
                    logger.info(
                        "🔗 Force Chaining: Running GET_TAX_PROJECTION with gross=%s",
                        gross_for_tax,
                    )
                    tax_msg = build_tax_result_system_message_for_chat(tax_result)
                    messages.append(ChatMessage(role="system", content=tax_msg))

                current_step += 1
                continue

            except json.JSONDecodeError:
                logger.error("Failed to parse TOOL_CALL JSON: %s", tool_part_for_log)
                messages.append(
                    ChatMessage(
                        role="system",
                        content="Error: Invalid JSON in TOOL_CALL. Please try again.",
                    )
                )
                current_step += 1
                continue

        else:
            has_tool_results = any(
                m.role == "system" and "Tool Result (" in m.content for m in messages
            )
            if is_net_request and (not no_tools_requested) and (not has_tool_results):
                warning_msg = (
                    "אזהרה: אסור לך לענות על שאלות נטו/אחרי מס ללא הרצת כלים. "
                    "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                    '###TOOL_CALL### {"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {"retirement_date": "YYYY-MM-DD"}} ללא טקסט נוסף.'
                )
                messages.append(ChatMessage(role="system", content=warning_msg))
                current_step += 1
                continue

            if is_doc_request and not has_tool_results:
                warning_msg = (
                    "אזהרה: המשתמש ביקש דוח/מסמך להורדה. אסור לך להשיב טקסט חופשי או לטעון שהופק דוח ללא הפעלת כלי GENERATE_* "
                    "(למשל GENERATE_FULL_REPORT) והחזרת download_url. התשובה האחרונה שלך בוטלה. "
                    "כעת עליך להחזיר רק בלוק יחיד בפורמט "
                    '###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {}} ללא טקסט נוסף.'
                )
                messages.append(ChatMessage(role="system", content=warning_msg))
                current_step += 1
                continue

            final_reply = raw_reply
            break

    log_llm_event(
        request_id=request_id,
        event_type="final_answer",
        payload=final_reply,
        client_id=request.client_id,
    )

    if current_step >= max_steps:
        final_reply += "\n\n(הערה: עצרתי את רצף הפעולות האוטומטי כדי למנוע לולאה אינסופית)"

    if qa_summary_required:
        lowered_final = (final_reply or "").lower()
        if ("pass" not in lowered_final) and ("fail" not in lowered_final):
            if report_open_path:
                final_reply += (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                final_reply += "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."

    return ChatResponse(reply=forced_user_prefix + final_reply, computed_data=computed_data)


def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    return run_pension_chat_stream_impl(request, db)
