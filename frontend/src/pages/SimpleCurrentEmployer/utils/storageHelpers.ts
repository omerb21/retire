/**
 * LocalStorage helper utilities for SimpleCurrentEmployer
 */

import { PlanDetail } from '../types';
import {
  loadPensionDataFromStorage,
  updatePensionDataInStorage,
} from '../../PensionPortfolio/services/pensionPortfolioStorageService';

/**
 * Get severance from pension portfolio localStorage
 */
export const getSeveranceFromPension = (clientId: string): number => {
  const terminationConfirmed = isTerminationConfirmed(clientId);
  if (terminationConfirmed) {
    const savedDistribution = localStorage.getItem(`severanceDistribution_${clientId}`);
    if (savedDistribution) {
      try {
        const distribution = JSON.parse(savedDistribution);
        if (distribution && typeof distribution === 'object') {
          const severanceFromDistribution = Object.values(distribution).reduce(
            (sum: number, value: any) => sum + Number(value || 0),
            0
          );
          console.log('יתרת פיצויים (מהתפלגות שמורה):', severanceFromDistribution);
          return severanceFromDistribution;
        }
      } catch (e) {
        console.warn('שגיאה בקריאת התפלגות פיצויים שמורה:', e);
      }
    }
  }

  const pensionData = loadPensionDataFromStorage(clientId);

  if (!pensionData || pensionData.length === 0) {
    console.log('לא נמצא תיק פנסיוני ב-localStorage עבור לקוח:', clientId);
    return 0;
  }

  try {
    const severanceFromPension = pensionData.reduce((sum: number, account: any) => {
      const currentEmployerSeverance = Number(account.פיצויים_מעסיק_נוכחי || 0);
      return sum + currentEmployerSeverance;
    }, 0);

    console.log('יתרת פיצויים מתיק פנסיוני:', severanceFromPension);
    console.log('מספר חשבונות:', pensionData.length);

    return severanceFromPension;
  } catch (e) {
    console.error('שגיאה בטעינת נתוני תיק פנסיוני:', e);
    return 0;
  }
};

/**
 * Save severance distribution before termination
 */
export const saveSeveranceDistribution = (clientId: string): {
  sourceAccountNames: string[];
  planDetails: PlanDetail[];
} => {
  const sourceAccountNames: string[] = [];
  const planDetails: PlanDetail[] = [];
  
  const pensionData = loadPensionDataFromStorage(clientId);

  if (!pensionData || pensionData.length === 0) {
    return { sourceAccountNames, planDetails };
  }
  
  try {
    const distribution: { [key: string]: number } = {};
    let totalSeverance = 0;
    
    pensionData.forEach((account: any, idx: number) => {
      const amount = Number(account.פיצויים_מעסיק_נוכחי) || 0;
      if (amount > 0) {
        const accountName = account.שם_תכנית || account.שם_מוצר || `חשבון ${idx + 1}`;
        sourceAccountNames.push(accountName);
        
        planDetails.push({
          plan_name: accountName,
          plan_start_date: account.תאריך_התחלה || null,
          product_type: account.שם_מוצר || account.סוג_מוצר || 'קופת גמל',
          amount: amount
        });
      }
      
      const accountKey = account.מספר_חשבון || `account_${idx}`;
      distribution[accountKey] = amount;
      totalSeverance += amount;
    });
    
    console.log('💾 שמירת התפלגות מדויקת לפני עזיבה:', distribution);
    console.log('💾 סכום כולל:', totalSeverance);
    console.log('📋 שמות תכניות מקור:', sourceAccountNames);
    console.log('📋 פרטי תכניות מלאים:', planDetails);
    
    localStorage.setItem(`severanceDistribution_${clientId}`, JSON.stringify(distribution));
  } catch (e) {
    console.error('שגיאה בשמירת התפלגות פיצויים:', e);
  }
  
  return { sourceAccountNames, planDetails };
};

/**
 * Clear severance from pension portfolio
 */
