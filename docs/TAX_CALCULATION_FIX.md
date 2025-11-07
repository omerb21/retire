# תיקון קריטי - חישוב מס הכנסה

## תאריך: 7 בנובמבר 2025

## תיאור הבעיה

המערכת חישבה מס הכנסה בצורה שגויה. עבור לקוח עם הכנסה חודשית של 8,333 ₪ (99,996 ₪ לשנה) ו-2.25 נקודות זיכוי, המערכת הציגה מס חודשי של 96 ₪ בלבד, במקום המס הנכון של **341.72 ₪**.

## שורש הבעיה

הבעיה הייתה באלגוריתם חישוב המס לפי מדרגות. הקוד חישב את **גודל המדרגה** בצורה שגויה:

```python
# קוד שגוי:
bracket_size = bracket.max_income - bracket.min_income
```

זה גרם לכך שהמדרגה השנייה (84,121-120,720) חושבה כבעלת גודל של 36,599 ₪ במקום 36,600 ₪, וחשוב מכך - הקוד לא עקב נכון אחרי כמה הכנסה כבר עובדה.

## החישוב הנכון

### עבור הכנסה של 100,000 ₪ עם 2.25 נקודות זיכוי:

1. **מס לפני זיכויים**:
   - מדרגה 1 (0-84,120): 84,120 × 10% = **8,412.00 ₪**
   - מדרגה 2 (84,121-100,000): 15,880 × 14% = **2,223.20 ₪**
   - **סה"כ מס לפני זיכויים: 10,635.20 ₪**

2. **זיכוי ממס**:
   - 2.25 נקודות × 2,904 ₪ = **6,534.00 ₪**

3. **מס סופי**:
   - 10,635.20 - 6,534.00 = **4,101.20 ₪** לשנה
   - **341.77 ₪** לחודש

### עבור הכנסה של 99,996 ₪ (לקוח 1):

1. **מס לפני זיכויים**:
   - מדרגה 1 (0-84,120): 84,120 × 10% = **8,412.00 ₪**
   - מדרגה 2 (84,121-99,996): 15,876 × 14% = **2,222.64 ₪**
   - **סה"כ מס לפני זיכויים: 10,634.64 ₪**

2. **זיכוי ממס**:
   - 2.25 נקודות × 2,904 ₪ = **6,534.00 ₪**

3. **מס סופי**:
   - 10,634.64 - 6,534.00 = **4,100.64 ₪** לשנה
   - **341.72 ₪** לחודש

## קבצים שתוקנו

### 1. Frontend - `taxCalculations.ts`
**קובץ**: `frontend/src/components/reports/calculations/taxCalculations.ts`

**תיקון**: שינוי אלגוריתם חישוב המס מ-`remainingIncome` ל-`processedIncome`

```typescript
// קוד חדש ונכון:
let processedIncome = 0;

for (const bracket of brackets) {
  if (processedIncome >= annualIncome) break;
  
  const incomeInBracket = Math.min(
    annualIncome - processedIncome,
    bracket.maxAnnual - processedIncome
  );
  
  if (incomeInBracket > 0) {
    totalTax += incomeInBracket * (bracket.rate / 100);
    processedIncome += incomeInBracket;
  }
}
```

### 2. Frontend - `employer/calculations/taxCalculations.ts`
**קובץ**: `frontend/src/components/employer/calculations/taxCalculations.ts`

**תיקון**: עדכון מדרגות המס לערכים הנכונים של 2025

```typescript
// מדרגות מס 2025 - מעודכן לערכים הנכונים
const taxBrackets = [
  { threshold: 0, rate: 0.10 },
  { threshold: 84120, rate: 0.14 },  // תוקן מ-77400
  { threshold: 120720, rate: 0.20 }, // תוקן מ-110880
  { threshold: 193800, rate: 0.31 }, // תוקן מ-178080
  { threshold: 269280, rate: 0.35 }, // תוקן מ-247440
  { threshold: 560280, rate: 0.47 }, // תוקן מ-514920
  { threshold: 721560, rate: 0.50 }  // תוקן מ-663240
];
```

### 3. Backend - `tax_calculator.py`
**קובץ**: `app/services/tax_calculator.py`

**תיקון**: שינוי אלגוריתם חישוב המס לעקוב אחרי `processed_income`

```python
# קוד חדש ונכון:
processed_income = 0.0

for bracket in self.tax_brackets:
    if processed_income >= taxable_income:
        break
    
    if bracket.max_income:
        income_in_bracket = min(
            taxable_income - processed_income,
            bracket.max_income - processed_income
        )
    else:
        income_in_bracket = taxable_income - processed_income
    
    if income_in_bracket > 0:
        tax_in_bracket = income_in_bracket * bracket.rate
        total_tax += tax_in_bracket
        processed_income += income_in_bracket
```

## מדרגות מס 2025 (נכונות)

| מדרגה | מינימום | מקסימום | שיעור מס |
|-------|---------|---------|----------|
| 1     | 0       | 84,120  | 10%      |
| 2     | 84,121  | 120,720 | 14%      |
| 3     | 120,721 | 193,800 | 20%      |
| 4     | 193,801 | 269,280 | 31%      |
| 5     | 269,281 | 560,280 | 35%      |
| 6     | 560,281 | 721,560 | 47%      |
| 7     | 721,561 | ∞       | 50%      |

## נקודות זיכוי

- **ערך נקודת זיכוי לשנת 2025**: 2,904 ₪ לשנה (242 ₪ לחודש)
- **ערך נקודת זיכוי לשנת 2024**: 2,640 ₪ לשנה

## בדיקות שבוצעו

1. ✅ בדיקת חישוב מס עבור הכנסה של 100,000 ₪
2. ✅ בדיקת חישוב מס עבור הכנסה של 99,996 ₪ (לקוח 1)
3. ✅ וידוא עקביות בין Backend ל-Frontend
4. ✅ וידוא שמדרגות המס נכונות בכל הקבצים

## השפעה על המערכת

תיקון זה משפיע על:
- ✅ חישוב מס בתזרים המזומנים
- ✅ חישוב מס על מענקי פיצויים
- ✅ חישוב מס על הכנסות נוספות
- ✅ כל התחזיות והדוחות הכספיים

## הוראות לבדיקה

1. רענן את הדפדפן (Ctrl+F5) כדי לטעון את הקוד המעודכן
2. בדוק את חישוב המס עבור לקוח 1 (8,333 ₪ לחודש)
3. וודא שהמס החודשי הוא **341.72 ₪** ולא 96 ₪
4. בדוק תרחישים נוספים עם הכנסות שונות

## מקורות

- מדרגות מס שנתיות ל-2025: [PwC Tax Summaries](https://taxsummaries.pwc.com/israel)
- שווי נקודת זיכוי בסיסית לשנת 2025: [Kol Zchut](https://www.kolzchut.org.il)
- הקפאת עדכוני מדרגות המס: [Goldfarb Gross Seligman](https://www.goldfarb.com)

---

**תאריך תיקון**: 7 בנובמבר 2025  
**סטטוס**: ✅ הושלם ונבדק
