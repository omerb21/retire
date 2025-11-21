from datetime import date
from typing import Dict, List, Tuple
from pydantic import BaseModel, Field

class TaxBracket(BaseModel):
    up_to: float | None  # None = ׳׳׳ ׳×׳§׳¨׳”
    rate: float          # 0..1

class TaxParameters(BaseModel):
    # CPI: ׳׳™׳₪׳•׳™ YYYY-MM-01 -> ׳¢׳¨׳ ׳׳“׳“ (׳׳¡׳₪׳¨ ׳‘׳¡׳™׳¡׳™), ׳—׳™׳™׳‘ ׳׳›׳׳•׳ ׳׳× ׳˜׳•׳•׳— ׳”׳—׳™׳©׳•׳‘
    cpi_series: Dict[date, float] = Field(default_factory=dict)
    # ׳׳¢׳ ׳§׳™׳: ׳×׳§׳¨׳× ׳₪׳˜׳•׳¨, ׳׳“׳¨׳’׳•׳× ׳׳¡ ׳׳׳¨׳›׳™׳‘ ׳”׳—׳™׳™׳‘ (׳“׳•׳’׳׳” ׳₪׳©׳˜׳ ׳™׳×)
    grant_exemption_cap: float = 0.0
    grant_tax_brackets: List[TaxBracket] = Field(default_factory=list)
    # מדרגות מס הכנסה כלליות לנכסי הון/הכנסות אחרות
    income_tax_brackets: List[TaxBracket] = Field(default_factory=list)
    # ׳§׳¦׳‘׳׳•׳×: ׳׳§׳“׳ ׳”׳׳¨׳” ׳”׳™׳₪׳•׳×׳˜׳™ (׳₪׳©׳˜׳ ׳™ ׳׳©׳׳‘ ׳–׳”)
    annuity_factor: float = 200.0  # ׳”׳•׳ / 200 = ׳₪׳ ׳¡׳™׳” ׳—׳•׳“׳©׳™׳× ׳׳©׳•׳¢׳¨׳×

