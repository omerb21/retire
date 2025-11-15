import { PensionFund, Commutation } from './types';
import { calculateOriginalBalance } from './utils';
import { formatCurrency } from '../../lib/validation';
import {
  loadPensionFunds,
  savePensionFund,
  computePensionFund,
  deletePensionFund,
  deleteCommutation,
  createCapitalAsset,
  updatePensionFund,
  updateClientPensionStartDate
} from './api';
import { convertDDMMYYToISO } from '../../utils/dateUtils';

/**
 * Helper: מחשב ומעדכן את תאריך הקצבה הראשונה של הלקוח
 * לפי התאריך המוקדם ביותר מבין כל הקצבאות הפעילות.
 */
export async function recalculateClientPensionStartDate(clientId: string): Promise<void> {
  const updatedFunds = await loadPensionFunds(clientId);

  if (updatedFunds.funds && updatedFunds.funds.length > 0) {
    const sortedFunds = [...updatedFunds.funds].sort((a, b) => {
      const dateA = a.pension_start_date || a.start_date || '';
      const dateB = b.pension_start_date || b.start_date || '';
      return dateA.localeCompare(dateB);
    });

    const earliestDate = sortedFunds[0].pension_start_date || sortedFunds[0].start_date || null;

    if (earliestDate) {
      await updateClientPensionStartDate(clientId, earliestDate);
    }
  } else {
    // אין קצבאות כלל - ננקה את התאריך ברמת הלקוח
    await updateClientPensionStartDate(clientId, null);
  }
}

export async function handleSubmitPensionFund(
  clientId: string,
  form: Partial<PensionFund>,
  editingFundId: number | null,
  funds: PensionFund[],
  clientData: any
): Promise<void> {
  // Basic validation
  if (!form.fund_name || form.fund_name.trim() === "") {
    throw new Error("חובה למלא שם משלם");
  }

  if (form.calculation_mode === "calculated") {
    if (!form.balance || form.balance <= 0) {
      throw new Error("חובה למלא יתרה חיובית");
    }
    if (!form.annuity_factor || form.annuity_factor <= 0) {
      throw new Error("חובה למלא מקדם קצבה חיובי");
    }
  } else if (form.calculation_mode === "manual") {
    if (!form.monthly_amount || form.monthly_amount <= 0) {
      throw new Error("חובה למלא סכום חודשי חיובי");
    }
  }

  if (form.indexation_method === "fixed" && (!form.indexation_rate || form.indexation_rate < 0)) {
    throw new Error("חובה למלא שיעור הצמדה קבוע");
  }

  // חישוב תאריך התחלה (תמיד נשמר בפורמט ISO YYYY-MM-DD)
  let finalStartDate: string;

  if (form.pension_start_date) {
    // המשתמש הזין תאריך ידני בטופס (DD/MM/YYYY)
    finalStartDate = convertDDMMYYToISO(form.pension_start_date);
  } else if (funds.length > 0) {
    // אם יש כבר קצבאות, ניקח את התאריך המוקדם ביותר מביניהן (כפי שנשמר מהשרת)
    const earliestFromFunds = funds.reduce((earliest, fund) => {
      const fundDate = fund.pension_start_date || fund.start_date;
      if (!fundDate) return earliest;
      return !earliest || fundDate < earliest ? fundDate : earliest;
    }, "");

    finalStartDate = earliestFromFunds || new Date().toISOString().slice(0, 10);
  } else if (clientData && clientData.birth_date) {
    // אם אין קצבאות עדיין, ננסה להעריך תאריך פרישה ראשוני לפי גיל ומגדר
    try {
      const birthDate = new Date(clientData.birth_date);
      const retirementDate = new Date(birthDate);
      const retirementAge = clientData.gender?.toLowerCase() === "female" ? 62 : 67;
      retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
      finalStartDate = retirementDate.toISOString().slice(0, 10);
      console.log(`חישוב תאריך פרישה לפי מגדר: ${clientData.gender}, גיל פרישה: ${retirementAge}`);
    } catch (error) {
      console.error("Error calculating retirement date:", error);
      finalStartDate = new Date().toISOString().slice(0, 10);
    }
  } else {
    // ברירת מחדל: היום (בפורמט ISO)
    finalStartDate = new Date().toISOString().slice(0, 10);
  }
  
  // Create payload
  const payload: Record<string, any> = {
    client_id: Number(clientId),
    fund_name: form.fund_name?.trim() || "קצבה",
    fund_type: "pension",
    input_mode: form.calculation_mode,
    start_date: finalStartDate,
    pension_start_date: finalStartDate,
    indexation_method: form.indexation_method || "none",
    tax_treatment: form.tax_treatment || "taxable",
    deduction_file: form.deduction_file || ""
  };
  
  if (form.calculation_mode === "calculated") {
    payload.current_balance = Number(form.balance);
    payload.balance = Number(form.balance);
    payload.annuity_factor = Number(form.annuity_factor);
  } else if (form.calculation_mode === "manual") {
    payload.pension_amount = Number(form.monthly_amount);
    const defaultAnnuityFactor = 200;
    const calculatedBalance = Number(form.monthly_amount) * defaultAnnuityFactor;
    payload.balance = calculatedBalance;
    payload.annuity_factor = defaultAnnuityFactor;
    console.log(`📊 Manual mode: monthly=${form.monthly_amount}, calculated balance=${calculatedBalance}, factor=${defaultAnnuityFactor}`);
  }
  
  if (form.indexation_method === "fixed" && form.indexation_rate !== undefined) {
    payload.indexation_rate = Number(form.indexation_rate);
  }
  
  console.log("Sending pension fund payload:", payload);

  await savePensionFund(clientId, payload, editingFundId);

  // עדכון תאריך הקצבה הראשונה ברמת הלקוח (מרוכז בפונקציה משותפת)
  try {
    await recalculateClientPensionStartDate(clientId);
  } catch (updateError) {
    console.error("שגיאה בעדכון תאריך הקצבה הראשונה:", updateError);
  }
  
  console.log("✅ הקצבה נשמרה בהצלחה ותאריך הקצבה הראשונה עודכן!");
}

