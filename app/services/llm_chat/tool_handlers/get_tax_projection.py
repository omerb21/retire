import logging

from sqlalchemy.orm import Session

from app.models import CurrentEmployer, PensionFund
from app.services.llm_agent_tools_service import AgentToolsService

logger = logging.getLogger("app.llm_chat.tools")


def handle_get_tax_projection(
    *,
    args: dict,
    client_id: int,
    db: Session,
    agent_tools: AgentToolsService,
) -> str:
    projections = args.get("projections")
    if isinstance(projections, list) and projections:
        lines: list[str] = []
        for item in projections:
            if not isinstance(item, dict):
                continue
            gross = item.get("gross_monthly_pension")
            scenario_id = item.get("scenario_id")
            if gross is None:
                if scenario_id is not None:
                    lines.append(
                        f"תרחיש {scenario_id}: Error: Missing argument 'gross_monthly_pension'"
                    )
                else:
                    lines.append("Error: Missing argument 'gross_monthly_pension'")
                continue
            try:
                gross_value = float(gross)
            except Exception:
                if scenario_id is not None:
                    lines.append(
                        f"תרחיש {scenario_id}: Error: invalid gross_monthly_pension"
                    )
                else:
                    lines.append("Error: invalid gross_monthly_pension")
                continue
            try:
                result = agent_tools.get_tax_projection(monthly_pension=gross_value)
                explanation = result.get("explanation", "No details available")
            except Exception as e:
                explanation = str(e) or "Unknown error"
            prefix = f"תרחיש {scenario_id}: " if scenario_id is not None else ""
            lines.append(f"{prefix}קצבה ברוטו {gross_value:,.0f} ₪ ->\n{explanation}")

        if not lines:
            return "Error: Missing argument 'gross_monthly_pension'"
        return "תוצאות הערכת מס (לפי תרחיש):\n" + "\n\n".join(lines)

    gross = args.get("gross_monthly_pension")
    if gross is None:
        return "Error: Missing argument 'gross_monthly_pension'"

    try:
        gross_value = float(gross)
    except Exception:
        return "Error: invalid gross_monthly_pension"

    try:
        result = agent_tools.get_tax_projection(monthly_pension=gross_value)
        explanation = result.get("explanation", "No details available")
    except Exception as e:
        explanation = str(e) or "Unknown error"

    return f"תוצאת הערכת מס (קצבה ברוטו):\n{explanation}"
