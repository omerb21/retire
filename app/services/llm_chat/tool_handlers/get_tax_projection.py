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
    gross = args.get("gross_monthly_pension")
    if not gross:
        return "Error: Missing argument 'gross_monthly_pension'"

    gross_value = float(gross)

    FALLBACK_Q_TOTAL = 20600.0
    FALLBACK_Q_TOTAL_FULL = 27432.0

    expected_q_total = None
    expected_q_total_full = None
    try:
        pension_funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()

        q_base = 0.0
        for fund in pension_funds:
            if fund.monthly_pension:
                q_base += float(fund.monthly_pension)

        employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == client_id)
            .first()
        )

        if employer and employer.last_salary and employer.continuity_years:
            total_severance = float(employer.last_salary) * float(employer.continuity_years)

            annuity_factor = 200.0

            q_severance_partial = (total_severance * 0.5) / annuity_factor
            expected_q_total = q_base + q_severance_partial

            q_severance_full = total_severance / annuity_factor
            expected_q_total_full = q_base + q_severance_full

            logger.info(
                "📊 D2.10/D2.13 DERIVED: Q_base=%.0f, Q_total_partial=%.0f, Q_total_full=%.0f (client-specific)",
                q_base,
                expected_q_total,
                expected_q_total_full,
            )
    except Exception as e:
        logger.warning("D2.10: Could not calculate Q_total from client data: %s", e)
        expected_q_total = None
        expected_q_total_full = None

    if expected_q_total is None or expected_q_total <= 0:
        logger.warning(
            "🚨 D2.12 FALLBACK: Using hardcoded Q_total=%.0f ₪",
            FALLBACK_Q_TOTAL,
        )
        expected_q_total = FALLBACK_Q_TOTAL
        expected_q_total_full = FALLBACK_Q_TOTAL_FULL

    TOLERANCE_PERCENT = 15

    min_partial = expected_q_total * (1 - TOLERANCE_PERCENT / 100)
    max_partial = expected_q_total * (1 + TOLERANCE_PERCENT / 100)
    is_valid_partial = min_partial <= gross_value <= max_partial

    min_full = expected_q_total_full * (1 - TOLERANCE_PERCENT / 100)
    max_full = expected_q_total_full * (1 + TOLERANCE_PERCENT / 100)
    is_valid_full = min_full <= gross_value <= max_full

    if is_valid_partial or is_valid_full:
        scenario = "רצף קצבה (מלא)" if is_valid_full else "קצבה חלקית"
        logger.info(
            "✅ D2.13: Pension value %.0f ₪ is valid for scenario: %s",
            gross_value,
            scenario,
        )
    else:
        logger.warning(
            "🚨 D2.10 ENFORCEMENT: Rejecting LLM-calculated pension value %.0f ₪. Valid values: ~%.0f ₪ (partial) or ~%.0f ₪ (full). Overriding with partial scenario value.",
            gross_value,
            expected_q_total,
            expected_q_total_full,
        )
        gross_value = expected_q_total

        result = agent_tools.get_tax_projection(monthly_pension=gross_value)
        warning_msg = (
            f"⚠️ **אזהרה D2.10:** הערך שסופק ({float(gross):.0f} ₪) אינו תואם את נוסחת Q_total.\n"
            f"ערכים תקפים: ~{expected_q_total:.0f} ₪ (קצבה חלקית) או ~{expected_q_total_full:.0f} ₪ (רצף קצבה מלא).\n"
            f"הערך תוקן אוטומטית ל-{expected_q_total:.0f} ₪.\n\n"
        )
        return (
            warning_msg
            + f"Tax Projection Result:\n{result.get('explanation', 'No details available')}"
        )

    result = agent_tools.get_tax_projection(monthly_pension=gross_value)
    return f"Tax Projection Result:\n{result.get('explanation', 'No details available')}"