export async function handleCommutationSubmitLogic(
  clientId: string,
  commutationForm: Commutation,
  funds: PensionFund[]
): Promise<{ shouldDeleteFund: boolean; fundBalance: number; createdAsset: any }> {
  if (!commutationForm.pension_fund_id) {
    throw new Error("חובה לבחור קצבה");
  }
  if (!commutationForm.exempt_amount || commutationForm.exempt_amount <= 0) {
    throw new Error("חובה למלא סכום חיובי");
  }
  if (!commutationForm.commutation_date) {
    throw new Error("חובה למלא תאריך היוון");
  }

  const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
  if (!selectedFund) {
    throw new Error("קצבה לא נמצאה");
  }

  const fundBalance = calculateOriginalBalance(selectedFund);
  
  if (commutationForm.exempt_amount > fundBalance) {
    throw new Error(`סכום ההיוון (${formatCurrency(commutationForm.exempt_amount)}) גדול מהיתרה המקורית של הקצבה (${formatCurrency(fundBalance)})`);
  }

  const pensionTaxTreatment = selectedFund.tax_treatment || "taxable";
  
  if (pensionTaxTreatment === "exempt" && commutationForm.commutation_type !== "exempt") {
    throw new Error("קצבה פטורה ממס יכולה ליצור רק היוון פטור ממס");
  }
  
  const taxTreatment = commutationForm.commutation_type === "exempt" ? "exempt" : "taxable";
  console.log(`🔍 Pension tax: ${pensionTaxTreatment}, User selected: ${commutationForm.commutation_type} → Capital asset will be: ${taxTreatment}`);
  
  const capitalAssetData = {
    client_id: parseInt(clientId),
    asset_type: "deposits",
    description: `היוון של ${selectedFund.fund_name || 'קצבה'}`,
    remarks: `COMMUTATION:pension_fund_id=${selectedFund.id}&amount=${commutationForm.exempt_amount}`,
    current_value: 0,
    purchase_value: commutationForm.exempt_amount,
    purchase_date: commutationForm.commutation_date,
    monthly_income: commutationForm.exempt_amount,
    annual_return: commutationForm.exempt_amount,
    annual_return_rate: 0,
    payment_frequency: "annually" as const,
    start_date: commutationForm.commutation_date,
    indexation_method: "none" as const,
    tax_treatment: taxTreatment
  };

  console.log('🟢 Creating capital asset with data:', capitalAssetData);
  const createdAsset = await createCapitalAsset(clientId, capitalAssetData);
  console.log('🟢 Capital asset created:', createdAsset);

  const shouldDeleteFund = commutationForm.exempt_amount >= fundBalance;
  
  if (shouldDeleteFund) {
    await deletePensionFund(clientId, selectedFund.id!);
  } else {
    const newCommutableBalance = fundBalance - commutationForm.exempt_amount;
    const annuityFactor = selectedFund.annuity_factor || 200;
    const newMonthlyAmount = Math.round(newCommutableBalance / annuityFactor);
    
    await updatePensionFund(selectedFund.id!, {
      fund_name: selectedFund.fund_name,
      fund_type: selectedFund.fund_type,
      input_mode: selectedFund.input_mode,
      balance: newCommutableBalance,
      pension_amount: newMonthlyAmount,
      annuity_factor: annuityFactor,
      pension_start_date: selectedFund.pension_start_date,
      indexation_method: selectedFund.indexation_method || "none"
    });
  }

  return { shouldDeleteFund, fundBalance, createdAsset };
}
