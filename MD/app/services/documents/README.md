# מודול יצירת מסמכים - מבנה מודולרי

## סקירה כללית

מודול זה אחראי על יצירת מסמכי קיבוע זכויות, כולל טופס 161ד ונספחים שונים.
הקובץ המקורי `document_generator.py` (933 שורות) פוצל למבנה מודולרי ברור ונקי.

## מבנה התיקיות

```
app/services/documents/
├── __init__.py                          # ייצוא ראשי
├── README.md                            # תיעוד זה
│
├── utils/                               # פונקציות עזר
│   ├── __init__.py
│   ├── paths.py                         # ניהול נתיבים ותיקיות
│   └── text_utils.py                    # פונקציות טיפול בטקסט
│
├── converters/                          # המרת HTML ל-PDF
│   ├── __init__.py
│   └── html_to_pdf.py                   # המרה באמצעות wkhtmltopdf
│
├── templates/                           # תבניות HTML
│   ├── __init__.py
│   ├── styles.py                        # סגנונות CSS
│   ├── grants_template.py               # תבנית נספח מענקים
│   ├── commutations_template.py         # תבנית נספח היוונים
│   └── summary_template.py              # תבנית טבלת סיכום
│
├── data_fetchers/                       # שליפת נתונים מ-DB
│   ├── __init__.py
│   ├── client_data.py                   # שליפת נתוני לקוח
│   ├── fixation_data.py                 # שליפת נתוני קיבוע זכויות
│   ├── grants_data.py                   # שליפת נתוני מענקים
│   ├── pension_data.py                  # שליפת נתוני קצבאות
│   └── commutations_data.py             # שליפת נתוני היוונים
│
└── generators/                          # יצירת מסמכים
    ├── __init__.py
    ├── form_161d_generator.py           # יצירת טופס 161ד
    ├── grants_generator.py              # יצירת נספח מענקים
    ├── commutations_generator.py        # יצירת נספח היוונים
    ├── summary_generator.py             # יצירת טבלת סיכום
    └── package_generator.py             # יצירת חבילת מסמכים מלאה
```

## שימוש בסיסי

### יצירת חבילת מסמכים מלאה

```python
from sqlalchemy.orm import Session
from app.services.documents import generate_document_package

# יצירת חבילת מסמכים
result = generate_document_package(db=db_session, client_id=123)

if result["success"]:
    print(f"חבילה נוצרה בהצלחה: {result['folder']}")
    print(f"קבצים: {result['files']}")
else:
    print(f"שגיאה: {result['error']}")
```

### יצירת מסמך בודד

```python
from pathlib import Path
from app.services.documents import fill_161d_form, generate_grants_appendix

# מילוי טופס 161ד
output_dir = Path("./output")
form_path = fill_161d_form(db=db_session, client_id=123, output_dir=output_dir)

# יצירת נספח מענקים
grants_path = generate_grants_appendix(db=db_session, client_id=123, output_dir=output_dir)
```

## רכיבים עיקריים

### 1. Utils - פונקציות עזר

**קובץ**: `utils/paths.py`

מכיל:
- `get_client_package_dir()` - יוצר תיקייה ללקוח
- `TEMPLATE_DIR` - נתיב לתבניות
- `TEMPLATE_161D` - נתיב לטופס 161ד
- `PACKAGES_DIR` - נתיב לחבילות מסמכים

**קובץ**: `utils/text_utils.py`

מכיל:
- `sanitize_filename()` - ניקוי שמות קבצים

### 2. Converters - המרת HTML ל-PDF

**קובץ**: `converters/html_to_pdf.py`

מכיל:
- `find_wkhtmltopdf()` - מחפש את wkhtmltopdf במערכת
- `html_to_pdf()` - ממיר HTML ל-PDF

**דרישות**:
- wkhtmltopdf מותקן במערכת
- ניתן להוריד מ: https://wkhtmltopdf.org/downloads.html

### 3. Data Fetchers - שליפת נתונים

**קובץ**: `data_fetchers/fixation_data.py`

מחלקה: `FixationData` (dataclass)

פונקציה: `fetch_fixation_data()`
- שולף נתוני קיבוע זכויות מה-DB
- מחזיר: לקוח, סיכום פטור, מענקים, תאריך זכאות

**קבצים נוספים**:
- `client_data.py` - שליפת נתוני לקוח
- `grants_data.py` - שליפת תאריכי עבודה למענקים
- `pension_data.py` - שליפת קצבאות
- `commutations_data.py` - שליפת היוונים פטורים

### 4. Templates - תבניות HTML

**קובץ**: `templates/styles.py`

פונקציות:
- `get_base_styles()` - סגנונות בסיסיים
- `get_grants_styles()` - סגנונות לנספח מענקים
- `get_commutations_styles()` - סגנונות לנספח היוונים
- `get_summary_styles()` - סגנונות לטבלת סיכום

**קובץ**: `templates/grants_template.py`

מחלקה: `GrantsHTMLTemplate`

מתודות:
- `_build_header()` - כותרת המסמך
- `_build_table()` - טבלת מענקים
- `render()` - רינדור HTML מלא

