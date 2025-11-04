"""
תבנית HTML לטופס קיבוע זכויות
"""
from datetime import date, datetime
from typing import Dict, Any, List
from .styles import get_fixation_styles


class FixationHTMLTemplate:
    """
    תבנית HTML לטופס קיבוע זכויות (161ד)
    """
    
    def __init__(
        self,
        client_name: str,
        client_id_number: str,
        exemption_summary: Dict[str, Any],
        grants_summary: List[Dict[str, Any]]
    ):
        """
        Args:
            client_name: שם הלקוח
            client_id_number: תעודת זהות
            exemption_summary: סיכום פטור
            grants_summary: רשימת מענקים
        """
        self.client_name = client_name
        self.client_id_number = client_id_number
        self.exemption_summary = exemption_summary
        self.grants_summary = grants_summary
    
    def _build_header(self) -> str:
        """בניית כותרת המסמך"""
        return f"""
    <div class="header">
        <h1>📋 טופס קיבוע זכויות (161ד)</h1>
        <p style="font-size: 14px; color: #666;">מסמך רשמי לרשות המיסים</p>
    </div>
"""
    
    def _build_client_info(self) -> str:
        """בניית מידע לקוח"""
        return f"""
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {self.client_name}</p>
        <p><strong>תעודת זהות:</strong> {self.client_id_number}</p>
        <p><strong>תאריך חישוב:</strong> {date.today().strftime("%d/%m/%Y")}</p>
        <p><strong>שנת זכאות:</strong> {self.exemption_summary.get('eligibility_year', '')}</p>
    </div>
"""
    
    def _build_summary_table(self) -> str:
        """בניית טבלת סיכום"""
        es = self.exemption_summary
        
        return f"""
    <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">סיכום קיבוע זכויות</h2>
    
    <table class="summary-table">
        <tbody>
            <tr>
                <td>יתרת הון פטורה ראשונית</td>
                <td class="green-text">{es.get('exempt_capital_initial', 0):,.0f} ₪</td>
            </tr>
            <tr>
                <td>סך מענקים נומינליים רלוונטיים</td>
                <td>{es.get('grants_nominal', 0):,.0f} ₪</td>
            </tr>
            <tr>
                <td>סך המענקים הרלוונטיים לאחר הוצמדה</td>
                <td>{es.get('grants_indexed', 0):,.0f} ₪</td>
            </tr>
            <tr>
                <td>סך הכל פגיעה בפטור בגין מענקים פטורים</td>
                <td>{es.get('total_impact', 0):,.0f} ₪</td>
            </tr>
            <tr class="secondary-row">
                <td>מענק עתידי משוריין (נומינלי)</td>
                <td>0 ₪</td>
            </tr>
            <tr class="secondary-row">
                <td>השפעת מענק עתידי (×1.35)</td>
                <td>0 ₪</td>
            </tr>
            <tr class="secondary-row">
                <td>סך היוונים</td>
                <td>0 ₪</td>
            </tr>
            <tr>
                <td>יתרת הון פטורה לאחר קיזוזים</td>
                <td class="green-text">{es.get('remaining_exempt_capital', 0):,.0f} ₪</td>
            </tr>
            <tr style="background-color: #fff3cd;">
                <td>תקרת קצבה מזכה</td>
                <td>{es.get('pension_ceiling', 0):,.0f} ₪</td>
            </tr>
            <tr class="highlight-row">
                <td>קצבה פטורה מחושבת</td>
                <td>{es.get('exempt_pension_monthly', 0):,.0f} ₪ ({es.get('exemption_percentage', 0) * 100:.1f}%)</td>
            </tr>
        </tbody>
    </table>
"""
    
    def _build_grants_table(self) -> str:
        """בניית טבלת מענקים"""
        grants_rows = ""
        for grant in self.grants_summary:
            grants_rows += f"""
            <tr>
                <td>{grant.get('employer_name', '')}</td>
                <td>{grant.get('grant_date_formatted', '')}</td>
                <td style="text-align: left;">{grant.get('amount', 0):,.0f} ₪</td>
                <td style="text-align: left;">{grant.get('relevant_amount', 0):,.0f} ₪</td>
                <td style="text-align: left;">{grant.get('indexed_amount', 0):,.0f} ₪</td>
                <td style="text-align: left;">{grant.get('impact_on_exemption', 0):,.0f} ₪</td>
            </tr>
"""
        
        return f"""
    <div style="page-break-before: always;"></div>
    
    <h2 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px;">פירוט מענקים</h2>
    
    <table>
        <thead>
            <tr>
                <th>שם מעסיק</th>
                <th>תאריך קבלת מענק</th>
                <th>מענק נומינאלי</th>
                <th>סכום רלוונטי</th>
                <th>לאחר הצמדה</th>
                <th>פגיעה בפטור</th>
            </tr>
        </thead>
        <tbody>
{grants_rows}
        </tbody>
    </table>
"""
    
    def _build_footer(self) -> str:
        """בניית כותרת תחתונה"""
        return f"""
    <div class="footer">
        <p>מסמך זה הופק אוטומטית ממערכת ניהול פנסיה</p>
        <p>תאריך הפקה: {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
    </div>
"""
    
    def render(self) -> str:
        """
        מייצר את ה-HTML המלא
        
        Returns:
            מחרוזת HTML
        """
        return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>טופס קיבוע זכויות - {self.client_name}</title>
    <style>
{get_fixation_styles()}
    </style>
</head>
<body>
{self._build_header()}
{self._build_client_info()}
{self._build_summary_table()}
{self._build_grants_table()}
{self._build_footer()}
</body>
</html>
"""
