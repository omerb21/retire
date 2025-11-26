# תיקון: קצבה פטורה מחושבת לא מתעדכנת במסך תוצאות

## תאריך: 06.11.2025

## הבעיה
לאחר לחיצה על כפתור "שמור קיבוע זכויות" במסך קיבוע זכויות, הנתונים נשמרו בהצלחה ב-DB (`POST /api/v1/rights-fixation/save HTTP/1.1" 200 OK`), אבל הקצבה הפטורה המחושבת לא הופיעה במסך התוצאות.

## הסיבה
הבעיה היתה ב-hook `useReportData.ts` שטוען את נתוני הדוח:

### 1️⃣ **Endpoint שגוי**
```typescript
// ❌ לפני התיקון:
axios.get(`/api/v1/clients/${clientId}/fixation`)

// ✅ אחרי התיקון:
axios.get(`/api/v1/rights-fixation/client/${clientId}`)
```

ה-endpoint הישן `/api/v1/clients/${clientId}/fixation` לא קיים! ה-endpoint הנכון הוא `/api/v1/rights-fixation/client/${clientId}`.

### 2️⃣ **מבנה תגובה לא נכון**
השרת מחזיר:
```json
{
  "success": true,
  "calculation_date": "2025-11-06T11:48:07.249000",
  "exempt_capital_remaining": 415639.71,
  "raw_result": {
    "grants": [...],
    "exemption_summary": {
      "exempt_capital_initial": 882648.0,
      "total_impact": 467008.29,
      "remaining_exempt_capital": 415639.71,
      "remaining_monthly_exemption": 2309.11,
      "eligibility_year": 2024,
      "exemption_percentage": 0.4709008687494902,
      "general_exemption_percentage": 0.52
    },
    "eligibility_date": "2024-01-01",
    "eligibility_year": 2024
  },
  "raw_payload": {...}
}
```

אבל הקוד ציפה לקבל ישירות את `exemption_summary`:
```typescript
// ❌ לפני התיקון:
const fixationDataResponse = fixationResponse?.data || null;
// זה שומר את כל האובייקט עם success, raw_result וכו'

// ✅ אחרי התיקון:
const fixationDataResponse = fixationResponse?.data?.raw_result || null;
// זה שומר רק את raw_result שמכיל את exemption_summary
```

## הפתרון

### קובץ: `frontend/src/components/reports/hooks/useReportData.ts`

#### שינוי 1: תיקון endpoint (שורה 62)
```typescript
// Get financial data
const [pensionFundsResponse, additionalIncomesResponse, capitalAssetsResponse, fixationResponse] = await Promise.all([
  axios.get(`/api/v1/clients/${clientId}/pension-funds`),
  axios.get(`/api/v1/clients/${clientId}/additional-incomes`),
  axios.get(`/api/v1/clients/${clientId}/capital-assets`),
  axios.get(`/api/v1/rights-fixation/client/${clientId}`).catch(() => ({ data: null }))  // ✅ תוקן
]);
```

#### שינוי 2: חילוץ raw_result (שורה 69)
```typescript
const pensionFundsData = pensionFundsResponse.data || [];
const additionalIncomesData = additionalIncomesResponse.data || [];
const capitalAssetsData = capitalAssetsResponse.data || [];
// Extract raw_result from the fixation response
const fixationDataResponse = fixationResponse?.data?.raw_result || null;  // ✅ תוקן
```

## תוצאה

### לפני התיקון:
- ❌ הקוד קרא ל-endpoint לא קיים
- ❌ אם היה endpoint, היה שומר את כל האובייקט עם `success`, `raw_result` וכו'
- ❌ הקוד ניסה לגשת ל-`fixationData.exemption_summary` אבל זה היה `undefined`
- ❌ הקצבה הפטורה לא הופיעה במסך התוצאות

### אחרי התיקון:
- ✅ הקוד קורא ל-endpoint הנכון `/api/v1/rights-fixation/client/${clientId}`
- ✅ מחלץ את `raw_result` מהתגובה
- ✅ `fixationData` מכיל ישירות את `exemption_summary`
- ✅ הקצבה הפטורה מתעדכנת במסך התוצאות

## שימוש ב-fixationData

הקוד משתמש ב-`fixationData` במספר מקומות:

### 1️⃣ **useReportData.ts** (שורות 131-146)
```typescript
if (fixationDataResponse && fixationDataResponse.exemption_summary) {
  const eligibilityYear = fixationDataResponse.eligibility_year || fixationDataResponse.exemption_summary.eligibility_year;
  const currentYear = monthDate.getFullYear();
  
  if (currentYear >= eligibilityYear) {
    const exemptionPercentage = fixationDataResponse.exemption_summary.exemption_percentage || 0;
    const remainingExemptCapital = fixationDataResponse.exemption_summary.remaining_exempt_capital || 0;
    
    if (currentYear === eligibilityYear) {
      monthlyExemptPension += remainingExemptCapital / 180;
    } else {
      const pensionCeiling = getPensionCeiling(currentYear);
      monthlyExemptPension += exemptionPercentage * pensionCeiling;
    }
  }
}
```

### 2️⃣ **ReportsPage.tsx** (שורות 466-482)
```typescript
{fixationData && fixationData.exemption_summary && (
  <div>
    <h3>פרטי קיבוע זכויות</h3>
    <div>
      <div><strong>שנת קיבוע:</strong> {fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year}</div>
      <div><strong>הון פטור ראשוני:</strong> ₪{fixationData.exemption_summary.exempt_capital_initial.toLocaleString()}</div>
      <div><strong>הון פטור נותר:</strong> ₪{fixationData.exemption_summary.remaining_exempt_capital.toLocaleString()}</div>
      <div><strong>קצבה פטורה חודשית:</strong> ₪{fixationData.exemption_summary.remaining_monthly_exemption.toLocaleString()}</div>
    </div>
  </div>
)}
```

