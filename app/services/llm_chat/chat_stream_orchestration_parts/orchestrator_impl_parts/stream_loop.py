import json
import logging
import inspect
import importlib
import re
import uuid
import time
import threading
import queue
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    build_forced_document_reply,
    build_pension_portfolio_update_after_commutation,
    build_pension_portfolio_update_after_transform,
    build_transform_accounts_from_target_plan_payload,
    format_transform_result_for_user,
    get_gross_for_tax_chaining,
    build_approval_request_ui_action,
    load_pending_approval_request,
    clear_pending_approval_request,
    load_latest_target_pension_plan,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
)

from datetime import date
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import (
    extract_user_approval_for_tool_call,
    extract_user_cancel_for_tool_call,
    extract_latest_approval_request,
    get_tool_call_approval_signature,
    extract_latest_target_pension_plan_payload,
    extract_target_pension_from_message,
    find_last_user_message,
    is_user_approval_intent_text,
)
from app.services.llm_chat.intent_classifier import (
    ChatIntent,
    detect_intent,
    get_stream_base_system_prompt,
    get_stream_system_prompt_for_intent,
    report_requires_qa_line,
)
from app.guards.advisor_behavior_guard import enforce_behavioral_limits
from app.guards.tool_intent_guard import (
    allow_tools_for_intent,
    get_tools_disabled_reason,
    sanitize_words_only_conceptual,
    sanitize_words_only_output,
)
from app.guards.advice_domain import AdviceDomain
from app.guards.advice_domain_resolver import resolve_advice_domain
from app.guards.orchestration_plan import OrchestrationPlan
from app.guards.orchestration_plan_resolver import resolve_orchestration_plan
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_partial_pension_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_stream,
    build_tool_call_message_content,
    build_tool_result_system_message_for_stream,
    compute_default_retirement_date_for_tool_call,
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    is_document_request,
    is_portfolio_breakdown_request,
    is_tax_documents_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_no_termination_request,
    is_no_tools_request,
    is_portfolio_analysis_request,
    is_process_termination_request,
    is_pension_commutation_request,
    is_qa_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_termination_change_request,
    is_transform_request,
    is_max_capital_request,
    extract_desired_monthly_income_from_text,
    is_data_awareness_request,
    is_list_all_financial_entities_request,
    infer_desired_income_is_net_explicit,
    is_cashflow_missing_income_followup,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_targeted_component_conversion_request,
    normalize_retirement_date_if_jan1_placeholder,
    parse_tool_call_from_reply,
    sanitize_user_visible_text,
)
from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)
from app.services.llm_chat.execution_only_guard import (
    is_execution_only,
    get_execution_only_system_prompt,
    validate_execution_only_output,
    execution_only_blocked,
)
from app.services.llm_chat.prompts_stream_retirement_kb import get_stream_professional_system_prompt
from app.services.llm_chat.execution_only_rewriter import build_exec_only_rewrite_prompt
from app.services.llm_chat.execution_only_fallback import build_execution_only_fallback
from app.models.client import Client
from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.utils.knowledge_loader import get_retirement_kb_for_stream
from app.utils.llm_chat_log import (
    generate_request_id,
    log_llm_event,
    set_current_case_id,
    set_current_request_id,
)
from app.services.llm_agent_tools_service import AgentToolsService
from ..chat_helpers import (
    _digits_only,
    _extract_commutation_account_number,
    _extract_target_monthly_pension,
    _first_name,
    _fmt_money,
    _format_system_results_from_cashflow,
    _infer_target_is_net,
    _infer_target_is_net_explicit,
    _is_ignore_blocked_text,
    _is_system_inventory_request,
    _is_system_results_request,
    _is_target_plan_adjust_followup,
    _is_target_plan_adjust_request,
    _item_to_dict,
    _last_assistant_message_text,
    _user_requested_target_pension_plan,
    _user_wants_full_balance,
)
from ..stream_top_level_helpers import (
    _build_transform_accounts_from_target_plan_payload,
    _get_llm_service,
    _get_retry_settings,
    _get_stream_orchestration_facade,
    _load_latest_pension_portfolio_snapshot_models,
    _store_pending_approval_request,
)
from ..stream_tool_execution import _execute_tool_call
from ..stream_more_nested_helpers import _format_system_inventory_snapshot
from ..stream_formatters import _format_data_awareness_snapshot, _format_list_all_entities
from ..stream_streaming_helpers import _stream_execute_tool_no_approval, _stream_request_approval
from ..stream_llm_collectors import _collect_llm_response_with_retry
from ..stream_commutation_generators import (
    generate_commutation_need_account,
    generate_commutation_need_amount_existing,
    generate_commutation_need_amount,
    generate_commutation_missing,
)
from ..stream_system_prompt_generators import (
    generate_adjust_reply,
    generate_system_results,
    generate_system_inventory,
    generate_data_awareness,
    generate_list_all_entities,
    generate_target_plan,
    generate_cashflow,
)
from ..stream_portfolio_analysis_generators import (
    generate_breakdown,
    generate_portfolio_analysis,
)
from ..stream_approval_generators import (
    generate_forced_approval,
    generate_execute_target_after_termination,
    generate_approval_exec,
)
from .stream_loop_explicit_transform import _stream_handle_explicit_transform
from .stream_loop_commutation_deterministic import _maybe_handle_commutation_deterministic
from .stream_loop_commutation_approval import _stream_maybe_request_commutation_approval
from .stream_loop_cashflow_retirement_date_normalization import _maybe_normalize_cashflow_retirement_date
from .stream_loop_retirement_scenarios_portfolio_analysis import _maybe_prepare_retirement_scenarios_args_for_portfolio_analysis
from .stream_loop_forced_fixation_chain import _stream_run_forced_fixation_chain_if_needed
from .stream_loop_transform_tool_args_accounts_override import _maybe_override_transform_tool_args_accounts
from .stream_loop_missing_required_tools_guardrail import _maybe_append_missing_required_tools_guardrail
from .stream_loop_tax_autochain_output import _stream_maybe_emit_tax_autochain_result
from .stream_loop_forced_document_reply import _stream_maybe_emit_forced_document_reply
from .stream_loop_tax_force_chaining import _maybe_run_tax_force_chaining
from .stream_loop_numeric_provenance_guardrail import _compute_final_out_with_numeric_provenance_guardrail
from .stream_loop_numeric_provenance_allowed_sources import _build_allowed_sources_for_numeric_provenance
from .stream_loop_build_target_pension_plan_guardrail import _maybe_apply_build_target_pension_plan_guardrail
from .stream_loop_mandatory_fixation_chain import _stream_maybe_run_mandatory_fixation_chain
from .stream_loop_ui_action_approval_short_circuit import _stream_maybe_short_circuit_on_ui_action_approval_request
from .stream_loop_document_request_allowed_tools_guardrail import _maybe_guardrail_document_request_allowed_tools
from .stream_loop_transform_funds_to_assets_guardrails import _maybe_guardrail_transform_funds_to_assets
from .stream_loop_pre_tool_execution_guardrails import _maybe_apply_pre_tool_execution_guardrails
from .stream_loop_post_tool_execution_processing import _stream_handle_post_tool_execution_processing
from .stream_loop_non_tool_response_guardrails import _maybe_apply_non_tool_response_guardrails
from .stream_loop_tool_call_preparation import _stream_prepare_tool_call_and_maybe_request_commutation_approval
from .stream_loop_llm_response_with_retry import _stream_collect_llm_response_with_retry_or_yield_error
from .stream_loop_tool_execution_and_processing import _stream_execute_tool_and_process_result
from .stream_loop_approval_cancel_handling import _maybe_handle_approval_or_cancel_flow
from .stream_loop_max_capital_deterministic import _maybe_handle_max_capital_request
from .stream_loop_system_message_injection import (
    _apply_wants_ignore_blocked_and_portfolio_analysis_messages,
)
from .stream_loop_termination_deterministic import _maybe_handle_termination_deterministic
from .stream_loop_analysis_default_retirement_age import _compute_analysis_default_retirement_age
from .stream_loop_fixation_documents_deterministic import _maybe_handle_fixation_documents_deterministic
from .stream_loop_target_plan_deterministic import _maybe_handle_target_plan_deterministic
from .stream_loop_cashflow_deterministic import _maybe_handle_cashflow_deterministic

