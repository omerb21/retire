from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from typing import Any, List, Optional
from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime, date
from decimal import Decimal
import subprocess
from pathlib import Path

from app.database import get_db
from app.services.pension_portfolio import PensionPortfolioProcessor
from app.services.pension_portfolio.snapshot_loader import (
    dedupe_pension_portfolio_snapshot,
    load_latest_pension_portfolio_snapshot,
    upsert_snapshot,
)
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.models.client import Client
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.pension_portfolio.conversion_rules import (
    validate_component_conversion,
)
from app.services.retirement_age_service import (
    calculate_retirement_age,
    get_retirement_age_simple,
)

logger = logging.getLogger("app.routers.pension_portfolio")


def extract_selected_accounts(portfolio: Any) -> list[dict]:
    if not isinstance(portfolio, list):
        return []

    def _coerce_float(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0
            cleaned = raw.replace(",", "").replace("₪", "").replace(" ", "")
            try:
                return float(cleaned)
            except (TypeError, ValueError):
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    selected: list[dict] = []
    for item in portfolio:
        if not isinstance(item, dict):
            continue

        selected_amounts_raw = (
            item.get("selected_amounts")
            if isinstance(item.get("selected_amounts"), dict)
            else (
                item.get("selected_components")
                if isinstance(item.get("selected_components"), dict)
                else (
                    item.get("specific_amounts")
                    if isinstance(item.get("specific_amounts"), dict)
                    else {}
                )
            )
        )

        normalized_amounts: dict[str, float] = {}
        for k, v in dict(selected_amounts_raw or {}).items():
            amount = _coerce_float(v)
            if amount > 0:
                normalized_amounts[str(k)] = amount

        if not normalized_amounts:
            continue

        updated = dict(item)
        updated["selected_amounts"] = normalized_amounts
        selected.append(updated)

    return selected


router = APIRouter()


@router.post("/clients/{client_id}/pension-portfolio/process-xml")
async def process_pension_xml_files(
    client_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """עיבוד קבצי XML ו-DAT של המסלקה"""

    if not files:
        raise HTTPException(status_code=400, detail="לא נבחרו קבצים")

    processor = PensionPortfolioProcessor()
    all_accounts = []
    processed_files = []
    skipped_files = []

    for file in files:
        filename_lower = file.filename.lower()

        # תמיכה בקבצי XML ו-DAT
        if not (filename_lower.endswith(".xml") or filename_lower.endswith(".dat")):
            skipped_files.append(
                {"file": file.filename, "reason": "סוג קובץ לא נתמך (נדרש XML או DAT)"}
            )
            continue

        try:
            content = await file.read()

            # ניסיון לפענח עם קידודים שונים
            file_content = None
            for encoding in ["utf-8", "windows-1255", "iso-8859-8", "latin1"]:
                try:
                    file_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if file_content is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"לא הצלחתי לפענח את הקובץ {file.filename}. קידוד לא נתמך",
                )

            result = processor.process_file(file_content, file.filename)
            if result is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"לא הצלחתי לחלץ נתונים מקובץ {file.filename}. הקובץ עשוי להיות פגום או בפורמט לא נתמך.",
                )

            accounts = result.get("accounts", [])
            all_accounts.extend(accounts)

            processed_files.append(
                {
                    "file": result.get("file", file.filename),
                    "file_type": "DAT" if filename_lower.endswith(".dat") else "XML",
                    "accounts_count": len(accounts),
                    "accounts": accounts,
                    "processed_at": result.get(
                        "processed_at", datetime.now().isoformat()
                    ),
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"שגיאה בעיבוד קובץ {file.filename}: {str(e)}"
            )

    saved_snapshot_result = None
    try:
        saved_snapshot_result = await save_pension_portfolio(
            client_id=client_id,
            portfolio_data={"pension_portfolio": all_accounts},
            db=db,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"שגיאה בשמירת תיק פנסיוני: {str(e)}"
        )

    return {
        "total_accounts": len(all_accounts),
        "processed_files_count": len(processed_files),
        "skipped_files_count": len(skipped_files),
        "processed_files": processed_files,
        "skipped_files": skipped_files,
        "accounts": all_accounts,
        "saved_snapshot": saved_snapshot_result,
    }


@router.get("/clients/{client_id}/pension-portfolio/")
async def get_pension_portfolio(client_id: int, db: Session = Depends(get_db)):
    """קבלת נתוני תיק פנסיוני קיימים"""

    def _coerce_float(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0
            cleaned = raw.replace(",", "").replace("₪", "").replace(" ", "")
            try:
                return float(cleaned)
            except (TypeError, ValueError):
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _recompute_row(row: dict) -> dict:
        balance_key = (
            "יתרה" if "יתרה" in row else ("balance" if "balance" in row else None)
        )
        computed_balance = _coerce_float(row.get(balance_key)) if balance_key else 0.0

        if "סך_תגמולים" in row or "סך_פיצויים" in row:
            computed_components_sum = _coerce_float(
                row.get("סך_תגמולים")
            ) + _coerce_float(row.get("סך_פיצויים"))
        else:
            component_prefixes = ("תגמולי_", "פיצויים_")
            computed_components_sum = 0.0
            for k, v in row.items():
                if isinstance(k, str) and k.startswith(component_prefixes):
                    computed_components_sum += _coerce_float(v)
            if "קרן_השתלמות" in row:
                computed_components_sum += _coerce_float(row.get("קרן_השתלמות"))

        row["סך_רכיבים"] = computed_components_sum

        computed_gap = computed_balance - computed_components_sum
        if (computed_balance <= 0.01) and (computed_components_sum <= 0.01):
            computed_gap = 0.0
        elif abs(computed_gap) <= 0.01:
            computed_gap = 0.0

        row["פער_יתרה_מול_רכיבים"] = computed_gap
        return row

    snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )

    scenarios = []
    if snapshot is not None:
        scenarios.append(snapshot)
    scenarios.extend(
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .order_by(Scenario.created_at.desc())
        .limit(20)
        .all()
    )

    for scenario in scenarios:
        if not scenario.parameters:
            continue
        try:
            params = json.loads(scenario.parameters)
        except Exception:
            continue
        portfolio = params.get("pension_portfolio")
        if isinstance(portfolio, list):
            normalized = []
            for item in portfolio:
                if not isinstance(item, dict):
                    continue
                normalized.append(_recompute_row(dict(item)))
            return normalized

    return []


@router.post("/clients/{client_id}/pension-portfolio/save")
async def save_pension_portfolio(
    client_id: int,
    portfolio_data: Any = Body(...),
    db: Session = Depends(get_db),
):
    """שמירת נתוני תיק פנסיוני"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="לקוח לא נמצא")

    accounts: Any = None
    if isinstance(portfolio_data, list):
        accounts = portfolio_data
    elif isinstance(portfolio_data, dict):
        if "pension_portfolio" in portfolio_data:
            accounts = portfolio_data.get("pension_portfolio")
        elif "accounts" in portfolio_data:
            accounts = portfolio_data.get("accounts")

    if not isinstance(accounts, list):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid payload: expected a JSON list of accounts or an object with "
                "pension_portfolio: [ ... ]"
            ),
        )

    scenario = upsert_snapshot(
        db,
        client_id,
        accounts,
        meta={"operation_type": "portfolio_import"},
    )
    kept_snapshot_id, deleted_ids = dedupe_pension_portfolio_snapshot(db, client_id)

    return {
        "message": "נתוני התיק הפנסיוני נשמרו בהצלחה",
        "client_id": client_id,
        "accounts_count": len(accounts),
        "scenario_id": int(kept_snapshot_id or getattr(scenario, "id", 0) or 0),
        "kept_snapshot_id": kept_snapshot_id,
        "dedupe_deleted_count": int(len(deleted_ids)),
        "dedupe_deleted_ids": deleted_ids,
    }


@router.post("/clients/{client_id}/pension-portfolio/convert")
async def convert_pension_accounts(
    client_id: int, conversion_data: dict, db: Session = Depends(get_db)
):
    """המרת חשבונות פנסיוניים לקצבאות או נכסי הון - מיידי ישירות ל-DB"""

    request_accounts: Any = None
    for key in (
        "accounts",
        "selected_accounts",
        "accounts_to_convert",
        "accountsToConvert",
        "portfolio",
        "pension_portfolio",
    ):
        candidate = conversion_data.get(key)
        if isinstance(candidate, list):
            request_accounts = candidate
            break

    snapshot_portfolio: list[dict] = []
    snapshot_at = ""
    loaded_snapshot = load_latest_pension_portfolio_snapshot(db, client_id)
    if loaded_snapshot is not None:
        snapshot_portfolio, snapshot_at = loaded_snapshot

    request_selected = extract_selected_accounts(request_accounts)
    db_selected = extract_selected_accounts(snapshot_portfolio)
    selected_accounts = request_selected or db_selected

    logger.info(
        "pension_portfolio.convert selection (client_id=%s, snapshot_at=%s, portfolio_count=%s, request_selected_count=%s, db_selected_count=%s, selected_count=%s)",
        client_id,
        snapshot_at,
        len(snapshot_portfolio) if isinstance(snapshot_portfolio, list) else 0,
        len(request_selected),
        len(db_selected),
        len(selected_accounts),
    )

    debug_account_number = "494930"
    debug_row = next(
        (
            r
            for r in (snapshot_portfolio or [])
            if isinstance(r, dict)
            and str(r.get("מספר_חשבון") or r.get("account_number") or "")
            == debug_account_number
        ),
        None,
    )
    if isinstance(debug_row, dict):
        logger.info(
            "pension_portfolio.convert debug_account=%s found_in_snapshot=true selected=%s selected_amounts_type=%s selected_amounts_keys=%s",
            debug_account_number,
            debug_row.get("selected"),
            type(debug_row.get("selected_amounts")).__name__,
            (
                list(debug_row.get("selected_amounts").keys())
                if isinstance(debug_row.get("selected_amounts"), dict)
                else None
            ),
        )
    else:
        logger.info(
            "pension_portfolio.convert debug_account=%s found_in_snapshot=false",
            debug_account_number,
        )

    if not selected_accounts:
        raise HTTPException(status_code=400, detail="לא נבחרו חשבונות להמרה")

    if isinstance(request_accounts, list):
        try:
            upsert_snapshot(
                db,
                client_id,
                request_accounts,
                meta={"operation_type": "portfolio_import"},
            )
            db.commit()
            dedupe_pension_portfolio_snapshot(db, client_id)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    retirement_age = None
    retirement_date = None
    retirement_year = date.today().year
    client = db.query(Client).filter(Client.id == client_id).first()
    if (
        client
        and getattr(client, "birth_date", None)
        and getattr(client, "gender", None)
    ):
        try:
            retirement_info = calculate_retirement_age(client.birth_date, client.gender)
            retirement_date = retirement_info.get("retirement_date")
            age_years = int(retirement_info.get("age_years") or 0)
            age_months = int(retirement_info.get("age_months") or 0)
            retirement_age = age_years + (1 if age_months > 0 else 0)
            if retirement_date:
                retirement_year = retirement_date.year
        except Exception:
            retirement_date = None

    if retirement_age is None:
        try:
            retirement_age = int(
                get_retirement_age_simple(client.birth_date, client.gender)
            )
        except Exception:
            retirement_age = None

    if retirement_age is None:
        retirement_age = 67

    converted_count = 0

    for account in selected_accounts:
        if not isinstance(account, dict):
            continue

        selected_amounts = (
            account.get("selected_amounts")
            if isinstance(account.get("selected_amounts"), dict)
            else {}
        )
        if not selected_amounts:
            continue

        conversion_mode = (
            str(conversion_data.get("conversion_mode") or "").strip().lower()
        )
        desired_conversion_type = (
            "capital_asset" if conversion_mode == "assets" else "pension"
        )

        product_type = account.get("סוג_מוצר", "")
        account_number = account.get("מספר_חשבון", "")
        company = account.get("חברה_מנהלת", "")
        plan_name = account.get("שם_תכנית", "")

        pension_components: dict[str, float] = {}
        capital_components: dict[str, float] = {}
        component_errors: list[dict[str, str]] = []

        for field, amount_raw in dict(selected_amounts).items():
            try:
                amount = float(amount_raw or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount <= 0:
                continue

            ok, _tax_treatment, err = validate_component_conversion(
                field=str(field),
                amount=float(amount),
                conversion_type=desired_conversion_type,
                product_type=str(product_type or ""),
            )
            actual_type = desired_conversion_type
            if (not ok) and (desired_conversion_type == "capital_asset"):
                ok2, _tax2, err2 = validate_component_conversion(
                    field=str(field),
                    amount=float(amount),
                    conversion_type="pension",
                    product_type=str(product_type or ""),
                )
                if ok2:
                    ok = True
                    actual_type = "pension"
                    err = None
                else:
                    err = err2 or err

            if not ok:
                if err:
                    component_errors.append({"field": str(field), "error": str(err)})
                continue

            if actual_type == "capital_asset":
                capital_components[str(field)] = float(amount)
            else:
                pension_components[str(field)] = float(amount)

        pension_balance = sum(pension_components.values())
        capital_balance = sum(capital_components.values())
        if (pension_balance <= 0) and (capital_balance <= 0):
            continue

        start_date_raw = account.get("תאריך_התחלה")
        if isinstance(start_date_raw, str) and start_date_raw.strip():
            start_date_obj = None
            try:
                start_date_obj = date.fromisoformat(start_date_raw.strip())
            except ValueError:
                try:
                    start_date_obj = datetime.strptime(
                        start_date_raw.strip(), "%d/%m/%Y"
                    ).date()
                except Exception:
                    start_date_obj = None
        else:
            start_date_obj = None

        if pension_balance > 0:
            # המרה לקצבה - שמירה ישירה ל-DB
            # קביעת יחס מס לפי סוג המוצר
            tax_treatment = (
                "exempt" if "השתלמות" in str(product_type or "") else "taxable"
            )

            annuity_factor = 200.0
            coeff = None
            try:
                coeff = get_annuity_coefficient(
                    product_type=str(product_type or ""),
                    start_date=start_date_obj or date(retirement_year, 1, 1),
                    gender=getattr(client, "gender", None) or "זכר",
                    retirement_age=retirement_age,
                    company_name=company or None,
                    option_name=None,
                    survivors_option="תקנוני",
                    spouse_age_diff=0,
                    target_year=retirement_year,
                    birth_date=getattr(client, "birth_date", None) if client else None,
                    pension_start_date=retirement_date,
                )
                annuity_factor = float(coeff.get("factor_value") or annuity_factor)
                if annuity_factor <= 0:
                    annuity_factor = 200.0
            except Exception:
                annuity_factor = 200.0

            pension_amount = float(pension_balance) / float(annuity_factor or 200.0)

            conversion_source_json = json.dumps(
                {
                    "source": "pension_portfolio_convert",
                    "account_number": account_number,
                    "account_name": plan_name,
                    "company": company,
                    "product_type": product_type,
                    "start_date": start_date_raw,
                    "conversion_mode": conversion_mode,
                    "selected_amounts": selected_amounts,
                    "pension_components": pension_components,
                    "capital_components": capital_components,
                    "component_errors": component_errors,
                    "resolved_annuity_factor": annuity_factor,
                    "coeff_source_table": (
                        coeff.get("source_table") if isinstance(coeff, dict) else None
                    ),
                    "converted_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )

            existing_pf = None
            if account_number:
                existing_pf = (
                    db.query(PensionFund)
                    .filter(
                        PensionFund.client_id == client_id,
                        PensionFund.deduction_file == account_number,
                        PensionFund.conversion_source.like(
                            '%"source": "pension_portfolio_convert"%'
                        ),
                    )
                    .first()
                )

            if existing_pf:
                existing_pf.fund_name = plan_name or "תכנית ללא שם"
                existing_pf.fund_type = product_type or "קופת גמל"
                existing_pf.input_mode = "manual"
                existing_pf.balance = float(pension_balance)
                existing_pf.annuity_factor = annuity_factor
                existing_pf.pension_amount = pension_amount
                existing_pf.pension_start_date = retirement_date or date(
                    retirement_year, 1, 1
                )
                existing_pf.indexation_method = "none"
                existing_pf.tax_treatment = tax_treatment
                existing_pf.conversion_source = conversion_source_json
                existing_pf.remarks = f"הומר מתיק פנסיוני - {company}"
            else:
                pf = PensionFund(
                    client_id=client_id,
                    fund_name=plan_name or "תכנית ללא שם",
                    fund_type=product_type or "קופת גמל",
                    input_mode="manual",
                    balance=float(pension_balance),
                    annuity_factor=annuity_factor,
                    pension_amount=pension_amount,
                    pension_start_date=retirement_date or date(retirement_year, 1, 1),
                    indexation_method="none",
                    tax_treatment=tax_treatment,
                    deduction_file=account_number,
                    conversion_source=conversion_source_json,
                    remarks=f"הומר מתיק פנסיוני - {company}",
                )
                db.add(pf)
            converted_count += 1

        if capital_balance > 0:
            # המרה לנכס הון - שמירה ישירה ל-DB
            conversion_source_json = json.dumps(
                {
                    "source": "pension_portfolio_convert",
                    "account_number": account_number,
                    "account_name": plan_name,
                    "company": company,
                    "product_type": product_type,
                    "start_date": start_date_raw,
                    "conversion_mode": conversion_mode,
                    "selected_amounts": selected_amounts,
                    "pension_components": pension_components,
                    "capital_components": capital_components,
                    "component_errors": component_errors,
                    "converted_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )

            ca = CapitalAsset(
                client_id=client_id,
                asset_name=plan_name or "נכס ללא שם",
                asset_type="provident_fund",
                current_value=Decimal(str(float(capital_balance))),
                monthly_income=Decimal("0"),
                annual_return_rate=Decimal("0.03"),
                payment_frequency="monthly",
                start_date=date(2025, 1, 1),
                indexation_method="none",
                tax_treatment="taxable",
                description=f"הומר מתיק פנסיוני - {company}",
                conversion_source=conversion_source_json,
            )
            db.add(ca)
            converted_count += 1

    db.commit()

    return {
        "success": True,
        "message": f"✅ הומרו ונשמרו בהצלחה {converted_count} חשבונות!",
        "converted_count": converted_count,
    }


@router.post("/clients/{client_id}/pension-portfolio/restore")
async def restore_pension_amounts(client_id: int, restore_data: dict):
    """החזרת סכומים שהומרו חזרה לתיק הפנסיוני

    נקרא כאשר מוחקים קצבה או נכס הון שמקורם בהמרה מתיק פנסיוני.
    הפונקציה מחזירה את הסכומים לשדות המקוריים בטבלה.

    בשלב זה, הפונקציה מחזירה הצלחה כיוון שהנתונים נשמרים ב-localStorage בצד הלקוח.
    בעתיד ניתן להוסיף שמירה במסד נתונים.
    """

    account_name = restore_data.get("account_name")
    company = restore_data.get("company")
    account_number = restore_data.get("account_number")
    product_type = restore_data.get("product_type")
    amount = restore_data.get("amount")
    specific_amounts = restore_data.get("specific_amounts", {})

    if not account_name or not amount:
        raise HTTPException(status_code=400, detail="חסרים פרטים נדרשים להחזרת הסכומים")

    # כאן ניתן להוסיף לוגיקה לעדכון מסד נתונים אם נשמור את נתוני התיק הפנסיוני
    # לעת עתה, הנתונים מנוהלים ב-localStorage בצד הלקוח

    return {
        "success": True,
        "message": "הסכומים הוחזרו בהצלחה לתיק הפנסיוני",
        "restored_account": {
            "account_name": account_name,
            "company": company,
            "account_number": account_number,
            "product_type": product_type,
            "amount": amount,
            "specific_amounts": specific_amounts,
        },
    }


@router.post("/clients/{client_id}/pension-portfolio/process-directory")
async def process_pension_directory(client_id: int, directory_path: str):
    """עיבוד תיקייה של קבצי XML באמצעות הסקריפט הקיים"""

    # נתיב לתיקיית NESS
    ness_dir = Path(__file__).parent.parent.parent / "NESS"
    process_script = ness_dir / "process_pensions.py"

    if not process_script.exists():
        raise HTTPException(status_code=404, detail="סקריפט עיבוד המסלקה לא נמצא")

    try:
        # הרצת הסקריפט
        result = subprocess.run(
            ["python", str(process_script)],
            cwd=str(ness_dir),
            capture_output=True,
            text=True,
            timeout=300,  # 5 דקות timeout
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"שגיאה בהרצת סקריפט העיבוד: {result.stderr}"
            )

        # קריאת תוצאות
        results_file = ness_dir / "DATA" / "pension_results.json"
        if results_file.exists():
            with open(results_file, "r", encoding="utf-8") as f:
                results = json.load(f)
            return results
        else:
            raise HTTPException(status_code=404, detail="קובץ תוצאות לא נמצא")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="עיבוד הקבצים ארך יותר מדי זמן")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בעיבוד התיקייה: {str(e)}")
