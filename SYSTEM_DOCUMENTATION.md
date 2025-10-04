# מערכת תכנון פרישה - תיעוד מערכת

## סקירה כללית

מערכת תכנון פרישה מקיפה הכוללת:
- ניהול לקוחות ונתונים אישיים
- חישוב מענקי פיצויים ופנסיה
- תכנון תרחישי פרישה
- יצירת דוחות PDF מפורטים
- ממשק משתמש אינטואיטיבי

## ארכיטקטורת המערכת

### Backend (FastAPI)
- **שרת API**: FastAPI עם תמיכה בתיעוד אוטומטי
- **בסיס נתונים**: SQLite/PostgreSQL עם SQLAlchemy ORM
- **יצירת PDF**: ReportLab עם תמיכה בעברית
- **חישובי מס**: מודול מיוחד לחישוב מס על מענקים

### Frontend (React + TypeScript)
- **ממשק משתמש**: React עם Vite
- **ניהול מצב**: React Hooks
- **תקשורת API**: Fetch API
- **עיצוב**: CSS מותאם אישית

## נקודות קצה עיקריות

### לקוחות
- `GET /api/v1/clients` - רשימת לקוחות
- `POST /api/v1/clients` - יצירת לקוח חדש
- `GET /api/v1/clients/{id}` - פרטי לקוח
- `PUT /api/v1/clients/{id}` - עדכון לקוח

### תרחישים
- `GET /api/v1/scenarios/{id}` - פרטי תרחיש
- `GET /api/v1/scenarios/{id}/cashflow` - נתוני תזרים
- `POST /api/v1/scenarios/{id}/report/pdf` - יצירת דוח PDF

### נתוני מס
- `GET /api/v1/tax-data/severance-caps` - תקרות פיצויים
- `GET /api/v1/tax-data/tax-brackets` - מדרגות מס

## הפעלת המערכת

### שרת Backend
```bash
# שרת מינימלי (מומלץ לפיתוח)
python minimal_working_server.py

# שרת מלא (עם SQLAlchemy)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm start
```

## בדיקות אוטומטיות

### הרצת בדיקות מקיפות
```bash
python comprehensive_test_suite.py
```

הבדיקות כוללות:
- בריאות השרת
- פעולות CRUD על לקוחות
- API תרחישים
- נתוני תזרים
- יצירת PDF
- APIs נתוני מס

## מבנה קבצים

```
retire/
├── app/                    # קוד Backend
│   ├── main.py            # נקודת כניסה FastAPI
│   ├── database.py        # הגדרות בסיס נתונים
│   ├── models/            # מודלי SQLAlchemy
│   ├── routers/           # נתיבי API
│   ├── services/          # לוגיקה עסקית
│   └── utils/             # כלי עזר
├── frontend/              # קוד Frontend
│   ├── src/
│   │   ├── components/    # רכיבי React
│   │   └── pages/         # דפי המערכת
│   └── public/
├── tests/                 # בדיקות יחידה
├── minimal_working_server.py  # שרת מינימלי
├── comprehensive_test_suite.py # בדיקות מקיפות
└── requirements.txt       # תלויות Python
```

## תכונות עיקריות

### 1. ניהול לקוחות
- הזנת פרטים אישיים (שם, ת.ז., תאריך לידה)
- ניהול מעסיק נוכחי ושכר
- מעקב אחר מענקים ממעסיקים קודמים

### 2. חישובי מס
- תקרות פיצויים עדכניות (41,667 ₪/חודש)
- מדרגות מס ישראליות
- חישוב פטור ממס על מענקים
- תמיכה בשנות שירות ומקדמי הצמדה

### 3. תכנון תרחישים
- יצירת תרחישי פרישה מרובים
- חישוב תזרים חודשי ל-12 חודשים
- השוואת תרחישים שונים

### 4. דוחות PDF
- דוחות מפורטים בעברית
- טבלאות תזרים חודשי
- גרפים וחישובים סיכום
- ייצוא לקובץ PDF

## אבטחה

### הגנות בסיסיות
- CORS מוגדר לפיתוח מקומי
- Validation של נתוני קלט עם Pydantic
- טיפול בשגיאות מובנה

### המלצות לייצור
- הגדרת HTTPS
- אימות משתמשים
- הגבלת CORS לדומיינים מאושרים
- הצפנת בסיס נתונים רגיש

## פתרון בעיות נפוצות

### בעיות SQLAlchemy
אם יש שגיאות mapper conflicts:
```bash
python fix_sqlalchemy_complete.py
```

### בעיות PDF
אם יצירת PDF נכשלת:
1. ודא התקנת ReportLab: `pip install reportlab`
2. בדוק זכויות כתיבה בתיקייה
3. הרץ: `python test_pdf_fix.py`

### בעיות Frontend
אם Frontend לא עולה:
```bash
cd frontend
npm install
npm start
```

## מדדי ביצועים

### תוצאות בדיקות אחרונות
- ✅ בריאות שרת: PASS
- ✅ CRUD לקוחות: PASS (2 לקוחות)
- ✅ API תרחישים: PASS (12 חודשים)
- ✅ נתוני תזרים: PASS (₪108,000 נטו)
- ✅ יצירת PDF: PASS (2,568 bytes)
- ✅ נתוני מס: PASS (7 מדרגות מס)

### זמני תגובה טיפוסיים
- API בסיסי: < 100ms
- יצירת PDF: < 2s
- טעינת Frontend: < 1s

## תחזוקה ועדכונים

### עדכון נתוני מס
עדכן את הקבצים:
- `app/services/tax_data_service.py`
- `minimal_working_server.py`

### גיבוי בסיס נתונים
```bash
# SQLite
cp retire.db retire_backup_$(date +%Y%m%d).db

# PostgreSQL
pg_dump retirement_db > backup_$(date +%Y%m%d).sql
```

## תמיכה וקשר

למידע נוסף או דיווח על בעיות, עיין בקבצים:
- `UPDATED_SERVER_INSTRUCTIONS.md`
- `SQLALCHEMY_FIX_SUMMARY.md`
- `TEST_FIXES_SUMMARY.md`

---

**עדכון אחרון**: ספטמבר 2025  
**גרסה**: 1.0.0  
**סטטוס**: פעיל ויציב
