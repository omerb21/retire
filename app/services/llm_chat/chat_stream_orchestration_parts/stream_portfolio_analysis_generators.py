import json

from app.models.client import Client
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_agent_tools_service import AgentToolsService


def generate_breakdown(*, computed_data, portfolio, original_user_msg, effective_snapshot_at) -> str:
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


def generate_portfolio_analysis(*, computed_data, request, db, portfolio, original_user_msg, effective_snapshot_at) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    full_name = None
    if request.client_id is not None:
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
            full_name = getattr(client, "full_name", None) if client else None
        except Exception:
            full_name = None

    title_name = (
        str(full_name).strip()
        if isinstance(full_name, str) and full_name.strip()
        else ""
    )
    title = "כותרת: ניתוח תיק פנסיוני מלא"
    if title_name:
        title = f"{title} — {title_name}"

    scenarios_text = ""
    if request.client_id is not None:
        try:
            client_obj = db.query(Client).filter(Client.id == request.client_id).first()
            client_age = None
            try:
                client_age = (
                    client_obj.get_age()
                    if client_obj and hasattr(client_obj, "get_age")
                    else None
                )
            except Exception:
                client_age = None

            from app.services.retirement_age_service import (
                DEFAULT_MALE_RETIREMENT_AGE,
                get_retirement_age_simple,
            )

            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            try:
                if (
                    client_obj
                    and getattr(client_obj, "birth_date", None)
                    and getattr(client_obj, "gender", None)
                ):
                    legal_ret_age = int(
                        get_retirement_age_simple(
                            client_obj.birth_date,
                            client_obj.gender,
                        )
                    )
            except Exception:
                legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

            retirement_age = legal_ret_age
            if client_age is not None:
                retirement_age = max(int(legal_ret_age), int(client_age))

            agent_tools = AgentToolsService(
                db=db,
                client_id=request.client_id,
                client_object=client_obj,
                pension_portfolio_data=portfolio,
            )
            scenario_result = agent_tools.run_retirement_scenarios(
                retirement_age=int(retirement_age),
                pension_portfolio=portfolio,
                include_current_employer_termination=False,
            )
            if scenario_result.get("success"):
                scenarios_text = str(
                    scenario_result.get("explanation") or ""
                ).strip()
            else:
                scenarios_text = ""
        except Exception:
            scenarios_text = ""

    analysis = (
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

    note = "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק."
    if analysis:
        extra = ""
        if isinstance(scenarios_text, str) and scenarios_text.strip():
            extra = f"\n\n{scenarios_text}"
        yield f"{note}\n\n{title}\n\n{analysis}{extra}"
        return

    yield f"{title}\n\nאין תיק פנסיוני לניתוח."
