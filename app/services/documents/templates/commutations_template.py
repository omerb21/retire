"""
תבנית HTML לנספח היוונים
"""
from typing import List
import re
from .styles import get_commutations_styles
from app.models.capital_asset import CapitalAsset


class CommutationsHTMLTemplate:
    """תבנית HTML לנספח היוונים"""
    
    def __init__(
        self,
        client_name: str,
        client_id_number: str,
        commutations: List[CapitalAsset]
    ):
        self.client_name = client_name
        self.client_id_number = client_id_number
        self.commutations = commutations
    
    def _build_header(self) -> str:
        """בניית כותרת"""
        return f"""
    <h1>נספח היוונים - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {self.client_name}</p>
        <p><strong>תעודת זהות:</strong> {self.client_id_number}</p>
    </div>
"""
    
    def _build_table(self) -> str:
        """בניית טבלת היוונים"""
        rows = ""
        total_amount = 0
        
        for comm in self.commutations:
            amount_match = re.search(r'amount=([\d.]+)', comm.remarks or '')
            amount = float(amount_match.group(1)) if amount_match else (comm.current_value or 0)
            
            fund_name = comm.asset_name or comm.description or 'לא ידוע'
            start_date = comm.start_date.strftime("%d/%m/%Y") if comm.start_date else ""
            tax_treatment = "פטור ממס" if comm.tax_treatment == "exempt" else "חייב במס"
            
            rows += f"""
            <tr>
                <td>{fund_name}</td>
                <td>-</td>
                <td>{start_date}</td>
                <td>{amount:,.2f}</td>
                <td>{tax_treatment}</td>
            </tr>
"""
            total_amount += amount
        
        return f"""
    <table>
        <thead>
            <tr>
                <th>שם המשלם</th>
                <th>תיק ניכויים</th>
                <th>תאריך היוון</th>
                <th>סכום היוון</th>
                <th>סוג ההיוון</th>
            </tr>
        </thead>
        <tbody>
{rows}
            <tr class="total-row">
                <td colspan="3">סה"כ</td>
                <td>{total_amount:,.2f}</td>
                <td></td>
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
    <title>נספח היוונים</title>
    <style>
{get_commutations_styles()}
    </style>
</head>
<body>
{self._build_header()}
{self._build_table()}
</body>
</html>
"""
