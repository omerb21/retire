import { PensionFund, Commutation } from './types';
import { calculateOriginalBalance } from './utils';
import { formatCurrency } from '../../lib/validation';
import {
  loadPensionFunds,
  savePensionFund,
  computePensionFund,
  deleteCommutation,
  createCapitalAsset,
  updatePensionFund,
  updateClientPensionStartDate,
  getCapitalAsset
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

  // השוואה עם עיגול לשתי ספרות כדי למנוע שגיאות מעיגול מסכום זהה
  const roundedAmount = Math.round((commutationForm.exempt_amount || 0) * 100) / 100;
  const roundedBalance = Math.round(fundBalance * 100) / 100;

  if (roundedAmount > roundedBalance) {
    throw new Error(`סכום ההיוון (${formatCurrency(commutationForm.exempt_amount)}) גדול מהיתרה המקורית של הקצבה (${formatCurrency(fundBalance)})`);
  }

  const pensionTaxTreatment = selectedFund.tax_treatment || "taxable";
  
  if (pensionTaxTreatment === "exempt" && commutationForm.commutation_type !== "exempt") {
    throw new Error("קצבה פטורה ממס יכולה ליצור רק היוון פטור ממס");
  }
  
  const taxTreatment = commutationForm.commutation_type === "exempt" ? "exempt" : "taxable";
  console.log(`🔍 Pension tax: ${pensionTaxTreatment}, User selected: ${commutationForm.commutation_type} → Capital asset will be: ${taxTreatment}`);
  
  // צילום הקצבה כפי שהייתה לפני ההיוון – ישמש לשחזור מדויק אם הקצבה תימחק בעתיד
  const originalPensionSnapshot: PensionFund = {
    id: selectedFund.id,
    fund_name: selectedFund.fund_name,
    fund_type: selectedFund.fund_type,
    input_mode: selectedFund.input_mode || selectedFund.calculation_mode || "calculated",
    balance: selectedFund.balance ?? selectedFund.current_balance ?? fundBalance,
    annuity_factor: selectedFund.annuity_factor,
    pension_amount:
      selectedFund.pension_amount ??
      selectedFund.monthly ??
      selectedFund.monthly_amount,
    pension_start_date: selectedFund.pension_start_date || selectedFund.start_date,
    indexation_method: selectedFund.indexation_method || "none",
    tax_treatment: selectedFund.tax_treatment || "taxable",
    deduction_file: selectedFund.deduction_file || "",
  };
  
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
    tax_treatment: taxTreatment,
    conversion_source: JSON.stringify({
      type: "pension_commutation",
      pension_fund_id: selectedFund.id,
      original_pension: originalPensionSnapshot,
    }),
  };

  console.log('🟢 Creating capital asset with data:', capitalAssetData);
  const createdAsset = await createCapitalAsset(clientId, capitalAssetData);
  console.log('🟢 Capital asset created:', createdAsset);
  // חישוב יתרה חדשה לאחר ההיוון – גם אם ההיוון מלא, לא מוחקים את הקצבה אלא
  // משאירים אותה עם יתרה 0 כדי לאפשר מחיקת ההיוון והחזרת הקצבה.
  const newCommutableBalance = fundBalance - commutationForm.exempt_amount;
  const isFullCommutation = newCommutableBalance <= 0;

  const annuityFactor = selectedFund.annuity_factor || 200;
  const safeNewBalance = Math.max(0, newCommutableBalance);
  const newMonthlyAmount = safeNewBalance > 0 ? Math.round(safeNewBalance / annuityFactor) : 0;

  await updatePensionFund(selectedFund.id!, {
    fund_name: selectedFund.fund_name,
    fund_type: selectedFund.fund_type,
    input_mode: selectedFund.input_mode,
    balance: safeNewBalance,
    pension_amount: newMonthlyAmount,
    annuity_factor: annuityFactor,
    pension_start_date: selectedFund.pension_start_date,
    indexation_method: selectedFund.indexation_method || "none"
  });

  // נשמר את השדה shouldDeleteFund רק לצורך הודעת UI (מציין שהיתרה הגיעה ל-0),
  // אך הקצבה עצמה לא נמחקת בפועל.
  const shouldDeleteFund = isFullCommutation;

  return { shouldDeleteFund, fundBalance, createdAsset };
}

