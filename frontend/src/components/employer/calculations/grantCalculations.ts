/**
 * חישובי מענקי פיצויים ופרישה
 */

import { GrantDetails } from '../types/employerTypes';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

/**
 * מחשב שנות ותק בין שני תאריכים
 */
export const calculateServiceYears = (startDate: Date, endDate: Date): number => {
  const timeDiff = endDate.getTime() - startDate.getTime();
  return timeDiff / (1000 * 60 * 60 * 24 * 365.25);
};

/**
 * מחשב מספר שנות פריסת מס מקסימלי לפי וותק
 */
export const calculateMaxSpreadYears = (serviceYears: number): number => {
  if (serviceYears >= 22) return 6;
  if (serviceYears >= 18) return 5;
  if (serviceYears >= 14) return 4;
  if (serviceYears >= 10) return 3;
  if (serviceYears >= 6) return 2;
  if (serviceYears >= 2) return 1;
  return 0;
};

/**
 * מחשב פרטי מענק פיצויים באמצעות API
 */
export const calculateGrantDetailsAPI = async (
  startDate: string,
  lastSalary: number,
  severanceAccrued: number
): Promise<GrantDetails> => {
  try {
    const response = await fetch(`${API_BASE}/current-employer/calculate-severance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        start_date: startDate,
        last_salary: lastSalary
      })
    });

    if (!response.ok) {
      throw new Error('API call failed');
    }

    const calculation = await response.json();
    
    // תיקון לוגיקה: אם יתרת הפיצויים גבוהה מהמענק הצפוי, המענק הצפוי מקבל את הערך של יתרת הפיצויים
    const actualExpectedGrant = Math.max(calculation.severance_amount, severanceAccrued);
    
    // חישוב השלמת המעסיק = סכום המענק הצפוי פחות יתרת פיצויים נצברת
    const employerCompletion = Math.max(0, actualExpectedGrant - severanceAccrued);
    
    console.log('💰 Grant calculation (API):', {
      calculated_grant: calculation.severance_amount,
      severance_accrued: severanceAccrued,
      actual_expected_grant: actualExpectedGrant,
      employer_completion: employerCompletion
    });
    
    return {
      serviceYears: calculation.service_years || 0,
      expectedGrant: actualExpectedGrant || 0,
      taxExemptAmount: calculation.exempt_amount || 0,
      taxableAmount: calculation.taxable_amount || 0,
      severanceCap: calculation.annual_exemption_cap || 165240
    };
  } catch (error) {
    console.error('Error in API grant calculation:', error);
    throw error;
  }
};

/**
 * מחשב פרטי מענק פיצויים - חישוב fallback מקומי
 */
export const calculateGrantDetailsFallback = (
  startDate: string,
  lastSalary: number,
  severanceAccrued: number
): GrantDetails => {
  // המרת תאריך מ-DD/MM/YYYY ל-ISO אם צריך
  let startISO = startDate.includes('/') 
    ? startDate.split('/').reverse().join('-') 
    : startDate;
  
  const start = new Date(startISO);
  const now = new Date();
  
  const serviceYears = calculateServiceYears(start, now);
  
  // Basic severance calculation (1 month salary per year)
  const expectedGrant = lastSalary * serviceYears;
  
  // תקרת פטור למענקי פרישה 2025
  const currentYearCap = 13750;
  const severanceExemption = currentYearCap * serviceYears;
  
  // תיקון לוגיקה: אם יתרת הפיצויים גבוהה מהמענק הצפוי, המענק הצפוי מקבל את הערך של יתרת הפיצויים
  const actualExpectedGrant = Math.max(Math.round(expectedGrant), severanceAccrued);
  
  const taxExemptAmount = Math.min(actualExpectedGrant, severanceExemption);
  const taxableAmount = Math.max(0, actualExpectedGrant - taxExemptAmount);
  
  // חישוב השלמת המעסיק = סכום המענק הצפוי פחות יתרת פיצויים נצברת
  const employerCompletion = Math.max(0, actualExpectedGrant - severanceAccrued);
  
  console.log('💰 Grant calculation (Fallback):', {
    calculated_grant: Math.round(expectedGrant),
    severance_accrued: severanceAccrued,
    actual_expected_grant: actualExpectedGrant,
    employer_completion: employerCompletion
  });
  
  return {
    serviceYears: Math.round(serviceYears * 100) / 100,
    expectedGrant: actualExpectedGrant,
    taxExemptAmount: Math.round(taxExemptAmount),
    taxableAmount: Math.round(taxableAmount),
    severanceCap: currentYearCap
  };
};

/**
 * מחשב פרטי מענק פיצויים - מנסה API ואם נכשל עובר ל-fallback
 */
export const calculateGrantDetails = async (
  startDate: string,
  lastSalary: number,
  severanceAccrued: number
): Promise<GrantDetails> => {
  try {
    return await calculateGrantDetailsAPI(startDate, lastSalary, severanceAccrued);
  } catch (error) {
    console.warn('API calculation failed, using fallback:', error);
    return calculateGrantDetailsFallback(startDate, lastSalary, severanceAccrued);
  }
};
