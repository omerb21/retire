from datetime import date

def calc_seniority_years(start: date, end: date) -> float:
    if end < start:
        raise ValueError("׳×׳׳¨׳™׳ ׳¡׳™׳•׳ ׳׳₪׳ ׳™ ׳×׳—׳™׳׳× ׳¢׳‘׳•׳“׳”")
    # ׳—׳™׳©׳•׳‘ ׳₪׳©׳˜׳ ׳™: ׳©׳ ׳™׳ + ׳—׳׳§ ׳™׳—׳¡׳™ ׳©׳ ׳—׳•׳“׳©׳™׳/׳™׳׳™׳
    days = (end - start).days
    return round(days / 365.0, 4)

