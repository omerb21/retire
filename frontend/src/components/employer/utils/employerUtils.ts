/**
 * פונקציות עזר לניהול מעסיק נוכחי
 */

import { SimpleEmployer, PensionAccount } from '../types/employerTypes';
import { convertISOToDDMMYY } from '../../../utils/dateUtils';
import { loadPensionDataFromStorage } from '../../../pages/PensionPortfolio/services/pensionPortfolioStorageService';
import {
  isTerminationConfirmed as baseIsTerminationConfirmed,
  setTerminationConfirmed as baseSetTerminationConfirmed,
  saveOriginalSeveranceAmount as baseSaveOriginalSeveranceAmount,
  loadOriginalSeveranceAmount as baseLoadOriginalSeveranceAmount,
} from '../../../pages/SimpleCurrentEmployer/utils/storageHelpers';

/**
 * טוען יתרת פיצויים מתיק פנסיוני מ-localStorage
 */
export const loadSeveranceFromPension = (clientId: string): number => {
  const pensionData = loadPensionDataFromStorage(clientId);

  if (!pensionData || pensionData.length === 0) {
    console.log('לא נמצא תיק פנסיוני ב-localStorage עבור לקוח:', clientId);
    return 0;
  }

  try {
    // Sum all severance amounts from "פיצויים מעסיק נוכחי" column
    const severanceFromPension = pensionData.reduce((sum: number, account: PensionAccount) => {
      const currentEmployerSeverance = Number(account.פיצויים_מעסיק_נוכחי || 0);
      return sum + currentEmployerSeverance;
    }, 0);

    console.log('יתרת פיצויים מתיק פנסיוני:', severanceFromPension);
    console.log('מספר חשבונות:', pensionData.length);

    pensionData.forEach((acc: PensionAccount, idx: number) => {
      console.log(`חשבון ${idx + 1}: פיצויים מעסיק נוכחי = ${acc.פיצויים_מעסיק_נוכחי || 0}`);
    });

    return severanceFromPension;
  } catch (e) {
    console.error('שגיאה בטעינת נתוני תיק פנסיוני:', e);
    return 0;
  }
};

/**
 * בדיקה אם עזיבה אושרה
 */
export const isTerminationConfirmed = (clientId: string): boolean => {
  return baseIsTerminationConfirmed(clientId);
};

/**
 * סימון עזיבה כמאושרת
 */
export const setTerminationConfirmed = (clientId: string, confirmed: boolean): void => {
  baseSetTerminationConfirmed(clientId, confirmed);
};

/**
 * שמירת סכום פיצויים מקורי
 */
export const saveOriginalSeveranceAmount = (clientId: string, amount: number): void => {
  baseSaveOriginalSeveranceAmount(clientId, amount);
  console.log(`💾 שמירת סכום פיצויים מקורי: ${amount}`);
};

/**
 * טעינת סכום פיצויים מקורי
 */
export const loadOriginalSeveranceAmount = (clientId: string): number => {
  return baseLoadOriginalSeveranceAmount(clientId);
};

/**
 * המרת נתוני מעסיק מ-API לפורמט הקומפוננטה
 */
export const formatEmployerData = (
  employerData: any,
  severanceAccrued: number
): SimpleEmployer => {
  return {
    id: employerData.id,
    employer_name: employerData.employer_name || '',
    start_date: employerData.start_date || '',
    end_date: employerData.end_date ? convertISOToDDMMYY(employerData.end_date) : undefined,
    last_salary: Number(
      employerData.monthly_salary || 
      employerData.last_salary || 
      employerData.average_salary || 
      0
    ),
    severance_accrued: severanceAccrued,
    employer_completion: employerData.employer_completion,
    service_years: employerData.service_years,
    expected_grant_amount: employerData.expected_grant_amount,
    tax_exempt_amount: employerData.tax_exempt_amount,
    taxable_amount: employerData.taxable_amount
  };
};

/**
 * אימות תקינות נתוני מעסיק
 */
export const validateEmployerData = (employer: SimpleEmployer): string[] => {
  const errors: string[] = [];
  
  if (!employer.employer_name || employer.employer_name.trim() === '') {
    errors.push('שם מעסיק חובה');
  }
  
  if (!employer.start_date) {
    errors.push('תאריך תחילת עבודה חובה');
  }
  
  if (employer.last_salary <= 0) {
    errors.push('שכר חודשי חייב להיות גדול מאפס');
  }
  
  return errors;
};

/**
 * אימות תקינות החלטת עזיבה
 */
export const validateTerminationDecision = (
  terminationDate: string,
  startDate: string
): string[] => {
  const errors: string[] = [];
  
  if (!terminationDate || terminationDate.length < 10) {
    errors.push('תאריך עזיבה חובה');
  }
  
  if (terminationDate && startDate) {
    // המרת תאריכים להשוואה
    const termDate = new Date(terminationDate.split('/').reverse().join('-'));
    const stDate = new Date(startDate.split('/').reverse().join('-'));
    
    if (termDate < stDate) {
      errors.push('תאריך עזיבה לא יכול להיות לפני תאריך תחילת עבודה');
    }
  }
  
  return errors;
};
