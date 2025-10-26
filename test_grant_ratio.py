"""בדיקה ישירה של חישוב היחס"""
import sys
sys.path.insert(0, '.')

from app.services.rights_fixation import work_ratio_within_last_32y
from datetime import date

# נתוני לקוח 6
birth_date = date(1951, 11, 19)
gender = "male"
work_start = date(2012, 1, 1)
work_end = date(2020, 1, 1)
eligibility_date = date(2025, 10, 9)  # תאריך החישוב, לא תאריך תחילת הקצבה

print("🔍 בדיקת חישוב יחס 32 שנים עם קיזוז גיל פרישה")
print(f"\nנתונים:")
print(f"  תאריך לידה: {birth_date}")
print(f"  מגדר: {gender}")
print(f"  עבודה: {work_start} עד {work_end}")
print(f"  תאריך זכאות: {eligibility_date}")

# חישוב גיל פרישה
from app.services.retirement_age_service import get_retirement_date
retirement_date = get_retirement_date(birth_date, gender)
print(f"\n📅 גיל פרישה מחושב: {retirement_date}")

# חישוב היחס
ratio = work_ratio_within_last_32y(
    start_date=work_start,
    end_date=work_end,
    elig_date=eligibility_date,
    birth_date=birth_date,
    gender=gender
)

print(f"\n📊 תוצאה:")
print(f"  יחס מחושב: {ratio:.4f} ({ratio * 100:.2f}%)")

# חישוב ידני
total_days = (work_end - work_start).days
effective_end = min(work_end, retirement_date)
limit_start = eligibility_date - __import__('datetime').timedelta(days=int(365.25 * 32))
overlap_start = max(work_start, limit_start)
overlap_end = min(effective_end, eligibility_date)
overlap_days = max((overlap_end - overlap_start).days, 0)

print(f"\n🧮 חישוב ידני:")
print(f"  סה\"כ ימי עבודה: {total_days:,} ({(total_days / 365.25):.2f} שנים)")
print(f"  תאריך סיום אפקטיבי (עד גיל פרישה): {effective_end}")
print(f"  חלון 32 שנים מתחיל: {limit_start}")
print(f"  חפיפה מתחילה: {overlap_start}")
print(f"  חפיפה מסתיימת: {overlap_end}")
print(f"  ימי חפיפה: {overlap_days:,} ({(overlap_days / 365.25):.2f} שנים)")
print(f"  יחס: {overlap_days} / {total_days} = {overlap_days / total_days:.4f}")

# בדיקה אם יש שנים מעל גיל פרישה
years_beyond_retirement = (work_end - retirement_date).days / 365.25 if work_end > retirement_date else 0
print(f"\n⚠️ שנים מעל גיל פרישה: {years_beyond_retirement:.2f}")

if years_beyond_retirement > 0:
    print(f"   ✅ צריך להיות קיזוז!")
    expected_ratio = overlap_days / total_days
    print(f"   יחס צפוי: {expected_ratio:.4f}")
    if abs(ratio - expected_ratio) < 0.0001:
        print(f"   ✅ החישוב נכון!")
    else:
        print(f"   ❌ החישוב שגוי! קיבלנו {ratio:.4f} במקום {expected_ratio:.4f}")
else:
    print(f"   אין שנים מעל גיל פרישה")

print("\n✅ בדיקה הושלמה")
