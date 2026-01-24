import json
import logging
import inspect
import importlib
import re
import uuid
import time
import threading
import queue
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
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
    store_pending_approval_request,
    store_pending_plan_target_marker,
    load_latest_target_pension_plan,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
    store_latest_target_pension_plan_data,
)
from app.services.llm_chat.pending_approvals import (
    compute_args_hash,
    load_pending_approval_payload_if_match_and_args_hash,
    load_pending_approval_ui_action_if_match,
)
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
    load_current_effective_state,
    load_latest_pension_portfolio_snapshot_models,
)
from app.services.state.effective_client_state_loader import load_effective_client_state
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
from app.models.scenario import Scenario
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


def extract_target_net_ils(user_text: str) -> int | None:
    if not isinstance(user_text, str) or not user_text.strip():
        return None

    cleaned = user_text.replace(",", "").replace(".", "")
    lowered = cleaned.lower()

    nums: list[tuple[int, int, int]] = []
    for m in re.finditer(r"\b\d{4,6}\b", cleaned):
        try:
            nums.append((m.start(), m.end(), int(m.group(0))))
        except Exception:
            continue
    if not nums:
        return None

    net_positions = [m.start() for m in re.finditer(r"נטו|\bnet\b", lowered)]
    if net_positions:
        best = None
        best_dist = None
        for s, e, val in nums:
            d = min(abs(s - p) for p in net_positions)
            if best_dist is None or d < best_dist:
                best = val
                best_dist = d
        return best

    keyword_positions: list[int] = []
    for kw in (
        "קצבת יעד",
        "יעד הכנסה",
        "יעד",
    ):
        keyword_positions.extend([m.start() for m in re.finditer(re.escape(kw), lowered)])

    if not keyword_positions:
        return None

    best = None
    best_dist = None
    for s, e, val in nums:
        d = min(abs(s - p) for p in keyword_positions)
        if best_dist is None or d < best_dist:
            best = val
            best_dist = d
    return best


@dataclass(frozen=True)
class PendingPlanTargetMarker:
    row: Scenario
    session: Session
    expires_at: datetime | None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires_at


