from typing import Any

from fastapi.responses import StreamingResponse

from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.orchestration_utils import (
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
)

from ..stream_streaming_helpers import _stream_execute_tool_no_approval
from ..stream_approval_generators import generate_forced_approval


def _maybe_handle_termination_deterministic(
    *,
    request: ChatRequest,
    db,
    original_user_msg: str,
    explicit_termination: bool,
    termination_change: bool,
    no_tools_requested: bool,
    is_qa_mode: bool,
    wants_execute_target_plan: bool,
    wants_fixation_execute: bool,
    computed_data,
    effective_portfolio,
    force_max_exemption: bool,
    stream_request_id: str,
    is_portfolio_analysis: bool,
):
    termination_already_executed = False
    if request.client_id is not None:
        current_employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == request.client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )
        if current_employer is not None and current_employer.end_date is not None:
            grants_count = (
                db.query(EmployerGrant)
                .filter(
                    EmployerGrant.employer_id == current_employer.id,
                    EmployerGrant.grant_type == GrantType.severance,
                )
                .count()
            )
            confirmed = False
            try:
                other_grants = current_employer.other_grants or {}
                if isinstance(other_grants, dict):
                    confirmed = bool(other_grants.get("termination_confirmed"))
            except Exception:
                confirmed = False
            termination_already_executed = confirmed or (grants_count > 0)

    if (
        explicit_termination
        and request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
        and (not (wants_execute_target_plan or wants_fixation_execute))
    ):
        recent_user_text = "\n".join(
            [
                str(getattr(m, "content", ""))
                for m in (request.messages or [])
                if getattr(m, "role", None) == "user"
            ][-8:]
        )
        tool_args: dict[str, Any] = {"confirmed": True}
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(recent_user_text)
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override
        tool_args.update(extract_process_termination_choice_overrides(original_user_msg))

        return (
            termination_already_executed,
            _stream_execute_tool_no_approval(
                "PROCESS_TERMINATION",
                tool_args,
                computed_data=computed_data,
                client_id=request.client_id,
                db=db,
                effective_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                stream_request_id=stream_request_id,
                is_portfolio_analysis=is_portfolio_analysis,
            ),
        )

    if (
        request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
        and (wants_execute_target_plan or wants_fixation_execute)
    ):
        return (
            termination_already_executed,
            StreamingResponse(
                generate_forced_approval(
                    computed_data=computed_data,
                    explicit_termination=explicit_termination,
                    termination_already_executed=termination_already_executed,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    force_max_exemption=force_max_exemption,
                    stream_request_id=stream_request_id,
                    wants_execute_target_plan=wants_execute_target_plan,
                    wants_fixation_execute=wants_fixation_execute,
                ),
                media_type="text/plain; charset=utf-8",
            ),
        )

    return termination_already_executed, None
