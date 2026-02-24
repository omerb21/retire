from __future__ import annotations

import json

from app.schemas.llm_chat import ChatResponse


def _maybe_handle_list_all_financial_entities(
    *,
    request,
    db,
    request_id: str,
    original_user_msg,
    effective_portfolio,
    effective_snapshot_at,
    computed_data,
    _execute_tool_call,
    _fmt_money,
) -> ChatResponse | None:
    from app.services.llm_chat.orchestration_utils import (
        is_list_all_financial_entities_request,
    )

    if request.client_id is not None and is_list_all_financial_entities_request(
        original_user_msg
    ):
        tool_result = _execute_tool_call(
            "GET_SYSTEM_STATE_SNAPSHOT",
            {},
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )

        try:
            parsed = json.loads(tool_result)
        except Exception:
            parsed = None

        entities = parsed.get("entities") if isinstance(parsed, dict) else {}
        pension_funds = (
            entities.get("pension_funds") if isinstance(entities, dict) else None
        )
        capital_assets = (
            entities.get("capital_assets") if isinstance(entities, dict) else None
        )
        additional_incomes = (
            entities.get("additional_incomes") if isinstance(entities, dict) else None
        )

        lines: list[str] = []
        lines.append("הנתונים שנמצאים כרגע במערכת (DB) + תיק מסלקה שניטען:")

        if isinstance(effective_portfolio, list):
            lines.append("")
            lines.append("תיק פנסיוני (מסלקה / טבלת מוצרים):")
            lines.append(f"- מספר חשבונות: {len(effective_portfolio)}")
            if effective_snapshot_at:
                lines.append(f"- תאריך snapshot: {effective_snapshot_at}")

        lines.append("")
        lines.append("הכנסות נוספות (AdditionalIncome):")
        if isinstance(additional_incomes, list) and additional_incomes:
            for ai in additional_incomes:
                if not isinstance(ai, dict):
                    continue
                desc = (
                    (ai.get("description") or ai.get("source_type") or "הכנסה").strip()
                    if isinstance(
                        ai.get("description") or ai.get("source_type") or "", str
                    )
                    else "הכנסה"
                )
                amount = _fmt_money(ai.get("amount"))
                freq = ai.get("frequency") or ""
                lines.append(f"- {desc}: {amount} ₪ ({freq})")
        else:
            lines.append("- לא נמצאו הכנסות נוספות ב-DB")

        lines.append("")
        lines.append("קצבאות / קופות (PensionFund):")
        if isinstance(pension_funds, list) and pension_funds:
            for pf in pension_funds:
                if not isinstance(pf, dict):
                    continue
                name = (
                    (pf.get("fund_name") or "קופה").strip()
                    if isinstance(pf.get("fund_name") or "", str)
                    else "קופה"
                )
                p_amount = _fmt_money(pf.get("pension_amount"))
                bal = _fmt_money(pf.get("balance"))
                lines.append(f"- {name}: קצבה={p_amount} ₪/חודש | יתרה={bal} ₪")
        else:
            lines.append("- לא נמצאו קצבאות/קופות ב-DB")

        lines.append("")
        lines.append("נכסי הון (CapitalAsset):")
        if isinstance(capital_assets, list) and capital_assets:
            for ca in capital_assets:
                if not isinstance(ca, dict):
                    continue
                name = (
                    (ca.get("asset_name") or "נכס").strip()
                    if isinstance(ca.get("asset_name") or "", str)
                    else "נכס"
                )
                cur = _fmt_money(ca.get("current_value"))
                mi = _fmt_money(ca.get("monthly_income"))
                lines.append(f"- {name}: שווי={cur} ₪ | הכנסה חודשית={mi} ₪")
        else:
            lines.append("- לא נמצאו נכסי הון ב-DB")

        return ChatResponse(reply="\n".join(lines).strip(), computed_data=computed_data)

    return None
