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
  yearlyProjectionWithExemption: any[],
  yearlyProjectionWithoutExemption: any[],
  discountRate: number = 0.03,
  fixationData?: any
): { withExemption: number; withoutExemption: number; savings: number } {
  // NPV עם קיבוע זכויות – התזרים המלא לאחר קיבוע (קצבאות, הכנסות נוספות והיוונים פטורים)
  const withExemption = yearlyProjectionWithExemption.reduce(
    (sum, yearData, yearIndex) => {
      const annualNet = yearData.netMonthlyIncome * 12;
      return sum + annualNet / Math.pow(1 + discountRate, yearIndex);
    },
    0
  );

  // NPV ללא קיבוע זכויות – אותה תחזית אבל ללא קצבה פטורה וללא הטבה ממס על היוונים
  const withoutExemption = yearlyProjectionWithoutExemption.reduce(
    (sum, yearData, yearIndex) => {
      const annualNet = yearData.netMonthlyIncome * 12;
      return sum + annualNet / Math.pow(1 + discountRate, yearIndex);
    },
    0
  );

  return {
    withExemption,
    withoutExemption,
    // חיסכון מקיבוע = NPV(עם קיבוע מלא) - NPV(בלי קיבוע כלל)
    savings: withExemption - withoutExemption,
  };
}
