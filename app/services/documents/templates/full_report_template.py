from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.services.documents.data_fetchers.fixation_data import FixationData


def _format_currency(value: Any) -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f"{v:,.0f} ₪"


def _format_date(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _safe_str(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def _render_net_chart_svg(cashflow_rows: List[Dict[str, Any]]) -> str:
    points = []
    for r in cashflow_rows:
        net = r.get("net")
        try:
            points.append(float(net or 0))
        except (TypeError, ValueError):
            points.append(0.0)

    if not points:
        return "<div class=\"small\">אין נתוני תזרים להצגת גרף</div>"

    w = 820
    h = 220
    padding = 24

    min_v = min(points)
    max_v = max(points)
    if abs(max_v - min_v) < 1e-9:
        max_v = min_v + 1.0

    def x(i: int) -> float:
        if len(points) == 1:
            return padding
        return padding + (w - 2 * padding) * (i / (len(points) - 1))

    def y(v: float) -> float:
        norm = (v - min_v) / (max_v - min_v)
        return (h - padding) - norm * (h - 2 * padding)

    poly = " ".join(f"{x(i):.2f},{y(v):.2f}" for i, v in enumerate(points))
    zero_y = y(0.0)

    return f"""
<svg viewBox=\"0 0 {w} {h}\" xmlns=\"http://www.w3.org/2000/svg\" aria-label=\"Net cashflow chart\">
  <rect x=\"0\" y=\"0\" width=\"{w}\" height=\"{h}\" fill=\"#ffffff\" />
  <line x1=\"{padding}\" y1=\"{zero_y:.2f}\" x2=\"{w - padding}\" y2=\"{zero_y:.2f}\" stroke=\"#adb5bd\" stroke-width=\"1\" />
  <polyline fill=\"none\" stroke=\"#1f4e79\" stroke-width=\"2\" points=\"{poly}\" />
</svg>
"""


class FullReportHTMLTemplate:
    def __init__(
        self,
        *,
        client: Client,
        report_title: str,
        date_range: str,
        generated_at: str,
        analysis_result: Optional[dict],
        fixation_data: Optional[FixationData],
        pension_funds: List[PensionFund],
        additional_incomes: List[AdditionalIncome],
        capital_assets: List[CapitalAsset],
        commutations: List[CapitalAsset],
        grants_dates_map: Dict[str, Dict[str, str]],
        yearly_totals: Dict[str, Dict[str, float]],
        cashflow_rows: List[Dict[str, Any]],
        include_charts: bool,
        css_filename: str,
    ):
        self.client = client
        self.report_title = report_title
        self.date_range = date_range
        self.generated_at = generated_at
        self.analysis_result = analysis_result
        self.fixation_data = fixation_data
        self.pension_funds = pension_funds
        self.additional_incomes = additional_incomes
        self.capital_assets = capital_assets
        self.commutations = commutations
        self.grants_dates_map = grants_dates_map
        self.yearly_totals = yearly_totals
        self.cashflow_rows = cashflow_rows
        self.include_charts = include_charts
        self.css_filename = css_filename

    def _render_client_section(self) -> str:
        return f"""
<div class=\"section card\">
  <h2>פרטי לקוח</h2>
  <table>
    <tbody>
      <tr><td><strong>שם</strong></td><td>{_safe_str(self.client.full_name)}</td></tr>
      <tr><td><strong>תעודת זהות</strong></td><td>{_safe_str(getattr(self.client, 'id_number', None))}</td></tr>
      <tr><td><strong>טווח תאריכים</strong></td><td>{_safe_str(self.date_range)}</td></tr>
    </tbody>
  </table>
</div>
"""

    def _render_analysis_section(self) -> str:
        if not isinstance(self.analysis_result, dict):
            return ""
        r = self.analysis_result
        return f"""
<div class=\"section card\">
  <h2>סיכום ניתוח פרישה</h2>
  <table>
    <tbody>
      <tr><td><strong>תאריך פרישה</strong></td><td>{_safe_str(r.get('retirement_date'))}</td></tr>
      <tr><td><strong>גיל פרישה</strong></td><td>{_safe_str(r.get('retirement_age'))}</td></tr>
      <tr><td><strong>קצבה ברוטו</strong></td><td>{_format_currency(r.get('projected_pension'))}</td></tr>
      <tr><td><strong>מס הכנסה חודשי</strong></td><td>{_format_currency(r.get('monthly_income_tax'))}</td></tr>
      <tr><td><strong>קצבה נטו</strong></td><td>{_format_currency(r.get('projected_pension_net'))}</td></tr>
      <tr><td><strong>הכנסה נטו כוללת</strong></td><td>{_format_currency(r.get('total_guaranteed_income_net'))}</td></tr>
    </tbody>
  </table>
</div>
"""

    def _render_fixation_section(self) -> str:
        if not self.fixation_data or not isinstance(self.fixation_data.exemption_summary, dict):
            return ""
        es = self.fixation_data.exemption_summary
        pct = 0.0
        try:
            pct = float(es.get("exempt_pension_percentage", 0) or 0) * 100
        except (TypeError, ValueError):
            pct = 0.0
        return f"""
<div class=\"section card\">
  <h2>קיבוע זכויות</h2>
  <table>
    <tbody>
      <tr><td><strong>הון פטור נותר</strong></td><td>{_format_currency(es.get('remaining_exempt_capital'))}</td></tr>
      <tr><td><strong>אחוז קצבה פטורה</strong></td><td>{pct:.1f}%</td></tr>
      <tr><td><strong>סה\"כ היוונים</strong></td><td>{_format_currency(es.get('total_commutations'))}</td></tr>
    </tbody>
  </table>
</div>
"""

    def _render_pensions_section(self) -> str:
        rows = []
        for p in self.pension_funds:
            rows.append(
                "<tr>"
                f"<td>{_safe_str(getattr(p, 'fund_name', None) or getattr(p, 'pension_name', None))}</td>"
                f"<td>{_format_currency(getattr(p, 'balance', None))}</td>"
                f"<td>{_format_currency(getattr(p, 'pension_amount', None) or getattr(p, 'computed_monthly_amount', None))}</td>"
                f"<td>{_safe_str(getattr(p, 'annuity_factor', None))}</td>"
                f"<td>{_format_date(getattr(p, 'pension_start_date', None) or getattr(p, 'start_date', None))}</td>"
                "</tr>"
            )

        body = "".join(rows) if rows else "<tr><td colspan=\"5\">אין נתונים</td></tr>"
        return f"""
<div class=\"section card page-break\">
  <h2>פירוט קצבאות</h2>
  <table>
    <thead><tr><th>שם קרן</th><th>יתרה</th><th>קצבה חודשית</th><th>מקדם</th><th>תאריך תחילה</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def _render_additional_income_section(self) -> str:
        rows = []
        for i in self.additional_incomes:
            rows.append(
                "<tr>"
                f"<td>{_safe_str(getattr(i, 'description', None))}</td>"
                f"<td>{_format_currency(getattr(i, 'amount', None))}</td>"
                f"<td>{_safe_str(getattr(i, 'frequency', None))}</td>"
                f"<td>{_format_date(getattr(i, 'start_date', None))}</td>"
                f"<td>{_format_date(getattr(i, 'end_date', None))}</td>"
                "</tr>"
            )

        body = "".join(rows) if rows else "<tr><td colspan=\"5\">אין נתונים</td></tr>"
        return f"""
<div class=\"section card\">
  <h2>הכנסות נוספות</h2>
  <table>
    <thead><tr><th>תיאור</th><th>סכום</th><th>תדירות</th><th>תאריך התחלה</th><th>תאריך סיום</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def _render_capital_assets_section(self) -> str:
        rows = []
        for a in self.capital_assets:
            rows.append(
                "<tr>"
                f"<td>{_safe_str(getattr(a, 'asset_name', None) or getattr(a, 'description', None))}</td>"
                f"<td>{_format_currency(getattr(a, 'current_value', None))}</td>"
                f"<td>{_format_currency(getattr(a, 'monthly_income', None))}</td>"
                f"<td>{_format_date(getattr(a, 'start_date', None))}</td>"
                "</tr>"
            )

        body = "".join(rows) if rows else "<tr><td colspan=\"4\">אין נתונים</td></tr>"
        return f"""
<div class=\"section card\">
  <h2>נכסי הון</h2>
  <table>
    <thead><tr><th>תיאור</th><th>ערך נוכחי</th><th>תשלום חודשי</th><th>תאריך תחילה</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def _render_commutations_section(self) -> str:
        rows = []
        for c in self.commutations:
            rows.append(
                "<tr>"
                f"<td>{_safe_str(getattr(c, 'asset_name', None) or getattr(c, 'description', None))}</td>"
                f"<td>{_format_currency(getattr(c, 'current_value', None))}</td>"
                f"<td>{_format_date(getattr(c, 'start_date', None))}</td>"
                f"<td>{_safe_str(getattr(c, 'tax_treatment', None))}</td>"
                "</tr>"
            )

        body = "".join(rows) if rows else "<tr><td colspan=\"4\">אין נתונים</td></tr>"
        return f"""
<div class=\"section card\">
  <h2>היוונים (פטורים ממס)</h2>
  <table>
    <thead><tr><th>תיאור</th><th>סכום</th><th>תאריך</th><th>מיסוי</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def _render_grants_section(self) -> str:
        if not self.grants_dates_map:
            return ""

        rows = []
        for employer_name, dates in self.grants_dates_map.items():
            rows.append(
                "<tr>"
                f"<td>{_safe_str(employer_name)}</td>"
                f"<td>{_safe_str(dates.get('work_start_date'))}</td>"
                f"<td>{_safe_str(dates.get('work_end_date'))}</td>"
                "</tr>"
            )

        body = "".join(rows)
        return f"""
<div class=\"section card\">
  <h2>מענקים (תקופות עבודה)</h2>
  <table>
    <thead><tr><th>מעסיק</th><th>תחילת עבודה</th><th>סיום עבודה</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def _render_yearly_section(self) -> str:
        rows = []
        for y, t in sorted(self.yearly_totals.items()):
            rows.append(
                "<tr>"
                f"<td>{_safe_str(y)}</td>"
                f"<td>{_format_currency(t.get('inflow'))}</td>"
                f"<td>{_format_currency(t.get('outflow'))}</td>"
                f"<td>{_format_currency(t.get('additional_income_net'))}</td>"
                f"<td>{_format_currency(t.get('capital_return_net'))}</td>"
                f"<td>{_format_currency(t.get('net'))}</td>"
                "</tr>"
            )

        body = "".join(rows) if rows else "<tr><td colspan=\"6\">אין נתונים</td></tr>"
        return f"""
<div class=\"section card page-break\">
  <h2>סיכום שנתי</h2>
  <table>
    <thead><tr><th>שנה</th><th>הכנסות</th><th>הוצאות</th><th>הכנסות נוספות</th><th>החזרי הון</th><th>נטו</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def _render_monthly_section(self) -> str:
        rows = []
        for r in self.cashflow_rows:
            d = r.get("date")
            dstr = str(d)[:7] if d else "-"
            rows.append(
                "<tr>"
                f"<td>{dstr}</td>"
                f"<td>{_format_currency(r.get('inflow'))}</td>"
                f"<td>{_format_currency(r.get('outflow'))}</td>"
                f"<td>{_format_currency(r.get('additional_income_net'))}</td>"
                f"<td>{_format_currency(r.get('capital_return_net'))}</td>"
                f"<td>{_format_currency(r.get('net'))}</td>"
                "</tr>"
            )

        body = "".join(rows) if rows else "<tr><td colspan=\"6\">אין נתונים</td></tr>"
        chart_html = ""
        if self.include_charts:
            chart_html = f"<div class=\"section\"><h2>גרף תזרים נטו</h2>{_render_net_chart_svg(self.cashflow_rows)}</div>"

        return f"""
<div class=\"section card\">
  <h2>פירוט תזרים חודשי</h2>
  {chart_html}
  <table>
    <thead><tr><th>תאריך</th><th>הכנסות</th><th>הוצאות</th><th>הכנסות נוספות</th><th>החזרי הון</th><th>נטו</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""

    def render(self) -> str:
        return f"""<!DOCTYPE html>
<html dir=\"rtl\" lang=\"he\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{self.report_title}</title>
  <link rel=\"stylesheet\" href=\"{self.css_filename}\" />
</head>
<body>
  <h1>{self.report_title}</h1>
  <div class=\"meta\">נוצר בתאריך: {self.generated_at}</div>

  {self._render_client_section()}
  {self._render_analysis_section()}
  {self._render_fixation_section()}
  {self._render_pensions_section()}
  {self._render_additional_income_section()}
  {self._render_capital_assets_section()}
  {self._render_commutations_section()}
  {self._render_grants_section()}
  {self._render_yearly_section()}
  {self._render_monthly_section()}

  <div class=\"small\">דוח נוצר ע\"י מערכת תכנון פרישה</div>
</body>
</html>
"""
