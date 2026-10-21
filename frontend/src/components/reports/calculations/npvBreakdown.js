/**
 * V1-NPV-001: read-only decomposition of the existing report projection.
 * This module deliberately does NOT recalculate tax or change the cashflow engine.
 */
const amount = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const paymentYear = (value) => {
  if (!value) return null;
  const year = Number(String(value).slice(0, 4));
  return Number.isInteger(year) && year >= 1900 && year <= 2200 ? year : null;
};

/**
 * Annual cashflow rows are the authority for cashflow NPV and tax.
 * Capital assets with an explicit payment after the projection's base year
 * are independently discounted; assets with monthly_income are already in cashflow.
 *
 * @param {Array<any>} projection - generateYearlyProjection output
 * @param {Array<any>} capitalAssets - assets as returned by the report API
 * @param {number} pensionCount - number of pension sources in incomeBreakdown
 * @param {number} additionalIncomeCount - number of additional income sources
 * @param {number} discountRate - existing annual report rate (0.03)
 * @returns {{
 *   recurringNpv: number, projectedOneTimeNpv: number,
 *   reconciliationNpv: number,
 *   futureCapitalNpv: number, oneTimeNpv: number,
 *   remainingCapitalValue: number, cashflowNpv: number,
 *   totalEconomicValue: number, warnings: string[]
 * }}
 */
export function calculateNPVBreakdown(
  projection, capitalAssets, pensionCount, additionalIncomeCount, discountRate = 0.03
) {
  const warnings = [];
  if (!Array.isArray(projection) || projection.length === 0) {
    return {
      recurringNpv: 0, projectedOneTimeNpv: 0, reconciliationNpv: 0, futureCapitalNpv: 0,
      oneTimeNpv: 0, remainingCapitalValue: 0,
      cashflowNpv: 0, totalEconomicValue: 0, warnings,
    };
  }
  const baseYear = projection[0].year;
  const activeAssets = capitalAssets.filter(asset => amount(asset.monthly_income) > 0);
  let recurringNpv = 0;
  let projectedOneTimeNpv = 0;
  let reconciliationNpv = 0;
  const capitalOffset = pensionCount + additionalIncomeCount;

  projection.forEach((yearData, index) => {
    const annualNet = amount(yearData.netMonthlyIncome) * 12;
    const grossBreakdown = yearData.incomeBreakdown || [];
    const taxBreakdown = yearData.taxBreakdown || [];
    const totalDetailedTax = taxBreakdown.reduce((sum, tax) => sum + amount(tax), 0);
    // Each source and the total are rounded separately in V1. A 1 NIS tolerance
    // catches substantive discrepancies without suppressing the warning.
    const taxMismatch = Math.abs(totalDetailedTax - amount(yearData.totalMonthlyTax)) > Math.max(1, taxBreakdown.length / 2);
    if (taxMismatch) {
      warnings.push('אי התאמת מס בפירוט המקורות לשנת ' + yearData.year +
        ': מס מפורט ' + totalDetailedTax + ', מס כולל ' + amount(yearData.totalMonthlyTax));
    }

    let oneTimeMonthlyGross = 0;
    let oneTimeMonthlyTax = 0;
    activeAssets.forEach((asset, activeIndex) => {
      if (paymentYear(asset.start_date) !== yearData.year) return;
      const column = capitalOffset + activeIndex;
      oneTimeMonthlyGross += amount(grossBreakdown[column]);
      oneTimeMonthlyTax += amount(taxBreakdown[column]);
    });
    const projectedOneTimeAnnualNet = (oneTimeMonthlyGross - oneTimeMonthlyTax) * 12;
    const recurringMonthlyGross = grossBreakdown.slice(0, capitalOffset)
      .reduce((sum, value) => sum + amount(value), 0);
    const recurringMonthlyTax = taxBreakdown.slice(0, capitalOffset)
      .reduce((sum, value) => sum + amount(value), 0);
    const recurringAnnualNet = (recurringMonthlyGross - recurringMonthlyTax) * 12;
    const residualAnnual = annualNet - projectedOneTimeAnnualNet - recurringAnnualNet;
    const factor = Math.pow(1 + discountRate, index);
    projectedOneTimeNpv += projectedOneTimeAnnualNet / factor;
    recurringNpv += recurringAnnualNet / factor;
    // The report rounds each source and the total independently. Small rounding
    // differences are folded into the recurring component; larger differences
    // are surfaced separately, never mislabelled as pension income.
    if (!taxMismatch && Math.abs(residualAnnual / 12) <= Math.max(2, grossBreakdown.length / 2 + 1)) {
      recurringNpv += residualAnnual / factor;
    } else {
      reconciliationNpv += residualAnnual / factor;
      if (Math.abs(residualAnnual) > 12) {
        warnings.push('הפרש התאמה בין נטו כולל לפירוט לשנת ' + yearData.year +
          ': ' + residualAnnual + ' לשנה. לא סווג כהכנסה חוזרת.');
      }
    }
  });

  let futureCapitalNpv = 0;
  let remainingCapitalValue = 0;
  const maxProjectionYear = projection[projection.length - 1].year;
  capitalAssets.forEach(asset => {
    const capital = amount(asset.current_value);
    const payment = amount(asset.monthly_income);
    const year = paymentYear(asset.start_date);
    const name = String(asset.asset_name || asset.description || 'נכס ללא שם');
    if (payment > 0) {
      if (capital > 0) {
        warnings.push('נכס עם יתרה ותשלום באותה רשומה: ' + name +
          '. היתרה לא נספרה שוב, יש לבדוק את ייצוג המקור.');
      }
      if (year === null || year < baseYear || year > maxProjectionYear) {
        warnings.push('תשלום מחוץ לטווח התחזית: ' + name +
          '. אין לכלול אותו בהיוון ללא בירור.');
      }
      return;
    }
    if (capital <= 0) return;
    if (year !== null && year > baseYear && year <= maxProjectionYear) {
      futureCapitalNpv += capital / Math.pow(1 + discountRate, year - baseYear);
      if (asset.tax_treatment !== 'exempt') {
        warnings.push('תשלום הוני עתידי שלא חושב עבורו מס בדוח: ' + name +
          '. הערך המהוון מוצג לפני מס ולא כאישור זכאות.');
      }
    } else {
      // No confirmed future cashflow; preserve the existing asset value
      // without conflating it with pension NPV.
      remainingCapitalValue += capital;
      if (year !== null && year > maxProjectionYear) {
        warnings.push('נכס שתאריך תשלומו אחרי אופק התחזית: ' + name +
          '. מוצג כיתרת נכס ולא כתקבול מהוון.');
      }
    }
  });
  const cashflowNpv = recurringNpv + projectedOneTimeNpv + reconciliationNpv;
  const oneTimeNpv = projectedOneTimeNpv + futureCapitalNpv;
  return {
    recurringNpv, projectedOneTimeNpv, reconciliationNpv, futureCapitalNpv, oneTimeNpv,
    remainingCapitalValue, cashflowNpv,
    totalEconomicValue: cashflowNpv + futureCapitalNpv + remainingCapitalValue,
    warnings,
  };
}
