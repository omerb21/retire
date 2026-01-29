import json
import logging
from datetime import date
from typing import Any, Dict, Optional

from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.pension_portfolio.conversion_rules import (
    COMPONENT_RULES,
    rule_for_tagmulim_by_product_type,
)
from app.services.retirement.constants import PENSION_COEFFICIENT
from app.services.llm_agent_tools.adapters.target_plan_explanation import (
    build_target_pension_plan_explanation,
)
from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot

logger = logging.getLogger("app.llm_agent_tools")


def build_target_pension_plan(
    self,
    target_monthly_pension: float,
    retirement_age: Optional[int] = None,
    target_is_net: bool = True,
    ignore_blocked_balances: bool = True,
) -> Dict[str, Any]:
    """
    בונה תכנית להשגת קצבת יעד בצורה אופטימלית.

    האלגוריתם:
    1. אוסף את כל מקורות הקצבה הפוטנציאליים (קרנות פנסיה, נכסי הון)
    2. מדרג אותם לפי "איכות" (מקדם קצבה - הנמוך יותר = טוב יותר)
    3. ממיר בסדר מהטוב לפחות טוב עד להגעה ליעד
    4. מחזיר תכנית מפורטת עם יתרונות/חסרונות
    """
    client = self.client
    if not client:
        return {
            "success": False,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {},
            "explanation": "לא נמצא לקוח עם המזהה שסופק.",
        }

    if not client.birth_date:
        return {
            "success": False,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {},
            "explanation": "חסר תאריך לידה ללקוח - לא ניתן לחשב מקדמי קצבה.",
        }

    # קביעת גיל/תאריך תחילת קצבה (ברירת מחדל: max(גיל נוכחי, גיל פרישה חוקי לפי הגדרות))
    from app.services.retirement_age_service import (
        DEFAULT_MALE_RETIREMENT_AGE,
        get_retirement_age_simple,
        get_retirement_date,
    )

    current_age = client.get_age()
    legal_retirement_age = int(DEFAULT_MALE_RETIREMENT_AGE)
    legal_retirement_date = None
    try:
        legal_retirement_age = int(
            get_retirement_age_simple(client.birth_date, client.gender or "")
        )
    except Exception:
        legal_retirement_age = int(DEFAULT_MALE_RETIREMENT_AGE)
    try:
        legal_retirement_date = get_retirement_date(client.birth_date, client.gender or "")
    except Exception:
        legal_retirement_date = None

    inferred_default_retirement_date = False
    if retirement_age is None:
        if current_age is not None:
            retirement_age = max(int(current_age), int(legal_retirement_age))
        else:
            retirement_age = int(legal_retirement_age)
        inferred_default_retirement_date = True

    if retirement_age < current_age:
        return {
            "success": False,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {},
            "explanation": f"גיל הפרישה ({retirement_age}) לא יכול להיות נמוך מהגיל הנוכחי ({current_age}).",
        }

    # חישוב תאריך תחילת קצבה
    if inferred_default_retirement_date:
        # אם כבר עבר גיל פרישה (או שווה לו) – מתחילים היום; אחרת לפי תאריך הפרישה החוקי
        if current_age is not None and current_age >= legal_retirement_age:
            retirement_date = date.today()
        else:
            retirement_date = legal_retirement_date
        if retirement_date is None:
            retirement_date = date.today()
    else:
        try:
            retirement_date = date(
                client.birth_date.year + retirement_age,
                client.birth_date.month,
                client.birth_date.day,
            )
        except ValueError:
            retirement_date = client.birth_date.replace(
                year=client.birth_date.year + retirement_age,
                day=min(client.birth_date.day, 28),
            )
        # אם המשתמש ביקש גיל נוכחי, אל תאפשר תאריך בעבר
        if (
            current_age is not None
            and retirement_age == current_age
            and retirement_date < date.today()
        ):
            retirement_date = date.today()
    retirement_year = retirement_date.year

    target = float(target_monthly_pension)

    # Net target requires a tax projection conversion (net -> required gross).
    # This must run before checking pension sources availability so that
    # tax projection failures are reported deterministically.
    required_gross_for_target = target
    required_gross_tax_projection = None
    if target_is_net:

        def _gross_for_net_target(
            target_net: float,
        ) -> tuple[Optional[float], Optional[dict], Optional[str]]:
            try:
                target_net_val = float(target_net or 0)
            except Exception:
                target_net_val = 0.0
            if target_net_val <= 0:
                return None, None, "invalid_target_net"

            def _net_from_gross(
                gross: float,
            ) -> tuple[Optional[float], Optional[dict], Optional[str]]:
                try:
                    proj = self.get_tax_projection(monthly_pension=float(gross))
                    if not (
                        isinstance(proj, dict) and isinstance(proj.get("result"), dict)
                    ):
                        return None, None, "invalid_tax_projection_response"
                    res = proj.get("result")
                    monthly_tax = res.get("monthly_tax")
                    try:
                        tax_val = float(monthly_tax or 0)
                    except Exception:
                        tax_val = 0.0
                    return float(gross) - tax_val, res, None
                except Exception as e:
                    return None, None, str(e) or "tax_projection_failed"

            low = max(1000.0, target_net_val)
            low_net, low_res, low_err = _net_from_gross(low)
            if low_net is None:
                return None, None, low_err
            if low_net >= target_net_val:
                return low, low_res, None

            high = low
            high_net = low_net
            high_res: Optional[dict] = low_res
            high_err: Optional[str] = None
            for _ in range(16):
                high = min(high * 1.5, 500_000.0)
                high_net, high_res, high_err = _net_from_gross(high)
                if high_net is not None and high_net >= target_net_val:
                    break
            if high_net is None or high_net < target_net_val:
                return None, None, high_err

            best_gross = high
            best_res = high_res
            for _ in range(30):
                mid = (low + high) / 2.0
                mid_net, mid_res, _ = _net_from_gross(mid)
                if mid_net is None:
                    low = mid
                    continue
                if mid_net >= target_net_val:
                    best_gross = mid
                    best_res = mid_res
                    high = mid
                else:
                    low = mid
                if abs(high - low) < 1.0:
                    break

            try:
                best_gross = float(round(best_gross, 2))
            except Exception:
                pass
            return best_gross, best_res, None

        computed_gross, tax_result, gross_err = _gross_for_net_target(target)
        if computed_gross is None:
            err = ((gross_err or "לא ניתן לחשב ברוטו נדרש ליעד נטו (כשל בהערכת מס)").strip())
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": (
                    "לא ניתן לתכנן יעד קצבה נטו ללא הערכת מס תקינה. "
                    "הערכת המס נכשלה ולכן לא ניתן להמיר יעד נטו לברוטו נדרש. "
                    f"פרטי שגיאה: {err}"
                ),
            }

        required_gross_for_target = float(computed_gross)
        required_gross_tax_projection = tax_result

    # שלב 1: איסוף כל מקורות הקצבה הפוטנציאליים
    pension_sources = []

    # קרנות פנסיה עם יתרות
    pension_funds = self.db.query(PensionFund).filter(
        PensionFund.client_id == self.client_id
    ).all()

    # נכסי הון שניתן להמיר לקצבה
    capital_assets = self.db.query(CapitalAsset).filter(
        CapitalAsset.client_id == self.client_id
    ).all()

    has_db_state_sources = False
    try:
        has_non_portfolio_pension_funds = False
        for pf in pension_funds or []:
            raw_src = getattr(pf, "conversion_source", None)
            raw_src_str = str(raw_src) if raw_src is not None else ""
            if raw_src_str and (
                '"source": "pension_portfolio"' in raw_src_str
                or '"type": "pension_portfolio"' in raw_src_str
                or '"source": "pension_portfolio_convert"' in raw_src_str
            ):
                continue
            has_non_portfolio_pension_funds = True
            break
        has_db_state_sources = bool(capital_assets) or bool(has_non_portfolio_pension_funds)
    except Exception:
        has_db_state_sources = False

    for pf in pension_funds:
        try:
            raw_src = getattr(pf, "conversion_source", None)
            raw_src_str = str(raw_src) if raw_src is not None else ""
        except Exception:
            raw_src_str = ""

        is_portfolio_imported = bool(
            raw_src_str
            and (
                '"source": "pension_portfolio"' in raw_src_str
                or '"type": "pension_portfolio"' in raw_src_str
                or '"source": "pension_portfolio_convert"' in raw_src_str
            )
        )
        # If we are planning from snapshot sources, skip portfolio-imported PensionFund rows
        # to avoid de-duping away the per-component snapshot sources.
        if (not has_db_state_sources) and raw_src_str and (
            '"source": "pension_portfolio"' in raw_src_str
            or '"type": "pension_portfolio"' in raw_src_str
            or '"source": "pension_portfolio_convert"' in raw_src_str
        ):
            continue

        balance = float(pf.balance or 0)
        existing_pension = float(pf.pension_amount or 0)

        # אם יש כבר קצבה מוגדרת - זה מקור קיים
        # NOTE: portfolio-imported PensionFund rows represent a raw balance source,
        # not an already-existing executed pension.
        if (existing_pension > 0) and (not is_portfolio_imported):
            pension_sources.append(
                {
                    "source_type": "existing_pension",
                    "source_id": pf.id,
                    "account_number": pf.deduction_file,
                    "source_name": pf.fund_name,
                    "fund_type": pf.fund_type,
                    "balance": 0,
                    "annuity_factor": pf.annuity_factor or PENSION_COEFFICIENT,
                    "monthly_pension": existing_pension,
                    "tax_treatment": pf.tax_treatment or "taxable",
                    "action_needed": "none",
                    "action_description": "קצבה קיימת - ללא פעולה נדרשת",
                }
            )
            continue

        # אם יש יתרה - ניתן להמיר לקצבה
        if balance > 0:
            # חישוב מקדם קצבה דינמי
            annuity_factor = float(pf.annuity_factor or 0)
            coeff_source_table = None
            fallback_used = False
            if annuity_factor <= 0:
                try:
                    coeff_result = get_annuity_coefficient(
                        product_type=pf.fund_type or "קרן פנסיה",
                        start_date=retirement_date,
                        gender=client.gender or "זכר",
                        retirement_age=retirement_age,
                        birth_date=client.birth_date,
                        pension_start_date=retirement_date,
                    )
                    try:
                        coeff_source_table = (
                            str(coeff_result.get("source_table") or "").strip()
                            if isinstance(coeff_result, dict)
                            else None
                        )
                    except Exception:
                        coeff_source_table = None
                    annuity_factor = float(
                        coeff_result.get("factor_value") or PENSION_COEFFICIENT
                    )
                except Exception:
                    fallback_used = True
                    annuity_factor = PENSION_COEFFICIENT

            if annuity_factor == PENSION_COEFFICIENT and (not coeff_source_table):
                fallback_used = True

            potential_pension = balance / annuity_factor

            pension_sources.append(
                {
                    "source_type": "pension_fund",
                    "source_id": pf.id,
                    "account_number": pf.deduction_file,
                    "source_name": pf.fund_name,
                    "fund_type": pf.fund_type,
                    "balance": balance,
                    "annuity_factor": annuity_factor,
                    "coeff_source_table": coeff_source_table,
                    "fallback_used": bool(fallback_used),
                    "monthly_pension": potential_pension,
                    "tax_treatment": pf.tax_treatment or "taxable",
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת יתרה של {balance:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                }
            )

    for ca in capital_assets:
        value = float(ca.current_value or 0)
        if value <= 0:
            value = float(ca.monthly_income or 0)

        if value > 0:
            # נכסי הון ממירים במקדם כללי
            potential_pension = value / PENSION_COEFFICIENT

            pension_sources.append(
                {
                    "source_type": "capital_asset",
                    "source_id": ca.id,
                    "account_number": None,
                    "source_name": ca.asset_name,
                    "fund_type": ca.asset_type,
                    "balance": value,
                    "annuity_factor": PENSION_COEFFICIENT,
                    "monthly_pension": potential_pension,
                    "tax_treatment": ca.tax_treatment or "taxable",
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת הון של {value:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                }
            )

    portfolio_sources_total = 0
    portfolio_sources_added = 0
    portfolio_sources_skipped_duplicates = 0
    portfolio_sources_unique_accounts = 0
    portfolio_sources_total_balance = 0.0
    portfolio_accounts_count = 0
    portfolio_accounts_total_balance = 0.0
    blocked_total_detected = 0.0

    pension_portfolio_data: Any = None
    if not has_db_state_sources:
        if (
            isinstance(getattr(self, "pension_portfolio_data", None), list)
            and getattr(self, "pension_portfolio_data")
        ):
            pension_portfolio_data = getattr(self, "pension_portfolio_data")
        else:
            try:
                scenarios = (
                    self.db.query(Scenario)
                    .filter(Scenario.client_id == self.client_id)
                    .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
                    .order_by(Scenario.created_at.desc())
                    .limit(20)
                    .all()
                )
            except Exception:
                scenarios = []

            chosen = None
            for row in scenarios or []:
                if not getattr(row, "parameters", None):
                    continue
                try:
                    params = json.loads(row.parameters)
                except Exception:
                    continue
                portfolio = params.get("pension_portfolio")
                if not (isinstance(portfolio, list) and portfolio):
                    continue
                meta = params.get("_meta") if isinstance(params, dict) else None
                op_type = None
                if isinstance(meta, dict):
                    op_type = str(meta.get("operation_type") or "").strip()
                if op_type == "TRANSFORM_FUNDS_TO_ASSETS":
                    continue
                chosen = (portfolio, row)
                break

            if chosen is None:
                try:
                    loaded = load_latest_pension_portfolio_snapshot(self.db, self.client_id)
                except Exception:
                    loaded = None
                if isinstance(loaded, tuple) and len(loaded) == 2:
                    pension_portfolio_data = loaded[0]
                else:
                    pension_portfolio_data = None
            else:
                pension_portfolio_data = chosen[0]

    def _safe_float(value: Any) -> float:
        try:
            if value is None:
                return 0.0
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace("₪", "").strip()
                if not cleaned:
                    return 0.0
                return float(cleaned)
            return float(value)
        except Exception:
            return 0.0

    if isinstance(pension_portfolio_data, list) and pension_portfolio_data:
        portfolio_accounts_count = len(pension_portfolio_data)
        try:
            portfolio_accounts_total_balance = float(
                sum(
                    _safe_float(
                        (acc or {}).get("יתרה")
                        or (acc or {}).get("balance")
                        or (acc or {}).get("סך_תגמולים")
                        or (acc or {}).get("תגמולים")
                    )
                    for acc in pension_portfolio_data
                    if isinstance(acc, dict)
                )
            )
        except Exception:
            portfolio_accounts_total_balance = 0.0

        portfolio_sources = self._build_sources_from_pension_portfolio(
            pension_portfolio=pension_portfolio_data,
            client=client,
            retirement_age=retirement_age,
            retirement_date=retirement_date,
            retirement_year=retirement_year,
        )

        blocked_fields = {
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
        }

        try:
            blocked_total_detected = float(
                sum(
                    float(s.get("balance") or 0)
                    for s in (portfolio_sources or [])
                    if isinstance(s, dict)
                    and str(s.get("component_field") or "").strip() in blocked_fields
                )
            )
        except Exception:
            blocked_total_detected = 0.0

        if ignore_blocked_balances:
            try:
                portfolio_sources = [
                    s
                    for s in (portfolio_sources or [])
                    if not (
                        isinstance(s, dict)
                        and str(s.get("component_field") or "").strip() in blocked_fields
                    )
                ]
            except Exception:
                portfolio_sources = portfolio_sources
        portfolio_sources_total = len(portfolio_sources)
        try:
            portfolio_sources_total_balance = float(
                sum(
                    float(s.get("balance") or 0)
                    for s in portfolio_sources
                    if isinstance(s, dict)
                )
            )
        except Exception:
            portfolio_sources_total_balance = 0.0

        existing_account_numbers: set[str] = set()
        for src in pension_sources:
            if not isinstance(src, dict):
                continue
            acc = src.get("account_number")
            if isinstance(acc, str) and acc.strip():
                existing_account_numbers.add(acc.strip())

        seen_portfolio_account_numbers: set[str] = set()
        seen_portfolio_source_keys: set[str] = set()
        filtered_portfolio_sources: list[dict] = []
        for src in portfolio_sources:
            if not isinstance(src, dict):
                continue
            acc = src.get("account_number")
            acc_norm = acc.strip() if isinstance(acc, str) else ""
            try:
                src_name_norm = str(src.get("source_name") or "").strip()
            except Exception:
                src_name_norm = ""
            source_key = f"{acc_norm}::{src_name_norm}" if acc_norm else src_name_norm
            if source_key:
                if source_key in seen_portfolio_source_keys:
                    continue
                seen_portfolio_source_keys.add(source_key)
            if acc_norm:
                if acc_norm in seen_portfolio_account_numbers:
                    # We still allow multiple component sources per account.
                    pass
                seen_portfolio_account_numbers.add(acc_norm)
                if acc_norm in existing_account_numbers:
                    portfolio_sources_skipped_duplicates += 1
                    continue
            filtered_portfolio_sources.append(src)

        portfolio_sources_unique_accounts = len(seen_portfolio_account_numbers)
        portfolio_sources_added = len(filtered_portfolio_sources)
        pension_sources.extend(filtered_portfolio_sources)

    if not pension_sources:
        return {
            "success": False,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {},
            "explanation": (
                "לא נמצאו מקורות קצבה (קרנות פנסיה או נכסי הון) ללקוח. "
                "ייתכן שטרם הורץ תרחיש פרישה עם תיק פנסיוני, או שהתיק הפנסיוני לא נשמר כראוי. "
                "אנא וודא שהעלית תיק פנסיוני והרצת תרחישי פרישה דרך המסך המיועד לכך."
            ),
        }

    def _infer_priority_bucket(source: dict[str, Any]) -> int:
        try:
            explicit = source.get("priority_bucket")
            if isinstance(explicit, (int, float)):
                return int(explicit)
        except Exception:
            pass
        src_type = str(source.get("source_type") or "")
        fund_type = str(source.get("fund_type") or "")
        name = str(source.get("source_name") or "")
        return (
            0
            if source.get("action_needed") == "none"
            else 1
            if ("pension_fund" in src_type or "from_portfolio" in src_type)
            else 4
            if "השתלמות" in fund_type or "השתלמות" in name
            else 3
            if "גמל" in fund_type or "קופת" in fund_type or "גמל" in name
            else 2
            if "capital_asset" in src_type
            else 9
        )

    def _is_pension_only_source(source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False

        src_type = str(source.get("source_type") or "")
        if src_type in {"existing_pension", "pension_fund"}:
            return True
        if src_type == "capital_asset":
            return False

        if src_type != "pension_fund_from_portfolio":
            return False

        field = str(source.get("component_field") or "").strip()
        product_type = str(source.get("fund_type") or "")
        if not field:
            return False

        if "השתלמות" in product_type or "השתלמות" in str(source.get("source_name") or ""):
            return False

        if field == "תגמולים":
            rule = rule_for_tagmulim_by_product_type(product_type=product_type)
            try:
                can_pension = bool(rule.get("pension"))
            except Exception:
                can_pension = True
            try:
                can_capital = bool(rule.get("capital") or rule.get("capital_asset"))
            except Exception:
                can_capital = False
            return can_pension and (not can_capital)

        rule = COMPONENT_RULES.get(field)
        if not isinstance(rule, dict):
            return False
        try:
            can_pension = bool(rule.get("pension"))
        except Exception:
            can_pension = True
        try:
            can_capital = bool(rule.get("capital") or rule.get("capital_asset"))
        except Exception:
            can_capital = False
        return can_pension and (not can_capital)

    def _is_hishtalmut_source(source: dict[str, Any]) -> bool:
        if not isinstance(source, dict):
            return False
        src_type = str(source.get("source_type") or "")
        if src_type != "pension_fund_from_portfolio":
            return False
        fund_type = str(source.get("fund_type") or "")
        if "השתלמות" in fund_type:
            return True
        source_name = str(source.get("source_name") or "")
        if "השתלמות" in source_name:
            return True
        component_field = str(source.get("component_field") or "")
        if component_field == "קרן_השתלמות":
            return True
        return False

    def _phase_rank(source: dict[str, Any]) -> int:
        if not isinstance(source, dict):
            return 99
        if source.get("action_needed") == "none":
            return 0
        if _is_pension_only_source(source):
            return 1
        if str(source.get("source_type") or "") == "capital_asset":
            return 3
        return 2

    # שלב 2: מיון לפי מתודולוגיה דטרמיניסטית + איכות (מקדם נמוך = טוב יותר)
    pension_sources.sort(
        key=lambda x: (
            _phase_rank(x),
            _infer_priority_bucket(x),
            float(x.get("annuity_factor") or PENSION_COEFFICIENT),
        )
    )

    # שלב 3: בניית התכנית - צבירת קצבה עד היעד
    plan_steps = []
    accumulated_pension = 0.0
    remaining_capital = 0.0
    blocked_for_execution_capital = 0.0
    sources_used = []
    sources_not_used = []

    existing_sources: list[dict[str, Any]] = []
    pension_only_sources: list[dict[str, Any]] = []
    other_sources: list[dict[str, Any]] = []
    for src in pension_sources:
        if not isinstance(src, dict):
            continue
        if src.get("action_needed") == "none":
            existing_sources.append(src)
            continue
        if _is_pension_only_source(src):
            pension_only_sources.append(src)
        else:
            other_sources.append(src)

    existing_sources.sort(
        key=lambda x: (
            _infer_priority_bucket(x),
            float(x.get("annuity_factor") or PENSION_COEFFICIENT),
        )
    )
    pension_only_sources.sort(
        key=lambda x: (
            _infer_priority_bucket(x),
            float(x.get("annuity_factor") or PENSION_COEFFICIENT),
        )
    )
    other_sources.sort(
        key=lambda x: (
            _phase_rank(x),
            _infer_priority_bucket(x),
            float(x.get("annuity_factor") or PENSION_COEFFICIENT),
        )
    )

    hishtalmut_sources: list[dict[str, Any]] = []
    non_hishtalmut_other_sources: list[dict[str, Any]] = []
    for src in other_sources:
        if _is_hishtalmut_source(src):
            hishtalmut_sources.append(src)
        else:
            non_hishtalmut_other_sources.append(src)

    pension_sources = [
        *existing_sources,
        *pension_only_sources,
        *non_hishtalmut_other_sources,
        *hishtalmut_sources,
    ]

    for source in pension_sources:
        if source.get("action_needed") == "requires_termination":
            sources_not_used.append(source)
            blocked_for_execution_capital += float(source.get("balance") or 0)
            continue
        if accumulated_pension >= required_gross_for_target:
            # כבר הגענו ליעד - השאר נשאר כהון
            sources_not_used.append(source)
            remaining_capital += source["balance"]
            continue

        pension_from_source = source["monthly_pension"]
        needed = required_gross_for_target - accumulated_pension

        if pension_from_source <= needed:
            # משתמשים בכל המקור
            accumulated_pension += pension_from_source
            sources_used.append(
                {
                    **source,
                    "pension_used": pension_from_source,
                    "balance_used": source["balance"],
                    "partial": False,
                }
            )
            plan_steps.append(
                {
                    "step_number": len(plan_steps) + 1,
                    "action": source["action_description"],
                    "pension_added": pension_from_source,
                    "accumulated_pension": accumulated_pension,
                    "source_name": source["source_name"],
                    "annuity_factor": source["annuity_factor"],
                }
            )
        else:
            # משתמשים רק בחלק מהמקור
            partial_balance = needed * source["annuity_factor"]
            accumulated_pension += needed
            remaining_from_source = source["balance"] - partial_balance
            remaining_capital += remaining_from_source

            sources_used.append(
                {
                    **source,
                    "pension_used": needed,
                    "balance_used": partial_balance,
                    "partial": True,
                    "remaining_balance": remaining_from_source,
                }
            )
            plan_steps.append(
                {
                    "step_number": len(plan_steps) + 1,
                    "action": f"המרה חלקית: {partial_balance:,.0f} ₪ מתוך {source['balance']:,.0f} ₪ לקצבה של {needed:,.0f} ₪/חודש",
                    "pension_added": needed,
                    "accumulated_pension": accumulated_pension,
                    "source_name": source["source_name"],
                    "annuity_factor": source["annuity_factor"],
                    "remaining_as_capital": remaining_from_source,
                }
            )

    # חישוב סיכום
    target_achieved_gross = accumulated_pension >= required_gross_for_target
    gap = max(0, required_gross_for_target - accumulated_pension)

    # בניית יתרונות וחסרונות
    advantages = []
    disadvantages = []

    if target_achieved_gross:
        if target_is_net:
            advantages.append(f"הושג יעד ברוטו שמוערך כמספיק ל-{target:,.0f} ₪ נטו")
        else:
            advantages.append(f"היעד של {target:,.0f} ₪ לחודש הושג")

    if remaining_capital > 0:
        advantages.append(f"נותר הון נזיל של {remaining_capital:,.0f} ₪")

    # בדיקת איכות המקורות שנבחרו
    avg_factor = (
        sum(s["annuity_factor"] for s in sources_used) / len(sources_used)
        if sources_used
        else 0
    )
    if avg_factor < 180:
        advantages.append(f"מקדם קצבה ממוצע טוב ({avg_factor:.0f})")
    elif avg_factor > 200:
        disadvantages.append(f"מקדם קצבה ממוצע גבוה ({avg_factor:.0f}) - פחות יעיל")

    # בדיקת מס
    taxable_pension = sum(
        s["pension_used"] for s in sources_used if s["tax_treatment"] == "taxable"
    )
    exempt_pension = sum(
        s["pension_used"] for s in sources_used if s["tax_treatment"] == "exempt"
    )

    if exempt_pension > 0:
        advantages.append(f"{exempt_pension:,.0f} ₪ מהקצבה פטורים ממס")
    if taxable_pension > accumulated_pension * 0.7:
        disadvantages.append(f"רוב הקצבה ({taxable_pension:,.0f} ₪) חייבת במס")

    if not target_achieved_gross:
        if target_is_net:
            disadvantages.append(
                f"לא ניתן להגיע ליעד נטו - חסרים {gap:,.0f} ₪ ברוטו לחודש לפי ההמרה הנוכחית"
            )
        else:
            disadvantages.append(f"לא ניתן להגיע ליעד - חסרים {gap:,.0f} ₪ לחודש")

    estimated_tax = None
    estimated_net = None
    tax_projection_result = None
    try:
        tax_proj = self.get_tax_projection(monthly_pension=accumulated_pension)
        if isinstance(tax_proj, dict) and isinstance(tax_proj.get("result"), dict):
            tax_projection_result = tax_proj.get("result")
            estimated_tax = tax_projection_result.get("monthly_tax")
            if estimated_tax is not None:
                try:
                    estimated_net = float(accumulated_pension) - float(estimated_tax)
                except Exception:
                    estimated_net = None
    except Exception:
        tax_projection_result = None

    # יעד נטו בפועל לפי הערכת מס - בדיקה סופית
    target_achieved_net = None
    if target_is_net and estimated_net is not None:
        try:
            target_achieved_net = float(estimated_net) >= float(target)
        except Exception:
            target_achieved_net = None
    if target_is_net and estimated_net is None:
        target_achieved_net = False

    explanation = build_target_pension_plan_explanation(
        target_achieved_gross=target_achieved_gross,
        target=target,
        target_is_net=target_is_net,
        retirement_age=retirement_age,
        plan_steps=plan_steps,
        remaining_capital=remaining_capital,
        advantages=advantages,
        disadvantages=disadvantages,
        blocked_for_execution_capital=blocked_for_execution_capital,
        accumulated_pension=accumulated_pension,
        estimated_net=estimated_net,
        gap=gap,
        required_gross_for_target=required_gross_for_target,
        exempt_pension=exempt_pension,
        avg_factor=avg_factor,
    )

    execution_plan_accounts: list[dict[str, Any]] = []
    try:
        for src in sources_used or []:
            if not isinstance(src, dict):
                continue
            if str(src.get("source_type") or "") != "pension_fund_from_portfolio":
                continue
            acc_id = src.get("account_number")
            if acc_id is None:
                acc_id = src.get("source_id")
            if acc_id is None:
                continue
            component = src.get("component_field")
            if component is None:
                component = src.get("fund_type")
            if component is None:
                component = "unknown"
            try:
                amount_to_convert = float(src.get("balance_used") or 0)
            except Exception:
                amount_to_convert = 0.0
            try:
                expected_monthly_pension = float(src.get("pension_used") or 0)
            except Exception:
                expected_monthly_pension = 0.0
            if amount_to_convert <= 0 or expected_monthly_pension <= 0:
                continue
            execution_plan_accounts.append(
                {
                    "account_id": str(acc_id),
                    "component": str(component),
                    "amount_to_convert": float(amount_to_convert),
                    "expected_monthly_pension": float(expected_monthly_pension),
                }
            )
    except Exception:
        execution_plan_accounts = []

    try:
        target_gross_val = (
            float(required_gross_for_target) if target_is_net else float(target_monthly_pension)
        )
    except Exception:
        target_gross_val = 0.0
    try:
        target_net_val = float(target_monthly_pension) if target_is_net else float(estimated_net or 0)
    except Exception:
        target_net_val = 0.0
    expected_total_gross_val = 0.0
    try:
        expected_total_gross_val = float(
            sum(
                float(a.get("expected_monthly_pension") or 0)
                for a in (execution_plan_accounts or [])
                if isinstance(a, dict)
            )
        )
    except Exception:
        expected_total_gross_val = 0.0
    try:
        expected_total_net_val = float(estimated_net or 0)
    except Exception:
        expected_total_net_val = 0.0

    execution_plan: dict[str, Any] = {
        "target_net": int(round(target_net_val)),
        "target_gross": int(round(target_gross_val)),
        "accounts": execution_plan_accounts,
        "expected_total_gross": float(expected_total_gross_val),
        "expected_total_net": float(expected_total_net_val),
    }

    return {
        "success": True,
        "tool_name": "BUILD_TARGET_PENSION_PLAN",
        "result": {
            "target_monthly_pension": target,
            "target_is_net": target_is_net,
            "retirement_age": retirement_age,
            "target_achieved": (
                target_achieved_net if target_is_net else target_achieved_gross
            ),
            "target_achieved_gross": target_achieved_gross,
            "target_achieved_net": target_achieved_net,
            "required_gross_for_target": required_gross_for_target,
            "required_gross_tax_projection": required_gross_tax_projection,
            "accumulated_pension": accumulated_pension,
            "taxable_pension": taxable_pension,
            "exempt_pension": exempt_pension,
            "estimated_monthly_tax": estimated_tax,
            "estimated_monthly_net": estimated_net,
            "tax_projection": tax_projection_result,
            "portfolio_sources_total": portfolio_sources_total,
            "portfolio_sources_added": portfolio_sources_added,
            "portfolio_sources_skipped_duplicates": portfolio_sources_skipped_duplicates,
            "portfolio_sources_unique_accounts": portfolio_sources_unique_accounts,
            "portfolio_sources_total_balance": portfolio_sources_total_balance,
            "debug_inputs": {
                "portfolio_sources_count": int(portfolio_accounts_count or 0),
                "portfolio_total_balance": float(portfolio_accounts_total_balance or 0.0),
                "blocked_total_detected": float(blocked_total_detected or 0.0),
                "ignore_blocked_balances": bool(ignore_blocked_balances),
                "sources_used": [
                    {
                        "account_number": str(s.get("account_number") or "") if isinstance(s, dict) else "",
                        "account_name": str(s.get("source_name") or "") if isinstance(s, dict) else "",
                        "product_type": str(s.get("fund_type") or "") if isinstance(s, dict) else "",
                        "component_key": (
                            str(s.get("component_field") or "") if isinstance(s, dict) and s.get("component_field") is not None else None
                        ),
                        "amount_used": float((s or {}).get("balance_used") or 0) if isinstance(s, dict) else 0.0,
                        "annuity_factor": float((s or {}).get("annuity_factor") or 0) if isinstance(s, dict) else 0.0,
                        "coeff_source_table": (
                            str((s or {}).get("coeff_source_table") or "") if isinstance(s, dict) and (s or {}).get("coeff_source_table") is not None else None
                        ),
                        "fallback_used": bool((s or {}).get("fallback_used")) if isinstance(s, dict) else False,
                    }
                    for s in (sources_used or [])
                    if isinstance(s, dict)
                ],
            },
            "gap_to_target": gap,
            "remaining_capital": remaining_capital,
            "blocked_for_execution_capital": blocked_for_execution_capital,
            "plan_steps": plan_steps,
            "sources_used": sources_used,
            "sources_not_used": sources_not_used,
            "advantages": advantages,
            "disadvantages": disadvantages,
            "total_sources_available": len(pension_sources),
            "sources_used_count": len(sources_used),
            "execution_plan": execution_plan,
        },
        "explanation": explanation,
    }
