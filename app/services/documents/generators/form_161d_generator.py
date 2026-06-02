"""
מחולל טופס 161ד
"""

import logging
from datetime import date, datetime
from pathlib import Path
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

import pdf_filler
from app.services.retirement.utils.pension_utils import get_effective_pension_start_date

from ..data_fetchers import (
    fetch_client_data,
    fetch_commutations_data,
    fetch_fixation_data,
    fetch_pension_data,
)
from ..utils import TEMPLATE_161D

logger = logging.getLogger(__name__)


def _format_date(value: Any) -> str:
    if not value:
        return ""
    try:
        if isinstance(value, str):
            return datetime.fromisoformat(value).strftime("%d/%m/%Y")
        return value.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _format_money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.0f}" if amount else ""


def _to_float(value: Any) -> float:
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def _get_form_161d_options(raw_payload: dict, raw_result: dict) -> dict:
    for source in (raw_payload, raw_result):
        if isinstance(source, dict):
            options = source.get("form_161d")
            if isinstance(options, dict):
                return options
    return {}


def _build_pension_rows(pensions: list[Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    for pension in pensions:
        amount = _to_float(getattr(pension, "pension_amount", None))
        status = str(getattr(pension, "record_status", "") or "active")
        if amount <= 0 or status == "invalid":
            continue
        candidates.append(pension)

    candidates.sort(
        key=lambda item: (
            getattr(item, "pension_start_date", None) is None,
            getattr(item, "pension_start_date", None) or date.max,
            str(getattr(item, "fund_name", "") or ""),
        )
    )
    return [
        {
            "payer": getattr(item, "fund_name", "") or "",
            "amount": _to_float(getattr(item, "pension_amount", None)),
            "start_date": getattr(item, "pension_start_date", None),
        }
        for item in candidates[:2]
    ]


def _build_grant_rows(
    grants: list[dict[str, Any]],
    eligibility_date: Any,
    current_employer_name: str = "",
) -> list[dict[str, Any]]:
    _ = eligibility_date

    rows: list[dict[str, Any]] = []
    for grant in grants:
        if not isinstance(grant, dict):
            continue
        employer_name = grant.get("employer_name") or ""
        employer_name_normalized = str(employer_name).strip().lower()
        current_name_normalized = str(current_employer_name or "").strip().lower()
        if (
            employer_name_normalized
            and (
                employer_name_normalized == current_name_normalized
                or "מעסיק נוכחי" in employer_name_normalized
                or "current employer" in employer_name_normalized
            )
        ):
            continue
        amount = _first_non_empty(
            grant.get("limited_indexed_amount"),
            grant.get("grant_indexed_amount"),
            grant.get("indexed_full"),
            grant.get("grant_amount"),
        )
        rows.append(
            {
                "employer": employer_name,
                "start_date": grant.get("work_start_date"),
                "end_date": grant.get("work_end_date"),
                "amount": amount,
            }
        )

    return rows[:3]


def _commutation_amount(asset: Any) -> float:
    remarks = str(getattr(asset, "remarks", "") or "")
    if "amount=" in remarks:
        try:
            marker_value = (
                remarks.split("amount=", 1)[1]
                .split(";", 1)[0]
                .split("&", 1)[0]
                .split(",", 1)[0]
            )
            return float(marker_value)
        except (TypeError, ValueError):
            pass
    return _to_float(getattr(asset, "current_value", None))


def _commutation_payer(asset: Any) -> str:
    return str(
        _first_non_empty(
            getattr(asset, "asset_name", None),
            getattr(asset, "description", None),
            "ראה נספח היוונים",
        )
    )


def _build_form_161d_field_data(
    *,
    client,
    fixation_data,
    pensions: list[Any],
    commutations: list[Any],
) -> dict[str, Any]:
    exemption_summary = fixation_data.exemption_summary
    raw_result = (
        fixation_data.raw_result if isinstance(fixation_data.raw_result, dict) else {}
    )
    raw_payload = getattr(fixation_data, "raw_payload", None)
    if not isinstance(raw_payload, dict):
        raw_payload = (
            raw_result.get("raw_payload")
            if isinstance(raw_result.get("raw_payload"), dict)
            else {}
        )
    form_options = _get_form_161d_options(raw_payload, raw_result)

    eligibility_date = fixation_data.eligibility_date
    grants_list = raw_result.get("grants", [])
    if not isinstance(grants_list, list):
        grants_list = []

    employer_snapshot = raw_result.get("current_employer_snapshot") or {}
    if not isinstance(employer_snapshot, dict):
        employer_snapshot = {}

    address_parts = []
    if getattr(client, "address_street", None):
        address_parts.append(client.address_street)
    if getattr(client, "address_city", None):
        address_parts.append(client.address_city)
    client_address = ", ".join(address_parts) if address_parts else ""

    pension_rows = _build_pension_rows(pensions)
    grant_rows = _build_grant_rows(
        grants_list,
        eligibility_date,
        employer_snapshot.get("employer_name") or "",
    )

    commutations_total = _first_non_empty(
        exemption_summary.get("total_commutations"),
        getattr(fixation_data, "used_commutation", 0),
        0,
    )
    commutations_total_float = _to_float(commutations_total)
    actual_commutations_total = sum(_commutation_amount(item) for item in commutations)
    if actual_commutations_total > 0:
        commutations_total_float = actual_commutations_total

    future_commutation_amount = _first_non_empty(
        form_options.get("future_commutation_amount"),
        raw_result.get("future_commutation_amount"),
        "",
    )
    request_current_commutation = bool(
        form_options.get(
            "request_current_commutation_approval",
            bool(commutations),
        )
    )
    current_commutation = commutations[0] if commutations else None

    allocation = str(form_options.get("additional_exemption_allocation") or "").lower()
    form_161h_submitted = form_options.get("form_161h_submitted")
    has_past_commutation = bool(
        form_options.get("has_past_exempt_commutation", commutations_total_float > 0)
    )
    continues_working = bool(employer_snapshot.get("continues_working"))

    fields: dict[str, Any] = {
        "Today": date.today().strftime("%d/%m/%Y"),
        "ClientFirstName": getattr(client, "first_name", None) or "",
        "ClientLastName": getattr(client, "last_name", None) or "",
        "ClientID": getattr(client, "id_number", None) or "",
        "ClientAddress": client_address,
        "ClientBdate": _format_date(getattr(client, "birth_date", None)),
        "Clientphone": getattr(client, "phone", None) or "",
        "ClientEmail": getattr(client, "email", None) or "",
        "clientcapsum": _format_money(commutations_total_float),
        "clientshiryun": _format_money(
            exemption_summary.get("future_grant_reserved", 0)
        ),
        "Clientemployer": employer_snapshot.get("employer_name") or "",
        "workstart": _format_date(
            _first_non_empty(
                employer_snapshot.get("work_start_date"),
                employer_snapshot.get("start_date"),
            )
        ),
        "workend": _format_date(
            _first_non_empty(
                employer_snapshot.get("work_end_date"),
                employer_snapshot.get("end_date"),
            )
        ),
        "lastpaycheck": _format_money(employer_snapshot.get("last_salary")),
        "mnkptryes": continues_working,
        "mnkptrno": not continues_working,
        "Check Box1": allocation == "proportional",
        "Check Box2": allocation == "commutation",
        "Check Box3": allocation == "pension",
        "Check Box4": form_161h_submitted is True,
        "Check Box5": form_161h_submitted is False,
        "Check Box6": not has_past_commutation,
        "Check Box7": has_past_commutation,
        "Check Box8": request_current_commutation,
        "futurecapital": _format_money(
            _first_non_empty(future_commutation_amount, commutations_total_float)
        ),
        "capitalpayer": "",
        "capitalsum": "",
        "capitaltime": "",
    }

    for idx in range(1, 3):
        row = pension_rows[idx - 1] if len(pension_rows) >= idx else {}
        fields[f"Kitzbapayer{idx}"] = row.get("payer", "")
        fields[f"Kitzbasum{idx}"] = _format_money(row.get("amount"))
        fields[f"Kitzbastart{idx}"] = _format_date(row.get("start_date"))

    for idx in range(1, 4):
        row = grant_rows[idx - 1] if len(grant_rows) >= idx else {}
        fields[f"pastemply{idx}"] = row.get("employer", "")
        fields[f"pastemplystart{idx}"] = _format_date(row.get("start_date"))
        fields[f"pastemplyend{idx}"] = _format_date(row.get("end_date"))
        fields["pastemply1sum3" if idx == 3 else f"pastemplysum{idx}"] = _format_money(
            row.get("amount")
        )

    if request_current_commutation and current_commutation is not None:
        payer_names = []
        for item in commutations:
            payer_name = _commutation_payer(item)
            if payer_name and payer_name not in payer_names:
                payer_names.append(payer_name)
        fields["capitalpayer"] = (
            " ; ".join(payer_names[:2])
            + (f" ועוד {len(payer_names) - 2}" if len(payer_names) > 2 else "")
            if payer_names
            else _commutation_payer(current_commutation)
        )
        fields["capitalsum"] = _format_money(commutations_total_float)
        fields["capitaltime"] = _format_date(
            _first_non_empty(
                getattr(current_commutation, "start_date", None),
                getattr(current_commutation, "purchase_date", None),
            )
        )

    return fields


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
        pensions = fetch_pension_data(db, client_id)
        commutations = fetch_commutations_data(db, client_id)

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
        field_data = _build_form_161d_field_data(
            client=client,
            fixation_data=fixation_data,
            pensions=pensions,
            commutations=commutations,
        )

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