export async function restorePensionFromCommutation(
  clientId: string,
  commutation: Commutation
): Promise<void> {
  let snapshot = commutation.original_pension;
  const amount = commutation.exempt_amount || 0;
  if (amount <= 0) {
    return;
  }
  // אם אין צילום בקומוטציה עצמה, ננסה לטעון אותו מנכס ההון בבקאנד
  if (!snapshot && commutation.id) {
    try {
      const asset = await getCapitalAsset(clientId, commutation.id);
      if (asset?.conversion_source) {
        const sourceData = JSON.parse(asset.conversion_source);
        if (sourceData && sourceData.type === 'pension_commutation' && sourceData.original_pension) {
          snapshot = sourceData.original_pension as PensionFund;
        }
      }
    } catch (e) {
      console.error('Error loading capital asset for commutation restore:', e);
    }
  }

  // אם יש צילום של הקצבה המקורית – נשחזר לפיו אחד‑לאחד
  if (snapshot) {
    const balance =
      snapshot.balance ??
      snapshot.current_balance ??
      snapshot.commutable_balance ??
      amount;

    const annuityFactor =
      snapshot.annuity_factor && snapshot.annuity_factor > 0
        ? snapshot.annuity_factor
        : balance > 0 && snapshot.pension_amount
        ? Math.round(balance / snapshot.pension_amount)
        : 200;

    const pensionAmount =
      snapshot.pension_amount ??
      snapshot.monthly ??
      snapshot.monthly_amount ??
      (annuityFactor > 0 ? Math.round(balance / annuityFactor) : 0);

    const pensionStartDate =
      snapshot.pension_start_date ||
      snapshot.start_date ||
      (commutation.commutation_date && commutation.commutation_date.length === 10
        ? commutation.commutation_date
        : new Date().toISOString().slice(0, 10));

    const inputMode = snapshot.input_mode || snapshot.calculation_mode || "manual";

    const taxTreatment = snapshot.tax_treatment ||
      (commutation.commutation_type === "exempt" ? "exempt" : "taxable");

    const payload: Record<string, any> = {
      client_id: Number(clientId),
      fund_name: snapshot.fund_name?.trim() || "קצבה",
      fund_type: snapshot.fund_type || "pension",
      input_mode: inputMode,
      balance,
      pension_amount: pensionAmount,
      annuity_factor: annuityFactor,
      pension_start_date: pensionStartDate,
      indexation_method: snapshot.indexation_method || "none",
      tax_treatment: taxTreatment,
      deduction_file: snapshot.deduction_file || "",
    };

    await savePensionFund(clientId, payload, null);
    return;
  }

  // Fallback ישן – רק אם אין בכלל צילום, משתמשים בנתוני ההיוון עצמו
  const fallbackAnnuityFactor = 200;
  const fallbackPensionAmount = Math.round(amount / fallbackAnnuityFactor);

  const fallbackDateString =
    commutation.commutation_date && commutation.commutation_date.length === 10
      ? commutation.commutation_date
      : new Date().toISOString().slice(0, 10);

  const fallbackTaxTreatment =
    commutation.commutation_type === "exempt" ? "exempt" : "taxable";

  const fallbackPayload: Record<string, any> = {
    client_id: Number(clientId),
    fund_name: "קצבה משוחזרת מהיוון",
    fund_type: "pension",
    input_mode: "manual",
    balance: amount,
    pension_amount: fallbackPensionAmount,
    annuity_factor: fallbackAnnuityFactor,
    pension_start_date: fallbackDateString,
    indexation_method: "none",
    tax_treatment: fallbackTaxTreatment,
    deduction_file: "",
  };

  await savePensionFund(clientId, fallbackPayload, null);
}
