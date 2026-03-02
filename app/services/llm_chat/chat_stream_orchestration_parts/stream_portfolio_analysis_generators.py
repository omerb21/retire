import json
from datetime import date
from decimal import Decimal

from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.services.additional_income_service import AdditionalIncomeService
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context


def _classify_system_source_label(name: str) -> str:
    lowered = (name or "").strip().lower()
    if not lowered:
        return "system_generated"
    if "פיצויים" in lowered or "עזיבת" in lowered or "termination" in lowered:
        return "termination"
    return "system_generated"


def _looks_portfolio_imported(conversion_source: object) -> bool:
    try:
        raw = str(conversion_source or "")
    except Exception:
        raw = ""
    if not raw:
        return False
    return (
        '"source": "pension_portfolio"' in raw
        or '"type": "pension_portfolio"' in raw
        or '"source": "pension_portfolio_convert"' in raw
    )


def _load_system_assets(*, db, client_id: int) -> dict:
    system_pension_streams: list[dict[str, object]] = []
    system_capital_assets: list[dict[str, object]] = []

    try:
        pension_rows = (
            db.query(PensionFund)
            .filter(PensionFund.client_id == client_id)
            .order_by(PensionFund.id.asc())
            .all()
        )
    except Exception:
        pension_rows = []

    for pf in pension_rows or []:
        try:
            if _looks_portfolio_imported(getattr(pf, "conversion_source", None)):
                continue
        except Exception:
            pass

        try:
            monthly_amount = float(getattr(pf, "pension_amount", 0) or 0)
        except Exception:
            monthly_amount = 0.0

        if monthly_amount <= 0:
            continue

        name = str(getattr(pf, "fund_name", "") or "").strip()
        system_pension_streams.append(
            {
                "id": getattr(pf, "id", None),
                "monthly_amount": monthly_amount,
                "source": _classify_system_source_label(name),
                "provider": None,
                "plan_name": name or None,
            }
        )

    try:
        asset_rows = (
            db.query(CapitalAsset)
            .filter(CapitalAsset.client_id == client_id)
            .order_by(CapitalAsset.id.asc())
            .all()
        )
    except Exception:
        asset_rows = []

    for asset in asset_rows or []:
        try:
            if _looks_portfolio_imported(getattr(asset, "conversion_source", None)):
                continue
        except Exception:
            pass

        try:
            monthly_income = float(getattr(asset, "monthly_income", 0) or 0)
        except Exception:
            monthly_income = 0.0
        try:
            current_value = float(getattr(asset, "current_value", 0) or 0)
        except Exception:
            current_value = 0.0

        amount = monthly_income if monthly_income > 0 else current_value
        if amount <= 0:
            continue

        asset_name = str(getattr(asset, "asset_name", "") or "").strip()
        desc = str(getattr(asset, "description", "") or "").strip()

        system_capital_assets.append(
            {
                "id": getattr(asset, "id", None),
                "amount": amount,
                "source": _classify_system_source_label(asset_name or desc),
                "description": desc or asset_name or None,
            }
        )

    return {
        "system_pension_streams": system_pension_streams,
        "system_capital_assets": system_capital_assets,
    }