export const clearSeveranceFromPension = (clientId: string): void => {
  try {
    updatePensionDataInStorage(clientId, (pensionData) => {
      const updatedPensionData = pensionData.map((account: any) => ({
        ...account,
        פיצויים_מעסיק_נוכחי: 0,
      }));

      return updatedPensionData;
    });
    console.log('✅ פיצויים מעסיק נוכחי אופסו בתיק הפנסיוני');
  } catch (e) {
    console.error('שגיאה במחיקת פיצויים מתיק פנסיוני:', e);
  }
};

/**
 * Restore severance to pension portfolio
 */
export const restoreSeveranceToPension = (clientId: string): number => {
  const savedDistribution = localStorage.getItem(`severanceDistribution_${clientId}`);
  
  let severanceToRestore = 0;
  
  if (!savedDistribution) {
    console.log('⚠️ לא נמצאה התפלגות שמורה');
    return 0;
  }
  
  try {
    const distribution = JSON.parse(savedDistribution);
    
    console.log('📦 התפלגות מקורית:', distribution);

    updatePensionDataInStorage(clientId, (pensionData) => {
      const updatedPensionData = pensionData.map((account: any, idx: number) => {
        const accountKey = account.מספר_חשבון || `account_${idx}`;
        const originalAmount = distribution[accountKey] || 0;

        console.log(
          `  חשבון ${account.שם_תכנית} (${accountKey}): ${account.פיצויים_מעסיק_נוכחי || 0} → ${originalAmount}`
        );
        severanceToRestore += originalAmount;

        return {
          ...account,
          פיצויים_מעסיק_נוכחי: originalAmount,
        };
      });

      return updatedPensionData;
    });
    console.log('✅ פיצויים מעסיק נוכחי הוחזרו לתיק הפנסיוני:', severanceToRestore);
  } catch (e) {
    console.error('שגיאה בהחזרת פיצויים לתיק פנסיוני:', e);
  }
  
  return severanceToRestore;
};

/**
 * Check if termination is confirmed
 */
export const isTerminationConfirmed = (clientId: string): boolean => {
  const terminationStorageKey = `terminationConfirmed_${clientId}`;
  return localStorage.getItem(terminationStorageKey) === 'true';
};

/**
 * Get employer completion preference for scenarios and termination
 */
export const getEmployerCompletionPreference = (clientId: string): boolean => {
  const key = `employerCompletion_${clientId}`;
  return localStorage.getItem(key) === 'true';
};

/**
 * Set employer completion preference for scenarios and termination
 */
export const setEmployerCompletionPreference = (
  clientId: string,
  useCompletion: boolean
): void => {
  const key = `employerCompletion_${clientId}`;
  if (useCompletion) {
    localStorage.setItem(key, 'true');
  } else {
    localStorage.removeItem(key);
  }
};

/**
 * Set termination confirmed status
 */
export const setTerminationConfirmed = (clientId: string, confirmed: boolean): void => {
  const terminationStorageKey = `terminationConfirmed_${clientId}`;
  if (confirmed) {
    localStorage.setItem(terminationStorageKey, 'true');
  } else {
    localStorage.removeItem(terminationStorageKey);
  }
};

/**
 * Clear termination state
 */
export const clearTerminationState = (clientId: string): void => {
  const terminationStorageKey = `terminationConfirmed_${clientId}`;
  const severanceStorageKey = `originalSeverance_${clientId}`;
  const distributionKey = `severanceDistribution_${clientId}`;
  
  localStorage.removeItem(terminationStorageKey);
  localStorage.removeItem(severanceStorageKey);
  localStorage.removeItem(distributionKey);
};

/**
 * Save original severance amount
 */
export const saveOriginalSeveranceAmount = (clientId: string, amount: number): void => {
  const severanceStorageKey = `originalSeverance_${clientId}`;
  localStorage.setItem(severanceStorageKey, amount.toString());
};

/**
 * Load original severance amount
 */
export const loadOriginalSeveranceAmount = (clientId: string): number => {
  const severanceStorageKey = `originalSeverance_${clientId}`;
  const stored = localStorage.getItem(severanceStorageKey);
  return stored ? Number(stored) : 0;
};
