"""
תבנית HTML לנספח מענקים
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from .styles import get_grants_styles


class GrantsHTMLTemplate:
    """תבנית HTML לנספח מענקים"""
    
    def __init__(
        self,
        client_name: str,
        client_id_number: str,
        eligibility_date: Optional[str],
        grants_summary: List[Dict[str, Any]],
        grants_dates_map: Dict[str, Dict[str, str]]
    ):
        self.client_name = client_name
        self.client_id_number = client_id_number
        self.eligibility_date = eligibility_date
        self.grants_summary = grants_summary
        self.grants_dates_map = grants_dates_map
    
    def _build_header(self) -> str:
        """בניית כותרת"""
        eligibility_str = self.eligibility_date if self.eligibility_date else "לא ידוע"
        if self.eligibility_date and isinstance(self.eligibility_date, datetime):
            eligibility_str = self.eligibility_date.strftime("%d/%m/%Y")
        
        return f"""
    <h1>נספח מענקים - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {self.client_name}</p>
        <p><strong>תעודת זהות:</strong> {self.client_id_number}</p>
        <p><strong>תאריך זכאות:</strong> {eligibility_str}</p>
    </div>
"""
    
    def _build_table(self) -> str:
        """בניית טבלת מענקים"""
        rows = ""
        total_nominal = 0
        total_relevant_nominal = 0
        total_indexed = 0
        total_impact = 0
        
        for grant in self.grants_summary:
            employer_name = grant.get('employer_name', '')
            grant_date = grant.get('grant_date', '')
            nominal = grant.get('grant_amount', 0)
            relevant_nominal = grant.get('grant_amount', 0)
            indexed = grant.get('limited_indexed_amount', 0)
            impact = grant.get('impact_on_exemption', 0)
            
            dates_info = self.grants_dates_map.get(employer_name, {})
            work_start = dates_info.get('work_start_date', '-')
            work_end = dates_info.get('work_end_date', '-')
            
            rows += f"""
            <tr>
                <td>{employer_name}</td>
                <td>{work_start}</td>
                <td>{work_end}</td>
                <td>{nominal:,.0f}</td>
                <td>{grant_date}</td>
                <td>{relevant_nominal:,.0f}</td>
                <td>{indexed:,.0f}</td>
                <td>{impact:,.0f}</td>
            </tr>
"""
            total_nominal += nominal
            total_relevant_nominal += relevant_nominal
            total_indexed += indexed
            total_impact += impact
        
        return f"""
    <table>
        <thead>
            <tr>
                <th>מעסיק</th>
                <th>תאריך תחילה</th>
                <th>תאריך סיום</th>
                <th>סכום נומינלי</th>
                <th>תאריך קבלה</th>
                <th>מענק נומינלי רלוונטי</th>
                <th>מענק פטור צמוד</th>
                <th>השפעה על הפטור</th>
            </tr>
        </thead>
        <tbody>
{rows}
            <tr class="total-row">
                <td colspan="3">סה"כ</td>
                <td>{total_nominal:,.2f}</td>
                <td></td>
                <td>{total_relevant_nominal:,.2f}</td>
                <td>{total_indexed:,.2f}</td>
                <td>{total_impact:,.2f}</td>
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
    <title>נספח מענקים</title>
    <style>
{get_grants_styles()}
    </style>
</head>
<body>
{self._build_header()}
{self._build_table()}
</body>
</html>
"""