**קבצים נוספים**:
- `commutations_template.py` - תבנית נספח היוונים
- `summary_template.py` - תבנית טבלת סיכום

### 5. Generators - יצירת מסמכים

**קובץ**: `generators/form_161d_generator.py`

פונקציה: `fill_161d_form()`

תהליך:
1. בדיקת קיום טמפלייט
2. שליפת נתוני לקוח וקיבוע זכויות
3. חישוב כל הערכים הנדרשים
4. מילוי הטופס באמצעות pdf_filler
5. החזרת נתיב לטופס שנוצר

**קובץ**: `generators/grants_generator.py`

פונקציה: `generate_grants_appendix()`

תהליך:
1. שליפת נתוני קיבוע זכויות
2. שליפת תאריכי עבודה
3. יצירת תבנית HTML
4. רינדור HTML
5. המרה ל-PDF
6. החזרת נתיב לנספח

**קבצים נוספים**:
- `commutations_generator.py` - נספח היוונים (2 פונקציות)
- `summary_generator.py` - טבלת סיכום
- `package_generator.py` - חבילת מסמכים מלאה

## Backward Compatibility

הקובץ המקורי `app/services/document_generator.py` נשמר כ-wrapper:

```python
# הקוד הישן ממשיך לעבוד בדיוק כמו קודם
from app.services.document_generator import generate_document_package

# זהה לחלוטין לשימוש החדש
from app.services.documents import generate_document_package
```

**כל הקוד הקיים ממשיך לעבוד ללא שינוי!**

## יתרונות המבנה החדש

### 1. ארגון ברור
- כל מודול אחראי על תפקיד אחד
- קל למצוא ולערוך קוד ספציפי
- מבנה היררכי לוגי

### 2. שימוש חוזר
- רכיבים ניתנים לשימוש חוזר
- תבניות HTML מפוצלות
- פונקציות עזר נפרדות

### 3. בדיקות
- כל מודול ניתן לבדיקה עצמאית
- קל לכתוב unit tests
- בידוד שגיאות

### 4. תחזוקה
- שינויים ממוקדים
- פחות סיכון לשבור קוד אחר
- קל להוסיף תכונות חדשות

### 5. הרחבה
- קל להוסיף תבניות חדשות
- קל להוסיף סוגי מסמכים נוספים
- מבנה גמיש

## הוספת מסמך חדש

### שלב 1: יצירת Data Fetcher (אם נדרש)

```python
# data_fetchers/my_data.py
from sqlalchemy.orm import Session
from typing import List

def fetch_my_data(db: Session, client_id: int) -> List:
    # שלוף נתונים מ-DB
    return data
```

### שלב 2: יצירת Template

```python
# templates/my_template.py
class MyHTMLTemplate:
    def __init__(self, data):
        self.data = data
    
    def _build_header(self) -> str:
        return "<h1>כותרת</h1>"
    
    def _build_content(self) -> str:
        return "<div>תוכן</div>"
    
    def render(self) -> str:
        return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>מסמך חדש</title>
    <style>{get_base_styles()}</style>
</head>
<body>
{self._build_header()}
{self._build_content()}
</body>
</html>
"""
```

### שלב 3: יצירת Generator

```python
# generators/my_generator.py
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..data_fetchers import fetch_my_data
from ..templates import MyHTMLTemplate
from ..converters import html_to_pdf

logger = logging.getLogger(__name__)


def generate_my_document(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר מסמך חדש
    """
    try:
        # שליפת נתונים
        data = fetch_my_data(db, client_id)
        if not data:
            return None
        
        # יצירת תבנית
        template = MyHTMLTemplate(data)
        html_content = template.render()
        
        # שמירת HTML
        html_path = output_dir / "my_document.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF
        pdf_path = output_dir / "מסמך_חדש.pdf"
        html_to_pdf(html_path, pdf_path)
        
        logger.info(f"✅ Document created: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"❌ Error creating document: {e}", exc_info=True)
        return None
```

### שלב 4: עדכון __init__.py

```python
# __init__.py
from .generators.my_generator import generate_my_document

__all__ = [
    'generate_document_package',
    'generate_my_document',  # הוסף כאן
    # ...
]
```

## סטטיסטיקה

### לפני הפיצול:
- **1 קובץ**: 933 שורות
- **7 פונקציות** בקובץ אחד
- קשה לתחזוקה והרחבה

### אחרי הפיצול:
- **20 קבצים** ממוקדים
- **5 מודולים** עצמאיים
- ממוצע **~70 שורות** לקובץ
- ארגון ברור ומודולרי

## תלויות

### Python Packages:
- `sqlalchemy` - גישה ל-DB
- `pathlib` - ניהול נתיבים
- `dataclasses` - מבני נתונים
- `logging` - רישום פעולות
- `pdf_filler` - מילוי טפסי PDF

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

- **מיקום**: `app/services/documents/`
- **Backward Compatibility**: `app/services/document_generator.py`
- **תיעוד**: קובץ זה

---

**תאריך יצירה**: 4 בנובמבר 2025  
**גרסה**: 1.0  
**מפתח**: Cascade AI
