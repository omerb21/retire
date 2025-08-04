from datetime import date

def calc_seniority_years(start: date, end: date) -> float:
    if end < start:
        raise ValueError("תאריך סיום לפני תחילת עבודה")
    # חישוב פשטני: שנים + חלק יחסי של חודשים/ימים
    days = (end - start).days
    return round(days / 365.0, 4)
