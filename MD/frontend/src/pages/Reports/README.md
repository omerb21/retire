# Reports Module - מודול דוחות

## 📋 מבנה התיקייה

```
Reports/
├── index.tsx                      # קומפוננטה ראשית (198 שורות)
├── components/                    # קומפוננטות UI
│   ├── ReportHeader/             # כותרת ופרטי לקוח (86 שורות)
│   │   └── index.tsx
│   ├── ExportControls/           # כפתורי ייצוא (75 שורות)
│   │   └── index.tsx
│   ├── YearlyBreakdown/          # טבלאות תזרים שנתי (169 שורות)
│   │   └── index.tsx
│   ├── NPVAnalysis/              # ניתוח NPV (83 שורות)
│   │   └── index.tsx
│   └── IncomeDetails/            # פירוט מקורות הכנסה (123 שורות)
│       └── index.tsx
└── utils/                         # פונקציות עזר
    └── htmlReportGenerator.ts    # יצירת דוח HTML (266 שורות)
```

## 🎯 תכונות

### קומפוננטות עיקריות:

#### 1. **ReportHeader**
- הצגת פרטי לקוח
- הצגת פרטי קיבוע זכויות
- חישוב קצבה פטורה

#### 2. **ExportControls**
- ייצוא ל-Excel
- ייצוא ל-PDF/HTML
- הורדת מסמכי קיבוע

#### 3. **YearlyBreakdown**
- טבלת תזרים שנתי - סיכום
- טבלת תזרים מפורט לפי מקור הכנסה
- הצגה עם צבעים מובחנים

#### 4. **NPVAnalysis**
- חישוב NPV עם פטור
- חישוב NPV ללא פטור
- חיסכון מקיבוע
- ערך נוכחי נכסי הון

#### 5. **IncomeDetails**
- טבלת קצבאות
- טבלת הכנסות נוספות
- טבלת נכסי הון

## 🔄 תהליך הפיצול

### מקור:
- `frontend/src/pages/ReportsPage.tsx` (838 שורות)

### תוצאה:
- 7 קבצים מודולריים
- כל קובץ מתחת ל-300 שורות
- הפרדה ברורה של אחריות

## 📦 Dependencies

```typescript
// Shared hooks
import { useReportData } from '../../components/reports/hooks/useReportData';

// Calculations
import { generateYearlyProjection } from '../../components/reports/calculations/cashflowCalculations';
import { calculateNPVComparison } from '../../components/reports/calculations/npvCalculations';
import { getPensionCeiling } from '../../components/reports/calculations/pensionCalculations';

// Generators
import { generatePDFReport } from '../../components/reports/generators/PDFGenerator';
import { generateExcelReport } from '../../components/reports/generators/ExcelGenerator';

// Types
import { YearlyProjection } from '../../components/reports/types/reportTypes';

// Utils
import { formatDateToDDMMYY } from '../../utils/dateUtils';
```

## 🚀 שימוש

```typescript
import ReportsPage from './pages/Reports';

// In router
<Route path="/clients/:id/reports" element={<ReportsPage />} />
```

## ✅ יתרונות הפיצול

1. **קריאות משופרת** - כל קומפוננטה ממוקדת באחריות אחת
2. **תחזוקה קלה** - קל למצוא ולתקן באגים
3. **שימוש חוזר** - קומפוננטות ניתנות לשימוש חוזר
4. **בדיקות** - קל יותר לכתוב unit tests
5. **ביצועים** - אפשרות ל-lazy loading
6. **עבודת צוות** - קל יותר לעבוד במקביל

## 🔍 בדיקות

### בדיקת Build:
```bash
cd frontend
npm run build
```

### בדיקת גדלי קבצים:
```powershell
Get-ChildItem -Path "frontend\src\pages\Reports" -Recurse -Include "*.tsx","*.ts" | 
  ForEach-Object { 
    $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
    Write-Host "$($_.Name): $lines lines" 
  }
```

## 📝 הערות

- כל הפונקציונליות המקורית נשמרה
- אין שינויים בלוגיקה העסקית
- התאימות לאחור מובטחת
- הקובץ המקורי נשאר עד לאישור סופי

## 🔗 קישורים

- [Original File](../ReportsPage.tsx)
- [Reports Calculations](../../components/reports/calculations/)
- [Reports Generators](../../components/reports/generators/)