def _format_system_assets_block(
    *, system_assets: dict, masleka_account_count: int
) -> str:
    pensions = system_assets.get("system_pension_streams") or []
    capitals = system_assets.get("system_capital_assets") or []
    if (not pensions) and (not capitals):
        return ""

    lines: list[str] = []
    lines.append("\n\n## נכסים שנוצרו במערכת (לא מהמסלקה)")

    pension_total = 0.0
    for p in pensions:
        try:
            pension_total += float(p.get("monthly_amount") or 0)
        except Exception:
            pass

    capital_total = 0.0
    for c in capitals:
        try:
            capital_total += float(c.get("amount") or 0)
        except Exception:
            pass

    total_sources = int(masleka_account_count or 0) + len(pensions) + len(capitals)
    lines.append(f"מקורות במסלקה: {int(masleka_account_count or 0)}")
    lines.append(f"קצבאות קיימות במערכת: {len(pensions)}")
    lines.append(f"נכסי הון קיימים במערכת: {len(capitals)}")
    lines.append(f'סה"כ מקורות זמינים לתכנון: {total_sources}')

    try:
        lines.append(
            f'\nסה"כ קצבאות קיימות במערכת (ברוטו חודשי): {pension_total:,.0f} ₪'
        )
    except Exception:
        lines.append('\nסה"כ קצבאות קיימות במערכת (ברוטו חודשי): לא זמין')

    try:
        lines.append(f'סה"כ נכסי הון קיימים במערכת: {capital_total:,.0f} ₪')
    except Exception:
        lines.append('סה"כ נכסי הון קיימים במערכת: לא זמין')

    if pensions:
        lines.append("\n### קצבאות במערכת")
        for p in pensions:
            try:
                amount = float(p.get("monthly_amount") or 0)
            except Exception:
                amount = 0.0
            title = str(p.get("plan_name") or "")
            source = str(p.get("source") or "system_generated")
            if title.strip():
                lines.append(f"- {title}: {amount:,.0f} ₪/חודש (מקור: {source})")
            else:
                lines.append(f"- קצבה: {amount:,.0f} ₪/חודש (מקור: {source})")

    if capitals:
        lines.append("\n### נכסי הון במערכת")
        for c in capitals:
            try:
                amount = float(c.get("amount") or 0)
            except Exception:
                amount = 0.0
            desc = str(c.get("description") or "")
            source = str(c.get("source") or "system_generated")
            if desc.strip():
                lines.append(f"- {desc}: {amount:,.0f} ₪ (מקור: {source})")
            else:
                lines.append(f"- נכס הון: {amount:,.0f} ₪ (מקור: {source})")

    return "\n".join(lines)


def generate_breakdown(
    *, computed_data, portfolio, original_user_msg, effective_snapshot_at
) -> str:
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


