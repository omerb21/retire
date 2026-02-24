import json

from fastapi.responses import StreamingResponse

from app.models.client import Client
from app.services.llm_chat.orchestration_utils import is_max_capital_request
from app.services.pension_portfolio.snapshot_loader import (
    load_current_effective_state,
    load_latest_pension_portfolio_snapshot_models,
)
from app.services.llm_chat.pending_approvals import (
    load_pending_approval_ui_action_if_match,
)

from ..stream_tool_execution import _execute_tool_call
from ..stream_streaming_helpers import _stream_request_approval


def _maybe_handle_max_capital_request(
    *,
    request,
    db,
    original_user_msg: str,
    lowered_user_msg: str,
    explicit_termination: bool,
    is_doc_request: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    computed_data,
    effective_portfolio,
    force_max_exemption: bool,
    stream_request_id: str,
):
    max_capital_request = (not explicit_termination) and is_max_capital_request(
        original_user_msg
    )
    wants_execute_max_capital = max_capital_request and ("בצע" in lowered_user_msg)

    if request.client_id is not None and wants_execute_max_capital:
        try:
            pending_ui = load_pending_approval_ui_action_if_match(
                db=db,
                client_id=request.client_id,
                request_kind="execute_retirement_scenario",
                tool_name="EXECUTE_RETIREMENT_SCENARIO",
            )
        except Exception:
            pending_ui = None
        if isinstance(pending_ui, str) and pending_ui.strip():
            return StreamingResponse(iter([pending_ui]), media_type="text/plain")

    if (
        request.client_id is not None
        and max_capital_request
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
    ):
        effective_state = None
        try:
            effective_state = load_current_effective_state(db, request.client_id)
        except Exception:
            effective_state = None

        banner = None
        if isinstance(effective_state, dict) and bool(
            effective_state.get("recent_update")
        ):
            op_type = str(effective_state.get("last_operation_type") or "").strip()
            if op_type:
                banner = f"מצב מערכת: עודכן לאחר פעולה אחרונה ({op_type})"
            else:
                banner = "מצב מערכת: עודכן לאחר פעולה אחרונה"

        try:
            loaded = load_latest_pension_portfolio_snapshot_models(
                db, request.client_id
            )
            if loaded is not None:
                effective_portfolio, _snapshot_at = loaded
        except Exception:
            pass

        retirement_age = None
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
            client_age = (
                client.get_age() if client and hasattr(client, "get_age") else None
            )
            from app.services.retirement_age_service import (
                DEFAULT_MALE_RETIREMENT_AGE,
                get_retirement_age_simple,
            )

            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            try:
                if (
                    client
                    and getattr(client, "birth_date", None)
                    and getattr(client, "gender", None)
                ):
                    legal_ret_age = int(
                        get_retirement_age_simple(client.birth_date, client.gender)
                    )
            except Exception:
                legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

            retirement_age = max(int(legal_ret_age), int(client_age or legal_ret_age))
        except Exception:
            retirement_age = 67

        scenarios_raw = _execute_tool_call(
            "RUN_RETIREMENT_SCENARIOS",
            {"retirement_age": int(retirement_age)},
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=stream_request_id,
        )
        try:
            parsed = json.loads(scenarios_raw) if scenarios_raw else {}
        except Exception:
            parsed = {}

        scenario_id = None
        for row in (parsed.get("scenarios") if isinstance(parsed, dict) else []) or []:
            if (
                isinstance(row, dict)
                and row.get("scenario_key") == "scenario_2_max_capital"
            ):
                scenario_id = row.get("scenario_id")
                break

        if scenario_id is None:
            lines = ["לא הצלחתי ליצור תרחיש 'מקסימום הון' במערכת."]
            if banner:
                lines = [banner, "", *lines]
            return StreamingResponse(iter(lines), media_type="text/plain")

        if wants_execute_max_capital:
            return _stream_request_approval(
                "EXECUTE_RETIREMENT_SCENARIO",
                {"scenario_id": int(scenario_id)},
                reason=(
                    "בקשת 'משיכה הונית מלאה' מחייבת שמירת קצבת מינימום 5,500 ₪. "
                    "אצור ואבצע את תרחיש 'מקסימום הון' (שמשאיר קצבת מינימום) רק לאחר אישור."
                ),
                computed_data=computed_data,
                client_id=request.client_id,
                db=db,
                request_kind="execute_retirement_scenario",
            )

        lines = [
            "יצרתי תרחיש 'מקסימום הון' (עם שמירת קצבת מינימום 5,500 ₪). "
            "אם תרצה לבצע אותו בפועל במערכת, כתוב: 'בצע'."
        ]
        if banner:
            lines = [banner, "", *lines]
        return StreamingResponse(iter(lines), media_type="text/plain")

    return None
