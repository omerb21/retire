/**
 * חישובי מס על מענקי פיצויים ופרישה
 */

/**
 * מחשב מס על סכום חייב במס עם אפשרות לפריסה
 * @param taxableAmount - הסכום החייב במס
 * @param spreadYears - מספר שנות הפריסה (1-6)
 * @returns המס השנתי והחודשי
 */
export const calculateTaxWithSpread = (
  taxableAmount: number,
  spreadYears: number = 1
): { annualTax: number; monthlyTax: number } => {
  if (taxableAmount <= 0 || spreadYears <= 0) {
    return { annualTax: 0, monthlyTax: 0 };
  }

  // חישוב הכנסה שנתית ממוצעת
  const annualIncome = taxableAmount / spreadYears;
  
  // מדרגות מס 2025 - מעודכן לערכים הנכונים
  const taxBrackets = [
    { threshold: 0, rate: 0.10 },
    { threshold: 84120, rate: 0.14 },
    { threshold: 120720, rate: 0.20 },
    { threshold: 193800, rate: 0.31 },
    { threshold: 269280, rate: 0.35 },
    { threshold: 560280, rate: 0.47 },
    { threshold: 721560, rate: 0.50 }
  ];

  let tax = 0;
  let remainingIncome = annualIncome;

  for (let i = 0; i < taxBrackets.length; i++) {
    const currentBracket = taxBrackets[i];
    const nextBracket = taxBrackets[i + 1];
    
    if (nextBracket) {
      const bracketSize = nextBracket.threshold - currentBracket.threshold;
      const taxableInBracket = Math.min(remainingIncome, bracketSize);
      tax += taxableInBracket * currentBracket.rate;
      remainingIncome -= taxableInBracket;
      
      if (remainingIncome <= 0) break;
    } else {
      // מדרגה אחרונה
      tax += remainingIncome * currentBracket.rate;
      break;
    }
  }

  const annualTax = Math.round(tax);
  const monthlyTax = Math.round(annualTax / 12);

  return { annualTax, monthlyTax };
};

/**
 * מחשב מס על מענק פיצויים מלא
 * @param exemptAmount - סכום פטור ממס
 * @param taxableAmount - סכום חייב במס
 * @param spreadYears - מספר שנות פריסה
 * @returns פירוט מס מלא
 */
export const calculateSeveranceTax = (
  exemptAmount: number,
  taxableAmount: number,
  spreadYears: number = 1
): {
  exemptAmount: number;
  taxableAmount: number;
  totalTax: number;
  annualTax: number;
  monthlyTax: number;
  spreadYears: number;
} => {
  const { annualTax, monthlyTax } = calculateTaxWithSpread(taxableAmount, spreadYears);
  const totalTax = annualTax * spreadYears;

  return {
    exemptAmount,
    taxableAmount,
    totalTax,
    annualTax,
    monthlyTax,
    spreadYears
  };
};

/**
 * מחשב מס שולי על הכנסה נוספת
 * @param baseIncome - הכנסה בסיסית
 * @param additionalIncome - הכנסה נוספת
 * @returns המס השולי על ההכנסה הנוספת
 */
export const calculateMarginalTax = (
  baseIncome: number,
  additionalIncome: number
): number => {
  const taxWithAdditional = calculateTaxWithSpread(baseIncome + additionalIncome, 1).annualTax;
  const taxWithoutAdditional = calculateTaxWithSpread(baseIncome, 1).annualTax;
  
  return taxWithAdditional - taxWithoutAdditional;
};