logger = logging.getLogger("app.llm_chat")

_NO_TOOLS_DECISION_PHRASES: tuple[str, ...] = (
    "האם",
    "תרצה",
    "רוצה",
    "בחר",
    "תעדיף",
    "מעוניין",
    "שאלה אחת",
)

_NO_TOOLS_FIXED_ENDING = "קיבלתי. אפשר להמשיך בהסבר מילולי בלבד על בסיס הנתונים שנשלחו."


def _postprocess_no_tools_user_visible_text(text: str) -> str:
    original = text or ""
    original = "\n".join(
        line
        for line in original.splitlines()
        if ("RAG_RETIREMENT_KB" not in line and "END_RAG_RETIREMENT_KB" not in line)
    )
    out = original.replace("?", "")
    for phrase in _NO_TOOLS_DECISION_PHRASES:
        out = out.replace(phrase, "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.strip()
    if not out.endswith(_NO_TOOLS_FIXED_ENDING):
        out = (out + "\n\n" if out else "") + _NO_TOOLS_FIXED_ENDING
    return out

@lru_cache(maxsize=1)
def _load_stream_intents_playbook_text() -> str | None:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        p = repo_root / "MD" / "docs" / "agent_playbooks" / "pension_chat_stream_playbook_intents.md"
        if not p.exists():
            return None
        txt = p.read_text(encoding="utf-8")
        cleaned = (txt or "").strip()
        return cleaned or None
    except Exception:
        return None

PC_LLM_MAX_RETRIES = 3
PC_LLM_TIMEOUT_SECONDS = 120.0
PC_LLM_BACKOFF_SECONDS = (0.75, 1.5, 3.0)

def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    stream_request_id = generate_request_id()
    set_current_request_id(stream_request_id)

    try:
        object.__setattr__(request, "prompt_variant", "pension_chat_stream_v2")
    except Exception:
        pass

    exec_only_active = is_execution_only(request)

    computed_data = None

    raw_user_msg = find_last_user_message(request.messages)

    try:
        messages, computed_data = prepare_messages_with_context(request=request, db=db)
    except Exception:
        messages = list(request.messages or [])
        computed_data = None

    original_user_msg = raw_user_msg

    def is_advice_request(user_msg: str) -> bool:
        candidate = (user_msg or "").strip()
        if not candidate:
            return False
        return any(
            token in candidate
            for token in (
                "ייעוץ",
                "יעוץ",
                "מה הכי נכון",
                "מה לעשות",
                "מה אתה מציע",
                "תן לי המלצה",
                "המלצה",
                "טיפ כללי",
                "ממליץ",
                "עדיף",
                "כולם עושים ככה",
                "כולם עושים",
                "רואה חשבון אמר לי",
                "אין לי זמן תן תשובה",
                "רק תשובה קצרה",
                "תן לי כיוון",
                "תן כיוון",
                "כיוון",
                "עזוב טפסים",
                "עזוב את זה",
                "עזוב מערכת",
                "כן או לא",
                "נכון או לא נכון",
                "טעות או לא טעות",
                "רק מילה אחת",
                "תענה רק",
                "תגיד רק",
                "רק תגיד",
                "רק תענה",
                "זה נכון",
                "זה לא נכון",
                "זו טעות",
                "לא טעות",
                "זה בסדר",
                "זה לא בסדר",
            )
        )

    def _is_report_request_for_early_block(user_msg: str) -> bool:
        lowered = ((user_msg or "").strip()).lower()
        return any(
            token in lowered
            for token in (
                "דוח",
                'דו"ח',
                "שלח דוח",
                "הפק דוח",
                "pdf",
                "report",
            )
        )

    advice_mode = (not exec_only_active) and is_advice_request(original_user_msg) and (
        not _is_report_request_for_early_block(original_user_msg)
    )

    resolved_intent = detect_intent(original_user_msg)

    advice_domain = AdviceDomain.UNKNOWN
    if advice_mode:
        advice_domain = resolve_advice_domain(original_user_msg or "")

    if advice_mode and advice_domain == AdviceDomain.COMMUTATION:
        def _advice_commutation_questions():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: הבהרה לפני היוון\n\n"
                "כדי להמשיך אני צריך 3 הבהרות קצרות:\n"
                "- איזו קצבה מדובר (שם קצבה או מספר חשבון/תיק ניכויים)\n"
                "- האם הכוונה ל**סכום חד-פעמי** או ל**הפחתה חודשית מהקצבה**\n"
                "- אם יש כמה קצבאות: לאיזו מהן זה מתייחס?\n"
            )

        return StreamingResponse(
            _advice_commutation_questions(),
            media_type="text/plain; charset=utf-8",
        )

    if advice_mode and advice_domain == AdviceDomain.FIXATION:
        def _advice_fixation_checklist():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: בדיקת קיבוע זכויות – שלב אבחון\n\n"
                "בדיקות נדרשות:\n"
                "- האם בוצע קיבוע זכויות בעבר\n"
                "- האם התקבלו מענקי פרישה\n"
                "- האם בוצעו היוונים\n"
                "- האם קיימים טפסי 161 / 161ד\n"
                "- מועד פרישה בפועל\n\n"
                "המשמעות:\n"
                "- בלי הנתונים האלו אי אפשר לקבוע פטור קצבה או מס\n\n"
                "פעולה הבאה:\n"
                "- איסוף נתונים והפקת מסמך קיבוע\n"
            )

        return StreamingResponse(
            _advice_fixation_checklist(),
            media_type="text/plain; charset=utf-8",
        )

    if advice_mode and advice_domain == AdviceDomain.INVESTMENT_RISK:
        def _advice_investment_risk_answer():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: סיכון השקעה בגיל פרישה\n\n"
                "איך סיכון משפיע בגיל פרישה\n"
                "- הסיכון המרכזי הוא תנודתיות סביב נקודת מימוש/משיכה, במיוחד אם מתכננים משיכות בזמן קצר.\n"
                "- ככל שהאופק קצר יותר, תנודות יכולות להכריח שינוי תכנית או דחיית החלטות.\n\n"
                "ההבדל בין תנודתיות לתשואה\n"
                "- תנודתיות מתארת את התזוזה בדרך (עליות/ירידות).\n"
                "- תשואה מתארת את התוצאה לאורך זמן, אך אינה מבטיחה מה יקרה בטווח קצר.\n\n"
                'למה אין מסלול "נכון לכולם"\n'
                "- כי זה תלוי בהרכב מקורות ההכנסה, גמישות תקציבית, צרכים משפחתיים, והיכולת לספוג ירידות.\n\n"
                "מתי כן צריך חישוב\n"
                "- כשיש החלטה אופרטיבית (תזמון משיכה/המרה/שינוי מסלול) או כשיש כמה מקורות הכנסה ורוצים לראות השלכות.\n\n"
                "בלי מספרים. בלי המלצה חד משמעית.\n"
            )

        return StreamingResponse(
            _advice_investment_risk_answer(),
            media_type="text/plain; charset=utf-8",
        )

    if advice_mode and advice_domain == AdviceDomain.TAX_OPTIMIZATION:
        def _advice_tax_mapping_answer():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: תכנון מס בפרישה – מיפוי ראשוני\n\n"
                "מקורות מס עיקריים בפרישה\n"
                "- קצבאות ותשלומים חודשיים\n"
                "- משיכות הון/מענקים בהתאם למקור ולסיווג\n"
                "- אירועים חד-פעמיים (למשל מענקי פרישה/היוון)\n\n"
                "איפה לרוב נשרף כסף\n"
                "- החלטות שמתבצעות בלי לוודא סטטוסים ומסמכים\n"
                "- חוסר עקביות בין גופים/נתונים שמוביל לבחירות לא נכונות\n\n"
                "מה דורש חישוב מדויק\n"
                "- כל החלטה שיש לה רכיב מס בפועל (נטו/ברוטו), במיוחד כשיש שילוב של כמה מקורות\n\n"
                "אילו החלטות בלתי הפיכות\n"
                "- בחירות שמוגשות למסמכי מס/קיבוע/היוון ושמשנות את מצב הזכויות\n"
            )

        return StreamingResponse(
            _advice_tax_mapping_answer(),
            media_type="text/plain; charset=utf-8",
        )

    if advice_mode and advice_domain == AdviceDomain.UNKNOWN:
        def _advice_unknown_domain_questions():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: הבהרה לפני ייעוץ\n\n"
                "כדי לבחור את הזרימה הנכונה אני צריך להבין על מה השאלה: \n"
                "- פיצויים / מענק פרישה\n"
                "- היוון קצבה\n"
                "- קיבוע זכויות / 161ד\n"
                "- סיכון השקעה / מסלול השקעה\n"
                "- תכנון מס\n\n"
                "כתוב משפט קצר עם אחד מהנושאים (אפשר גם לצרף שאלה)."
            )

        return StreamingResponse(
            _advice_unknown_domain_questions(),
            media_type="text/plain; charset=utf-8",
        )

    advice_compensation_mode = advice_mode and (advice_domain == AdviceDomain.COMPENSATION)
    if advice_compensation_mode:
        resolved_intent = ChatIntent.ANALYSIS

    tools_enabled_reason: str | None = None
    tools_disabled_reason: str | None = None
    tools_enabled = allow_tools_for_intent(original_user_msg or "", resolved_intent)
    if advice_compensation_mode:
        tools_enabled = True
    if not tools_enabled:
        tools_enabled_reason = get_tools_disabled_reason(original_user_msg or "", resolved_intent)
        tools_disabled_reason = tools_enabled_reason
        try:
            if tools_enabled_reason is not None:
                object.__setattr__(request, "tools_disabled_reason", tools_enabled_reason)
        except Exception:
            pass
        resolved_intent = ChatIntent.NO_TOOLS

    ui_action_short_circuit_allowed = tools_disabled_reason not in {"conceptual", "conceptual_form"}

    try:
        log_llm_event(
            request_id=stream_request_id,
            event_type="intent_resolution",
            payload={"intent": resolved_intent.value},
            client_id=request.client_id,
            extra={"endpoint": "stream"},
        )
    except Exception:
        pass

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    if request.client_id is not None:
        loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
            try:
                logger.info(
                    "📦 Using DB pension_portfolio_snapshot (client_id=%s, accounts=%s, snapshot_at=%s)",
                    request.client_id,
                    len(effective_portfolio),
                    effective_snapshot_at,
                )
            except Exception:
                pass

    if (
        tools_enabled
        and ui_action_short_circuit_allowed
        and resolved_intent == ChatIntent.REPORT
        and request.client_id is not None
    ):
        lowered_user_msg = (original_user_msg or "").lower()
        wants_pdf = "pdf" in lowered_user_msg
        report_tool_name = "GENERATE_FULL_REPORT"
        report_tool_args: dict[str, Any] = {
            "output_format": "pdf" if wants_pdf else "html",
            "report_type": "full",
        }

        if is_tax_documents_request(original_user_msg):
            report_tool_name = "GENERATE_TAX_DEDUCTION_DOCUMENTS"
            report_tool_args = {"document_type": "fixation_package"}

        def _generate_report_only(req_id: str):
            tool_db = SessionLocal()
            try:
                tool_result = _execute_tool_call(
                    report_tool_name,
                    report_tool_args,
                    request.client_id,
                    tool_db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=False,
                    user_approved=True,
                    request_id=req_id,
                )
            finally:
                tool_db.close()

            status_message: str | None = None
            open_path: str | None = None
            download_url: str | None = None
            try:
                parsed_tool = json.loads(tool_result)
                if isinstance(parsed_tool, dict):
                    open_path = parsed_tool.get("open_path")
                    download_url = parsed_tool.get("download_url")
                    status_message = parsed_tool.get("status_message") or parsed_tool.get(
                        "message"
                    )
            except Exception:
                pass

            actions: list[dict[str, str]] = []
            if isinstance(open_path, str) and open_path.strip():
                actions.append({"type": "navigate", "path": open_path.strip(), "label": "פתח דוח"})
            elif isinstance(download_url, str) and download_url.strip():
                actions.append(
                    {"type": "open_url", "url": download_url.strip(), "label": "פתח להורדה"}
                )
                actions.append(
                    {
                        "type": "navigate",
                        "path": f"/clients/{request.client_id}/reports",
                        "label": "פתח עמוד דוחות",
                    }
                )
            else:
                actions.append(
                    {
                        "type": "navigate",
                        "path": f"/clients/{request.client_id}/reports",
                        "label": "פתח עמוד דוחות",
                    }
                )

            ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
            if isinstance(status_message, str) and status_message.strip():
                ui_payload["status_message"] = status_message.strip()

            yield (
                "###UI_ACTION###"
                + json.dumps(ui_payload, ensure_ascii=False)
                + "###END_UI_ACTION###\n"
            )

            if is_qa_request(original_user_msg) or report_requires_qa_line(original_user_msg):
                yield "\n\nPASS - סיכום QA סופי לאחר יצירת הדוח"

        return StreamingResponse(
            _generate_report_only(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    plan_advice_domain = advice_domain if advice_mode else None
    plan = resolve_orchestration_plan(
        original_user_msg or "",
        resolved_intent,
        bool(tools_enabled),
        plan_advice_domain,
    )

    if plan == OrchestrationPlan.SYSTEM_SNAPSHOT and request.client_id is not None:
        def _generate_orchestration_plan_system_snapshot(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = _execute_tool_call(
                "GET_SYSTEM_STATE_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )
            if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
                yield sanitize_user_visible_text(tool_result)
                return

            yield sanitize_user_visible_text(_format_system_inventory_snapshot(tool_result))

        return StreamingResponse(
            _generate_orchestration_plan_system_snapshot(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    if plan == OrchestrationPlan.FIXATION_STATUS and request.client_id is not None:
        def _generate_orchestration_plan_fixation_status(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = _execute_tool_call(
                "GET_FIXATION_STATUS_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            yield (
                "🔧 **פלט כלי (סטטוס קיבוע זכויות):**\n"
                + sanitize_user_visible_text(tool_result)
                + "\n\n"
            )

            try:
                parsed = json.loads(tool_result) if isinstance(tool_result, str) else {}
            except Exception:
                parsed = {}

            has_prior_fixation = str(parsed.get("has_prior_fixation") or "unknown")
            has_161 = str(parsed.get("has_161") or "unknown")
            has_161d = str(parsed.get("has_161d") or "unknown")
            has_commutation = str(parsed.get("has_commutation") or "unknown")
            has_exempt_grants = str(parsed.get("has_exempt_grants") or "unknown")
            employment_ended = str(parsed.get("employment_ended") or "unknown")
            missing_inputs = parsed.get("missing_inputs") if isinstance(parsed.get("missing_inputs"), list) else []

            def _yn(value: str) -> str:
                v = (value or "").strip().lower()
                if v == "yes":
                    return "כן"
                if v == "no":
                    return "לא"
                return "לא ידוע"

            yield (
                "כותרת: סטטוס קיבוע זכויות במערכת\n\n"
                "מה נמצא:\n"
                f"- קיבוע קודם: {_yn(has_prior_fixation)}\n"
                f"- טופס 161: {_yn(has_161)}\n"
                f"- טופס 161ד: {_yn(has_161d)}\n"
                f"- היוונים: {_yn(has_commutation)}\n"
                f"- מענקים פטורים: {_yn(has_exempt_grants)}\n"
                f"- סטטוס סיום עבודה: {_yn(employment_ended)}\n\n"
                "מה חסר:\n"
            )

            if missing_inputs:
                for item in missing_inputs:
                    if isinstance(item, str) and item.strip():
                        yield f"- {item.strip()}\n"
            else:
                yield "- לא זוהה חוסר נתונים ספציפי\n"

            yield "\nפעולה הבאה במערכת:\n- להשלים את החוסרים ואז להריץ קיבוע/מסמכים בהתאם."

        return StreamingResponse(
            _generate_orchestration_plan_fixation_status(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    if plan == OrchestrationPlan.CASHFLOW_ONLY and request.client_id is not None:
        def _generate_orchestration_plan_cashflow(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            birth_date_for_default_date = None
            gender_for_default_date = None
            try:
                client_obj = db.query(Client).filter(Client.id == request.client_id).first()
                birth_date_for_default_date = getattr(client_obj, "birth_date", None) if client_obj else None
                gender_for_default_date = getattr(client_obj, "gender", None) if client_obj else None
            except Exception:
                birth_date_for_default_date = None
                gender_for_default_date = None

            default_retirement_date = compute_default_retirement_date_for_tool_call(
                birth_date=birth_date_for_default_date,
                gender=gender_for_default_date,
                user_message=original_user_msg or "",
            )

            desired_income = extract_desired_monthly_income_from_text(original_user_msg)
            desired_income_is_net = infer_desired_income_is_net_explicit(original_user_msg)
            if desired_income is not None and desired_income_is_net is None:
                yield (
                    "כדי לבנות תזרים לפי יעד הכנסה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '40 אלף ברוטו'\n"
                    "- '40 אלף נטו'"
                )
                return

            tool_args: dict[str, Any] = {"retirement_date": default_retirement_date}
            if desired_income is not None and desired_income_is_net is not None:
                tool_args["desired_monthly_income"] = float(desired_income)
                tool_args["desired_income_is_net"] = bool(desired_income_is_net)

            force_max_exemption = is_max_exemption_request(original_user_msg)

            tool_name = "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
            tool_result = _execute_tool_call(
                tool_name,
                tool_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=req_id,
            )

            tool_display = get_tool_display_name_hebrew(tool_name)
            user_tool_output = format_tool_output_for_user_stream(tool_name, tool_result)
            yield (
                f"🔧 **פלט כלי ({tool_display}):**\n" + sanitize_user_visible_text(user_tool_output)
            )

            if advice_compensation_mode:
                yield (
                    "\n\n"
                    + "כותרת: סיכום החלטה לגבי פיצויים\n\n"
                    + "מה בדקתי במערכת:\n"
                    + "- תזרים\n"
                    + "- מס\n"
                    + "- יתרות\n"
                    + "- סטטוסים (כולל חסומים) ואירוע סיום עבודה\n\n"
                    + "מה המשמעות של שתי אפשרויות עיקריות:\n"
                    + "- מימוש כהון: שינוי באופי המימוש והנזילות; עשוי להשפיע על רכיבי המס והיתרות שנצפות בדוחות\n"
                    + "- השארה כהמשך קצבתי/אחר: המשך צבירה/תשלום במבנה קצבתי בהתאם להגדרות הקופות והסטטוסים במערכת\n\n"
                    + "מה חסר כדי לתת המלצה סופית (אם חסר):\n"
                    + "- בחירת יעד (נזילות מול קצבה)\n"
                    + "- סטטוס תהליך סיום עבודה ומסמכים נלווים\n"
                    + "- אישור שהנתונים במערכת עדכניים לכל הגופים\n\n"
                    + "פעולה הבאה במערכת:\n"
                    + "- להפיק דוח מסכם מהמערכת כדי לקבל מסמך תומך החלטה על בסיס הנתונים והחישובים שבוצעו\n"
                )
            else:
                yield (
                    "\n\n" + "הפקתי את תוצאות הניתוח מהמערכת. להסבר מילולי בלי מספרים כתוב: הסבר במילים.\n"
                )

        return StreamingResponse(
            _generate_orchestration_plan_cashflow(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and request.client_id is not None and is_data_awareness_request(original_user_msg):
        return StreamingResponse(
            generate_data_awareness(
                computed_data=computed_data,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                effective_snapshot_at=effective_snapshot_at,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and request.client_id is not None and is_list_all_financial_entities_request(original_user_msg):
        return StreamingResponse(
            generate_list_all_entities(
                computed_data=computed_data,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                effective_snapshot_at=effective_snapshot_at,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:

            return StreamingResponse(
                generate_breakdown(
                    computed_data=computed_data,
                    portfolio=portfolio,
                    original_user_msg=original_user_msg,
                    effective_snapshot_at=effective_snapshot_at,
                ),
                media_type="text/plain; charset=utf-8",
            )

    if tools_enabled and is_portfolio_analysis_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:

            return StreamingResponse(
                generate_portfolio_analysis(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    portfolio=portfolio,
                    original_user_msg=original_user_msg,
                    effective_snapshot_at=effective_snapshot_at,
                ),
                media_type="text/plain; charset=utf-8",
            )

    if tools_enabled and request.client_id is not None and _is_system_inventory_request(original_user_msg):
        return StreamingResponse(
            generate_system_inventory(
                computed_data=computed_data,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and request.client_id is not None and _is_system_results_request(original_user_msg):
        return StreamingResponse(
            generate_system_results(
                computed_data=computed_data,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    is_net_request = is_net_pension_request(original_user_msg)
    is_doc_request = is_document_request(original_user_msg)
    is_tax_doc_request = is_tax_documents_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = (resolved_intent == ChatIntent.NO_TOOLS) or is_no_tools_request(original_user_msg)
    if advice_compensation_mode:
        no_tools_requested = False
    force_max_exemption = is_max_exemption_request(original_user_msg)
    commutation_intent = is_pension_commutation_request(original_user_msg)
    explicit_transform = (not commutation_intent) and is_transform_request(original_user_msg)
    explicit_termination = is_process_termination_request(original_user_msg)
    termination_change = is_termination_change_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)
    is_portfolio_analysis = is_portfolio_analysis_request(original_user_msg)

    conceptual_tools_disabled = (
        (tools_disabled_reason in {"conceptual", "conceptual_form"})
        and (resolved_intent != ChatIntent.REPORT)
        and (not exec_only_active)
    )

    lowered_user_msg = (original_user_msg or "").lower()
    wants_capital_transform = (
        (
            ("להון" in lowered_user_msg)
            or ("to capital" in lowered_user_msg)
            or ("הונית" in lowered_user_msg)
            or ("הוני" in lowered_user_msg)
            or ("מקסימום הון" in lowered_user_msg)
        )
        and ("המר" in lowered_user_msg or "המרה" in lowered_user_msg or "convert" in lowered_user_msg or "משיכה" in lowered_user_msg or "משוך" in lowered_user_msg)
    )
    wants_execute_target_plan = (
        "בצע" in lowered_user_msg
        and ("תכנית" in lowered_user_msg or "תוכנית" in lowered_user_msg or "מתווה" in lowered_user_msg)
    )
    wants_fixation_execute = (
        "בצע" in lowered_user_msg
        and ("קיבוע" in lowered_user_msg)
        and ("זכויות" in lowered_user_msg)
    )

    wants_fixation_documents = bool(
        is_tax_doc_request
        and any(token in lowered_user_msg for token in ("קיבוע", "זכויות", "161ד", "161d"))
    )

    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)

    wants_cashflow_refresh = is_cashflow_missing_income_followup(original_user_msg)

    requested_cashflow_calc = bool(
        explicit_cashflow_request
        or wants_cashflow_refresh
        or ("תחשב לי תזרים" in lowered_user_msg)
        or ("תחשב לי תזרים פרישה" in lowered_user_msg)
        or ("חישוב תזרים" in lowered_user_msg)
        or ("תזרים פרישה" in lowered_user_msg)
        or is_comparison_request
        or is_net_request
        or advice_compensation_mode
    )

    if (
        requested_cashflow_calc
        and (not commutation_intent)
        and (not conceptual_tools_disabled)
        and (resolved_intent != ChatIntent.REPORT)
    ):
        if (
            tools_enabled
            and (request.client_id is not None)
            and (not is_qa_mode)
            and (not no_tools_requested)
            and (not commutation_intent)
        ):
            def generate_cashflow_tool_exec():
                if computed_data is not None:
                    computed_json = json.dumps(
                        {"type": "computed_data", "data": computed_data.model_dump()},
                        ensure_ascii=False,
                    )
                    yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

                birth_date_for_default_date = None
                gender_for_default_date = None
                try:
                    client_obj = db.query(Client).filter(Client.id == request.client_id).first()
                    birth_date_for_default_date = getattr(client_obj, "birth_date", None) if client_obj else None
                    gender_for_default_date = getattr(client_obj, "gender", None) if client_obj else None
                except Exception:
                    birth_date_for_default_date = None
                    gender_for_default_date = None

                default_retirement_date = compute_default_retirement_date_for_tool_call(
                    birth_date=birth_date_for_default_date,
                    gender=gender_for_default_date,
                    user_message=original_user_msg or "",
                )
                desired_income = extract_desired_monthly_income_from_text(original_user_msg)
                desired_income_is_net = infer_desired_income_is_net_explicit(original_user_msg)

                if desired_income is not None and desired_income_is_net is None:
                    yield (
                        "כדי לבנות תזרים לפי יעד הכנסה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
                        "כתוב אחת מהאפשרויות:\n"
                        "- '40 אלף ברוטו'\n"
                        "- '40 אלף נטו'"
                    )
                    return

                tool_args: dict[str, Any] = {"retirement_date": default_retirement_date}
                if desired_income is not None and desired_income_is_net is not None:
                    tool_args["desired_monthly_income"] = float(desired_income)
                    tool_args["desired_income_is_net"] = bool(desired_income_is_net)

                tool_name = "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
                tool_result = _execute_tool_call(
                    tool_name,
                    tool_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=force_max_exemption,
                    user_approved=True,
                    request_id=stream_request_id,
                )

                tool_display = get_tool_display_name_hebrew(tool_name)
                user_tool_output = format_tool_output_for_user_stream(tool_name, tool_result)
                yield (
                    f"🔧 **פלט כלי ({tool_display}):**\n"
                    + sanitize_user_visible_text(user_tool_output)
                )
                if advice_compensation_mode:
                    yield (
                        "\n\n"
                        + "כותרת: סיכום החלטה לגבי פיצויים\n\n"
                        + "מה בדקתי במערכת:\n"
                        + "- תזרים\n"
                        + "- מס\n"
                        + "- יתרות\n"
                        + "- סטטוסים (כולל חסומים) ואירוע סיום עבודה\n\n"
                        + "מה המשמעות של שתי אפשרויות עיקריות:\n"
                        + "- מימוש כהון: שינוי באופי המימוש והנזילות; עשוי להשפיע על רכיבי המס והיתרות שנצפות בדוחות\n"
                        + "- השארה כהמשך קצבתי/אחר: המשך צבירה/תשלום במבנה קצבתי בהתאם להגדרות הקופות והסטטוסים במערכת\n\n"
                        + "מה חסר כדי לתת המלצה סופית (אם חסר):\n"
                        + "- בחירת יעד (נזילות מול קצבה)\n"
                        + "- סטטוס תהליך סיום עבודה ומסמכים נלווים\n"
                        + "- אישור שהנתונים במערכת עדכניים לכל הגופים\n\n"
                        + "פעולה הבאה במערכת:\n"
                        + "- להפיק דוח מסכם מהמערכת כדי לקבל מסמך תומך החלטה על בסיס הנתונים והחישובים שבוצעו\n"
                    )
                else:
                    yield (
                        "\n\n"
                        + "הפקתי את תוצאות הניתוח מהמערכת. להסבר מילולי בלי מספרים כתוב: הסבר במילים.\n"
                    )

            return StreamingResponse(
                generate_cashflow_tool_exec(),
                media_type="text/plain; charset=utf-8",
            )

        return StreamingResponse(
            iter(
                [
                    "כדי להריץ חישוב תזרים/ניתוח תזרים אני צריך הפעלה עם לקוח פעיל וכלים זמינים. "
                    "בבקשה נסה שוב עם client_id תקין (או בטל מצב ללא-כלים אם הופעל)."
                ]
            ),
            media_type="text/plain; charset=utf-8",
        )

    if (
        request.client_id is not None
        and is_doc_request
        and (not is_tax_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not conceptual_tools_disabled)
        and ui_action_short_circuit_allowed
        and (resolved_intent != ChatIntent.REPORT)
    ):
        wants_pdf = "pdf" in lowered_user_msg
        return _stream_execute_tool_no_approval(
            "GENERATE_FULL_REPORT",
            {
                "output_format": "pdf" if wants_pdf else "html",
                "report_type": "full",
                "ensure_analysis": False,
            },
            computed_data=computed_data,
            client_id=request.client_id,
            db=db,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
            is_portfolio_analysis=is_portfolio_analysis,
        )

    if not conceptual_tools_disabled:
        target_plan_response = _maybe_handle_target_plan_deterministic(
            request=request,
            db=db,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            is_doc_request=is_doc_request,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            wants_execute_target_plan=wants_execute_target_plan,
            stream_request_id=stream_request_id,
        )
        if target_plan_response is not None:
            return target_plan_response

    if commutation_intent and request.client_id is not None:
        account_number = _extract_commutation_account_number(original_user_msg)
        if not account_number:
            return StreamingResponse(
                generate_commutation_need_account(computed_data=computed_data),
                media_type="text/plain; charset=utf-8",
            )

    if not conceptual_tools_disabled:
        cashflow_response = _maybe_handle_cashflow_deterministic(
            request=request,
            db=db,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            is_doc_request=is_doc_request,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            commutation_intent=commutation_intent,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
        )
        if cashflow_response is not None:
            return cashflow_response

    if not conceptual_tools_disabled:
        max_capital_response = _maybe_handle_max_capital_request(
            request=request,
            db=db,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            explicit_termination=explicit_termination,
            is_doc_request=is_doc_request,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
        )
        if max_capital_response is not None:
            return max_capital_response

    if not conceptual_tools_disabled:
        fixation_documents_response = _maybe_handle_fixation_documents_deterministic(
            request=request,
            db=db,
            wants_fixation_documents=wants_fixation_documents,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
            is_portfolio_analysis=is_portfolio_analysis,
        )
        if fixation_documents_response is not None:
            return fixation_documents_response

    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    commutation_response = _maybe_handle_commutation_deterministic(
        commutation_intent=commutation_intent,
        request=request,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        original_user_msg=original_user_msg,
        db=db,
        effective_portfolio=effective_portfolio,
        computed_data=computed_data,
    )
    if commutation_response is not None:
        return commutation_response

    analysis_default_retirement_age = _compute_analysis_default_retirement_age(
        request=request,
        db=db,
        is_portfolio_analysis=is_portfolio_analysis,
    )

    termination_already_executed, termination_response = _maybe_handle_termination_deterministic(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        explicit_termination=explicit_termination,
        termination_change=termination_change,
        no_tools_requested=no_tools_requested,
        is_qa_mode=is_qa_mode,
        wants_execute_target_plan=wants_execute_target_plan,
        wants_fixation_execute=wants_fixation_execute,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
    )
    if termination_response is not None:
        return termination_response

    approval_response = _maybe_handle_approval_or_cancel_flow(
        request=request,
        db=db,
        no_tools_requested=no_tools_requested,
        computed_data=computed_data,
        termination_already_executed=termination_already_executed,
        termination_change=termination_change,
        wants_execute_target_plan=wants_execute_target_plan,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
    )
    if approval_response is not None:
        return approval_response

    wants_ignore_blocked = _apply_wants_ignore_blocked_and_portfolio_analysis_messages(
        request=request,
        messages=messages,
        is_portfolio_analysis=is_portfolio_analysis,
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

        if (
            resolved_intent == ChatIntent.REPORT
            and request.client_id is not None
            and (not no_tools_requested)
            and (not conceptual_tools_disabled)
        ):
            wants_pdf = "pdf" in lowered_user_msg
            report_tool_name = (
                "GENERATE_TAX_DEDUCTION_DOCUMENTS" if is_tax_doc_request else "GENERATE_FULL_REPORT"
            )
            report_tool_args: dict[str, Any] = {}
            if report_tool_name == "GENERATE_FULL_REPORT":
                report_tool_args = {
                    "output_format": "pdf" if wants_pdf else "html",
                    "report_type": "full",
                }

            tool_db = SessionLocal()
            try:
                tool_result = _execute_tool_call(
                    report_tool_name,
                    report_tool_args,
                    request.client_id,
                    tool_db,
                    pension_portfolio=current_pension_portfolio,
                    force_max_exemption=force_max_exemption_val,
                    user_approved=True,
                    request_id=req_id,
                )
            finally:
                tool_db.close()

            status_message: str | None = None
            open_path: str | None = None
            download_url: str | None = None
            try:
                parsed_tool = json.loads(tool_result)
                if isinstance(parsed_tool, dict):
                    open_path = parsed_tool.get("open_path")
                    download_url = parsed_tool.get("download_url")
                    status_message = parsed_tool.get("status_message") or parsed_tool.get("message")
            except Exception:
                pass

            actions: list[dict[str, str]] = []
            if isinstance(open_path, str) and open_path.strip():
                actions.append({"type": "navigate", "path": open_path.strip(), "label": "פתח דוח"})
            elif isinstance(download_url, str) and download_url.strip():
                actions.append(
                    {"type": "open_url", "url": download_url.strip(), "label": "פתח להורדה"}
                )
                actions.append(
                    {
                        "type": "navigate",
                        "path": f"/clients/{request.client_id}/reports",
                        "label": "פתח עמוד דוחות",
                    }
                )
            else:
                actions.append(
                    {
                        "type": "navigate",
                        "path": f"/clients/{request.client_id}/reports",
                        "label": "פתח עמוד דוחות",
                    }
                )

            ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
            if isinstance(status_message, str) and status_message.strip():
                ui_payload["status_message"] = status_message.strip()

            yield (
                "###UI_ACTION###"
                + json.dumps(ui_payload, ensure_ascii=False)
                + "###END_UI_ACTION###\n"
            )

            if is_qa_mode or report_requires_qa_line(original_user_msg):
                yield "\n\nPASS - סיכום QA סופי לאחר יצירת הדוח"
            return

        if explicit_transform and (not no_tools_requested) and (not is_doc_request) and (not is_qa_mode):
            yield from _stream_handle_explicit_transform(
                lowered_user_msg=lowered_user_msg,
                original_user_msg=original_user_msg,
                current_pension_portfolio=current_pension_portfolio,
                request=request,
                db=db,
                req_id=req_id,
                wants_capital_transform=wants_capital_transform,
            )
            return

        report_open_path: str | None = None
        qa_summary_required = False
        qa_summary_satisfied = False
        executed_tools: set[str] = set()
        forced_fixation_chain_done = False

        required_tools: set[str] = set()
        if not no_tools_requested:
            if is_doc_request:
                if is_tax_doc_request:
                    required_tools.add("GENERATE_TAX_DEDUCTION_DOCUMENTS")
                else:
                    required_tools.add("GENERATE_FULL_REPORT")

        tool_call_marker = "###TOOL_CALL###"
        max_steps = 5
        current_step = 0

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

        playbook_text = _load_stream_intents_playbook_text()
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

        while current_step < max_steps:
            current_step += 1

            should_break, full_response = yield from _stream_collect_llm_response_with_retry_or_yield_error(
                collect_llm_response_with_retry=_collect_llm_response_with_retry,
                history_messages=history_messages,
                client_id=request.client_id,
                stream_request_id=stream_request_id,
                current_step=current_step,
                logger=logger,
                get_llm_service=_get_llm_service,
                get_retry_settings=_get_retry_settings,
            )
            if should_break:
                break

            if tool_call_marker not in full_response:
                should_continue, has_pass_fail = _maybe_apply_non_tool_response_guardrails(
                    full_response=full_response,
                    request=request,
                    db=db,
                    history_messages=history_messages,
                    is_qa_mode=is_qa_mode,
                    no_tools_requested=no_tools_requested,
                    required_tools=required_tools,
                    executed_tools=executed_tools,
                    is_tax_doc_request=is_tax_doc_request,
                    qa_summary_required=qa_summary_required,
                    is_cashflow_request=is_cashflow_request,
                    is_comparison_request=is_comparison_request,
                    is_net_request=is_net_request,
                    is_doc_request=is_doc_request,
                )
                if should_continue:
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

                allowed_sources = _build_allowed_sources_for_numeric_provenance(
                    request=request,
                    history_messages=history_messages,
                )
                if no_tools_requested or (tools_disabled_reason in {"conceptual", "conceptual_form"}):
                    final_out = full_response
                else:
                    final_out = _compute_final_out_with_numeric_provenance_guardrail(
                        req_id=req_id,
                        request=request,
                        full_response=full_response,
                        allowed_sources=allowed_sources,
                        is_portfolio_analysis=is_portfolio_analysis,
                    )
                if (
                    resolved_intent == ChatIntent.NO_TOOLS
                    and (not exec_only_active)
                    and (tools_disabled_reason not in {"conceptual", "conceptual_form"})
                ):
                    final_out = _postprocess_no_tools_user_visible_text(final_out)
                if exec_only_active and resolved_intent != ChatIntent.REPORT:
                    try:
                        validate_execution_only_output(final_out)
                    except Exception as e:
                        try:
                            rewrite_prompt = build_exec_only_rewrite_prompt(
                                bad_text=final_out,
                                user_request_text=original_user_msg or "",
                            )
                            rewrite_messages = [
                                ChatMessage(role=m["role"], content=m["content"])
                                for m in rewrite_prompt
                            ]
                            _buf: list[str] = []
                            llm_service = _get_llm_service()
                            for _chunk in llm_service.chat_stream(rewrite_messages, request.client_id):
                                if _chunk:
                                    _buf.append(str(_chunk))
                            rewritten = "".join(_buf)
                            validate_execution_only_output(rewritten)
                            final_out = rewritten
                        except Exception as e2:
                            reason = getattr(e2, "reason", getattr(e, "reason", "policy_violation"))
                            logger.warning(
                                "EXECUTION_ONLY BLOCKED endpoint=stream trace_id=%s reason=%s",
                                stream_request_id,
                                reason,
                            )
                            yield build_execution_only_fallback(original_user_msg or "")
                            return
                if (
                    (not exec_only_active)
                    and (not conceptual_tools_disabled)
                    and (not no_tools_requested)
                    and (
                        "###UI_ACTION###" not in (final_out or "")
                        and "###END_UI_ACTION###" not in (final_out or "")
                    )
                ):
                    allowed, final_out = enforce_behavioral_limits(final_out)
                if no_tools_requested:
                    final_out = sanitize_words_only_output(final_out)
                try:
                    if (
                        (not exec_only_active)
                        and (tools_disabled_reason in {"conceptual", "conceptual_form"})
                        and ("###UI_ACTION###" not in (final_out or ""))
                        and ("###END_UI_ACTION###" not in (final_out or ""))
                    ):
                        final_out = sanitize_words_only_conceptual(final_out, original_user_msg or "")
                except Exception:
                    pass
                yield final_out
                break

            try:
                (
                    should_continue,
                    should_break,
                    should_return,
                    tool_name,
                    tool_args,
                    current_pension_portfolio,
                ) = yield from _stream_prepare_tool_call_and_maybe_request_commutation_approval(
                    full_response=full_response,
                    request=request,
                    db=db,
                    req_id=req_id,
                    history_messages=history_messages,
                    original_user_msg=original_user_msg,
                    is_portfolio_analysis=is_portfolio_analysis,
                    analysis_default_retirement_age=analysis_default_retirement_age,
                    no_tools_requested=no_tools_requested,
                    is_qa_mode=is_qa_mode,
                    is_doc_request=is_doc_request,
                    is_tax_doc_request=is_tax_doc_request,
                    wants_ignore_blocked=wants_ignore_blocked,
                    explicit_termination=explicit_termination,
                    termination_already_executed=termination_already_executed,
                    termination_change=termination_change,
                    current_pension_portfolio=current_pension_portfolio,
                    wants_capital_transform=wants_capital_transform,
                    force_max_exemption_val=force_max_exemption_val,
                )
                if should_continue:
                    continue
                if should_break:
                    break
                if should_return:
                    return

                (
                    should_break,
                    qa_summary_required,
                    report_open_path,
                    current_pension_portfolio,
                    forced_fixation_chain_done,
                ) = yield from _stream_execute_tool_and_process_result(
                    logger=logger,
                    req_id=req_id,
                    request=request,
                    db=db,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    current_pension_portfolio=current_pension_portfolio,
                    force_max_exemption_val=force_max_exemption_val,
                    full_response=full_response,
                    qa_summary_required=qa_summary_required,
                    report_open_path=report_open_path,
                    forced_fixation_chain_done=forced_fixation_chain_done,
                    required_tools=required_tools,
                    executed_tools=executed_tools,
                    is_tax_doc_request=is_tax_doc_request,
                    is_qa_mode=is_qa_mode,
                    history_messages=history_messages,
                )
                if should_break:
                    break

                # IMPORTANT: After we stream any tool output, we end the stream immediately.
                # This prevents the model from appending post-tool narrative that may include
                # unprovenanced numbers and get blocked by the numeric provenance guardrail.
                #
                # Exception: in QA mode, after generating a full report, we must continue
                # streaming to allow the model to emit the final QA summary.
                if resolved_intent == ChatIntent.ANALYSIS and (not qa_summary_required):
                    if exec_only_active:
                        yield execution_only_blocked("policy_violation")
                        return
                    yield (
                        "\n\n"
                        + "הפקתי את תוצאות הניתוח מהמערכת. להסבר מילולי בלי מספרים כתוב: הסבר במילים.\n"
                    )
                    return

            except Exception as e:
                logger.error("Stream Tool Execution Failed: %s", e, exc_info=True)
                if exec_only_active and resolved_intent != ChatIntent.REPORT:
                    yield execution_only_blocked("tool_execution_failed")
                    return
                yield f"\n\n(Error executing tool: {sanitize_user_visible_text(str(e))})"
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
