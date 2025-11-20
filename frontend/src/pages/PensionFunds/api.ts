import { apiFetch } from '../../lib/api';
import { PensionFund, Commutation } from './types';

/**
 * טעינת קצבאות והיוונים עבור לקוח
 */
export async function loadPensionFunds(clientId: string): Promise<{
  funds: PensionFund[];
  commutations: Commutation[];
}> {
  try {
    // Load pension funds (includes all pensions from termination decisions)
    const data = await apiFetch<PensionFund[]>(`/clients/${clientId}/pension-funds`);
    console.log("Loaded pension funds:", data);
    
    // מיפוי שדות לפורמט אחיד - השרת מחזיר את balance המקורי!
    const mappedFunds = (data || []).map(fund => {
      return {
        ...fund,
        pension_start_date: fund.pension_start_date || fund.start_date,
        commutable_balance: fund.balance || fund.current_balance || 0 // יתרה להיוון מהשרת
      };
    });
    
    // טעינת היוונים מנכסים הוניים
    let loadedCommutations: Commutation[] = [];
    try {
      const capitalAssets = await apiFetch<any[]>(`/clients/${clientId}/capital-assets`);
      console.log("Loaded capital assets:", capitalAssets);
      
      // סינון נכסים שהם היוונים (יש להם COMMUTATION ב-remarks)
      const commutationAssets = (capitalAssets || []).filter(asset => 
        asset.remarks && asset.remarks.includes('COMMUTATION:')
      );
      
      // המרה לפורמט Commutation
      loadedCommutations = commutationAssets.map(asset => {
        // חילוץ pension_fund_id מה-remarks
        const match = asset.remarks.match(/pension_fund_id=(\d+)/);
        const pensionFundId = match ? parseInt(match[1]) : undefined;
        
        // חילוץ amount מה-remarks
        const amountMatch = asset.remarks.match(/amount=([\d.]+)/);
        const amount = amountMatch ? parseFloat(amountMatch[1]) : asset.current_value;

        // ניסיון לקרוא צילום קצבה מקורית מתוך conversion_source (אם קיים)
        let originalPension: PensionFund | undefined;
        if (asset.conversion_source) {
          try {
            const sourceData = JSON.parse(asset.conversion_source);
            if (sourceData && sourceData.type === 'pension_commutation' && sourceData.original_pension) {
              originalPension = sourceData.original_pension as PensionFund;
            }
          } catch (e) {
            console.error('Error parsing conversion_source for commutation asset:', e);
          }
        }
        
        return {
          id: asset.id,
          pension_fund_id: pensionFundId,
          exempt_amount: amount,
          commutation_date: asset.start_date || asset.purchase_date,
          commutation_type: asset.tax_treatment === "exempt" ? "exempt" : "taxable",
          original_pension: originalPension
        };
      });
      
      console.log("Loaded commutations:", loadedCommutations);
    } catch (commutationError) {
      console.error("Error loading commutations:", commutationError);
      // לא נכשל את כל הטעינה אם יש בעיה בטעינת היוונים
      loadedCommutations = [];
    }
    
    return {
      funds: mappedFunds,
      commutations: loadedCommutations
    };
  } catch (e: any) {
    throw new Error(`שגיאה בטעינת קצבאות: ${e?.message || e}`);
  }
}

/**
 * טעינת נתוני לקוח
 */
export async function loadClientData(clientId: string): Promise<any> {
  try {
    const data = await apiFetch<any>(`/clients/${clientId}`);
    return data;
  } catch (error) {
    console.error("Error fetching client data:", error);
    throw error;
  }
}

/**
 * שמירת קצבה (יצירה או עדכון)
 */
export async function savePensionFund(
  clientId: string,
  payload: Record<string, any>,
  editingFundId: number | null
): Promise<void> {
  if (editingFundId) {
    // עדכון קצבה קיימת
    console.log(`מעדכן קצבה קיימת עם מזהה: ${editingFundId}`);
    await apiFetch(`/pension-funds/${editingFundId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  } else {
    // יצירת קצבה חדשה
    console.log("יוצר קצבה חדשה");
    await apiFetch(`/clients/${clientId}/pension-funds`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
}

/**
 * חישוב קצבה חודשית
 */
export async function computePensionFund(clientId: string, fundId: number): Promise<void> {
  await apiFetch(`/clients/${clientId}/pension-funds/${fundId}/compute`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

/**
 * מחיקת קצבה
 */
export async function deletePensionFund(clientId: string, fundId: number): Promise<any> {
  return await apiFetch(`/clients/${clientId}/pension-funds/${fundId}`, {
    method: 'DELETE'
  });
}

/**
 * מחיקת היוון (נכס הוני)
 */
export async function deleteCommutation(clientId: string, commutationId: number): Promise<void> {
  await apiFetch(`/clients/${clientId}/capital-assets/${commutationId}`, {
    method: 'DELETE'
  });
}

/**
 * יצירת נכס הוני (היוון)
 */
export async function createCapitalAsset(clientId: string, data: any): Promise<any> {
  return await apiFetch(`/clients/${clientId}/capital-assets/`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

/**
 * שליפת נכס הוני בודד (לצורך שחזור קצבה מהמרה)
 */
export async function getCapitalAsset(clientId: string, assetId: number): Promise<any> {
  return await apiFetch<any>(`/clients/${clientId}/capital-assets/${assetId}`);
}

/**
 * עדכון קצבה
 */
export async function updatePensionFund(fundId: number, data: any): Promise<void> {
  await apiFetch(`/pension-funds/${fundId}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  });
}

/**
 * עדכון תאריך הקצבה הראשונה של הלקוח
 */
export async function updateClientPensionStartDate(
  clientId: string,
  pensionStartDate: string | null
): Promise<void> {
  await apiFetch(`/clients/${clientId}`, {
    method: "PUT",
    body: JSON.stringify({
      pension_start_date: pensionStartDate
    }),
  });
}