def generate_portfolio_analysis(
    *, computed_data, request, db, portfolio, original_user_msg, effective_snapshot_at
) -> str:
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

    additional_incomes_block = ""
    system_assets_block = ""
    if request.client_id is not None:
        try:
            system_assets = _load_system_assets(db=db, client_id=int(request.client_id))
        except Exception:
            system_assets = {"system_pension_streams": [], "system_capital_assets": []}
        try:
            system_assets_block = _format_system_assets_block(
                system_assets=system_assets,
                masleka_account_count=len(portfolio or []),
            )
        except Exception:
            system_assets_block = ""

        try:
            reference_date = date.today()
            reference_date = date(reference_date.year, reference_date.month, 1)
        except Exception:
            reference_date = None

        try:
            additional_incomes = (
                db.query(AdditionalIncome)
                .filter(AdditionalIncome.client_id == request.client_id)
                .order_by(AdditionalIncome.id.asc())
                .all()
            )
        except Exception:
            additional_incomes = []

        if additional_incomes:
            income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
            try:
                client_for_tax = (
                    db.query(Client).filter(Client.id == request.client_id).first()
                )
            except Exception:
                client_for_tax = None

            def _fmt_date(d: object) -> str:
                try:
                    if d is None:
                        return ""
                    if hasattr(d, "isoformat"):
                        return str(d.isoformat())
                    return str(d)
                except Exception:
                    return ""

            def _fmt_frequency(value: object) -> str:
                raw = str(value or "").strip().lower()
                if raw == "monthly":
                    return "חודשי"
                if raw == "quarterly":
                    return "רבעוני"
                if raw == "annually":
                    return "שנתי"
                return raw or "לא ידוע"

            def _fmt_tax(income: AdditionalIncome) -> str:
                treatment = (
                    str(getattr(income, "tax_treatment", "") or "").strip().lower()
                )
                if treatment == "exempt":
                    return "פטור"
                if treatment == "fixed_rate":
                    rate = getattr(income, "tax_rate", None)
                    try:
                        if rate is None:
                            return "מס קבוע (לא ידוע)"
                        return f"מס קבוע ({float(rate):.0f}%)"
                    except Exception:
                        return "מס קבוע"
                if treatment == "taxable":
                    return "חייב"
                return treatment or "לא ידוע"

            def _fmt_indexation(income: AdditionalIncome) -> str:
                method = (
                    str(getattr(income, "indexation_method", "") or "").strip().lower()
                )
                if method in {"", "none"}:
                    return "ללא"
                if method == "cpi":
                    return "מדד"
                if method == "fixed":
                    rate = getattr(income, "fixed_rate", None)
                    try:
                        if rate is None:
                            return "קבוע"
                        return f"קבוע ({float(rate) * 100:.2f}%)"
                    except Exception:
                        return "קבוע"
                return method

            lines: list[str] = []
            lines.append("\n\n## הכנסות נוספות (Additional Incomes)")

            gross_total = Decimal("0")
            net_total = Decimal("0")
            any_unknown_tax = False

            for inc in additional_incomes:
                if reference_date is not None:
                    try:
                        if inc.start_date and reference_date < inc.start_date:
                            continue
                        if inc.end_date and reference_date > inc.end_date:
                            continue
                    except Exception:
                        pass

                source = str(getattr(inc, "source_type", "") or "").strip() or "other"
                desc = str(getattr(inc, "description", "") or "").strip()

                amount = getattr(inc, "amount", None)
                try:
                    amount_val = float(amount or 0)
                except Exception:
                    amount_val = 0.0

                freq = _fmt_frequency(getattr(inc, "frequency", None))
                tax_label = _fmt_tax(inc)
                index_label = _fmt_indexation(inc)

                start_s = _fmt_date(getattr(inc, "start_date", None))
                end_s = _fmt_date(getattr(inc, "end_date", None))
                date_range = start_s
                if end_s:
                    date_range = f"{start_s}–{end_s}" if start_s else end_s

                title_line = f"- מקור: {source}"
                if desc:
                    title_line = f"- מקור: {source} ({desc})"
                lines.append(title_line)
                lines.append(f"  סכום: {amount_val:,.0f} ₪")
                lines.append(f"  תדירות: {freq}")
                lines.append(f"  מס: {tax_label}")
                lines.append(f"  הצמדה: {index_label}")
                if date_range:
                    lines.append(f"  טווח: {date_range}")

                try:
                    monthly_gross = income_service.calculate_monthly_amount(inc)
                except Exception:
                    monthly_gross = None

                if monthly_gross is not None:
                    gross_total += monthly_gross
                    try:
                        tax_amt, _include = income_service.calculate_tax(
                            monthly_gross,
                            inc,
                            client_for_tax,
                            reference_date,
                        )
                        monthly_net = monthly_gross - tax_amt
                        net_total += monthly_net
                    except Exception:
                        any_unknown_tax = True

                if (
                    str(getattr(inc, "tax_treatment", "") or "").strip().lower()
                    == "fixed_rate"
                    and getattr(inc, "tax_rate", None) is None
                ):
                    any_unknown_tax = True

            if len(lines) > 1:
                if any_unknown_tax:
                    try:
                        gross_float = float(gross_total)
                        lines.append(
                            f'\nסה"כ הכנסות נוספות חודשי משוער (לפני מס): {gross_float:,.0f} ₪'
                        )
                    except Exception:
                        lines.append(
                            '\nסה"כ הכנסות נוספות חודשי משוער (לפני מס): לא זמין'
                        )
                else:
                    try:
                        net_float = float(net_total)
                        lines.append(
                            f'\nסה"כ הכנסות נוספות נטו חודשי משוער: {net_float:,.0f} ₪'
                        )
                    except Exception:
                        lines.append('\nסה"כ הכנסות נוספות נטו חודשי משוער: לא זמין')

                additional_incomes_block = "\n".join(lines)

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
                scenarios_text = str(scenario_result.get("explanation") or "").strip()
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

    note = (
        "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק."
    )
    if analysis:
        extra = ""
        if isinstance(scenarios_text, str) and scenarios_text.strip():
            extra = f"\n\n{scenarios_text}"
        yield f"{note}\n\n{title}\n\n{analysis}{system_assets_block}{additional_incomes_block}{extra}"
        return

    if system_assets_block.strip() or additional_incomes_block.strip():
        yield f"{note}\n\n{title}\n\nאין תיק פנסיוני לניתוח.{system_assets_block}{additional_incomes_block}"
        return
    yield f"{title}\n\nאין תיק פנסיוני לניתוח."
