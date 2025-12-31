import json
import logging
from datetime import date
from decimal import Decimal
import re

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.utils.date_serializer import parse_date_flexible

logger = logging.getLogger("app.llm_chat.tools")


def handle_execute_pension_commutation(*, args: dict, client_id: int, db: Session) -> str:
    logger.info("🔴 EXECUTE_PENSION_COMMUTATION called - Execution Mode!")

    pension_fund_id = args.get("pension_fund_id")
    raw_amount = (
        args.get("commutation_amount")
        if args.get("commutation_amount") is not None
        else args.get("exempt_amount")
    )
    commutation_date_raw = args.get("commutation_date")
    commutation_type = args.get("commutation_type")
    confirmed = args.get("confirmed")

    if confirmed is not True:
        return "Error: לביצוע היוון חובה confirmed=true"

    try:
        pension_fund_id_int = int(pension_fund_id)
    except Exception:
        return "Error: pension_fund_id לא תקין"

    try:
        amount = float(raw_amount or 0)
    except Exception:
        amount = 0.0

    if amount <= 0:
        return "Error: סכום היוון חייב להיות חיובי"

    if not commutation_date_raw:
        return "Error: חסר commutation_date"

    try:
        commutation_date = parse_date_flexible(str(commutation_date_raw))
    except Exception:
        return "Error: commutation_date לא תקין"

    commutation_type_norm = str(commutation_type or "taxable").strip().lower()
    if commutation_type_norm in {"exempt", "פטור", "פטורה"}:
        tax_treatment = "exempt"
    elif commutation_type_norm in {"taxable", "חייב", "חייבת"}:
        tax_treatment = "taxable"
    else:
        return "Error: commutation_type לא תקין (exempt/taxable)"

    fund = (
        db.query(PensionFund)
        .filter(PensionFund.client_id == client_id, PensionFund.id == pension_fund_id_int)
        .first()
    )
    if fund is None:
        return "Error: קצבה לא נמצאה"

    fund_balance = float(fund.balance or 0)

    rounded_amount = round(amount, 2)
    rounded_balance = round(fund_balance, 2)
    if rounded_amount > rounded_balance:
        return (
            f"Error: סכום ההיוון ({rounded_amount:,.2f}) גדול מהיתרה המקורית של הקצבה ({rounded_balance:,.2f})"
        )

    pension_tax_treatment = str(getattr(fund, "tax_treatment", "taxable") or "taxable")
    if pension_tax_treatment == "exempt" and tax_treatment != "exempt":
        return "Error: קצבה פטורה ממס יכולה ליצור רק היוון פטור ממס"

    original_snapshot = {
        "id": fund.id,
        "fund_name": fund.fund_name,
        "fund_type": fund.fund_type,
        "input_mode": fund.input_mode,
        "balance": fund.balance,
        "annuity_factor": fund.annuity_factor,
        "pension_amount": fund.pension_amount,
        "pension_start_date": fund.pension_start_date.isoformat() if isinstance(fund.pension_start_date, date) else None,
        "indexation_method": fund.indexation_method,
        "tax_treatment": fund.tax_treatment,
        "deduction_file": fund.deduction_file or "",
    }

    description = f"היוון של {fund.fund_name or 'קצבה'}"
    remarks = f"COMMUTATION:pension_fund_id={fund.id}&amount={amount}"

    asset = CapitalAsset(
        client_id=client_id,
        asset_name=description,
        asset_type="deposits",
        description=description,
        remarks=remarks,
        current_value=Decimal("0"),
        monthly_income=Decimal(str(amount)),
        annual_return_rate=Decimal("0"),
        payment_frequency="annually",
        start_date=commutation_date,
        indexation_method="none",
        tax_treatment=tax_treatment,
        conversion_source=json.dumps(
            {
                "type": "pension_commutation",
                "pension_fund_id": fund.id,
                "tax_treatment": tax_treatment,
                "original_pension": original_snapshot,
            },
            ensure_ascii=False,
        ),
    )

    db.add(asset)
    db.flush()

    annuity_factor = float(fund.annuity_factor or 200)
    if annuity_factor <= 0:
        annuity_factor = 200.0

    new_balance = max(0.0, fund_balance - amount)
    new_pension_amount = round(new_balance / annuity_factor) if new_balance > 0 else 0.0

    fund.balance = new_balance
    fund.pension_amount = new_pension_amount

    portfolio_account_number: str | None = None
    portfolio_snapshot_updated = False
    portfolio_account_matched = False

    source = None
    if getattr(fund, "conversion_source", None):
        try:
            source = json.loads(str(fund.conversion_source))
        except Exception:
            source = None

    is_from_snapshot = False
    if isinstance(source, dict):
        if str(source.get("type") or "").strip().lower() == "pension_portfolio":
            is_from_snapshot = True
        if str(source.get("source") or "").strip().lower() == "pension_portfolio":
            is_from_snapshot = True

    if is_from_snapshot:
        try:
            src_acc = str(source.get("account_number") or "").strip() if isinstance(source, dict) else ""
        except Exception:
            src_acc = ""
        portfolio_account_number = (src_acc or str(getattr(fund, "deduction_file", "") or "")).strip() or None

        def _digits_only(value: str | None) -> str:
            return "".join(ch for ch in (value or "") if ch.isdigit())

        target_digits = _digits_only(portfolio_account_number)

        scenario = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        if scenario is None:
            logger.warning(
                "⚠️ Commutation: no pension_portfolio_snapshot scenario found (client_id=%s)",
                client_id,
            )
        else:
            try:
                params = json.loads(scenario.parameters) if scenario.parameters else {}
            except Exception:
                params = {}
            portfolio = params.get("pension_portfolio")
            if not (isinstance(portfolio, list) and portfolio):
                logger.warning(
                    "⚠️ Commutation: pension_portfolio_snapshot has no portfolio list (client_id=%s scenario_id=%s)",
                    client_id,
                    getattr(scenario, "id", None),
                )
            else:
                component_fields = [
                    "פיצויים_מעסיק_נוכחי",
                    "פיצויים_לאחר_התחשבנות",
                    "פיצויים_שלא_עברו_התחשבנות",
                    "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
                    "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
                    "תגמולי_עובד_עד_2000",
                    "תגמולי_עובד_אחרי_2000",
                    "תגמולי_עובד_אחרי_2008_לא_משלמת",
                    "תגמולי_מעביד_עד_2000",
                    "תגמולי_מעביד_אחרי_2000",
                    "תגמולי_מעביד_אחרי_2008_לא_משלמת",
                    "תגמולים",
                    "סך_תגמולים",
                    "סך_פיצויים",
                    "סך_רכיבים",
                    "קרן_השתלמות",
                ]

                for item in portfolio:
                    if not isinstance(item, dict):
                        continue
                    acc_num = str(item.get("מספר_חשבון") or item.get("account_number") or "").strip()
                    if not acc_num:
                        continue
                    if portfolio_account_number and acc_num == portfolio_account_number:
                        matched = True
                    else:
                        matched = bool(target_digits) and _digits_only(acc_num) == target_digits
                    if not matched:
                        continue

                    portfolio_account_number = acc_num

                    current_total = None
                    for key in ("יתרה", "balance"):
                        if key in item:
                            try:
                                current_total = float(item.get(key) or 0)
                            except Exception:
                                current_total = 0.0
                            break

                    if current_total is None:
                        try:
                            current_total = float(
                                sum(
                                    float(item.get(f) or 0)
                                    for f in component_fields
                                    if f in item
                                )
                            )
                        except Exception:
                            current_total = 0.0

                    remaining_total = max(0.0, float(current_total or 0.0) - float(amount or 0.0))

                    item["יתרה"] = 0.0 if remaining_total <= 0.01 else remaining_total
                    if "balance" in item:
                        item["balance"] = item["יתרה"]

                    if item["יתרה"] == 0.0:
                        for f in component_fields:
                            if f in item:
                                item[f] = 0
                        nested = item.get("specific_amounts")
                        if isinstance(nested, dict):
                            for k in list(nested.keys()):
                                nested[k] = 0

                    portfolio_account_matched = True
                    break

                if portfolio_account_matched:
                    params["pension_portfolio"] = portfolio
                    scenario.parameters = json.dumps(params, ensure_ascii=False)
                    db.add(scenario)
                    portfolio_snapshot_updated = True
                else:
                    logger.warning(
                        "⚠️ Commutation: could not find matching account in snapshot (client_id=%s scenario_id=%s account_number=%s)",
                        client_id,
                        getattr(scenario, "id", None),
                        portfolio_account_number,
                    )

    db.commit()

    response = {
        "success": True,
        "message": "✅ היוון בוצע בהצלחה",
        "commutation_asset_id": getattr(asset, "id", None),
        "pension_fund_id": fund.id,
        "commutation_amount": amount,
        "commutation_date": commutation_date.isoformat(),
        "tax_treatment": tax_treatment,
        "new_balance": new_balance,
        "new_pension_amount": new_pension_amount,
        "portfolio_account_number": portfolio_account_number,
        "portfolio_snapshot_updated": portfolio_snapshot_updated,
        "portfolio_account_matched": portfolio_account_matched,
    }

    return json.dumps(response, ensure_ascii=False)
