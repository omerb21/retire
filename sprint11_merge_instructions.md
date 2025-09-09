# הוראות Merge לאחר אישור QA

לאחר קבלת אישור QA ו-CI ירוק, יש לבצע את הצעדים הבאים:

## 1. Merge ל-main
```bash
git checkout main
git pull
git merge sprint11-closure-20250908-164627
git push origin main
```

## 2. יצירת Tag
```bash
git tag -a sprint11-closed-20250909 -m "Sprint 11 closure - 2025-09-09"
git push origin sprint11-closed-20250909
```

## 3. אימות סופי
- ודא שה-tag נוצר בהצלחה בגיטהאב
- ודא שה-CI עובר על ה-main
- עדכן את צוות הפיתוח והמנהלים על סגירת הספרינט

## 4. סיכום
- Sprint 11 נסגר רשמית
- כל ה-artifacts נשמרו בתיקיית `artifacts`
- התיקונים העיקריים:
  - תיקון PDF generation
  - שיפור Decimal precision
  - הוספת defensive handling ל-scenario_id(s)
  - שיפור error handling
