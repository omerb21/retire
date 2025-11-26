# תיעוד פיצול report_service.py

## תאריך: 06.11.2025

## מטרה
פיצול הקובץ המונוליתי `report_service.py` (1014 שורות) למבנה מודולרי מאורגן.

## מבנה חדש

```
app/services/report/
├── __init__.py                    # ייצוא כל הפונקציות הציבוריות
├── base.py                        # מחלקת ReportService הראשית
├── config.py                      # הגדרות קבועות
├── models/                        # מודלי נתונים
│   ├── __init__.py
│   ├── report_data.py            # מודלים לנתוני דוח
│   └── chart_data.py             # מודלים לנתוני גרפים
├── services/                      # שירותים פנימיים
│   ├── __init__.py
│   ├── data_service.py           # אחזור ועיבוד נתונים
│   └── pdf_service.py            # יצירת PDF
├── generators/                    # פונקציות יצירה ברמה גבוהה
│   ├── __init__.py
│   └── report_generator.py       # generate_report_pdf
├── charts/                        # יצירת גרפים
│   ├── __init__.py
│   ├── cashflow_chart.py
│   └── scenarios_chart.py
├── fonts/                         # ניהול פונטים
│   ├── __init__.py
│   └── font_manager.py
└── utils/                         # כלי עזר
    ├── __init__.py
    ├── formatters.py
    └── styles.py
```

## קבצים שנוצרו

### 1. models/
- **report_data.py** - מודלי Pydantic לנתוני דוח (ClientInfo, EmploymentInfo, ScenarioSummary, etc.)
- **chart_data.py** - מודלים לנתוני גרפים (ChartData, SeriesData)

### 2. services/
- **data_service.py** - `DataService.build_summary_table()` - אחזור ועיבוד נתוני דוח
- **pdf_service.py** - `PDFService.create_pdf_with_cashflow()` - יצירת PDF עם תזרים מזומנים

### 3. generators/
- **report_generator.py** - `generate_report_pdf()` - פונקציה ראשית ליצירת PDF

### 4. base.py
- **ReportService** - מחלקה ראשית עם תאימות לאחור מלאה
  - `build_summary_table()`
  - `render_cashflow_chart()`
  - `render_scenarios_compare_chart()`
  - `generate_pdf_report()`
  - `compose_pdf()`

## שינויים בקובץ המקורי

הקובץ `app/services/report_service.py` הוחלף ב-**wrapper** שמייבא מהמודולים החדשים:

```python
from app.services.report import (
    ReportService,
    generate_report_pdf,
    ensure_fonts,
    # ... כל הפונקציות הציבוריות
)
```

## תאימות לאחור

✅ **100% תאימות לאחור** - כל הקוד הקיים ממשיך לעבוד ללא שינויים:

```python
# עובד בדיוק כמו קודם!
from app.services.report_service import ReportService, generate_report_pdf
```

## קבצים שנבדקו

✅ `app/routers/reports.py` - משתמש ב-`ReportService.generate_pdf_report()`
✅ `app/utils/contract_adapter.py` - משתמש ב-`generate_report_pdf()`
✅ כל הייבואים עובדים ללא שגיאות

## יתרונות הפיצול

1. **קריאות** - כל קובץ אחראי על תחום אחד
2. **תחזוקה** - קל יותר למצוא ולתקן באגים
3. **הרחבה** - קל להוסיף פונקציונליות חדשה
4. **בדיקות** - ניתן לבדוק כל מודול בנפרד
5. **שימוש חוזר** - קומפוננטות ניתנות לשימוש חוזר

## גיבוי

הקובץ המקורי נשמר ב:
`app/services/report_service.py.backup`

## בדיקות שבוצעו

✅ ייבוא מודולים
✅ טעינת FastAPI app
✅ טעינת reports router
✅ טעינת contract_adapter
✅ כל הפונקציות הציבוריות זמינות

## סיכום

הפיצול הושלם בהצלחה! המערכת עוברת להשתמש במבנה המודולרי החדש תוך שמירה על תאימות לאחור מלאה.
