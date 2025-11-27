"""
תבנית HTML לטבלת סיכום קיבוע זכויות
"""
from typing import Dict, Any, List
from datetime import date
from .styles import get_summary_styles


class SummaryHTMLTemplate:
    """תבנית HTML לטבלת סיכום"""
    
    def __init__(
        self,
        client_name: str,
        client_id_number: str,
        exemption_summary: Dict[str, Any],
        grants: List[Dict[str, Any]]
    ):
        self.client_name = client_name
        self.client_id_number = client_id_number
        self.exemption_summary = exemption_summary
        self.grants = grants
    
    def _calculate_values(self) -> Dict[str, float]:
        """חישוב כל הערכים לטבלה"""
        exempt_capital_initial = self.exemption_summary.get('exempt_capital_initial', 0)
        total_impact = self.exemption_summary.get('total_impact', 0)
        remaining_exempt_capital = self.exemption_summary.get('remaining_exempt_capital', 0)
        exempt_pension = remaining_exempt_capital / 180 if remaining_exempt_capital > 0 else 0
        
        grants_nominal = sum(g.get('grant_amount', 0) for g in self.grants)
        grants_indexed = sum(g.get('limited_indexed_amount', 0) for g in self.grants)
        future_grant_reserved = self.exemption_summary.get('future_grant_reserved', 0)
        future_grant_impact = self.exemption_summary.get('future_grant_impact', 0)
        total_commutations = self.exemption_summary.get('total_commutations', 0)
        idf_security_forces_impact = self.exemption_summary.get('idf_security_forces_impact', 0)
        pension_ceiling = 9430
        exemption_percentage = (exempt_pension / pension_ceiling * 100) if pension_ceiling > 0 else 0
        
        return {
            'exempt_capital_initial': exempt_capital_initial,
            'grants_nominal': grants_nominal,
            'grants_indexed': grants_indexed,
            'total_impact': total_impact,
            'future_grant_reserved': future_grant_reserved,
            'future_grant_impact': future_grant_impact,
            'total_commutations': total_commutations,
            'idf_security_forces_impact': idf_security_forces_impact,
            'remaining_exempt_capital': remaining_exempt_capital,
            'pension_ceiling': pension_ceiling,
            'exempt_pension': exempt_pension,
            'exemption_percentage': exemption_percentage
        }
    
    def _build_header(self) -> str:
        """בניית כותרת"""
        return f"""
    <h1>טבלת סיכום - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {self.client_name}</p>
        <p><strong>תעודת זהות:</strong> {self.client_id_number}</p>
        <p><strong>תאריך:</strong> {date.today().strftime('%d/%m/%Y')}</p>
    </div>
"""
    
    def _build_table(self) -> str:
        """בניית טבלת סיכום"""
        values = self._calculate_values()
        
        return f"""
    <table>
        <thead>
            <tr>
                <th>פרט</th>
                <th>סכום (₪)</th>
            </tr>
        </thead>
        <tbody>
            <tr style="background-color: #d1ecf1;">
                <td style="font-weight: bold;">יתרת הון פטורה לשנת הזכאות</td>
                <td style="font-weight: bold;">{values['exempt_capital_initial']:,.2f}</td>
            </tr>
            <tr>
                <td>סך נומינאלי של מענקי הפרישה</td>
                <td>{values['grants_nominal']:,.2f}</td>
            </tr>
            <tr>
                <td>סך המענקים הרלוונטים לאחר הוצמדה</td>
                <td>{values['grants_indexed']:,.2f}</td>
            </tr>
            <tr>
                <td>סך הכל פגיעה בפטור בגין מענקים פטורים</td>
                <td>{values['total_impact']:,.2f}</td>
            </tr>
            <tr>
                <td>פגיעה בפטור בגלל היוון צה"ל</td>
                <td>{values['idf_security_forces_impact']:,.2f}</td>
            </tr>
            <tr style="background-color: #f8f9fa; color: #6c757d;">
                <td>מענק עתידי משוריין (נומינלי)</td>
                <td>{values['future_grant_reserved']:,.2f}</td>
            </tr>
            <tr style="background-color: #f8f9fa; color: #6c757d;">
                <td>השפעת מענק עתידי (×1.35)</td>
                <td>{values['future_grant_impact']:,.2f}</td>
            </tr>
            <tr style="background-color: #f8f9fa; color: #6c757d;">
                <td>סך היוונים</td>
                <td>{values['total_commutations']:,.2f}</td>
            </tr>
            <tr>
                <td style="font-weight: 500;">יתרת הון פטורה לאחר קיזוזים</td>
                <td style="color: #28a745;">{values['remaining_exempt_capital']:,.2f}</td>
            </tr>
            <tr style="background-color: #fff3cd;">
                <td>תקרת קצבה מזכה</td>
                <td>{values['pension_ceiling']:,.2f}</td>
            </tr>
            <tr style="background-color: #d4edda;">
                <td style="font-weight: bold;">קצבה פטורה מחושבת</td>
                <td style="font-weight: bold;">{values['exempt_pension']:,.2f} ₪ ({values['exemption_percentage']:.1f}%)</td>
            </tr>
        </tbody>
    </table>
"""
    
    def render(self) -> str:
        """מייצר את ה-HTML המלא"""
        return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>טבלת סיכום קיבוע זכויות</title>
    <style>
{get_summary_styles()}
    </style>
</head>
<body>
{self._build_header()}
{self._build_table()}
</body>
</html>
"""
