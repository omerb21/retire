import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Client

logger = logging.getLogger("app.llm_chat.tools")


def handle_calculate_fixation_of_rights(
    *,
    args: dict,
    client_id: int,
    db: Session,
    client_obj: Optional[Client],
) -> str:
    logger.info("📋 CALCULATE_FIXATION_OF_RIGHTS called - Calculating fixation")

    try:
        include_current_employer = args.get("include_current_employer", False)
        save_result = args.get("save_result", True)

        from app.routers.rights_fixation import calculate_and_save_fixation_for_client
        from app.routers.rights_fixation import update_fixation_exempt_pension_fields

        if save_result:
            fixation_result = calculate_and_save_fixation_for_client(db, client_id)

            if not fixation_result:
                return json.dumps(
                    {
                        "success": False,
                        "message": "לא ניתן לחשב קיבוע זכויות. ייתכן שחסרים נתונים (תאריך לידה, מין, מענקים).",
                    },
                    ensure_ascii=False,
                )

            raw_result = fixation_result.raw_result or {}
            exemption_summary = raw_result.get("exemption_summary", {}) or {}

            try:
                update_fixation_exempt_pension_fields(fixation_result)
                db.flush()
                raw_result = fixation_result.raw_result or raw_result
                exemption_summary = raw_result.get("exemption_summary", exemption_summary) or {}
            except Exception:
                pass

            response = {
                "success": True,
                "message": "✅ חישוב קיבוע זכויות בוצע ונשמר בהצלחה!",
                "fixation_id": fixation_result.id,
                "remaining_exempt_capital": exemption_summary.get("remaining_exempt_capital", 0),
                "total_grants_used": exemption_summary.get("total_grants_used", 0),
                "exemption_percentage": exemption_summary.get("exemption_percentage", 0),
                "monthly_exempt_pension": exemption_summary.get("monthly_exempt_pension", 0),
                "remaining_monthly_exemption": exemption_summary.get(
                    "remaining_monthly_exemption", 0
                ),
                "exempt_pension_percentage": exemption_summary.get(
                    "exempt_pension_percentage", 0
                ),
                "saved": True,
            }
        else:
            from app.services.rights_fixation import calculate_full_fixation
            from app.models.grant import Grant

            grants = db.query(Grant).filter(Grant.client_id == client_id).all()

            if not client_obj.birth_date or not client_obj.gender:
                return json.dumps(
                    {
                        "success": False,
                        "message": "חסרים נתוני לקוח (תאריך לידה או מין) לחישוב קיבוע זכויות.",
                    },
                    ensure_ascii=False,
                )

            formatted_data = {
                "id": client_id,
                "birth_date": client_obj.birth_date.isoformat(),
                "gender": client_obj.gender,
                "grants": [
                    {
                        "grant_amount": g.grant_amount,
                        "work_start_date": g.work_start_date.isoformat() if g.work_start_date else None,
                        "work_end_date": g.work_end_date.isoformat() if g.work_end_date else None,
                        "grant_date": g.grant_date.isoformat() if g.grant_date else None,
                        "employer_name": g.employer_name,
                    }
                    for g in grants
                ],
            }

            result = calculate_full_fixation(formatted_data)
            exemption_summary = result.get("exemption_summary", {}) or {}

            response = {
                "success": True,
                "message": "✅ חישוב קיבוע זכויות בוצע (ללא שמירה).",
                "remaining_exempt_capital": exemption_summary.get("remaining_exempt_capital", 0),
                "total_grants_used": exemption_summary.get("total_grants_used", 0),
                "exemption_percentage": exemption_summary.get("exemption_percentage", 0),
                "monthly_exempt_pension": exemption_summary.get("monthly_exempt_pension", 0),
                "saved": False,
            }

        logger.info("✅ CALCULATE_FIXATION_OF_RIGHTS completed: saved=%s", save_result)

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("CALCULATE_FIXATION_OF_RIGHTS failed: %s", e, exc_info=True)
        return f"Error: שגיאה בחישוב קיבוע זכויות: {str(e)}"
