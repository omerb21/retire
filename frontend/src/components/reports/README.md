# מבנה קומפוננטות הדוחות

## סקירה כללית
הקבצים בתיקייה זו מהווים פיצול של הקובץ הגדול `SimpleReports.tsx` לקבצים קטנים יותר ומנוהלים.

## מבנה התיקיות

```
components/reports/
├── calculations/          # פונקציות חישוב
│   ├── npvCalculations.ts        # חישובי NPV
│   └── pensionCalculations.ts    # חישובי קצבה ופטורים
├── generators/           # יצירת דוחות
│   ├── PDFGenerator.ts          # יצירת דוח PDF
│   └── ExcelGenerator.ts        # יצירת דוח Excel
├── hooks/               # React hooks
│   └── useReportData.ts        # טעינת נתונים
├── types/               # הגדרות טיפוסים
│   └── reportTypes.ts          # טיפוסים משותפים
└── README.md           # מסמך זה
```

## קבצים

### 1. calculations/npvCalculations.ts
**תפקיד**: חישובי ערך נוכחי נקי (NPV)

**פונקציות**:
- `calculateNPV(cashFlows, discountRate)` - מחשב NPV של תזרים מזומנים

**שימוש**:
```typescript
import { calculateNPV } from '../components/reports/calculations/npvCalculations';

const annualCashFlows = [10000, 12000, 15000];
const npv = calculateNPV(annualCashFlows, 0.03);
```

### 2. calculations/pensionCalculations.ts
**תפקיד**: חישובי קצבה ופטורים ממס

**פונקציות**:
- `getPensionCeiling(year)` - מחזיר תקרת קצבה פטורה לפי שנה
- `getExemptCapitalPercentage(year)` - מחזיר אחוז הון פטור לפי שנה

**שימוש**:
```typescript
import { getPensionCeiling, getExemptCapitalPercentage } from '../components/reports/calculations/pensionCalculations';

const ceiling2025 = getPensionCeiling(2025); // 9430
const exemptPercent2025 = getExemptCapitalPercentage(2025); // 0.57
```

### 3. generators/PDFGenerator.ts
**תפקיד**: יצירת דוח PDF

**פונקציות**:
- `generatePDFReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, clientData)` - יוצר ושומר דוח PDF

**תכולת הדוח**:
- כותרת ופרטי לקוח
- חישוב NPV
- טבלת תזרים מזומנים שנתי
- פירוט נכסי הון
- פירוט קצבאות
- הכנסות נוספות
- סיכום כספי מקיף

**שימוש**:
```typescript
import { generatePDFReport } from '../components/reports/generators/PDFGenerator';

generatePDFReport(yearlyData, pensions, incomes, assets, client);
// הקובץ יישמר אוטומטית
```

### 4. generators/ExcelGenerator.ts
**תפקיד**: יצירת דוח Excel

**פונקציות**:
- `generateExcelReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, clientData)` - יוצר ושומר דוח Excel

**גיליונות בדוח**:
1. **תזרים מזומנים** - תחזית 30 שנים + NPV
2. **נכסי הון** - פירוט מלא + סיכומים
3. **קצבאות** - פירוט מלא + סיכומים
4. **הכנסות נוספות** - פירוט מלא + סיכומים
5. **סיכום כללי** - סיכום פיננסי מקיף

**שימוש**:
```typescript
import { generateExcelReport } from '../components/reports/generators/ExcelGenerator';

generateExcelReport(yearlyData, pensions, incomes, assets, client);
// הקובץ יישמר אוטומטית
```

### 5. hooks/useReportData.ts
**תפקיד**: Custom hook לטעינת נתוני דוח

**מה ה-hook עושה**:
- טוען נתוני לקוח
- טוען קצבאות, הכנסות נוספות, נכסי הון
- טוען נתוני קיבוע זכויות
- מחשב סיכומים פיננסיים
- יוצר תחזית תזרים מזומנים

**ערכים מוחזרים**:
```typescript
{
  loading: boolean,
  error: string | null,
  reportData: ReportData | null,
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  client: any,
  fixationData: any
}
```

**שימוש**:
```typescript
import { useReportData } from '../components/reports/hooks/useReportData';

function MyComponent() {
  const { loading, error, reportData, pensionFunds, client } = useReportData(clientId);
  
  if (loading) return <div>טוען...</div>;
  if (error) return <div>שגיאה: {error}</div>;
  
  return <div>{/* הצג נתונים */}</div>;
}
```

### 6. types/reportTypes.ts
**תפקיד**: הגדרות טיפוסים משותפים

**טיפוסים**:
- `YearlyProjection` - תחזית שנתית
- `ReportData` - מבנה נתוני דוח
- `ASSET_TYPES` - סוגי נכסים

## שימוש בקומפוננטה הראשית

הקובץ `SimpleReports.tsx` המקורי נשאר ללא שינוי כרגע, אך ניתן להשתמש בקבצים החדשים:

```typescript
import { useReportData } from '../components/reports/hooks/useReportData';
import { generatePDFReport } from '../components/reports/generators/PDFGenerator';
import { generateExcelReport } from '../components/reports/generators/ExcelGenerator';
import { calculateNPV } from '../components/reports/calculations/npvCalculations';

function SimpleReports() {
  const { id } = useParams();
  const { loading, error, pensionFunds, additionalIncomes, capitalAssets, client } = useReportData(id);
  
  // שאר הקוד...
}
```

## יתרונות הפיצול

### 1. תחזוקה קלה יותר
- כל קובץ מטפל באחריות אחת
- קל למצוא ולתקן באגים
- קל להוסיף פיצ'רים חדשים

### 2. קוד נקי יותר
- פונקציות קצרות וממוקדות
- קל לקריאה והבנה
- פחות סיכוי לשגיאות

### 3. שימוש חוזר
- ניתן להשתמש בפונקציות במקומות אחרים
- לא צריך לשכפל קוד
- עדכון במקום אחד משפיע על כל השימושים

### 4. בדיקות
- קל יותר לכתוב unit tests
- כל פונקציה ניתנת לבדיקה בנפרד
- קל לזהות בעיות

### 5. ביצועים
- ניתן לטעון רק את מה שצריך
- Code splitting אפשרי
- זמן טעינה מהיר יותר

## הערות חשובות

1. **תאימות לאחור**: הקבצים החדשים תואמים לחלוטין לקוד הקיים
2. **אין שינויים בלוגיקה**: הפיצול לא שינה את אופן הפעולה
3. **ניתן לשדרג בהדרגה**: אפשר להתחיל להשתמש בקבצים החדשים בהדרגה

## צעדים הבאים

1. ✅ יצירת מבנה תיקיות
2. ✅ הפרדת חישובים (NPV, פנסיה)
3. ✅ הפרדת generators (PDF, Excel)
4. ✅ יצירת useReportData hook
5. ⏳ עדכון SimpleReports.tsx להשתמש בקבצים החדשים
6. ⏳ הפרדת קומפוננטות UI נוספות
7. ⏳ כתיבת unit tests

## תיעוד נוסף

לתיעוד מפורט יותר על כל פונקציה, ראה את ה-JSDoc בתוך הקבצים עצמם.
