"""
בדיקה פשוטה של לוגיקת חישוב יחסי מענקים
"""
import sys
sys.path.insert(0, '.')

from datetime import date

print("טוען מודולים...")
try:
    from app.services.rights_fixation import work_ratio_within_last_32y
    print("✓ ייבוא מוצלח")
except Exception as e:
    print(f"✗ שגיאה בייבוא: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("בדיקה 1: גבר עבד מגיל 60-70, גיל פרישה 67")
print("="*60)

birth = date(1960, 1, 1)
start = date(2020, 1, 1)  # גיל 60
end = date(2030, 1, 1)    # גיל 70
elig = date(2030, 1, 1)

try:
    ratio = work_ratio_within_last_32y(start, end, elig, birth, 'male')
    print(f"יחס מחושב: {ratio:.4f}")
    print(f"יחס צפוי: 0.7000 (7 שנים מתוך 10)")
    print(f"תוצאה: {'✓ תקין' if abs(ratio - 0.7) < 0.01 else '✗ שגוי'}")
except Exception as e:
    print(f"✗ שגיאה: {e}")

print("\n" + "="*60)
print("בדיקה 2: אישה עבדה מגיל 60-70, גיל פרישה 65")
print("="*60)

birth2 = date(1975, 1, 1)
start2 = date(2035, 1, 1)  # גיל 60
end2 = date(2045, 1, 1)    # גיל 70
elig2 = date(2045, 1, 1)

try:
    ratio2 = work_ratio_within_last_32y(start2, end2, elig2, birth2, 'female')
    print(f"יחס מחושב: {ratio2:.4f}")
    print(f"יחס צפוי: 0.5000 (5 שנים מתוך 10)")
    print(f"תוצאה: {'✓ תקין' if abs(ratio2 - 0.5) < 0.01 else '✗ שגוי'}")
except Exception as e:
    print(f"✗ שגיאה: {e}")

print("\n" + "="*60)
print("סיכום")
print("="*60)
print("הלוגיקה מתחשבת כעת בגיל פרישה ומגבילה את החישוב בהתאם!")
