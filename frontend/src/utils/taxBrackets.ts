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
  { id: 1, minMonthly: 0, maxMonthly: 7000, minAnnual: 0, maxAnnual: 84000, rate: 14 },
  { id: 2, minMonthly: 7001, maxMonthly: 17140, minAnnual: 84001, maxAnnual: 205680, rate: 20 },
  { id: 3, minMonthly: 17141, maxMonthly: 33640, minAnnual: 205681, maxAnnual: 403680, rate: 31 },
  { id: 4, minMonthly: 33641, maxMonthly: 54600, minAnnual: 403681, maxAnnual: 655200, rate: 35 },
  { id: 5, minMonthly: 54601, maxMonthly: Infinity, minAnnual: 655201, maxAnnual: Infinity, rate: 47 }
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
  // כל השנים משתמשות באותן מדרגות כרגע (2025)
  // בעתיד, כאן יהיה קוד לטעינת מדרגות שנה-ספציפיות
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
