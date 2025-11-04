/**
 * חישובי NPV (Net Present Value) - ערך נוכחי נקי
 */

/**
 * מחשב את הערך הנוכחי הנקי (NPV) של תזרים מזומנים
 * @param cashFlows מערך של תזרימי מזומנים (ערך שלילי עבור השקעה ראשונית, חיובי עבור תקבולים)
 * @param discountRate שיעור היוון שנתי (למשל 0.05 עבור 5%)
 * @returns הערך הנוכחי הנקי (NPV)
 */
export function calculateNPV(cashFlows: number[], discountRate: number): number {
  return cashFlows.reduce((sum, cashFlow, year) => {
    return sum + (cashFlow / Math.pow(1 + discountRate, year));
  }, 0);
}

// ======= פונקציה לחישוב NPV עם ובלי פטורים =======
export function calculateNPVComparison(
  yearlyProjection: any[],
  discountRate: number = 0.03
): { withExemption: number; withoutExemption: number; savings: number } {
  // NPV עם פטור (מצב נוכחי - המס כבר מחושב עם קיזוז הקצבה הפטורה)
  const withExemption = yearlyProjection.reduce((sum, yearData, year) => {
    const annualNet = yearData.netMonthlyIncome * 12;
    return sum + (annualNet / Math.pow(1 + discountRate, year));
  }, 0);
  
  // NPV ללא פטור - חישוב מחדש של המס ללא קיזוז הקצבה הפטורה
  const withoutExemption = yearlyProjection.reduce((sum, yearData, year) => {
    const grossIncome = yearData.totalMonthlyIncome;
    const currentTax = yearData.totalMonthlyTax;
    const exemptPension = yearData.exemptPension || 0; // הקצבה הפטורה שמקזזת מההכנסה החייבת
    
    // אם אין פטור בשנה זו, ה-NPV זהה
    if (exemptPension === 0) {
      const annualNet = yearData.netMonthlyIncome * 12;
      return sum + (annualNet / Math.pow(1 + discountRate, year));
    }
    
    // חישוב מס נוסף על הקצבה הפטורה (שלא שולם בגלל הפטור)
    // הפטור גרם להפחתת ההכנסה החייבת, כלומר חסכנו מס על הסכום הזה
    // נניח מס שולי ממוצע של 31% (מדרגה רביעית)
    const additionalTax = exemptPension * 0.31;
    
    // הכנסה נטו ללא פטור = הכנסה נטו נוכחית - המס הנוסף שהיינו משלמים
    const netWithoutExemption = yearData.netMonthlyIncome - additionalTax;
    const annualNet = netWithoutExemption * 12;
    
    return sum + (annualNet / Math.pow(1 + discountRate, year));
  }, 0);
  
  return {
    withExemption,
    withoutExemption,
    savings: withExemption - withoutExemption
  };
}
