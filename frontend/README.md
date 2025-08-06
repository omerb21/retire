# מערכת תכנון פרישה - Frontend

אפליקציית React לניהול תכנון פרישה עם תמיכה מלאה בעברית ו-RTL.

## תכונות עיקריות

- **ניווט חכם**: מסכים המותאמים לפי סוג המקרה (Case 1-5)
- **תמיכה בעברית**: RTL מלא עם i18n
- **טפסים מתקדמים**: ולידציה מלאה עם הודעות שגיאה בעברית
- **תצוגת תוצאות**: גרפים וטבלאות אינטראקטיביים
- **QA מובנה**: בדיקות sanity ואזהרות אוטומטיות

## מסכים

1. **פרטי לקוח** - פרטים אישיים בסיסיים
2. **מעסיק נוכחי** - מוצג רק במקרה 5
3. **מעסיקים קודמים** - היסטוריית עבודה
4. **קצבאות** - קרנות פנסיה וקצבאות
5. **הכנסות ונכסים** - הכנסות נוספות ונכסי הון
6. **פרמטרי מס ומדד** - הגדרות מערכת (אדמין)
7. **בניית תרחישים** - יצירה וניהול תרחישים
8. **תוצאות** - גרפים, טבלאות ודוחות

## התקנה והרצה

```bash
# התקנת dependencies
npm install

# הרצה במצב פיתוח
npm start

# בניית production
npm run build

# הרצת בדיקות
npm test
```

## מבנה הפרויקט

```
src/
├── components/          # רכיבים משותפים
│   ├── forms/          # רכיבי טפסים
│   └── Layout.tsx      # Layout עיקרי
├── routes/             # מסכים עיקריים
│   ├── ClientNew.tsx
│   ├── EmployerCurrent.tsx
│   ├── EmployersPast.tsx
│   ├── Pensions.tsx
│   ├── IncomeAssets.tsx
│   ├── TaxAdmin.tsx
│   ├── Scenarios.tsx
│   └── Results.tsx
├── lib/                # ספריות עזר
│   ├── api.ts          # API wrapper
│   ├── case-detection.ts # לוגיקת זיהוי מקרים
│   ├── validation.ts   # ולידציות
│   └── i18n.ts         # תרגומים
├── App.tsx             # רכיב ראשי
└── main.tsx           # נקודת כניסה
```

## API Integration

האפליקציה מתחברת ל-API הקיים:

- `/api/v1/clients` - ניהול לקוחות
- `/api/v1/clients/{id}/employment/*` - ניהול תעסוקה
- `/api/v1/calc/{client_id}` - מנוע חישוב
- `/api/v1/clients/{id}/scenarios` - ניהול תרחישים
- `/api/v1/fixation/{client_id}/*` - יצירת מסמכים

## זיהוי מקרים (Cases)

המערכת מזהה אוטומטית את סוג המקרה:

- **Case 1**: ללא מעסיק נוכחי
- **Case 2**: עם מעסיק נוכחי - עזב
- **Case 3**: עם מעסיק נוכחי - יעזוב בעתיד
- **Case 4**: עם מעסיק נוכחי - תאריך עזיבה לא ידוע
- **Case 5**: עובד רגיל עם תכנון עזיבה

## תכונות מתקדמות

### מצב פיתוח (Dev Mode)
- הצגת ערכי debug
- מידע על נוסחאות חישוב
- לוגים מפורטים

### QA מובנה
- בדיקות sanity על תוצאות
- אזהרות על ערכים חריגים
- ולידציה מתקדמת של נתונים

### תמיכה בעברית
- RTL מלא
- תרגומים מלאים
- פורמט תאריכים ומספרים עברי

## Environment Variables

```bash
REACT_APP_API_BASE_URL=http://localhost:8000  # כתובת API
```

## טכנולוגיות

- **React 18** + TypeScript
- **Material-UI** עם תמיכה RTL
- **React Router** לניווט
- **Recharts** לגרפים
- **i18next** לתרגומים
- **Axios** לקריאות API
- **Day.js** לטיפול בתאריכים

## פיתוח

### הוספת מסך חדש
1. צור קובץ ב-`src/routes/`
2. הוסף route ב-`App.tsx`
3. הוסף לניווט ב-`Layout.tsx`
4. עדכן לוגיקת Case ב-`case-detection.ts`

### הוספת ולידציה
1. הוסף פונקציה ב-`validation.ts`
2. הוסף הודעות שגיאה ב-`i18n.ts`
3. השתמש ברכיב הטופס המתאים

### הוספת API endpoint
1. הוסף פונקציה ב-`api.ts`
2. הוסף types מתאימים
3. טפל בשגיאות עם `handleApiError`

## בדיקות

```bash
# בדיקות יחידה
npm test

# בדיקות אינטגרציה
npm run test:integration

# בדיקות E2E
npm run test:e2e
```

## Deployment

```bash
# בניית production
npm run build

# הקבצים יווצרו בתיקיית build/
# ניתן להעלות לכל שרת static hosting
```
