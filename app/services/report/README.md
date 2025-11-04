# Report Generation Module

מודול מודולרי ליצירת דוחות PDF עם תמיכה בעברית, גרפים, ונתונים פיננסיים מקיפים.

## 📁 מבנה המודול

```
app/services/report/
├── __init__.py                 # ייצוא ממשקים ציבוריים
├── config.py                   # הגדרות וקבועים
├── README.md                   # תיעוד זה
├── fonts/                      # ניהול פונטים
│   ├── __init__.py
│   └── font_manager.py        # FontManager class
├── utils/                      # כלי עזר
│   ├── __init__.py
│   ├── styles.py              # PDFStyles - סגנונות PDF
│   └── formatters.py          # DataFormatters - פורמט נתונים
├── charts/                     # יצירת גרפים
│   ├── __init__.py
│   ├── cashflow_chart.py      # CashflowChartRenderer
│   └── scenarios_chart.py     # ScenariosChartRenderer
├── builders/                   # בניית רכיבי דוח (להרחבה עתידית)
│   └── __init__.py
└── generators/                 # יצירת דוחות (להרחבה עתידית)
    └── __init__.py
```

## 🚀 שימוש

### ייבוא בסיסי

```python
from app.services.report import (
    FontManager,
    ensure_fonts,
    PDFStyles,
    DataFormatters,
    CashflowChartRenderer,
    ScenariosChartRenderer
)
```

### שימוש ב-FontManager

```python
# אתחול פונטים
FontManager.ensure_fonts()

# קבלת פונט ברירת מחדל
font_name = FontManager.get_default_font()

# רישום פונט ידני
FontManager.register_font_once("MyFont", "/path/to/font.ttf")
```

### שימוש ב-PDFStyles

```python
# קבלת סגנונות
styles = PDFStyles.get_all_styles()
hebrew_style = styles['hebrew']
title_style = styles['title']

# או סגנון ספציפי
section_style = PDFStyles.get_section_style()
table_style = PDFStyles.get_table_style()
```

### שימוש ב-DataFormatters

```python
# פורמט מטבע
formatted = DataFormatters.format_currency(1234567.89)  # "1,234,568 ₪"

# פורמט תאריך
formatted_date = DataFormatters.format_date(datetime.now())  # "04/11/2025"

# פורמט אחוזים
percentage = DataFormatters.format_percentage(0.15)  # "15.0%"

# Parse JSON בטוח
data = DataFormatters.parse_json_safely(json_string)
```

### שימוש ב-Charts

```python
# יצירת גרף תזרים מזומנים
cashflow_data = {'annual_cashflow': [...]}
chart_bytes = CashflowChartRenderer.render_cashflow_chart(cashflow_data)

# יצירת גרף השוואת תרחישים
scenarios = [scenario1, scenario2, scenario3]
comparison_bytes = ScenariosChartRenderer.render_scenarios_compare_chart(scenarios)

# יצירת גרף תזרים נטו חודשי
chart_data = {'dates': [...], 'values': [...]}
net_chart_bytes = CashflowChartRenderer.create_net_cashflow_chart(chart_data)
```

## 🔧 תאימות לאחור

הקובץ המקורי `report_service.py` ממשיך לעבוד בדיוק כמו קודם. כל הפונקציות והמחלקות הקיימות נשמרו:

```python
from app.services.report_service import (
    ReportService,
    ensure_fonts,
    generate_report_pdf,
    create_pdf_with_cashflow
)

# הכל עובד כמו קודם!
service = ReportService()
pdf_bytes = generate_report_pdf(db, client_id, scenario_id)
```

## 📝 הגדרות (config.py)

### פונטים
- `DEFAULT_HEBREW_FONT`: "DejaVu Sans"
- `FONT_ALIAS`: "HebrewUI"

### עמוד
- `DEFAULT_PAGE_SIZE`: A4
- `DEFAULT_MARGINS`: מרווחים סטנדרטיים

### גרפים
- `CHART_COLORS`: צבעים מוגדרים מראש
- `CHART_FIGURE_SIZE`: (12, 6)
- `CHART_DPI`: 100

## 🎨 סגנונות זמינים

### PDFStyles
- `get_hebrew_style()` - סגנון בסיסי לעברית עם RTL
- `get_title_style()` - כותרות
- `get_section_style()` - כותרות סקציות
- `get_body_style()` - טקסט גוף
- `get_footer_style()` - כותרת תחתונה
- `get_table_style()` - טבלאות

## 🔄 הרחבה עתידית

המבנה המודולרי מאפשר הרחבה קלה:

### הוספת גרפים חדשים
```python
# app/services/report/charts/my_chart.py
class MyChartRenderer:
    @staticmethod
    def render_my_chart(data: Dict) -> bytes:
        # יצירת גרף
        pass
```

### הוספת builders חדשים
```python
# app/services/report/builders/my_builder.py
class MyBuilder:
    @staticmethod
    def build_my_section(data: Dict) -> List:
        # בניית סקציה
        pass
```

## ⚠️ הערות חשובות

1. **אתחול פונטים**: יש לקרוא ל-`ensure_fonts()` לפני יצירת PDF או גרפים
2. **תאימות לאחור**: כל הקוד הקיים ממשיך לעבוד ללא שינויים
3. **מודולריות**: כל רכיב עצמאי וניתן לבדיקה בנפרד
4. **הרחבה**: קל להוסיף פונקציונליות חדשה

## 📚 תיעוד נוסף

לתיעוד מפורט של כל מחלקה ופונקציה, ראה את ה-docstrings בקוד.

## 🐛 דיבאג

אם יש בעיות עם פונטים:
```python
import logging
logging.getLogger("app.services.report").setLevel(logging.DEBUG)
```

## ✅ בדיקות

```python
# בדיקה בסיסית
from app.services.report import FontManager, PDFStyles

# בדוק שהפונטים עובדים
FontManager.ensure_fonts()
font = FontManager.get_default_font()
print(f"Using font: {font}")

# בדוק שהסגנונות עובדים
styles = PDFStyles.get_all_styles()
print(f"Available styles: {list(styles.keys())}")
```

---

**גרסה**: 1.5.0 (Core Components Refactored)  
**תאריך**: 4 נובמבר 2025  
**סטטוס**: ✅ פעיל - תאימות לאחור מלאה

### רכיבים שפוצלו:
✅ Font Management (FontManager)  
✅ PDF Styles (PDFStyles)  
✅ Data Formatters (DataFormatters)  
✅ Cashflow Charts (CashflowChartRenderer)  
✅ Scenarios Charts (ScenariosChartRenderer)

### רכיבים שנותרו ב-report_service.py:
- ReportService.build_summary_table()
- ReportService.compose_pdf()
- generate_report_pdf()
- create_pdf_with_cashflow()

**הערה**: ניתן להמשיך בפיצול הרכיבים הנותרים בעתיד ללא פגיעה בתפקוד.
