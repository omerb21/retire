import { formatCurrency } from '../../../lib/validation';
import {
  PensionSummary,
  GrantSummary,
  ExemptionSummary,
  Commutation,
  FixationData
} from '../types';
import { loadPensionCeilingsFromStorage } from '../../../services/systemSettingsStorageService';

export const formatMoney = (value: number): string => {
  const formatted = formatCurrency(value);
  return formatted.replace('₪', '').trim();
};

export const getPensionCeiling = (year: number): number => {
  try {
    const ceilings = loadPensionCeilingsFromStorage();

    if (Array.isArray(ceilings) && ceilings.length > 0) {
      const exactMatch = ceilings.find((item) => item.year === year);

      if (exactMatch) {
        return exactMatch.monthly_ceiling;
      }

      const sortedByYearDesc = [...ceilings].sort((a, b) => b.year - a.year);
      return sortedByYearDesc[0].monthly_ceiling;
    }
  } catch (e) {
    console.error('Error loading pensionCeilings from storage in fixationCalculations:', e);
  }

  const fallbackCeilings: { [key: number]: number } = {
    2025: 9430,
    2024: 9430,
    2023: 9120,
    2022: 8660,
    2021: 8460,
    2020: 8510,
    2019: 8480,
    2018: 8380
  };

  return fallbackCeilings[year] || 9430;
};

export const calculatePensionSummary = (
  grantsSummary: GrantSummary[],
  exemptionSummary: ExemptionSummary | null,
  futureGrantReserved: number,
  commutations: Commutation[],
  fixationData: FixationData | null,
  idfCommutationId?: number | null
): PensionSummary => {
  console.log('DEBUG: calculatePensionSummary called');
  console.log('DEBUG: grantsSummary:', grantsSummary);
  console.log('DEBUG: grantsSummary.length:', grantsSummary.length);
  console.log('DEBUG: exemptionSummary:', exemptionSummary);

  const exemptAmount = exemptionSummary?.exempt_capital_initial || 0;
  const remainingExemptCapital = exemptionSummary?.remaining_exempt_capital || 0;
  const exemptionPercentage = exemptionSummary?.exemption_percentage || 0;
  const idfImpact =
    typeof exemptionSummary?.idf_security_forces_impact === 'number'
      ? exemptionSummary!.idf_security_forces_impact
      : 0;

  const includedGrants = grantsSummary.filter((grant) =>
    !(grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) &&
    !grant.exclusion_reason
  );

  console.log('DEBUG: includedGrants:', includedGrants);

  const totalGrants = includedGrants.reduce((sum, grant) => sum + grant.grant_amount, 0);
  const totalIndexed = includedGrants.reduce((sum, grant) => sum + (grant.indexed_full || 0), 0);

  const totalImpact = includedGrants.reduce((sum, grant) => sum + (grant.impact_on_exemption || 0), 0);

  console.log('DEBUG: exemptAmount:', exemptAmount);
  console.log('DEBUG: remainingExemptCapital:', remainingExemptCapital);
  console.log('DEBUG: exemptionPercentage:', exemptionPercentage);
  console.log('DEBUG: totalGrants:', totalGrants);
  console.log('DEBUG: totalIndexed:', totalIndexed);
  console.log('DEBUG: totalImpact:', totalImpact);

  const usedExemption = totalImpact;
  const futureGrantImpact = futureGrantReserved * 1.35;

  // לפורשי צה״ל: ההיוון הצה״לי לא נכלל ב"סך היוונים" הרגילים
  // הפגיעה שלו מחושבת בנפרד לפי נוסחת צה״ל (idf_security_forces_impact)
  const filteredCommutations = idfCommutationId
    ? commutations.filter((c) => c.id !== idfCommutationId)
    : commutations;

  const totalDiscounts = filteredCommutations.reduce(
    (sum, commutation) => sum + (commutation.exempt_amount || 0),
    0
  );
  console.log('DEBUG: totalDiscounts from commutations (excluding IDF):', totalDiscounts);

  // לפורשי צה״ל: הפגיעה מחושבת לפי נוסחת צה״ל (idfImpact) במקום הקיזוז הרגיל של ההיוון
  // היתרה מופחתת ב: מענק עתידי + היוונים רגילים (לא כולל צה״ל) + פגיעת צה״ל (אם יש)
  const remainingExemption = remainingExemptCapital - futureGrantImpact - totalDiscounts - idfImpact;

  const eligibilityYear = fixationData?.eligibility_year || new Date().getFullYear();
  const pensionCeiling = getPensionCeiling(eligibilityYear);

  const baseAmount = remainingExemption / 180;
  const percentage = pensionCeiling > 0 ? (baseAmount / pensionCeiling) * 100 : 0;

  return {
    exempt_amount: exemptAmount,
    total_grants: totalGrants,
    total_indexed: totalIndexed,
    used_exemption: usedExemption,
    future_grant_reserved: futureGrantReserved,
    future_grant_impact: futureGrantImpact,
    total_discounts: totalDiscounts,
    remaining_exemption: remainingExemption,
    pension_ceiling: pensionCeiling,
    exempt_pension_calculated: {
      base_amount: baseAmount,
      percentage: percentage
    },
    idf_security_forces_impact: idfImpact
  };
};
