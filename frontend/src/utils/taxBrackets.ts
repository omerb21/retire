export interface TaxBracket {
  id: number;
  minMonthly: number;
  maxMonthly: number;
  minAnnual: number;
  maxAnnual: number;
  rate: number;
}

// מדרגות המס הברירת מחדל לשנת 2025
export const DEFAULT_TAX_BRACKETS: TaxBracket[] = [
  { id: 1, minMonthly: 0, maxMonthly: 7010, minAnnual: 0, maxAnnual: 84120, rate: 10 },
  { id: 2, minMonthly: 7011, maxMonthly: 10060, minAnnual: 84121, maxAnnual: 120720, rate: 14 },
  { id: 3, minMonthly: 10061, maxMonthly: 16150, minAnnual: 120721, maxAnnual: 193800, rate: 20 },
  { id: 4, minMonthly: 16151, maxMonthly: 22440, minAnnual: 193801, maxAnnual: 269280, rate: 31 },
  { id: 5, minMonthly: 22441, maxMonthly: 46690, minAnnual: 269281, maxAnnual: 560280, rate: 35 },
  { id: 6, minMonthly: 46691, maxMonthly: 60130, minAnnual: 560281, maxAnnual: 721560, rate: 47 },
  { id: 7, minMonthly: 60131, maxMonthly: Infinity, minAnnual: 721561, maxAnnual: Infinity, rate: 50 }
];

/**
 * טוען את מדרגות המס מההגדרות או מחזיר ברירת מחדל
 */
export const getTaxBrackets = (): TaxBracket[] => {
  try {
    const savedBrackets = localStorage.getItem('taxBrackets');
    if (savedBrackets) {
      const parsed = JSON.parse(savedBrackets);
      // וידוא שהמבנה תקין
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (error) {
    console.warn('שגיאה בטעינת מדרגות המס מההגדרות:', error);
  }
  
  return DEFAULT_TAX_BRACKETS;
};

/**
 * המרת מדרגות המס לפורמט הישן לתאימות לאחור
 */
export const getTaxBracketsLegacyFormat = (year?: number) => {
  // Use sync version for legacy compatibility
  const brackets = getTaxBrackets();
  return brackets.map(bracket => ({
    min: bracket.minAnnual,
    max: bracket.maxAnnual,
    rate: bracket.rate / 100 // המרה מאחוזים לעשרוני
  }));
};

/**
 * חישוב מס לפי מדרגות המס המעודכנות
 */
export const calculateTaxByBrackets = (annualIncome: number, year?: number): number => {
  if (annualIncome <= 0) return 0;
  
  // קבלת מדרגות המס - אם לא צוינה שנה, משתמשים בברירת מחדל
  let brackets = getTaxBracketsLegacyFormat(year);
  
  let totalTax = 0;
  let currentIncome = 0;
  
  for (const bracket of brackets) {
    if (annualIncome <= currentIncome) break;
    
    const bracketStart = bracket.min;
    const bracketEnd = bracket.max;
    const incomeInBracket = Math.min(annualIncome, bracketEnd) - Math.max(currentIncome, bracketStart);
    
    if (incomeInBracket > 0) {
      totalTax += incomeInBracket * bracket.rate;
    }
    
    currentIncome = bracketEnd;
  }
  
  return totalTax;
};
