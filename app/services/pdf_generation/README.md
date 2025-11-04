# מודול יצירת PDFs - מבנה מודולרי

## סקירה כללית

מודול זה אחראי על יצירת מסמכי PDF במערכת, בעיקר טפסי קיבוע זכויות (161ד).
הקובץ המקורי `fixation_pdf_generator.py` (289 שורות) פוצל למבנה מודולרי ברור ונקי.

## מבנה התיקיות

```
app/services/pdf_generation/
├── __init__.py                          # ייצוא ראשי
├── README.md                            # תיעוד זה
│
├── converters/                          # המרת HTML ל-PDF
│   ├── __init__.py
│   └── html_to_pdf.py                   # המרה באמצעות wkhtmltopdf
│
├── templates/                           # תבניות HTML
│   ├── __init__.py
│   ├── styles.py                        # סגנונות CSS
│   └── fixation_template.py            # תבנית קיבוע זכויות
│
├── data_fetchers/                       # שליפת נתונים מ-DB
│   ├── __init__.py
│   └── fixation_data.py                 # שליפת נתוני קיבוע זכויות
│
└── generators/                          # יצירת PDFs
    ├── __init__.py
    └── fixation_generator.py            # יצירת PDF קיבוע זכויות
```

## שימוש בסיסי

### יצירת PDF קיבוע זכויות

```python
from pathlib import Path
from sqlalchemy.orm import Session
from app.services.pdf_generation import generate_fixation_summary_pdf

# יצירת PDF
pdf_path = generate_fixation_summary_pdf(
    db=db_session,
    client_id=123,
    output_dir=Path("./output")
)

if pdf_path:
    print(f"PDF נוצר בהצלחה: {pdf_path}")
else:
    print("יצירת PDF נכשלה")
```

### שימוש במודולים בנפרד

#### המרת HTML ל-PDF

```python
from pathlib import Path
from app.services.pdf_generation.converters import html_to_pdf

html_path = Path("document.html")
pdf_path = Path("document.pdf")

html_to_pdf(
    html_path=html_path,
    pdf_path=pdf_path,
    page_size='A4',
    margin_top='15mm'
)
```

#### יצירת תבנית HTML

```python
from app.services.pdf_generation.templates import FixationHTMLTemplate

template = FixationHTMLTemplate(
    client_name="ישראל ישראלי",
    client_id_number="123456789",
    exemption_summary={
        'exempt_capital_initial': 1000000,
        'grants_nominal': 50000,
        # ...
    },
    grants_summary=[
        {
            'employer_name': 'חברה א',
            'grant_date_formatted': '01/01/2020',
            'amount': 100000,
            # ...
        }
    ]
)

html_content = template.render()
```

#### שליפת נתונים

```python
from app.services.pdf_generation.data_fetchers import fetch_fixation_data

data = fetch_fixation_data(db=db_session, client_id=123)

if data:
    print(f"לקוח: {data.client.first_name} {data.client.last_name}")
    print(f"מספר מענקים: {len(data.grants_summary)}")
```

## רכיבים עיקריים

### 1. Converters - המרת HTML ל-PDF

**קובץ**: `converters/html_to_pdf.py`

מכיל:
- `find_wkhtmltopdf()` - מחפש את wkhtmltopdf במיקומים נפוצים
- `html_to_pdf()` - ממיר HTML ל-PDF עם פרמטרים מותאמים אישית

**דרישות**:
- wkhtmltopdf מותקן במערכת
- ניתן להוריד מ: https://wkhtmltopdf.org/downloads.html

### 2. Templates - תבניות HTML

**קובץ**: `templates/fixation_template.py`

מחלקה: `FixationHTMLTemplate`

מתודות:
- `_build_header()` - כותרת המסמך
- `_build_client_info()` - מידע לקוח
- `_build_summary_table()` - טבלת סיכום
- `_build_grants_table()` - טבלת מענקים
- `_build_footer()` - כותרת תחתונה
- `render()` - רינדור HTML מלא

**סגנונות**: `templates/styles.py`
- סגנונות CSS מרוכזים במקום אחד
- קל לשינוי ועדכון

### 3. Data Fetchers - שליפת נתונים

**קובץ**: `data_fetchers/fixation_data.py`

מכיל:
- `FixationData` - dataclass למבנה נתונים
- `fetch_fixation_data()` - שליפה מ-DB

שולף:
- פרטי לקוח
- תוצאות קיבוע זכויות אחרונות
- סיכום פטור
- רשימת מענקים

