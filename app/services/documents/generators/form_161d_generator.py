"""
מחולל טופס 161ד
"""

from pathlib import Path
from datetime import date, datetime
from sqlalchemy.orm import Session
from typing import Optional
import logging
import pdf_filler

from ..utils import TEMPLATE_161D
from ..data_fetchers import fetch_fixation_data, fetch_client_data
from app.services.retirement.utils.pension_utils import get_effective_pension_start_date

logger = logging.getLogger(__name__)


def fill_161d_form(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    ממלא טופס 161ד עם נתוני קיבוע זכויות מהDB

    Args:
        db: סשן DB
        client_id: מזהה לקוח
        output_dir: תיקיית פלט

    Returns:
        נתיב לטופס שנוצר או None אם נכשל
    """
    try:
        logger.info(f"📝 Starting form 161d fill for client {client_id}")

        # בדיקת קיום טמפלייט
        if not TEMPLATE_161D.exists():
            logger.error(f"❌ Template not found: {TEMPLATE_161D}")
            return None

        logger.info(f"✅ Template found: {TEMPLATE_161D}")

        # שליפת נתוני לקוח
        client = fetch_client_data(db, client_id)
        if not client:
            return None

        # שליפת נתוני קיבוע זכויות
        fixation_data = fetch_fixation_data(db, client_id)
        if not fixation_data:
            logger.error(
                f"❌ No fixation data found for client {client_id}. Please calculate fixation first!"
            )
            return None

        exemption_summary = fixation_data.exemption_summary
        raw_result = fixation_data.raw_result

        logger.info(f"✅ Fixation data loaded from DB")

        # חישוב תאריך תחילת קצבה ראשון (לשדה firstkitzba)
        first_pension_date = get_effective_pension_start_date(db, client) or getattr(
            client,
            "pension_start_date",
            None,
        )
        first_pension_str_global = ""
        if first_pension_date:
            try:
                if isinstance(first_pension_date, str):
                    first_pension_str_global = datetime.fromisoformat(
                        first_pension_date
                    ).strftime("%d/%m/%Y")
                else:
                    first_pension_str_global = first_pension_date.strftime("%d/%m/%Y")
            except Exception:
                first_pension_str_global = ""

        # חילוץ תאריך זכאות
        eligibility_date = fixation_data.eligibility_date
        if eligibility_date:
            try:
                if isinstance(eligibility_date, str):
                    eligibility_date = datetime.fromisoformat(
                        eligibility_date
                    ).strftime("%d/%m/%Y")
                else:
                    eligibility_date = eligibility_date.strftime("%d/%m/%Y")
            except:
                eligibility_date = ""

        # חילוץ נתונים
        exempt_capital_initial = exemption_summary.get("exempt_capital_initial", 0)
        total_impact = exemption_summary.get("total_impact", 0)
        remaining_exempt_capital = exemption_summary.get("remaining_exempt_capital", 0)
        exemption_percentage = exemption_summary.get("exemption_percentage", 0)

        # חישוב מענקים
        grants_list = raw_result.get("grants", [])
        grants_nominal = sum(g.get("grant_amount", 0) for g in grants_list)
        grants_indexed = sum(g.get("limited_indexed_amount", 0) for g in grants_list)
        total_exempt_grants = sum(
            g.get("limited_indexed_amount", 0)
            for g in grants_list
            if g.get("impact_on_exemption", 0) > 0
        )

        # חישוב קצבה פטורה
        exempt_pension_monthly = (
            remaining_exempt_capital / 180 if remaining_exempt_capital > 0 else 0
        )
        pension_ceiling = 9430

        # מענק עתידי משוריין
        reserved_grant = exemption_summary.get("future_grant_reserved", 0)
        reserved_grant_impact = exemption_summary.get("future_grant_impact", 0)
        commutations_total = exemption_summary.get("total_commutations", 0)

        # נתוני מעסיק להמשך עבודה (אם הוזנו במסך קיבוע זכויות)
        employer_snapshot = raw_result.get("current_employer_snapshot") or {}

        employer_name = ""
        work_start_str = ""
        work_end_str = ""
        last_paycheck = 0.0
        first_pension_str = first_pension_str_global

        if isinstance(employer_snapshot, dict) and employer_snapshot.get(
            "continues_working"
        ):
            employer_name = employer_snapshot.get("employer_name") or ""

            work_start_iso = employer_snapshot.get(
                "work_start_date"
            ) or employer_snapshot.get("start_date")
            work_end_iso = employer_snapshot.get(
                "work_end_date"
            ) or employer_snapshot.get("end_date")
            first_pension_iso = employer_snapshot.get("first_pension_date")

            try:
                if work_start_iso:
                    if isinstance(work_start_iso, str):
                        work_start_str = datetime.fromisoformat(
                            work_start_iso
                        ).strftime("%d/%m/%Y")
                    else:
                        work_start_str = work_start_iso.strftime("%d/%m/%Y")
            except Exception:
                work_start_str = ""

            try:
                if work_end_iso:
                    if isinstance(work_end_iso, str):
                        work_end_str = datetime.fromisoformat(work_end_iso).strftime(
                            "%d/%m/%Y"
                        )
                    else:
                        work_end_str = work_end_iso.strftime("%d/%m/%Y")
            except Exception:
                work_end_str = ""

            try:
                if first_pension_iso:
                    if isinstance(first_pension_iso, str):
                        first_pension_str = datetime.fromisoformat(
                            first_pension_iso
                        ).strftime("%d/%m/%Y")
                    else:
                        first_pension_str = first_pension_iso.strftime("%d/%m/%Y")
            except Exception:
                first_pension_str = ""

            try:
                last_paycheck_raw = employer_snapshot.get("last_salary", 0) or 0
                last_paycheck = float(last_paycheck_raw)
            except (TypeError, ValueError):
                last_paycheck = 0.0

        # בניית כתובת
        address_parts = []
        if client.address_street:
            address_parts.append(client.address_street)
        if client.address_city:
            address_parts.append(client.address_city)
        client_address = ", ".join(address_parts) if address_parts else ""

        # נתוני הטופס
        field_data = {
            "Today": date.today().strftime("%d/%m/%Y"),
            "ClientFirstName": client.first_name or "",
            "ClientLastName": client.last_name or "",
            "ClientID": client.id_number or "",
            "ClientAddress": client_address,
            "ClientBdate": (
                client.birth_date.strftime("%d/%m/%Y") if client.birth_date else ""
            ),
            "Clientphone": client.phone or "",
            "ClientZdate": eligibility_date,
            "ExemptCapitalInitial": f"{exempt_capital_initial:,.0f}",
            "GrantsNominal": f"{grants_nominal:,.0f}",
            "GrantsIndexed": f"{grants_indexed:,.0f}",
            "TotalImpact": f"{total_impact:,.0f}",
            "ReservedGrant": f"{reserved_grant:,.0f}",
            "CommutationsTotal": f"{commutations_total:,.0f}",
            "RemainingExemptCapital": f"{remaining_exempt_capital:,.0f}",
            "PensionCeiling": f"{pension_ceiling:,.0f}",
            "ExemptPensionMonthly": f"{exempt_pension_monthly:,.0f}",
            "ExemptionPercentage": f"{exemption_percentage * 100:.1f}%",
            "Clientmaanakpatur": f"{total_exempt_grants:,.0f}",
            "Clientpgiabahon": f"{total_impact:,.0f}",
            "clientcapsum": f"{commutations_total:,.0f}",
            "clientshiryun": f"{reserved_grant:,.0f}",
            "Clientemployer": employer_name,
            "workstart": work_start_str,
            "workend": work_end_str,
            "lastpaycheck": f"{last_paycheck:,.0f}" if last_paycheck else "",
            "firstkitzba": first_pension_str,
        }

        logger.info(f"📊 Form data prepared: {len(field_data)} fields")

        # מילוי הטופס
        output_path = output_dir / "טופס_161ד.pdf"
        logger.info(f"📄 Filling PDF form...")

        result = pdf_filler.fill_acroform(TEMPLATE_161D, output_path, field_data)

        if output_path.exists():
            size = output_path.stat().st_size
            logger.info(
                f"✅ Form 161d created successfully: {output_path} ({size:,} bytes)"
            )
            return output_path
        else:
            logger.error(f"❌ Form file not created at {output_path}")
            return None

    except Exception as e:
        logger.error(f"❌ Error creating 161ד form: {e}", exc_info=True)
        return None
