# בקשת QA Signoff לסגירת ספרינט 11

שלום צוות QA,

אנו מבקשים את אישורכם לסגירת ספרינט 11. בוצעה ריצה קנונית אחת רציפה תחת commit SHA קבוע שיצרה את כל ה-artifacts המאומתים.

## פרטי הריצה הקנונית
- **Commit SHA:** sprint11-closure-20250908-164627
- **Timestamp:** 20250909_092911
- **תיקונים עיקריים:** PDF contract, Decimal precision, defensive handling scenario_id(s)

## קבצים לבדיקה
- **PDF:** artifacts/test_20250909_092911.pdf
- **ZIP:** artifacts/yearly_totals_verification_20250909_092911.zip
- **SHA256:** artifacts/zip_sha256_20250909_092911.txt

## נקודות לאימות
1. **PDF תקין:** פתחו את קובץ ה-PDF פיזית וודאו שהוא נפתח כראוי
2. **12 חודשים:** בדקו שיש 12 חודשים בתוצאות ה-compare
3. **עקביות נתונים:** אמתו שההפרש בין sum(monthly.net) לבין yearly.net הוא ≤ 0.01
4. **ZIP ו-SHA256:** ודאו שקובץ ה-ZIP קיים וחתימת ה-SHA256 תואמת

## תבנית אישור QA
אנא השתמשו בתבנית הבאה לאישור:

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

תודה,
צוות הפיתוח