def load_pending_plan_target_marker_direct(
    *, session: Session, client_id: int | None
) -> PendingPlanTargetMarker | None:
    if client_id is None:
        return None
    try:
        row = (
            session.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    if str(parsed.get("kind") or "").strip() != "pending_plan_target":
        return None
    if parsed.get("active", True) is False:
        return None

    expires_at = None
    expires_raw = parsed.get("expires_at")
    if isinstance(expires_raw, str) and expires_raw.strip():
        try:
            expires_at = datetime.fromisoformat(expires_raw.strip())
        except Exception:
            expires_at = None

    return PendingPlanTargetMarker(row=row, session=session, expires_at=expires_at)


def delete_marker(marker: PendingPlanTargetMarker) -> None:
    try:
        parsed = json.loads(marker.row.parameters or "{}")
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed["active"] = False
    marker.row.parameters = json.dumps(parsed, ensure_ascii=False)
    try:
        marker.session.add(marker.row)
        marker.session.commit()
    except Exception:
        try:
            marker.session.rollback()
        except Exception:
            pass

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

    original_user_msg = (raw_user_msg or "").strip()

    plan_phrase_detected = False
    try:
        msg_norm = (original_user_msg or "").replace("תוכנית", "תכנית")
        msg_norm_stripped = msg_norm.strip()
        msg_lower = msg_norm_stripped.lower()
        has_plan_phrase = bool(
            re.search(r"(?:^|\s)תכנית\s+(?:קצבה|יעד)(?:\s|$)", msg_norm_stripped)
            or re.search(r"(?:^|\s)חשב\s+תכנית\s+(?:קצבה|יעד)(?:\s|$)", msg_norm_stripped)
        )
        has_retirement_plan_phrase = bool(
            ("תכנית פרישה" in msg_norm_stripped)
            and (re.search(r"\b\d{4,6}\b", msg_norm_stripped) is not None)
            and (("נטו" in msg_norm_stripped) or ("net" in msg_lower))
        )
        plan_phrase_detected = bool(has_plan_phrase or has_retirement_plan_phrase)
    except Exception:
        plan_phrase_detected = False

    client_id = request.client_id

    if plan_phrase_detected:
        if client_id is not None:
            early_locked = False
            try:
                _st = load_effective_client_state(db, client_id)
                early_locked = str(getattr(_st, "mode", "") or "").strip() == "POST_CONVERSION_LOCKED"
            except Exception:
                early_locked = False
            if early_locked:
                return StreamingResponse(
                    iter(
                        [
                            sanitize_user_visible_text(
                                "כותרת: תכנית לאחר המרה\n\n"
                                "לא בונים מחדש תכנית יעד על בסיס התיק המקורי אחרי שכבר בוצעה המרה.\n"
                                "אם המטרה היא לבצע משיכה/קצבה מהמצב החדש - נדרש מסלול ייעודי שמחשב מהנכסים שנוצרו.\n"
                                'כתוב: "חשב תזרים על בסיס המצב הנוכחי" או "דוח מסכם".\n'
                            )
                        ]
                    ),
                    media_type="text/plain; charset=utf-8",
                )

        target_net_from_phrase = extract_target_net_ils(original_user_msg)
        if target_net_from_phrase is not None and client_id is not None:

            def _exec_target_plan_tools_first_from_phrase():
                tool_name = "BUILD_TARGET_PENSION_PLAN"
                tool_args = {
                    "target_monthly_pension": float(target_net_from_phrase),
                    "target_is_net": True,
                }
                tool_result = _execute_tool_call(
                    tool_name,
                    tool_args,
                    client_id,
                    db,
                    pension_portfolio=request.pension_portfolio,
                    force_max_exemption=False,
                    user_approved=True,
                    request_id=stream_request_id,
                )
                try:
                    store_latest_target_pension_plan_data(
                        db=db,
                        client_id=client_id,
                        tool_result=tool_result,
                    )
                except Exception:
                    pass
                try:
                    store_latest_target_pension_plan(
                        db=db,
                        client_id=client_id,
                        tool_result=tool_result,
                    )
                except Exception:
                    pass
                yield sanitize_user_visible_text(
                    "🔧 **פלט כלי (" + get_tool_display_name_hebrew(tool_name) + "):**\n"
                    + format_tool_output_for_user_stream(tool_name, tool_result)
                )

            return StreamingResponse(
                _exec_target_plan_tools_first_from_phrase(),
                media_type="text/plain; charset=utf-8",
            )

        if client_id is not None:
            try:
                store_pending_plan_target_marker(
                    db=db,
                    client_id=client_id,
                    ttl_seconds=5 * 60,
                    source="stream_plan_phrase",
                )
            except Exception:
                pass

        def _prompt_for_target_net_for_phrase():
            yield sanitize_user_visible_text(
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                "כתוב: יעד נטו: <מספר>."
            )

        return StreamingResponse(
            _prompt_for_target_net_for_phrase(),
            media_type="text/plain; charset=utf-8",
        )

    if request.client_id is not None and isinstance(original_user_msg, str):
        lowered_user_msg = original_user_msg.strip().lower()
        if lowered_user_msg in {"מאשר", "אשר", "כן", "approve", "ok"}:
            def _load_latest_pending_approval_payload() -> tuple[str, dict] | None:
                try:
                    row = (
                        db.query(Scenario)
                        .filter(Scenario.client_id == request.client_id)
                        .filter(Scenario.scenario_name == "pending_approval")
                        .order_by(Scenario.created_at.desc())
                        .first()
                    )
                except Exception:
                    row = None
                if row is None or not getattr(row, "parameters", None):
                    return None
                try:
                    parsed = json.loads(row.parameters)
                except Exception:
                    return None
                if not isinstance(parsed, dict):
                    return None
                tool_name = parsed.get("tool_name")
                tool_args = parsed.get("arguments")
                if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
                    return None
                return tool_name, tool_args

            pending = _load_latest_pending_approval_payload()
            if pending is None:
                return StreamingResponse(
                    iter(["אין בקשת אישור פתוחה."]),
                    media_type="text/plain; charset=utf-8",
                )

            approved_tool, approved_args = pending

            def _append_transform_hint_if_needed(*, tool_name: str, rendered_output: str) -> str:
                if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
                    return rendered_output
                try:
                    parsed = json.loads(rendered_output)
                except Exception:
                    parsed = None
                if not (isinstance(parsed, dict) and parsed.get("success") is True):
                    return rendered_output
                if "השלב הבא המומלץ: הפקת דוח" in rendered_output:
                    return rendered_output
                return rendered_output + "\n\nהשלב הבא המומלץ: הפקת דוח"

            def _generate_text_approved_exec(req_id: str):
                try:
                    effective_portfolio = request.pension_portfolio
                    try:
                        loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                        if loaded is not None:
                            effective_portfolio, _snapshot_at = loaded
                    except Exception:
                        pass

                    tool_result = _execute_tool_call(
                        approved_tool,
                        approved_args,
                        request.client_id,
                        db,
                        pension_portfolio=effective_portfolio,
                        force_max_exemption=False,
                        user_approved=True,
                        request_id=req_id,
                    )
                finally:
                    try:
                        clear_pending_approval_request(db=db, client_id=request.client_id)
                    except Exception:
                        pass

                tool_display = get_tool_display_name_hebrew(approved_tool)
                user_tool_output = format_tool_output_for_user_stream(approved_tool, tool_result)
                rendered = (
                    f"🔧 **פלט כלי ({tool_display}):**\n"
                    + sanitize_user_visible_text(user_tool_output)
                )
                yield _append_transform_hint_if_needed(tool_name=approved_tool, rendered_output=rendered)

            return StreamingResponse(
                _generate_text_approved_exec(stream_request_id),
                media_type="text/plain; charset=utf-8",
            )

    pending_plan = load_pending_plan_target_marker_direct(
        session=db,
        client_id=client_id,
    )

    target_net = extract_target_net_ils(original_user_msg)

    if pending_plan is not None and target_net is not None and (not original_user_msg.startswith("###USER_APPROVED###")):
        if pending_plan.is_expired():
            delete_marker(pending_plan)

            def _prompt_for_target_net_again():
                yield sanitize_user_visible_text(
                    "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                    "כתוב: יעד נטו: <מספר>."
                )

            return StreamingResponse(
                _prompt_for_target_net_again(),
                media_type="text/plain; charset=utf-8",
            )

        def _exec_target_plan_tools_first():
            tool_name = "BUILD_TARGET_PENSION_PLAN"
            tool_args = {
                "target_monthly_pension": float(target_net),
                "target_is_net": True,
            }
            tool_result = _execute_tool_call(
                tool_name,
                tool_args,
                client_id,
                db,
                pension_portfolio=request.pension_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=stream_request_id,
            )
            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=client_id,
                    tool_result=tool_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=client_id,
                    tool_result=tool_result,
                )
            except Exception:
                pass
            yield sanitize_user_visible_text(
                "🔧 **פלט כלי (" + get_tool_display_name_hebrew(tool_name) + "):**\n"
                + format_tool_output_for_user_stream(tool_name, tool_result)
            )
            delete_marker(pending_plan)

        return StreamingResponse(
            _exec_target_plan_tools_first(),
            media_type="text/plain; charset=utf-8",
        )

    try:
        messages, computed_data = prepare_messages_with_context(request=request, db=db)
    except Exception:
        messages = list(request.messages or [])
        computed_data = None

    def _parse_user_approved_payload(user_msg: str) -> tuple[str, dict] | None:
        marker = "###USER_APPROVED###"
        if not isinstance(user_msg, str) or marker not in user_msg:
            return None
        after = user_msg.split(marker, 1)[1].strip()
        json_str = after.strip("`").strip()
        json_str = json_str.splitlines()[0] if json_str else ""
        if not json_str:
            return None
        try:
            parsed = json.loads(json_str)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        tool_name = parsed.get("tool_name")
        tool_args = parsed.get("arguments")
        if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
            return None
        return tool_name, tool_args

    def _should_route_to_reports_page(user_msg: str) -> bool:
        lowered = (user_msg or "").strip().lower()
        if not lowered:
            return False

        # Do NOT intercept system results reports ("דוח תוצאות") or conceptual questions
        # like "איך לקרוא דוח תזרים".
        if ("תוצאות" in lowered) or ("results" in lowered):
            return False
        if ("תזרים" in lowered) or ("cashflow" in lowered):
            return False
        if lowered.startswith("איך ") or lowered.startswith("כיצד ") or lowered.startswith("how "):
            return False

        # Do not intercept full report generation / QA flows.
        if ("מלא" in lowered) or ("full" in lowered) or ("qa" in lowered):
            return False

        report_verbs = ("שלח", "הפק", "צור", "תפיק", "פתח")
        has_verb = any(tok in lowered for tok in report_verbs)
        has_report_word = ("דוח" in lowered) or ('דו"ח' in lowered) or ("report" in lowered) or ("reports" in lowered)
        if not has_report_word:
            return False

        lowered_compact = lowered.strip()
        if lowered_compact in {"report", "reports"}:
            return True

        # For generic "דוח" requests we only route when it's clearly a document open request.
        wants_summary = ("דוח מסכם" in lowered) or ("מסכם" in lowered) or ("summary" in lowered)
        return bool(has_verb or wants_summary)

    if (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and (not original_user_msg.strip().startswith("###USER_APPROVED###"))
        and _should_route_to_reports_page(original_user_msg)
    ):
        ui_payload: dict[str, Any] = {
            "type": "ui_actions",
            "actions": [
                {
                    "type": "navigate",
                    "path": f"/clients/{request.client_id}/reports?auto_html=1",
                    "label": "פתח דוח",
                }
            ],
        }
        ui_action = "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
        return StreamingResponse(iter([ui_action]), media_type="text/plain; charset=utf-8")

    def _extract_first_json_object(raw: str) -> dict | None:
        if not isinstance(raw, str) or not raw:
            return None
        start = raw.find("{")
        if start < 0:
            return None

        in_string = False
        escaped = False
        depth = 0
        end = None
        for i in range(start, len(raw)):
            ch = raw[i]
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end is None:
            return None
        try:
            parsed = json.loads(raw[start:end])
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _append_transform_next_step_hint(*, tool_name: str, rendered_output: str) -> str:
        if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
            return rendered_output
        parsed = _extract_first_json_object(rendered_output)
        if not (isinstance(parsed, dict) and parsed.get("success") is True):
            return rendered_output
        if "השלב הבא המומלץ: הפקת דוח" in rendered_output:
            return rendered_output
        return rendered_output + "\n\nהשלב הבא המומלץ: הפקת דוח"

    if (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and original_user_msg.strip().startswith("###USER_APPROVED###")
    ):
        def _approval_refusal_lines() -> list[str]:
            return [
                "אין בקשת אישור פתוחה תואמת לביצוע הפעולה הזו. בקש שוב ביצוע כדי לקבל אישור חדש.",
                "טיפ: לחץ על אשר מתוך חלון האישור, או בקש שוב אישור כדי לקבל JSON עדכני.",
            ]

        approved = _parse_user_approved_payload(original_user_msg)
        if approved is None:
            return StreamingResponse(
                iter(_approval_refusal_lines()),
                media_type="text/plain; charset=utf-8",
            )

        approved_tool, approved_args = approved

        effective_mode = ""
        try:
            _st = load_effective_client_state(db, request.client_id)
            effective_mode = str(getattr(_st, "mode", "") or "")
        except Exception:
            effective_mode = ""
        is_locked_now = effective_mode.strip() == "POST_CONVERSION_LOCKED"

        accounts_obj = approved_args.get("accounts") if isinstance(approved_args, dict) else None
        has_nonempty_accounts = isinstance(accounts_obj, list) and len(accounts_obj) > 0

        dangerous_request_kind: str | None = None
        if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS":
            dangerous_request_kind = "execute_target_plan"
        elif approved_tool == "EXECUTE_RETIREMENT_SCENARIO":
            dangerous_request_kind = "execute_retirement_scenario"

        must_require_pending = bool(
            dangerous_request_kind is not None and (is_locked_now or has_nonempty_accounts)
        )

        if must_require_pending and dangerous_request_kind is not None:
            args_hash = compute_args_hash(approved_args)
            pending = load_pending_approval_payload_if_match_and_args_hash(
                db=db,
                client_id=request.client_id,
                request_kind=dangerous_request_kind,
                tool_name=approved_tool,
                args_hash=args_hash,
            )
            if pending is None:
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain; charset=utf-8",
                )

        if approved_tool == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT":
            try:
                pending_basic = load_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                )
            except Exception:
                pending_basic = None
            if pending_basic is None:
                return StreamingResponse(
                    iter(
                        [
                            "אין בקשת אישור פתוחה תואמת לביצוע הפעולה הזו. בקש שוב ביצוע כדי לקבל אישור חדש."
                        ]
                    ),
                    media_type="text/plain; charset=utf-8",
                )
            pending_tool_name, pending_tool_args = pending_basic
            if (
                not isinstance(pending_tool_name, str)
                or pending_tool_name != approved_tool
                or (compute_args_hash(pending_tool_args) != compute_args_hash(approved_args))
            ):
                return StreamingResponse(
                    iter(
                        [
                            "אין בקשת אישור פתוחה תואמת לביצוע הפעולה הזו. בקש שוב ביצוע כדי לקבל אישור חדש."
                        ]
                    ),
                    media_type="text/plain; charset=utf-8",
                )

        def _generate_user_approved_exec(req_id: str):
            should_clear_pending = True
            try:
                effective_portfolio = request.pension_portfolio
                try:
                    loaded = _load_latest_pension_portfolio_snapshot_models(
                        db, request.client_id
                    )
                    if loaded is not None:
                        effective_portfolio, _snapshot_at = loaded
                except Exception:
                    pass

                tool_result = _execute_tool_call(
                    approved_tool,
                    approved_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=False,
                    user_approved=True,
                    request_id=req_id,
                )

                if must_require_pending:
                    parsed = _extract_first_json_object(tool_result)
                    if isinstance(parsed, dict) and parsed.get("success") is False:
                        should_clear_pending = False

                if approved_tool == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT":
                    try:
                        _refreshed = load_current_effective_state(db, request.client_id)
                    except Exception:
                        _refreshed = None

                    try:
                        loaded_after = _load_latest_pension_portfolio_snapshot_models(
                            db, request.client_id
                        )
                        if loaded_after is not None:
                            effective_portfolio, _snapshot_at = loaded_after
                    except Exception:
                        pass
            finally:
                try:
                    if should_clear_pending:
                        clear_pending_approval_request(db=db, client_id=request.client_id)
                except Exception:
                    pass

            tool_display = get_tool_display_name_hebrew(approved_tool)
            user_tool_output = format_tool_output_for_user_stream(approved_tool, tool_result)
            rendered = (
                f"🔧 **פלט כלי ({tool_display}):**\n"
                + sanitize_user_visible_text(user_tool_output)
            )
            yield _append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

        return StreamingResponse(
            _generate_user_approved_exec(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    effective_client_state = None
    if request.client_id is not None:
        try:
            effective_client_state = load_effective_client_state(db, request.client_id)
        except Exception:
            effective_client_state = None

    def _is_post_conversion_locked() -> bool:
        if effective_client_state is None:
            return False
        try:
            return str(getattr(effective_client_state, "mode", "")).strip() == "POST_CONVERSION_LOCKED"
        except Exception:
            return False

    def _should_show_post_conversion_messages() -> bool:
        if not _is_post_conversion_locked():
            return False
        if effective_client_state is None:
            return False
        try:
            return bool(getattr(effective_client_state, "has_any_conversion_assets", False))
        except Exception:
            return False

    def _build_post_conversion_lock_message() -> str:
        return (
            "כותרת: מצב תיק לאחר המרה\n\n"
            "המערכת מזהה שכבר בוצעו המרות בתיק (Post Conversion).\n"
            "כדי למנוע דריסה/כפל המרות, לא מבצעים שוב המרה על בסיס snapshot.\n\n"
            "מה אפשר לעשות עכשיו:\n"
            "- להפיק דוח מסכם\n"
            "- לבצע משיכה/פעולות נוספות על בסיס הנכסים שנוצרו\n"
            "- לבצע קיבוע זכויות אם נדרש\n\n"
            'אם רצית לבצע פעולה אחרת, כתוב במפורש: "דוח מסכם" / "משיכה מהנכסים" / "קיבוע זכויות".\n'
        )

    def _build_post_conversion_plan_message() -> str:
        return (
            "כותרת: תכנית לאחר המרה\n\n"
            "לא בונים מחדש תכנית יעד על בסיס התיק המקורי אחרי שכבר בוצעה המרה.\n"
            "אם המטרה היא לבצע משיכה/קצבה מהמצב החדש - נדרש מסלול ייעודי שמחשב מהנכסים שנוצרו.\n"
            'כתוב: "חשב תזרים על בסיס המצב הנוכחי" או "דוח מסכם".\n'
        )

    if (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and original_user_msg.strip()
        and (not is_no_tools_request(original_user_msg))
    ):
        candidate = original_user_msg.strip()
        wants_restore_snapshot = any(
            phrase in candidate
            for phrase in (
                "שחזר תיק",
                "שחזר סנאפסוט",
                "החזר מצב קודם",
                "חזור לסנאפסוט מלא",
            )
        )
        if wants_restore_snapshot:
            selected_snapshot_id: int | None = None
            try:
                snapshot = (
                    db.query(Scenario)
                    .filter(Scenario.client_id == request.client_id)
                    .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
                    .order_by(Scenario.id.desc())
                    .first()
                )
            except Exception:
                snapshot = None

            if snapshot is None:
                return StreamingResponse(
                    iter(["לא נמצא סנאפסוט תיק לשחזור. אנא העלה/שמור תיק פנסיוני ואז נסה שוב."]),
                    media_type="text/plain; charset=utf-8",
                )

            try:
                selected_snapshot_id = int(getattr(snapshot, "id", 0) or 0)
            except Exception:
                selected_snapshot_id = 0

            if not selected_snapshot_id or selected_snapshot_id <= 0:
                return StreamingResponse(
                    iter(["לא הצלחתי לזהות סנאפסוט תיק לשחזור."]),
                    media_type="text/plain; charset=utf-8",
                )

            tool_args = {
                "snapshot_scenario_id": int(selected_snapshot_id),
                "safety_mode": "strict",
            }
            ui_action = build_approval_request_ui_action(
                tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
                tool_args=tool_args,
                reason="שחזור תיק לסנאפסוט קודם עלול לדרוס מצב אחרי המרות. נדרש אישור.",
                risk_level="high",
                rag_sources=None,
            )
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
                    tool_args=tool_args,
                )
            except Exception:
                pass
            return StreamingResponse(iter([ui_action]), media_type="text/plain; charset=utf-8")

    if _should_show_post_conversion_messages() and isinstance(original_user_msg, str):
        candidate = original_user_msg.strip()
        lowered = candidate.lower()

        wants_execute_target_plan_local = (
            ("בצע" in lowered)
            and ("תכנית" in lowered or "תוכנית" in lowered or "מתווה" in lowered)
        )

        pending_execute_target_plan = False
        pending_execute_scenario = False
        if request.client_id is not None:
            try:
                pending_execute_target_plan = bool(
                    load_pending_approval_ui_action_if_match(
                        db=db,
                        client_id=request.client_id,
                        request_kind="execute_target_plan",
                        tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    )
                )
            except Exception:
                pending_execute_target_plan = False

            try:
                pending_execute_scenario = bool(
                    load_pending_approval_ui_action_if_match(
                        db=db,
                        client_id=request.client_id,
                        request_kind="execute_retirement_scenario",
                        tool_name="EXECUTE_RETIREMENT_SCENARIO",
                    )
                )
            except Exception:
                pending_execute_scenario = False

        # The post-conversion lock must not prevent returning an approval UI_ACTION
        # (or its deterministic replay) for execute-target-plan.
        if not wants_execute_target_plan_local:
            wants_plan_build = ("תכנית" in candidate) or ("תוכנית" in candidate)
            has_numeric_target = False
            try:
                cleaned = candidate.replace(",", "")
                has_numeric_target = bool(re.search(r"\b\d{4,6}\b", cleaned))
            except Exception:
                has_numeric_target = False

            wants_direct_transform = bool(
                is_transform_request(candidate)
                or ("transform" in lowered)
                or ("המר" in candidate)
                or ("המרה" in candidate)
            )

            if wants_direct_transform or (wants_plan_build and has_numeric_target):
                logger.info(
                    "post_conversion_lock_early_cutoff",
                    extra={
                        "endpoint": "stream",
                        "request_id": stream_request_id,
                        "client_id": request.client_id,
                        "post_conversion_locked": True,
                        "wants_execute_target_plan": bool(wants_execute_target_plan_local),
                        "pending_execute_target_plan": bool(pending_execute_target_plan),
                        "pending_execute_retirement_scenario": bool(pending_execute_scenario),
                    },
                )

                if wants_plan_build and has_numeric_target:
                    return StreamingResponse(
                        iter([_build_post_conversion_plan_message()]),
                        media_type="text/plain; charset=utf-8",
                    )

                return StreamingResponse(
                    iter([_build_post_conversion_lock_message()]),
                    media_type="text/plain; charset=utf-8",
                )

    if (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and original_user_msg.strip().startswith("###USER_APPROVED###")
    ):
        approved = extract_user_approval_for_tool_call(messages)
        if approved is not None:
            approved_tool, approved_args = approved

            if _should_show_post_conversion_messages() and approved_tool in {
                "TRANSFORM_FUNDS_TO_ASSETS",
                "EXECUTE_RETIREMENT_SCENARIO",
            }:
                return StreamingResponse(
                    iter([_build_post_conversion_lock_message()]),
                    media_type="text/plain; charset=utf-8",
                )

            def _generate_user_approved_exec(req_id: str):
                if computed_data is not None:
                    computed_json = json.dumps(
                        {"type": "computed_data", "data": computed_data.model_dump()},
                        ensure_ascii=False,
                    )
                    yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

                try:
                    clear_pending_approval_request(db=db, client_id=request.client_id)
                except Exception:
                    pass

                effective_portfolio = request.pension_portfolio
                try:
                    loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                    if loaded is not None:
                        effective_portfolio, _snapshot_at = loaded
                except Exception:
                    pass

                tool_result = _execute_tool_call(
                    approved_tool,
                    approved_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=False,
                    user_approved=True,
                    request_id=req_id,
                )

                tool_display = get_tool_display_name_hebrew(approved_tool)
                user_tool_output = format_tool_output_for_user_stream(
                    approved_tool, tool_result
                )
                rendered = (
                    f"🔧 **פלט כלי ({tool_display}):**\n"
                    + sanitize_user_visible_text(user_tool_output)
                )
                yield _append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

            return StreamingResponse(
                _generate_user_approved_exec(stream_request_id),
                media_type="text/plain; charset=utf-8",
            )

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
    effective_state: dict | None = None
    if request.client_id is not None:
        try:
            effective_state = load_current_effective_state(db, request.client_id)
        except Exception:
            effective_state = None
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

    def _parse_iso_datetime_utc(raw: object) -> datetime | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        cleaned = raw.strip()
        try:
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _load_latest_snapshot_meta() -> dict[str, Any] | None:
        if request.client_id is None:
            return None
        latest = (
            db.query(Scenario)
            .filter(Scenario.client_id == request.client_id)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .first()
        )
        if latest is None:
            return None
        try:
            params = json.loads(latest.parameters) if latest.parameters else {}
        except Exception:
            params = {}
        if not isinstance(params, dict):
            return None
        meta = params.get("_meta")
        return meta if isinstance(meta, dict) else None

    def _build_restore_snapshot_banner(*, now_utc: datetime) -> str | None:
        if request.client_id is None:
            return None
        if not isinstance(effective_state, dict):
            return None

        meta = _load_latest_snapshot_meta()
        if not isinstance(meta, dict):
            return None
        op_type = str(meta.get("operation_type") or "").strip()
        if op_type != "restore_snapshot":
            return None
        restored_at = _parse_iso_datetime_utc(meta.get("restored_at_utc"))
        if restored_at is None:
            return None

        try:
            age_sec = (now_utc - restored_at).total_seconds()
        except Exception:
            return None
        if age_sec < 0 or age_sec > 120:
            return None
        return "מצב מערכת: שוחזר סנאפסוט (restore_snapshot). אפשר להמשיך לתכנית/תרחיש."

    def _latest_snapshot_operation_type() -> str | None:
        if request.client_id is None:
            return None
        meta = _load_latest_snapshot_meta()
        if not isinstance(meta, dict):
            return None
        op_type = str(meta.get("operation_type") or "").strip()
        return op_type if op_type else None

    def _wrap_with_restore_banner(inner):
        now = datetime.now(timezone.utc)
        banner = _build_restore_snapshot_banner(now_utc=now)
        if isinstance(banner, str) and banner.strip() and (resolved_intent != ChatIntent.REPORT):
            yield banner.strip() + "\n\n"
        yield from inner

    def _build_recent_state_banner() -> str | None:
        now = datetime.now(timezone.utc)
        restore_banner = _build_restore_snapshot_banner(now_utc=now)
        if isinstance(restore_banner, str) and restore_banner.strip():
            return restore_banner

        if not isinstance(effective_state, dict):
            return None
        if not bool(effective_state.get("recent_update")):
            return None
        op_type = str(effective_state.get("last_operation_type") or "").strip()
        if op_type:
            return f"מצב מערכת: עודכן לאחר פעולה אחרונה ({op_type})"
        return "מצב מערכת: עודכן לאחר פעולה אחרונה"

    target_net_for_plan = extract_target_net_ils(original_user_msg or "")
    lowered_user_msg = (original_user_msg or "").lower()
    plan_tokens = re.findall(r"[א-תA-Za-z]+", lowered_user_msg)
    plan_token_pairs = set(zip(plan_tokens, plan_tokens[1:]))
    has_plan_build_token = (
        ("בנה" in plan_tokens)
        or ("צור" in plan_tokens)
        or ("תכנן" in plan_tokens)
        or ("תכנון" in plan_tokens)
    )
    has_plan_noun_token = ("תכנית" in plan_tokens) or ("תוכנית" in plan_tokens) or ("מתווה" in plan_tokens)
    has_plan_pension_token = ("קצבה" in plan_tokens) or ("קצבת" in plan_tokens)
    has_plan_domain_token = ("פרישה" in plan_tokens) or ("משיכה" in plan_tokens)
    has_target_plan_phrase_tokens = (
        (("קצבת", "יעד") in plan_token_pairs)
        or (("יעד", "קצבה") in plan_token_pairs)
        or (("יעד", "הכנסה") in plan_token_pairs)
    )
    has_pension_plan_phrase = any(
        token in lowered_user_msg
        for token in (
            "חשב תכנית קצבה",
            "חשב תוכנית קצבה",
            "תכנית קצבה",
            "תוכנית קצבה",
            "תכנית יעד",
            "תוכנית יעד",
            "בנה תכנית קצבה",
            "בנה תוכנית קצבה",
        )
    )
    is_plan_request_tokens = (
        has_target_plan_phrase_tokens
        or has_pension_plan_phrase
        or ((has_plan_build_token or has_plan_noun_token) and has_plan_domain_token)
        or (has_plan_noun_token and has_plan_pension_token)
    )
    has_target_plan_keywords = any(
        token in lowered_user_msg
        for token in (
            "קצבת יעד",
            "יעד קצבה",
            "תכנית קצבה",
            "תוכנית קצבה",
            "תכנית יעד",
            "תוכנית יעד",
            "בנה תכנית קצבה",
            "בנה תוכנית קצבה",
            "חשב תכנית קצבה",
            "חשב תוכנית קצבה",
            "בנה תכנית פרישה",
            "בנה תוכנית פרישה",
            "תכנית משיכה",
            "תוכנית משיכה",
            "תכנית יעד",
            "תוכנית יעד",
            "תכנית פרישה",
            "תוכנית פרישה",
        )
    )

    wants_execute_target_plan_text = (
        ("בצע" in lowered_user_msg)
        and ("תכנית" in lowered_user_msg or "תוכנית" in lowered_user_msg or "מתווה" in lowered_user_msg)
    )
    no_tools_requested_local = (resolved_intent == ChatIntent.NO_TOOLS) or is_no_tools_request(
        original_user_msg
    )
    commutation_intent_local = is_pension_commutation_request(original_user_msg)
    explicit_transform_local = is_transform_request(original_user_msg)
    is_qa_mode_local = is_qa_request(original_user_msg)
    max_capital_requested_local = is_max_capital_request(original_user_msg or "")

    _PENDING_PLAN_TARGET_SCENARIO_NAME = "pending_plan_target"
    _PENDING_PLAN_TARGET_TTL_SECONDS = 5 * 60

    def _store_pending_plan_target(*, client_id: int) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=_PENDING_PLAN_TARGET_TTL_SECONDS)
        payload = {
            "kind": "pending_plan_target",
            "active": True,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        try:
            (
                db.query(Scenario)
                .filter(Scenario.client_id == client_id)
                .filter(Scenario.scenario_name == _PENDING_PLAN_TARGET_SCENARIO_NAME)
                .delete(synchronize_session=False)
            )
            db.flush()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return

        try:
            scenario = Scenario(
                client_id=client_id,
                scenario_name=_PENDING_PLAN_TARGET_SCENARIO_NAME,
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(payload, ensure_ascii=False),
            )
            db.add(scenario)
            db.flush()
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    def _clear_pending_plan_target(*, client_id: int) -> None:
        try:
            (
                db.query(Scenario)
                .filter(Scenario.client_id == client_id)
                .filter(Scenario.scenario_name == _PENDING_PLAN_TARGET_SCENARIO_NAME)
                .delete(synchronize_session=False)
            )
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    def _load_pending_plan_target(*, client_id: int) -> dict | None:
        try:
            row = (
                db.query(Scenario)
                .filter(Scenario.client_id == client_id)
                .filter(Scenario.scenario_name == _PENDING_PLAN_TARGET_SCENARIO_NAME)
                .order_by(Scenario.created_at.desc())
                .first()
            )
        except Exception:
            row = None
        if row is None or not getattr(row, "parameters", None):
            return None
        try:
            parsed = json.loads(row.parameters)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None

        if parsed.get("active", True) is False:
            return None

        expires_raw = parsed.get("expires_at")
        expired = False
        if isinstance(expires_raw, str) and expires_raw.strip():
            try:
                expires_at = datetime.fromisoformat(expires_raw.strip())
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                expired = datetime.now(timezone.utc) >= expires_at
            except Exception:
                expired = False

        if str(parsed.get("kind") or "").strip() != "pending_plan_target":
            return None
        if expired:
            parsed = dict(parsed)
            parsed["_expired"] = True
        return parsed
    if (
        (resolved_intent != ChatIntent.REPORT)
        and is_plan_request_tokens
        and (target_net_for_plan is None)
        and (not wants_execute_target_plan_text)
        and (not commutation_intent_local)
        and (not explicit_transform_local)
        and (not max_capital_requested_local)
    ):
        try:
            if request.client_id is not None:
                _store_pending_plan_target(client_id=request.client_id)
        except Exception:
            pass

        def _prompt_for_target_net():
            yield (
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                "כתוב: יעד נטו: <מספר>.\n"
                "לדוגמה: יעד נטו: 28000"
            )

        return StreamingResponse(
            _prompt_for_target_net(),
            media_type="text/plain; charset=utf-8",
        )

    pending_plan_target = None
    try:
        if request.client_id is not None:
            pending_plan_target = _load_pending_plan_target(client_id=request.client_id)
    except Exception:
        pending_plan_target = None

    def _extract_target_net_reply(user_msg: str) -> int | None:
        if not isinstance(user_msg, str) or not user_msg.strip():
            return None
        cleaned = user_msg.replace(",", "").replace(".", "").strip()
        if re.fullmatch(r"\d{4,6}", cleaned):
            try:
                return int(cleaned)
            except Exception:
                return None
        try:
            return extract_target_net_ils(user_msg)
        except Exception:
            return None

    target_net_reply = _extract_target_net_reply(original_user_msg or "")

    if (
        (resolved_intent != ChatIntent.REPORT)
        and request.client_id is not None
        and (target_net_reply is not None)
        and (pending_plan_target is not None)
        and (not bool(pending_plan_target.get("_expired")))
        and (not commutation_intent_local)
        and (not explicit_transform_local)
        and (not _is_post_conversion_locked())
    ):

        def _generate_target_plan_tools_first_from_pending(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            banner = _build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            try:
                loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    nonlocal effective_portfolio, effective_snapshot_at
                    effective_portfolio, effective_snapshot_at = loaded
            except Exception:
                pass

            plan_args = {
                "target_monthly_pension": float(target_net_reply),
                "target_is_net": True,
            }
            plan_result = _execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                plan_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass

            try:
                _clear_pending_plan_target(client_id=request.client_id)
            except Exception:
                pass

            yield sanitize_user_visible_text(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
            )

        return StreamingResponse(
            _generate_target_plan_tools_first_from_pending(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    if (
        request.client_id is not None
        and pending_plan_target is not None
        and bool(pending_plan_target.get("_expired"))
        and (target_net_reply is not None)
    ):
        try:
            _store_pending_plan_target(client_id=request.client_id)
        except Exception:
            pass

        def _prompt_for_target_net_again():
            yield (
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                "כתוב: יעד נטו: <מספר>.\n"
                "לדוגמה: יעד נטו: 28000"
            )

        return StreamingResponse(
            _prompt_for_target_net_again(),
            media_type="text/plain; charset=utf-8",
        )
    if (
        tools_enabled
        and (resolved_intent != ChatIntent.REPORT)
        and request.client_id is not None
        and (not no_tools_requested_local)
        and (not is_qa_mode_local)
        and (target_net_for_plan is not None)
        and has_target_plan_keywords
        and (not _is_post_conversion_locked())
    ):
        def _generate_target_plan_tools_first(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            banner = _build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            try:
                loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    nonlocal effective_portfolio, effective_snapshot_at
                    effective_portfolio, effective_snapshot_at = loaded
            except Exception:
                pass

            plan_args = {
                "target_monthly_pension": float(target_net_for_plan),
                "target_is_net": True,
            }
            plan_result = _execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                plan_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )
            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            yield sanitize_user_visible_text(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
            )

        return StreamingResponse(
            _generate_target_plan_tools_first(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and request.client_id is not None:
        lowered_for_report = (original_user_msg or "").lower()
        is_system_results_report_request = (
            (("דוח" in lowered_for_report) and ("תוצאות" in lowered_for_report))
            or (("report" in lowered_for_report) and ("results" in lowered_for_report))
        )
        if (
            is_system_results_report_request
            and is_document_request(original_user_msg)
            and (not is_tax_documents_request(original_user_msg))
            and (not is_qa_request(original_user_msg))
            and (not is_no_tools_request(original_user_msg))
        ):

            latest_op = _latest_snapshot_operation_type()
            if latest_op is not None and latest_op != "TRANSFORM_FUNDS_TO_ASSETS":
                ui_payload: dict[str, Any] = {
                    "type": "ui_actions",
                    "actions": [
                        {
                            "type": "navigate",
                            "path": f"/clients/{request.client_id}/pension-portfolio",
                            "label": "פתח תיק",
                        }
                    ],
                    "status_message": "כדי להפיק דוח חייבים קודם לבצע המרה (TRANSFORM) כך שהנתונים יהיו במצב יציב.",
                }
                ui_action = (
                    "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
                )
                return StreamingResponse(iter([ui_action]), media_type="text/plain; charset=utf-8")

            def _generate_system_results_report_only(req_id: str):
                tool_db = SessionLocal()
                try:
                    tool_result = _execute_tool_call(
                        "GENERATE_FULL_REPORT",
                        {"output_format": "html", "report_type": "full"},
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
                    "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
                )

            return StreamingResponse(
                _generate_system_results_report_only(stream_request_id),
                media_type="text/plain; charset=utf-8",
            )

    if (
        tools_enabled
        and ui_action_short_circuit_allowed
        and resolved_intent == ChatIntent.REPORT
        and request.client_id is not None
    ):
        actions: list[dict[str, str]] = [
            {
                "type": "navigate",
                "path": f"/clients/{request.client_id}/reports?auto_html=1",
                "label": "פתח דוח",
            }
        ]
        ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
        ui_action = (
            "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
        )
        return StreamingResponse(iter([ui_action]), media_type="text/plain; charset=utf-8")

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

            banner = _build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            try:
                loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    nonlocal effective_portfolio, effective_snapshot_at
                    effective_portfolio, effective_snapshot_at = loaded
            except Exception:
                pass

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

            target_net = extract_target_net_ils(original_user_msg or "")
            desired_income = extract_desired_monthly_income_from_text(original_user_msg)
            desired_income_is_net = infer_desired_income_is_net_explicit(original_user_msg)

            if target_net is not None:
                desired_income = float(target_net)
                desired_income_is_net = True
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
                if bool(desired_income_is_net):
                    tool_args["desired_net_monthly_income"] = int(float(desired_income))

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
            _wrap_with_restore_banner(
                generate_data_awareness(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    effective_snapshot_at=effective_snapshot_at,
                    stream_request_id=stream_request_id,
                )
            ),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and request.client_id is not None and is_list_all_financial_entities_request(original_user_msg):
        return StreamingResponse(
            _wrap_with_restore_banner(
                generate_list_all_entities(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    effective_snapshot_at=effective_snapshot_at,
                    stream_request_id=stream_request_id,
                )
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
            _wrap_with_restore_banner(
                generate_system_inventory(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    stream_request_id=stream_request_id,
                )
            ),
            media_type="text/plain; charset=utf-8",
        )

    if tools_enabled and request.client_id is not None and _is_system_results_request(original_user_msg):
        return StreamingResponse(
            _wrap_with_restore_banner(
                generate_system_results(
                    computed_data=computed_data,
                    original_user_msg=original_user_msg,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    stream_request_id=stream_request_id,
                )
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
    target_net_for_cashflow = extract_target_net_ils(original_user_msg or "")
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
        or (target_net_for_cashflow is not None)
    )

    if plan_phrase_detected:
        requested_cashflow_calc = False

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

                banner = _build_recent_state_banner()
                if banner:
                    yield banner + "\n\n"

                try:
                    loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                    if loaded is not None:
                        nonlocal effective_portfolio, effective_snapshot_at
                        effective_portfolio, effective_snapshot_at = loaded
                except Exception:
                    pass

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

                if target_net_for_cashflow is not None:
                    desired_income = float(target_net_for_cashflow)
                    desired_income_is_net = True

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
                    if bool(desired_income_is_net):
                        tool_args["desired_net_monthly_income"] = int(float(desired_income))

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
        latest_op = _latest_snapshot_operation_type()
        if latest_op is not None and latest_op != "TRANSFORM_FUNDS_TO_ASSETS":
            return StreamingResponse(
                iter(
                    [
                        "כדי להפיק דוח חייבים קודם לבצע המרה (TRANSFORM) כך שהנתונים יהיו במצב יציב."
                    ]
                ),
                media_type="text/plain; charset=utf-8",
            )
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

    if _should_show_post_conversion_messages() and isinstance(original_user_msg, str):
        candidate = original_user_msg.strip()
        lowered = candidate.lower()

        # IMPORTANT: post-conversion lock must NOT block deterministic approval/replay
        # for execute-target-plan (TRANSFORM_FUNDS_TO_ASSETS), but it should block
        # rebuilding plans or direct transform execution on the original snapshot.
        if not wants_execute_target_plan:
            wants_plan_build = ("תכנית" in candidate) or ("תוכנית" in candidate)
            has_numeric_target = False
            try:
                cleaned = candidate.replace(",", "")
                has_numeric_target = bool(re.search(r"\b\d{4,6}\b", cleaned))
            except Exception:
                has_numeric_target = False

            wants_direct_transform = bool(
                explicit_transform
                or is_transform_request(candidate)
                or ("transform" in lowered)
                or ("המר" in candidate)
                or ("המרה" in candidate)
            )

            if wants_direct_transform or (wants_plan_build and has_numeric_target):
                pending_execute_target_plan = False
                try:
                    pending_execute_target_plan = bool(
                        load_pending_approval_ui_action_if_match(
                            db=db,
                            client_id=request.client_id,
                            request_kind="execute_target_plan",
                            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                        )
                    )
                except Exception:
                    pending_execute_target_plan = False

                logger.info(
                    "post_conversion_lock_early_block",
                    extra={
                        "endpoint": "stream",
                        "request_id": stream_request_id,
                        "client_id": request.client_id,
                        "post_conversion_locked": True,
                        "wants_execute_target_plan": bool(wants_execute_target_plan),
                        "pending_execute_target_plan": bool(pending_execute_target_plan),
                        "blocked_plan_build": bool(wants_plan_build and has_numeric_target),
                        "blocked_direct_transform": bool(wants_direct_transform),
                    },
                )

                if wants_plan_build and has_numeric_target:
                    return StreamingResponse(
                        iter([_build_post_conversion_plan_message()]),
                        media_type="text/plain; charset=utf-8",
                    )

                return StreamingResponse(
                    iter([_build_post_conversion_lock_message()]),
                    media_type="text/plain; charset=utf-8",
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

    if _should_show_post_conversion_messages() and isinstance(original_user_msg, str):
        candidate = original_user_msg.strip()
        lowered = candidate.lower()

        wants_plan_build = ("תכנית" in candidate) or ("תוכנית" in candidate)
        has_numeric_target = False
        try:
            cleaned = candidate.replace(",", "")
            has_numeric_target = bool(re.search(r"\b\d{4,6}\b", cleaned))
        except Exception:
            has_numeric_target = False

        pending_execute_target_plan = False
        pending_execute_scenario = False
        if request.client_id is not None:
            try:
                pending_execute_target_plan = bool(
                    load_pending_approval_ui_action_if_match(
                        db=db,
                        client_id=request.client_id,
                        request_kind="execute_target_plan",
                        tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    )
                )
            except Exception:
                pending_execute_target_plan = False

            try:
                pending_execute_scenario = bool(
                    load_pending_approval_ui_action_if_match(
                        db=db,
                        client_id=request.client_id,
                        request_kind="execute_retirement_scenario",
                        tool_name="EXECUTE_RETIREMENT_SCENARIO",
                    )
                )
            except Exception:
                pending_execute_scenario = False

        logger.info(
            "post_conversion_lock_evaluation",
            extra={
                "endpoint": "stream",
                "request_id": stream_request_id,
                "client_id": request.client_id,
                "post_conversion_locked": True,
                "wants_execute_target_plan": bool(wants_execute_target_plan),
                "pending_execute_target_plan": bool(pending_execute_target_plan),
                "pending_execute_retirement_scenario": bool(pending_execute_scenario),
            },
        )

        wants_direct_transform = bool(
            explicit_transform
            or is_transform_request(candidate)
            or ("transform" in lowered)
            or ("המר" in candidate)
            or ("המרה" in candidate)
        )

        if wants_direct_transform:
            return StreamingResponse(
                iter([_build_post_conversion_lock_message()]),
                media_type="text/plain; charset=utf-8",
            )

        if wants_plan_build and has_numeric_target and (not wants_execute_target_plan):
            return StreamingResponse(
                iter([_build_post_conversion_plan_message()]),
                media_type="text/plain; charset=utf-8",
            )

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

        now = datetime.now(timezone.utc)
        banner = _build_restore_snapshot_banner(now_utc=now)
        if isinstance(banner, str) and banner.strip() and (resolved_intent != ChatIntent.REPORT):
            yield banner.strip() + "\n\n"

        current_pension_portfolio = effective_portfolio

        if (
            resolved_intent == ChatIntent.REPORT
            and request.client_id is not None
            and (not no_tools_requested)
            and (not conceptual_tools_disabled)
        ):
            actions: list[dict[str, str]] = [
                {
                    "type": "navigate",
                    "path": f"/clients/{request.client_id}/reports?auto_html=1",
                    "label": "פתח דוח",
                }
            ]
            ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
            yield (
                "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
            )
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
