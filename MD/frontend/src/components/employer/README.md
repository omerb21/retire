# מודול ניהול מעסיק נוכחי (Employer Module)

## סקירה כללית

מודול זה מכיל את כל הלוגיקה והפונקציונליות הקשורה לניהול מעסיק נוכחי, כולל חישובי מענקי פיצויים, חישובי מס, וניהול החלטות עזיבה.

## מבנה התיקיות

```
employer/
├── calculations/           # חישובים
│   ├── grantCalculations.ts    # חישובי מענקי פיצויים
│   └── taxCalculations.ts      # חישובי מס
├── hooks/                 # Custom Hooks
│   └── useEmployerData.ts      # ניהול state ונתוני מעסיק
├── types/                 # טיפוסי TypeScript
│   └── employerTypes.ts        # ממשקים וטיפוסים
├── utils/                 # פונקציות עזר
│   └── employerUtils.ts        # כלי עזר שונים
└── README.md             # תיעוד זה
```

## קבצים ופונקציות

### 1. `types/employerTypes.ts`

**טיפוסים עיקריים:**

- **`SimpleEmployer`** - נתוני מעסיק בסיסיים
- **`TerminationDecision`** - החלטות עזיבה
- **`GrantDetails`** - פרטי מענק פיצויים
- **`PensionAccount`** - חשבון פנסיוני
- **`CalculateGrantResponse`** - תגובת API לחישוב מענק
- **`CalculateSeveranceResponse`** - תגובת API לחישוב פיצויים

### 2. `calculations/grantCalculations.ts`

**פונקציות עיקריות:**

#### `calculateServiceYears(startDate, endDate)`
מחשב שנות ותק בין שני תאריכים.

```typescript
const serviceYears = calculateServiceYears(new Date('2020-01-01'), new Date('2025-01-01'));
// Returns: 5.0
```

#### `calculateMaxSpreadYears(serviceYears)`
מחשב מספר שנות פריסת מס מקסימלי לפי וותק.

```typescript
const maxSpread = calculateMaxSpreadYears(15);
// Returns: 4 (14+ שנים = 4 שנות פריסה)
```

#### `calculateGrantDetails(startDate, lastSalary, severanceAccrued)`
מחשב פרטי מענק פיצויים מלאים (מנסה API, fallback מקומי).

```typescript
const details = await calculateGrantDetails('2020-01-01', 15000, 50000);
// Returns: {
//   serviceYears: 5.0,
//   expectedGrant: 75000,
//   taxExemptAmount: 68750,
//   taxableAmount: 6250,
//   severanceCap: 13750
// }
```

### 3. `calculations/taxCalculations.ts`

**פונקציות עיקריות:**

#### `calculateTaxWithSpread(taxableAmount, spreadYears)`
מחשב מס על סכום חייב במס עם אפשרות לפריסה.

```typescript
const tax = calculateTaxWithSpread(100000, 3);
// Returns: { annualTax: 11667, monthlyTax: 972 }
```

#### `calculateSeveranceTax(exemptAmount, taxableAmount, spreadYears)`
מחשב מס מלא על מענק פיצויים.

```typescript
const tax = calculateSeveranceTax(50000, 25000, 2);
// Returns: {
//   exemptAmount: 50000,
//   taxableAmount: 25000,
//   totalTax: 7000,
//   annualTax: 3500,
//   monthlyTax: 292,
//   spreadYears: 2
// }
```

#### `calculateMarginalTax(baseIncome, additionalIncome)`
מחשב מס שולי על הכנסה נוספת.

```typescript
const marginalTax = calculateMarginalTax(100000, 50000);
// Returns: 17500 (המס הנוסף על 50,000 ₪)
```

### 4. `utils/employerUtils.ts`

**פונקציות עיקריות:**

#### `loadSeveranceFromPension(clientId)`
טוען יתרת פיצויים מתיק פנסיוני מ-localStorage.

```typescript
const severance = loadSeveranceFromPension('123');
// Returns: 75000
```

#### `isTerminationConfirmed(clientId)`
בדיקה אם עזיבה אושרה.

```typescript
const confirmed = isTerminationConfirmed('123');
// Returns: true/false
```

#### `setTerminationConfirmed(clientId, confirmed)`
סימון עזיבה כמאושרת.

```typescript
setTerminationConfirmed('123', true);
```

#### `validateEmployerData(employer)`
אימות תקינות נתוני מעסיק.

```typescript
const errors = validateEmployerData(employer);
// Returns: ['שם מעסיק חובה', 'שכר חודשי חייב להיות גדול מאפס']
```

#### `validateTerminationDecision(terminationDate, startDate)`
אימות תקינות החלטת עזיבה.

```typescript
const errors = validateTerminationDecision('01/01/2025', '01/01/2020');
// Returns: [] (אין שגיאות)
```

### 5. `hooks/useEmployerData.ts`

**Custom Hook לניהול נתוני מעסיק**

```typescript
const {
  loading,
  error,
  employer,
  setEmployer,
  terminationDecision,
  setTerminationDecision,
  grantDetails,
  originalSeveranceAmount,
  fetchEmployer,
  saveEmployer
} = useEmployerData(clientId);
```

