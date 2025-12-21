import json
import logging
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    build_forced_document_reply,
    build_pension_portfolio_update_after_transform,
    format_transform_result_for_user,
    get_gross_for_tax_chaining,
    maybe_clear_pension_portfolio_after_transform,
    run_tax_projection_autochain,
)
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import find_last_user_message
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_stream,
    build_tool_call_message_content,
    build_tool_result_system_message_for_stream,
    format_tool_output_for_user_stream,
    normalize_retirement_date_if_jan1_placeholder,
    is_document_request,
    is_no_tools_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_qa_request,
    is_transform_request,
    is_portfolio_breakdown_request,
    parse_tool_call_from_reply,
)
from app.services.llm_chat.tool_execution import execute_tool_call
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)
from app.models.client import Client
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


def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    stream_request_id = generate_request_id()

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

        def generate_breakdown():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

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
            yield breakdown or "אין תיק פנסיוני לניתוח."

        return StreamingResponse(generate_breakdown(), media_type="text/plain; charset=utf-8")
    is_net_request = is_net_pension_request(original_user_msg)
    is_doc_request = is_document_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = is_no_tools_request(original_user_msg)
    force_max_exemption = is_max_exemption_request(original_user_msg)
    explicit_transform = is_transform_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)

    def _is_ignore_blocked_text(text: str) -> bool:
        lowered = (text or "").lower()
        return any(
            token in lowered
            for token in (
                "התעלם",
                "להתעלם",
                "דלג",
                "לדלג",
                "המשך",
                "להמשיך",
                "בלי",
            )
        ) and any(
            token in lowered
            for token in (
                "חסומ",
                "פיצויים מעסיק נוכחי",
                "מעסיק נוכחי",
                "רצף זכויות",
                "שלא עברו התחשבנות",
                "התחשבנות",
            )
        )

    wants_ignore_blocked = any(
        _is_ignore_blocked_text(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    log_llm_event(
        request_id=stream_request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    def generate(force_max_exemption_val: bool, req_id: str):
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        current_pension_portfolio = effective_portfolio

        if explicit_transform and (not no_tools_requested) and (not is_doc_request) and (not is_qa_mode):
            derived_accounts = build_transform_accounts_from_portfolio(current_pension_portfolio)
            if not derived_accounts:
                yield (
                    "לא ניתן לבצע המרה כי אין תיק מסלקה/סנאפשוט זמין במערכת (pension_portfolio_snapshot ריק). "
                    "כדי לבצע המרה מלאה צריך קודם לטעון תיק מסלקה כך שיופיע פירוט חשבונות."
                )
                return

            tool_args: dict[str, Any] = {
                "accounts": derived_accounts,
            }
            if wants_ignore_blocked:
                tool_args["ignore_blocked_balances"] = True
                tool_args["skip_non_convertible_accounts"] = True

            log_llm_event(
                request_id=req_id,
                event_type="tool_call",
                payload={"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
                client_id=request.client_id,
                extra={"endpoint": "stream"},
            )

            tool_result = _execute_tool_call(
                "TRANSFORM_FUNDS_TO_ASSETS",
                tool_args,
                request.client_id,
                db,
                pension_portfolio=current_pension_portfolio,
                force_max_exemption=False,
            )

            log_llm_event(
                request_id=req_id,
                event_type="tool_result",
                payload={"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "result": tool_result},
                client_id=request.client_id,
                extra={"endpoint": "stream"},
            )

            portfolio_update_marker = build_pension_portfolio_update_after_transform(
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                tool_result=tool_result,
                tool_args=tool_args,
                current_pension_portfolio=current_pension_portfolio,
            )

            if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
                yield portfolio_update_marker

            yield format_transform_result_for_user(tool_result=tool_result)
            return

        report_open_path: str | None = None
        qa_summary_required = False
        qa_summary_satisfied = False
        executed_tools: set[str] = set()

        required_tools: set[str] = set()
        if not no_tools_requested:
            if is_doc_request:
                required_tools.add("GENERATE_FULL_REPORT")
            if (
                is_doc_request
                and isinstance(current_pension_portfolio, list)
                and current_pension_portfolio
            ):
                required_tools.add("TRANSFORM_FUNDS_TO_ASSETS")

        tool_call_marker = "###TOOL_CALL###"
        max_steps = 5
        current_step = 0

        history_messages: list[ChatMessage] = list(messages)

        if wants_ignore_blocked:
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                        "אל תשאל שוב לאישור על זה. אל תבצע PROCESS_TERMINATION בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                    ),
                )
            )

        while current_step < max_steps:
            current_step += 1
            full_response = ""

            for chunk in pension_llm_service.chat_stream(history_messages, request.client_id):
                full_response += chunk

            if tool_call_marker not in full_response:
                lowered = (full_response or "").lower()
                has_pass_fail = ("pass" in lowered) or ("fail" in lowered)

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
                    continue

                missing_tools = required_tools.difference(executed_tools)

                if missing_tools and not no_tools_requested:
                    preferred_order = [
                        "TRANSFORM_FUNDS_TO_ASSETS",
                        "GENERATE_FULL_REPORT",
                    ]
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
                                "החזר רק בלוק יחיד בפורמט: "
                                '###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                            ),
                        )
                    )
                    continue

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
                    continue

                has_tool_results = any(
                    m.role == "system" and "Tool Result (" in m.content
                    for m in history_messages
                )
                if (
                    is_cashflow_request
                    and (not no_tools_requested)
                    and (not has_tool_results)
                ):
                    warning_msg = (
                        "אזהרה: אסור לך לענות על בקשות חישוב/השוואת קצבה ללא הרצת כלים. "
                        "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        '###TOOL_CALL### {"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {"retirement_date": "YYYY-MM-DD"}} ללא טקסט נוסף.'
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                if is_comparison_request and (not no_tools_requested):
                    cashflow_results = sum(
                        1
                        for m in history_messages
                        if (m.role == "system")
                        and ("Tool Result (RUN_RETIREMENT_CASHFLOW_ANALYSIS" in m.content)
                    )
                    if cashflow_results < 2:
                        warning_msg = (
                            "אזהרה: המשתמש ביקש השוואה בין שני תרחישי פרישה (למשל גיל 68 מול 69). "
                            "אסור לספק תשובה מספרית לפני שתי הרצות של RUN_RETIREMENT_CASHFLOW_ANALYSIS (אחת לכל תרחיש). "
                            "כעת עליך להחזיר רק בלוק יחיד בפורמט "
                            '###TOOL_CALL### {"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {"retirement_date": "YYYY-MM-DD"}} ללא טקסט נוסף.'
                        )
                        history_messages.append(ChatMessage(role="system", content=warning_msg))
                        continue

                if is_net_request and (not no_tools_requested) and not has_tool_results:
                    warning_msg = (
                        "אזהרה: אסור לך לענות על שאלות נטו או אחרי מס ללא הרצת כלים. "
                        "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        '###TOOL_CALL### {"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {"retirement_date": "YYYY-MM-DD"}} ללא טקסט נוסף.'
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                if is_doc_request and not has_tool_results:
                    warning_msg = (
                        "אזהרה: המשתמש ביקש דוח/מסמך להורדה. אסור לך להשיב טקסט חופשי או לטעון שהופק דוח ללא הפעלת כלי GENERATE_* "
                        "(למשל GENERATE_FULL_REPORT) והחזרת download_url או open_path. התשובה האחרונה שלך בוטלה. "
                        "כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        '###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {}} ללא טקסט נוסף.'
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                log_llm_event(
                    request_id=req_id,
                    event_type="final_answer",
                    payload=full_response,
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )
                if qa_summary_required and has_pass_fail:
                    qa_summary_satisfied = True
                yield full_response
                break

            try:
                parsed = parse_tool_call_from_reply(full_response)
                if parsed is None:
                    break

                text_part, tool_data = parsed
                tool_name = tool_data.get("name")
                tool_args = tool_data.get("arguments", {})

                if tool_name == "PROCESS_TERMINATION" and wants_ignore_blocked:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש במפורש להתעלם מיתרות חסומות/עזיבת עבודה ולהמשיך ללא טיפול בעזיבת עבודה. "
                                "אסור לבצע PROCESS_TERMINATION. כעת המשך ללא TOOL_CALL ובחר כלי אחר שמתאים לבקשה."
                            ),
                        )
                    )
                    continue

                if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
                    if (not is_doc_request) and (not is_qa_mode) and (not explicit_transform):
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: אסור לבצע TRANSFORM_FUNDS_TO_ASSETS ללא בקשה מפורשת להמרה, "
                                    "או במסגרת בקשת דוח/QA. כעת המשך ללא TOOL_CALL."
                                ),
                            )
                        )
                        continue

                    derived_accounts = build_transform_accounts_from_portfolio(
                        current_pension_portfolio
                    )
                    if derived_accounts:
                        tool_args_accounts = tool_args.get("accounts") if isinstance(tool_args, dict) else None
                        if not isinstance(tool_args, dict):
                            tool_args = {}
                        if not (isinstance(tool_args_accounts, list) and tool_args_accounts):
                            tool_args["accounts"] = derived_accounts
                        else:
                            def _is_aggregate_account(acc: dict) -> bool:
                                name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
                                number = str(acc.get("account_number") or acc.get("מספר_חשבון") or "")
                                product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
                                return (
                                    name.startswith("Aggregate_")
                                    or number.startswith("AGG-")
                                    or product_type.startswith("aggregate_")
                                )

                            if any(
                                _is_aggregate_account(acc)
                                for acc in tool_args_accounts
                                if isinstance(acc, dict)
                            ):
                                tool_args["accounts"] = derived_accounts
                            else:
                                by_number = {
                                    (acc.get("account_number") or acc.get("מספר_חשבון") or "").strip(): acc
                                    for acc in derived_accounts
                                    if isinstance(acc, dict)
                                }
                                enriched: list[dict] = []
                                for acc in tool_args_accounts:
                                    if not isinstance(acc, dict):
                                        continue
                                    num = (acc.get("account_number") or acc.get("מספר_חשבון") or "").strip()
                                    base = by_number.get(num) if num else None
                                    if base is None:
                                        continue
                                    merged = dict(base or {})
                                    merged.update(acc)
                                    enriched.append(merged)
                                if enriched:
                                    tool_args["accounts"] = enriched
                                else:
                                    tool_args["accounts"] = derived_accounts
                    else:
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: TRANSFORM_FUNDS_TO_ASSETS דורש רשימת accounts תקינה. "
                                    "אין accounts ואין pension_portfolio שממנו ניתן לגזור accounts. "
                                    "כעת אל תחזיר TOOL_CALL."
                                ),
                            )
                        )
                        continue

                    if wants_ignore_blocked:
                        tool_args["ignore_blocked_balances"] = True
                        tool_args["skip_non_convertible_accounts"] = True

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
                    continue

                if is_doc_request and not is_qa_mode:
                    allowed_doc_tools = {"GENERATE_FULL_REPORT"}
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
                        continue

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
                    continue

                log_llm_event(
                    request_id=req_id,
                    event_type="tool_call",
                    payload={"name": tool_name, "arguments": tool_args},
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )

                apply_max_exemption_if_requested(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    force_max_exemption=force_max_exemption_val,
                )

                if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
                    date_str = tool_args.get("retirement_date")
                    if isinstance(date_str, str) and date_str.strip() and request.client_id is not None:
                        client = (
                            db.query(Client)
                            .filter(Client.id == request.client_id)
                            .first()
                        )
                        birth_date = getattr(client, "birth_date", None) if client else None
                        if birth_date is not None:
                            tool_args["retirement_date"] = normalize_retirement_date_if_jan1_placeholder(
                                retirement_date=date_str.strip(),
                                birth_date=birth_date,
                                user_message=original_user_msg,
                            )

                if text_part:
                    history_messages.append(ChatMessage(role="assistant", content=text_part))

                tool_msg_content = build_tool_call_message_content(
                    tool_data, ensure_ascii=False
                )
                history_messages.append(ChatMessage(role="assistant", content=tool_msg_content))

                tool_db = SessionLocal()
                try:
                    tool_result = _execute_tool_call(
                        tool_name,
                        tool_args,
                        request.client_id,
                        tool_db,
                        pension_portfolio=current_pension_portfolio,
                        force_max_exemption=force_max_exemption_val,
                    )

                    if tool_name:
                        executed_tools.add(tool_name)

                    portfolio_update_marker = build_pension_portfolio_update_after_transform(
                        tool_name=tool_name,
                        tool_result=tool_result,
                        tool_args=tool_args,
                        current_pension_portfolio=current_pension_portfolio,
                    )
                    if portfolio_update_marker:
                        yield "\n\n" + portfolio_update_marker

                    missing_tools_after = required_tools.difference(executed_tools)
                    if missing_tools_after:
                        preferred_order = [
                            "TRANSFORM_FUNDS_TO_ASSETS",
                            "GENERATE_FULL_REPORT",
                        ]
                        suggested_tool = next(
                            (name for name in preferred_order if name in missing_tools_after),
                            next(iter(missing_tools_after)),
                        )
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: נותרו שלבי חובה לבקשה. "
                                    f"כעת עליך להפעיל את הכלי: {suggested_tool}. "
                                    "החזר רק בלוק יחיד בפורמט: "
                                    '###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                                ),
                            )
                        )

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

                    forced_document_reply = build_forced_document_reply(
                        tool_name=tool_name,
                        tool_result=tool_result,
                    )

                    if forced_document_reply:
                        yield "\n\n" + forced_document_reply
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

                    user_tool_output = format_tool_output_for_user_stream(
                        tool_name, tool_result
                    )

                    yield f"\n\n🔧 **Tool Output ({tool_name}):**\n{user_tool_output}"

                    log_llm_event(
                        request_id=req_id,
                        event_type="tool_result",
                        payload={"tool_name": tool_name, "result": tool_result},
                        client_id=request.client_id,
                        extra={"endpoint": "stream"},
                    )

                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=build_tool_result_system_message_for_stream(
                                tool_name, tool_result
                            ),
                        )
                    )

                    current_user_msg = find_last_user_message(request.messages)
                    is_net = is_net_pension_request(current_user_msg)
                    is_doc = is_document_request(current_user_msg)

                    logger.info(
                        "🔗 Checking Force Chaining (Stream): Tool=%s, IsNet=%s, Msg='%s'",
                        tool_name,
                        is_net,
                        current_user_msg[:50],
                    )

                    gross_for_tax = get_gross_for_tax_chaining(
                        is_net=is_net,
                        tool_name=tool_name,
                        tool_result=tool_result,
                    )

                    logger.info(
                        "🔗 Force Chaining (Stream): Tool=%s, IsNet=%s, GrossForTax=%s",
                        tool_name,
                        is_net,
                        gross_for_tax,
                    )

                    tax_result = run_tax_projection_autochain(
                        gross_for_tax=gross_for_tax,
                        execute_tool_call_fn=lambda name, args: _execute_tool_call(
                            name,
                            args,
                            request.client_id,
                            tool_db,
                            pension_portfolio=current_pension_portfolio,
                            force_max_exemption=force_max_exemption_val,
                        ),
                    )
                    if tax_result is not None:
                        logger.info(
                            "🔗 Force Chaining (Stream): Running GET_TAX_PROJECTION with gross=%s",
                            gross_for_tax,
                        )
                        yield (
                            "\n\n🔧 **Tool Output (GET_TAX_PROJECTION - Auto-chained):**\n"
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

                finally:
                    tool_db.close()

            except Exception as e:
                logger.error("Stream Tool Execution Failed: %s", e, exc_info=True)
                yield f"\n\n(Error executing tool: {str(e)})"
                break

        if qa_summary_required and not qa_summary_satisfied:
            if report_open_path:
                yield (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                yield "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."

        if not no_tools_requested:
            missing_tools_final = required_tools.difference(executed_tools)
            if missing_tools_final:
                yield (
                    "\n\nFAIL - לא הושלמו שלבי החובה לבקשה. חסרים הכלים: "
                    + ", ".join(sorted(missing_tools_final))
                )

    return StreamingResponse(
        generate(force_max_exemption, stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
