"""
בדיקת לוגיקת חישוב יחסי מענקים עם הגבלה לגיל פרישה
"""
from datetime import date
from app.services.rights_fixation import work_ratio_within_last_32y

# דוגמה 1: גבר שעבד מגיל 60 עד 70 (גיל פרישה 67)
print("=" * 80)
print("דוגמה 1: גבר שעבד מגיל 60 עד 70")
print("=" * 80)

# נניח שהוא נולד ב-1960, אז:
# גיל 60 = 2020
# גיל 67 = 2027 (גיל פרישה)
# גיל 70 = 2030

birth_date_male = date(1960, 1, 1)
start_date_male = date(2020, 1, 1)  # גיל 60
end_date_male = date(2030, 1, 1)    # גיל 70
elig_date_male = date(2030, 1, 1)   # תאריך זכאות

ratio_male = work_ratio_within_last_32y(
    start_date=start_date_male,
    end_date=end_date_male,
    elig_date=elig_date_male,
    birth_date=birth_date_male,
    gender='male'
)

print(f"תאריך לידה: {birth_date_male}")
print(f"תקופת עבודה: {start_date_male} עד {end_date_male} (10 שנים)")
print(f"גיל פרישה צפוי: 67 (2027)")
print(f"יחס מחושב: {ratio_male:.4f}")
print(f"תקופה רלוונטית: 7 שנים (מגיל 60 עד 67)")
print(f"יחס צפוי: 0.7000 (7/10)")
print(f"התאמה: {'✓' if abs(ratio_male - 0.7) < 0.01 else '✗'}")

# דוגמה 2: אישה שעבדה מגיל 60 עד 70 (גיל פרישה 65)
print("\n" + "=" * 80)
print("דוגמה 2: אישה שעבדה מגיל 60 עד 70")
print("=" * 80)

# נניח שהיא נולדה ב-1975, אז:
# גיל 60 = 2035
# גיל 65 = 2040 (גיל פרישה)
# גיל 70 = 2045

birth_date_female = date(1975, 1, 1)
start_date_female = date(2035, 1, 1)  # גיל 60
end_date_female = date(2045, 1, 1)    # גיל 70
elig_date_female = date(2045, 1, 1)   # תאריך זכאות

ratio_female = work_ratio_within_last_32y(
    start_date=start_date_female,
    end_date=end_date_female,
    elig_date=elig_date_female,
    birth_date=birth_date_female,
    gender='female'
)

print(f"תאריך לידה: {birth_date_female}")
print(f"תקופת עבודה: {start_date_female} עד {end_date_female} (10 שנים)")
print(f"גיל פרישה צפוי: 65 (2040)")
print(f"יחס מחושב: {ratio_female:.4f}")
print(f"תקופה רלוונטית: 5 שנים (מגיל 60 עד 65)")
print(f"יחס צפוי: 0.5000 (5/10)")
print(f"התאמה: {'✓' if abs(ratio_female - 0.5) < 0.01 else '✗'}")

# דוגמה 3: עבודה לפני גיל פרישה (לא צריך להגביל)
print("\n" + "=" * 80)
print("דוגמה 3: עבודה שהסתיימה לפני גיל פרישה")
print("=" * 80)

start_date_before = date(2010, 1, 1)
end_date_before = date(2020, 1, 1)  # הסתיים בגיל 60
elig_date_before = date(2030, 1, 1)

ratio_before = work_ratio_within_last_32y(
    start_date=start_date_before,
    end_date=end_date_before,
    elig_date=elig_date_before,
    birth_date=birth_date_male,
    gender='male'
)

print(f"תקופת עבודה: {start_date_before} עד {end_date_before}")
print(f"העבודה הסתיימה לפני גיל פרישה (67)")
print(f"יחס מחושב: {ratio_before:.4f}")
print(f"יחס צפוי: 1.0000 (כל התקופה נכללת)")
print(f"התאמה: {'✓' if abs(ratio_before - 1.0) < 0.01 else '✗'}")

print("\n" + "=" * 80)
print("סיכום הבדיקות")
print("=" * 80)
print("הלוגיקה החדשה מתחשבת בגיל הפרישה ומגבילה את החישוב היחסי בהתאם!")