**מה ה-hook עושה:**
- טוען נתוני מעסיק מה-API
- מחשב אוטומטית פרטי מענק כאשר נתונים משתנים
- מנהל state של עזיבה והחלטות
- מספק פונקציות לשמירה וטעינה

## דוגמאות שימוש

### דוגמה 1: שימוש ב-hook בקומפוננטה

```typescript
import { useEmployerData } from '../components/employer/hooks/useEmployerData';

function EmployerPage() {
  const { id } = useParams();
  const {
    loading,
    error,
    employer,
    setEmployer,
    grantDetails,
    saveEmployer
  } = useEmployerData(id);

  if (loading) return <div>טוען...</div>;
  if (error) return <div>שגיאה: {error}</div>;

  const handleSave = async () => {
    try {
      await saveEmployer(employer);
      alert('נשמר בהצלחה!');
    } catch (err) {
      alert('שגיאה בשמירה');
    }
  };

  return (
    <div>
      <h1>{employer.employer_name}</h1>
      <p>מענק צפוי: {grantDetails.expectedGrant}</p>
      <button onClick={handleSave}>שמור</button>
    </div>
  );
}
```

### דוגמה 2: חישוב מענק ישירות

```typescript
import { calculateGrantDetails } from '../components/employer/calculations/grantCalculations';

async function calculateEmployerGrant() {
  const details = await calculateGrantDetails(
    '2020-01-01',  // תאריך התחלה
    15000,         // שכר אחרון
    50000          // יתרת פיצויים נצברת
  );
  
  console.log('מענק צפוי:', details.expectedGrant);
  console.log('פטור ממס:', details.taxExemptAmount);
  console.log('חייב במס:', details.taxableAmount);
}
```

### דוגמה 3: חישוב מס עם פריסה

```typescript
import { calculateSeveranceTax } from '../components/employer/calculations/taxCalculations';
import { calculateMaxSpreadYears } from '../components/employer/calculations/grantCalculations';

function calculateTaxOnSeverance(serviceYears: number, taxableAmount: number) {
  const maxSpread = calculateMaxSpreadYears(serviceYears);
  const tax = calculateSeveranceTax(0, taxableAmount, maxSpread);
  
  console.log(`פריסה על ${maxSpread} שנים`);
  console.log(`מס שנתי: ${tax.annualTax}`);
  console.log(`מס חודשי: ${tax.monthlyTax}`);
  console.log(`סה"כ מס: ${tax.totalTax}`);
}
```

## לוגיקה עסקית חשובה

### חישוב מענק פיצויים
1. **וותק** = (תאריך עזיבה - תאריך התחלה) / 365.25
2. **מענק בסיסי** = שכר אחרון × וותק
3. **מענק בפועל** = max(מענק בסיסי, יתרת פיצויים נצברת)
4. **השלמת מעסיק** = max(0, מענק בפועל - יתרת פיצויים)

### חישוב פטור ממס
- **תקרה שנתית** (2025): 13,750 ₪
- **פטור כולל** = תקרה שנתית × וותק
- **סכום פטור** = min(מענק בפועל, פטור כולל)
- **סכום חייב** = max(0, מענק בפועל - סכום פטור)

### שנות פריסת מס
| וותק | שנות פריסה |
|------|-----------|
| עד 2 שנים | 0 |
| 2-6 שנים | 1 |
| 6-10 שנים | 2 |
| 10-14 שנים | 3 |
| 14-18 שנים | 4 |
| 18-22 שנים | 5 |
| 22+ שנים | 6 |

## תלויות

- `axios` - קריאות API
- `react` - hooks (useState, useEffect)
- `../utils/dateUtils` - פונקציות המרת תאריכים

## הערות חשובות

1. **localStorage** - המודול משתמש ב-localStorage לשמירת:
   - יתרת פיצויים מתיק פנסיוני
   - סטטוס אישור עזיבה
   - סכום פיצויים מקורי

2. **Debouncing** - חישובי מענק מבוצעים עם debounce של 500ms למניעת קריאות מיותרות

3. **Fallback** - אם קריאת API נכשלת, המערכת עוברת לחישוב מקומי

4. **תאימות לאחור** - הקובץ המקורי `SimpleCurrentEmployer.tsx` נשאר ללא שינוי

## בדיקות

לבדיקת הקוד, ניתן להשתמש בדוגמאות הבאות:

```typescript
// בדיקת חישוב וותק
console.assert(
  calculateServiceYears(new Date('2020-01-01'), new Date('2025-01-01')) === 5.0,
  'Service years calculation failed'
);

// בדיקת שנות פריסה
console.assert(
  calculateMaxSpreadYears(15) === 4,
  'Spread years calculation failed'
);

// בדיקת אימות
const errors = validateEmployerData({
  employer_name: '',
  start_date: '2020-01-01',
  last_salary: -100,
  severance_accrued: 0
});
console.assert(
  errors.length === 2,
  'Validation failed'
);
```

## תיעוד נוסף

- [תיעוד API](../../docs/API.md)
- [מדריך פיתוח](../../docs/DEVELOPMENT.md)
- [מדריך משתמש](../../docs/USER_GUIDE.md)

---

**עודכן לאחרונה:** 3 בנובמבר 2025  
**גרסה:** 1.0  
**מחבר:** Cascade AI