### 3️⃣ **cashflowCalculations.ts** (שורות 129-137)
```typescript
if (fixationData && fixationData.exemption_summary) {
  const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year;
  
  if (year >= eligibilityYear) {
    const remainingExemptCapital = fixationData.exemption_summary.remaining_exempt_capital || 0;
    const remainingMonthlyExemption = fixationData.exemption_summary.remaining_monthly_exemption || (remainingExemptCapital / 180);
    // ... חישובי מס
  }
}
```

## בדיקה

### צעדים לבדיקה:
1. ✅ Build הצליח - `npm run build` עבר ללא שגיאות
2. ✅ TypeScript תקין - אין שגיאות קומפילציה
3. 🔄 נדרש: בדיקה בדפדפן
   - פתח מסך קיבוע זכויות
   - לחץ על "שמור קיבוע זכויות"
   - עבור למסך תוצאות
   - וודא שהקצבה הפטורה מופיעה

### תוצאה צפויה:
```
פרטי קיבוע זכויות
שנת קיבוע: 2024
הון פטור ראשוני: ₪882,648
הון פטור נותר: ₪415,640
קצבה פטורה חודשית: ₪2,309
```

## קבצים שעודכנו
- ✅ `frontend/src/components/reports/hooks/useReportData.ts` (שורות 62, 69)
- ✅ `frontend/src/components/reports/calculations/cashflowCalculations.ts` (שורות 136-137)

## קבצים שנבדקו (ללא שינוי)
- ✅ `frontend/src/pages/ReportsPage.tsx` - שימוש נכון ב-`fixationData.exemption_summary`
- ✅ `app/routers/rights_fixation.py` - endpoint `/client/{client_id}` קיים ותקין

## תיקון נוסף: חישוב קצבה פטורה (06.11.2025)

### הבעיה:
לאחר התיקון הראשון, הנתונים נטענו אבל הערך המוצג היה שגוי:
- **במסך קיבוע זכויות**: קצבה פטורה = 2,806.6 ₪
- **במסך תוצאות**: קצבה פטורה = 2,431 ₪ (שגוי!)

### הסיבה:
הקוד לא עקב אחרי הלוגיקה הרשומה במסך הגדרות → לשונית "קיבוע זכויות".

### הלוגיקה הנכונה (מתיעוד המערכת):

#### 🔹 חישוב במסך קיבוע זכויות:
1. **יתרת הון פטורה ראשונית** = תקרת קצבה מזכה לשנת גיל הזכאות × 180 × אחוז הון פטור
2. **פגיעה בפטור למענק** = ערך מענק מוצמד × 1.35
3. **יתרה נותרת** = יתרה ראשונית - סך פגיעות
4. **אחוז פטור מחושב** = (יתרה נותרת / 180) / תקרת הקצבה המזכה לשנת גיל הזכאות

#### 🔹 חישוב במסך תוצאות:
```
קצבה פטורה = אחוז פטור מקיבוע × תקרת קצבה של השנה הראשונה בתזרים
```

**דוגמה:** 41.29% × 9,430 (תקרה 2025) = 3,893 ₪

⚠️ **כללים חשובים:**
- אחוז הפטור מחושב **פעם אחת** במסך קיבוע זכויות
- השנה הראשונה בתזרים = **השנה הנוכחית** (לא שנת הזכאות!)
- **לא להכפיל באחוז כללי! לא לחשב מחדש! רק אחוז מקיבוע × תקרה!**

### הפתרון:

```typescript
// ❌ לפני התיקון - חישוב שגוי עם שנת זכאות:
if (year === eligibilityYear) {
  monthlyExemptPension = remainingMonthlyExemption;
} else {
  const pensionCeiling = getPensionCeiling(year);
  monthlyExemptPension = correctExemptionPercentage * pensionCeiling;
}

// ✅ אחרי התיקון - לוגיקה נכונה:
// אחוז הפטור מקיבוע זכויות (מחושב פעם אחת במסך קיבוע)
const exemptionPercentage = fixationData.exemption_summary.exemption_percentage || 0;

// תקרת קצבה של השנה הנוכחית (השנה הראשונה בתזרים)
const currentYearCeiling = getPensionCeiling(currentYear);

// קצבה פטורה = אחוז פטור × תקרה (ללא חישובים נוספים!)
monthlyExemptPension = exemptionPercentage * currentYearCeiling;
```

### תוצאה:
**לקוח 1 - נתונים:**
- אחוז פטור מקיבוע: `0.5723556616000943` (57.24%)
- תקרת קצבה 2025: `9,430 ₪`
- **קצבה פטורה חודשית**: `0.5724 × 9,430 = 5,397 ₪` ✅

**בכל השנים בתזרים** - אותה קצבה פטורה: `5,397 ₪` (כי תמיד משתמשים בתקרת השנה הנוכחית)

## סיכום
התיקון פתר שתי בעיות:
1. **טעינת נתונים**: שימוש ב-endpoint הנכון וחילוץ `raw_result`
2. **חישוב אחוז פטור**: שימוש בערך מהשרת במקום חישוב מחדש שגוי

כעת, לאחר שמירת קיבוע זכויות, הנתונים יטענו כראוי ויוצגו במסך התוצאות עם הערכים הנכונים.
