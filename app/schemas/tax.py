from datetime import date
from typing import Dict, List, Tuple
from pydantic import BaseModel, Field

class TaxBracket(BaseModel):
    up_to: float | None  # None = ללא תקרה
    rate: float          # 0..1

class TaxParameters(BaseModel):
    # CPI: מיפוי YYYY-MM-01 -> ערך מדד (מספר בסיסי), חייב לכלול את טווח החישוב
    cpi_series: Dict[date, float] = Field(default_factory=dict)
    # מענקים: תקרת פטור, מדרגות מס למרכיב החייב (דוגמה פשטנית)
    grant_exemption_cap: float = 0.0
    grant_tax_brackets: List[TaxBracket] = Field(default_factory=list)
    # קצבאות: מקדם המרה היפותטי (פשטני לשלב זה)
    annuity_factor: float = 200.0  # הון / 200 = פנסיה חודשית משוערת