### 4. Generators - יצירת PDFs

**קובץ**: `generators/fixation_generator.py`

פונקציה: `generate_fixation_summary_pdf()`

תהליך:
1. שליפת נתונים מ-DB
2. יצירת תבנית HTML
3. רינדור HTML
4. שמירת HTML זמני
5. המרה ל-PDF
6. מחיקת HTML זמני
7. החזרת נתיב ל-PDF

## Backward Compatibility

הקובץ המקורי `app/services/fixation_pdf_generator.py` נשמר כ-wrapper:

```python
# הקוד הישן ממשיך לעבוד
from app.services.fixation_pdf_generator import generate_fixation_summary_pdf

# זהה לחלוטין לשימוש החדש
from app.services.pdf_generation import generate_fixation_summary_pdf
```

**כל הקוד הקיים ממשיך לעבוד ללא שינוי!**

## יתרונות המבנה החדש

### 1. ארגון ברור
- כל מודול אחראי על תפקיד אחד
- קל למצוא ולערוך קוד ספציפי

### 2. שימוש חוזר
- רכיבים ניתנים לשימוש חוזר
- קל להוסיף PDFs חדשים

### 3. בדיקות
- כל מודול ניתן לבדיקה עצמאית
- קל לכתוב unit tests

### 4. תחזוקה
- שינויים ממוקדים
- פחות סיכון לשבור קוד אחר

### 5. הרחבה
- קל להוסיף תבניות חדשות
- קל להוסיף סוגי PDFs נוספים

## הוספת PDF חדש

### שלב 1: יצירת Data Fetcher

```python
# data_fetchers/my_data.py
from dataclasses import dataclass
from sqlalchemy.orm import Session

@dataclass
class MyData:
    # הגדר שדות...
    pass

def fetch_my_data(db: Session, client_id: int):
    # שלוף נתונים מ-DB
    pass
```

### שלב 2: יצירת Template

```python
# templates/my_template.py
class MyHTMLTemplate:
    def __init__(self, data):
        self.data = data
    
    def render(self) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        ...
        </html>
        """
```

### שלב 3: יצירת Generator

```python
# generators/my_generator.py
from ..data_fetchers import fetch_my_data
from ..templates import MyHTMLTemplate
from ..converters import html_to_pdf

def generate_my_pdf(db, client_id, output_dir):
    data = fetch_my_data(db, client_id)
    template = MyHTMLTemplate(data)
    html_content = template.render()
    
    html_path = output_dir / "temp.html"
    html_path.write_text(html_content, encoding='utf-8')
    
    pdf_path = output_dir / "my_document.pdf"
    html_to_pdf(html_path, pdf_path)
    
    html_path.unlink()
    return pdf_path
```

### שלב 4: עדכון __init__.py

```python
# __init__.py
from .generators.my_generator import generate_my_pdf

__all__ = [
    'generate_fixation_summary_pdf',
    'generate_my_pdf',  # הוסף כאן
]
```

## סטטיסטיקה

### לפני הפיצול:
- **1 קובץ**: 289 שורות
- **2 פונקציות** בקובץ אחד
- קשה לתחזוקה והרחבה

### אחרי הפיצול:
- **9 קבצים** ממוקדים
- **4 מודולים** עצמאיים
- ממוצע **~80 שורות** לקובץ
- ארגון ברור ומודולרי

## תלויות

### Python Packages:
- `sqlalchemy` - גישה ל-DB
- `pathlib` - ניהול נתיבים
- `dataclasses` - מבני נתונים
- `logging` - רישום פעולות

### External Tools:
- `wkhtmltopdf` - המרת HTML ל-PDF
  - Windows: הורד מ-https://wkhtmltopdf.org/downloads.html
  - התקן ב-`C:\Program Files\wkhtmltopdf\`

## Logging

כל המודולים משתמשים ב-logging:

```python
import logging
logger = logging.getLogger(__name__)

logger.info("✅ Success message")
logger.warning("⚠️ Warning message")
logger.error("❌ Error message", exc_info=True)
```

## תמיכה ותחזוקה

- **מיקום**: `app/services/pdf_generation/`
- **Backward Compatibility**: `app/services/fixation_pdf_generator.py`
- **תיעוד**: קובץ זה

---

**תאריך יצירה**: 4 בנובמבר 2025  
**גרסה**: 1.0  
**מפתח**: Cascade AI
