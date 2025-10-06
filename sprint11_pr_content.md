# Sprint11 closure: Fix PDF generation & yearly totals — commit sprint11-closure-20250908-164627

## סגירת ספרינט 11

### מידע כללי
- **Commit SHA:** sprint11-closure-20250908-164627
- **Canonical Run Timestamp:** 20250909_092911
- **תיאור:** תיקוני PDF contract, Decimal precision, defensive handling scenario_id(s)

### תיקונים עיקריים
1. **תיקון משתנים לא מוגדרים ב-report_service.py**: הוספת זיהוי case עם טיפול fallback בפונקציית build_summary_table
2. **נורמליזציה של PDF contract handling**: עדכון contract adapter עם נורמליזציה וטיפול בעדיפויות (scenario_id מ-path → scenario_ids מ-body → scenarios מ-body)
3. **שיפור חישוב yearly totals**: מימוש Decimal precision לכל החישובים הפיננסיים עם עיגול נכון ל-2 ספרות אחרי הנקודה
4. **הוספת logging ו-error handling**: שיפור טיפול בשגיאות לאורך תהליך יצירת ה-PDF

### קבצים מצורפים
- artifacts/yearly_totals_verification_20250909_092911.zip
- artifacts/zip_sha256_20250909_092911.txt

### תוצאות אימות
- ✓ Months Count: 12/12
- ✓ PDF Generation: תקין, גודל 76,869 בייט
- ✓ Yearly Totals: הפרש 0.00 (≤0.01)
- ✓ API Health: תקין

### בקשת QA
אנא בדקו את הנקודות הבאות:
- פתחו את קובץ ה-PDF פיזית (test_20250909_092911.pdf)
- אמתו: Months: 12/12
- אמתו: |sum(monthly.net) - yearly.net| ≤ 0.01
- אנא השתמשו בתבנית QA signoff להלן

## תבנית QA Signoff
```
QA signoff:
Name: <QA_NAME>
Time: <ISO_TIMESTAMP>
Commit: sprint11-closure-20250908-164627
Checks:
- PDF opens and is a real PDF: YES / NO
- Months: 12/12: YES / NO
- sum(monthly.net) == yearly_totals['2025'].net (diff = <value>): PASS / FAIL
- ZIP present and SHA256 matches: YES / NO
Verdict: APPROVED / REJECTED
Comments: <אם יש>
```
