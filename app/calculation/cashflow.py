from datetime import date
from typing import List
from app.schemas.scenario import CashflowPoint

def make_simple_cashflow(start: date, months: int, income: float, expense: float) -> List[CashflowPoint]:
    # ׳‘׳ ׳™׳™׳× ׳¡׳“׳¨׳× ׳×׳–׳¨׳™׳ ׳—׳•׳“׳©׳™׳× ׳₪׳©׳˜׳ ׳™׳×
    pts: List[CashflowPoint] = []
    y, m = start.year, start.month
    for _ in range(months):
        d = date(y, m, 1)
        net = round(income - expense, 2)
        pts.append(CashflowPoint(date=d, inflow=income, outflow=expense, net=net))
        m += 1
        if m > 12: m = 1; y += 1
    return pts

