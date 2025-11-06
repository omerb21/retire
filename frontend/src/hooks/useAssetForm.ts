/**
 * useAssetForm Hook
 * =================
 * Custom hook for managing asset form state and submission
 */

import { useState } from 'react';
import { apiFetch } from '../lib/api';
import { CapitalAsset, INITIAL_FORM_STATE } from '../types/capitalAsset';
import { convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

export function useAssetForm(clientId: string | undefined, onSuccess: () => void) {
  const [form, setForm] = useState<Partial<CapitalAsset>>(INITIAL_FORM_STATE);
  const [editingAssetId, setEditingAssetId] = useState<number | null>(null);
  const [error, setError] = useState<string>("");

  function resetForm() {
    setForm(INITIAL_FORM_STATE);
    setEditingAssetId(null);
  }

  function populateForm(asset: CapitalAsset) {
    setEditingAssetId(asset.id || null);
    setForm({
      asset_name: asset.asset_name || "",
      asset_type: asset.asset_type,
      current_value: asset.current_value || 0,
      monthly_income: asset.monthly_income || 0,
      annual_return_rate: asset.annual_return_rate || 0,
      payment_frequency: asset.payment_frequency,
      start_date: asset.start_date ? convertISOToDDMMYY(asset.start_date) : "",
      indexation_method: asset.indexation_method,
      tax_treatment: asset.tax_treatment,
      fixed_rate: asset.fixed_rate || 0,
      tax_rate: asset.tax_rate || 0,
      spread_years: asset.spread_years || 0,
      nominal_principal: asset.nominal_principal || 0,
    });
    
    // Scroll to form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      // Basic validation
      if (!form.asset_name || form.asset_name.trim() === "") {
        throw new Error("חובה למלא שם הנכס");
      }
      if (!form.asset_type) {
        throw new Error("חובה לבחור סוג נכס");
      }
      // תשלום אינו חובה - יכול להיות 0
      if (!form.start_date) {
        throw new Error("חובה למלא תאריך התחלה");
      }
      
      // Validation for capital gains tax
      if (form.tax_treatment === "capital_gains" && (form.annual_return_rate === undefined || form.annual_return_rate < 2)) {
        throw new Error("עבור מס רווח הון, חובה למלא שיעור תשואה שנתי של לפחות 2%");
      }

      if (form.indexation_method === "fixed" && (!form.fixed_rate || form.fixed_rate < 0)) {
        throw new Error("חובה למלא שיעור הצמדה קבוע");
      }

      if (form.tax_treatment === "fixed_rate" && (!form.tax_rate || form.tax_rate < 0 || form.tax_rate > 100)) {
        throw new Error("חובה למלא שיעור מס בין 0-100");
      }

      // Convert dates to ISO format
      const startDateISO = convertDDMMYYToISO(form.start_date);
      if (!startDateISO) {
        throw new Error("תאריך התחלה לא תקין - יש להזין בפורמט DD/MM/YYYY");
      }
      
      // Validation - ערך נוכחי יכול להיות 0 (למשל להיוונים)
      if (form.current_value === undefined || form.current_value === null) {
        throw new Error("יש להזין ערך נכס");
      }
      if (Number(form.current_value) < 0) {
        throw new Error("ערך נכס לא יכול להיות שלילי");
      }
      
      // חישוב מס רווח הון אם נבחר
      let adjustedMonthlyIncome = Number(form.monthly_income) || 0;
      let adjustedTaxTreatment = form.tax_treatment || "taxable";
      
      if (form.tax_treatment === "capital_gains" && form.monthly_income && form.nominal_principal !== undefined) {
        const payment = Number(form.monthly_income);
        const principal = Number(form.nominal_principal) || payment; // ברירת מחדל = סכום התשלום
        const gain = payment - principal;
        const tax = gain * 0.25;
        adjustedMonthlyIncome = payment - tax;
        adjustedTaxTreatment = "exempt"; // שמירה כפטור ממס
        
        console.log(`💰 CAPITAL GAINS TAX CALCULATION:`);
        console.log(`   Payment: ${payment}`);
        console.log(`   Principal: ${principal}`);
        console.log(`   Gain: ${gain}`);
        console.log(`   Tax (25%): ${tax}`);
        console.log(`   Adjusted payment: ${adjustedMonthlyIncome}`);
        console.log(`   Tax treatment changed to: exempt`);
      }
      
      const payload = {
        asset_type: form.asset_type,
        description: form.asset_name?.trim() || "נכס הון",
        current_value: Number(form.current_value),
        purchase_value: Number(form.current_value), // ערך רכישה = ערך נוכחי כברירת מחדל
        purchase_date: startDateISO,
        annual_return: 0, // ערך ברירת מחדל
        annual_return_rate: Number(form.annual_return_rate) / 100 || 0, // המרה לעשרוני
        payment_frequency: "annually", // תמיד שנתי - תשלום חד פעמי
        liquidity: "medium", // ערך ברירת מחדל
        risk_level: "medium", // ערך ברירת מחדל
        
        // השדות הנדרשים לתצוגה
        monthly_income: adjustedMonthlyIncome,
        start_date: startDateISO,
        end_date: null,  // תמיד null - תשלום חד פעמי
        indexation_method: form.indexation_method || "none",
        fixed_rate: form.fixed_rate !== undefined ? Number(form.fixed_rate) : 0,
        tax_treatment: adjustedTaxTreatment,
        tax_rate: form.tax_rate !== undefined ? Number(form.tax_rate) : 0,
        spread_years: form.spread_years && form.spread_years > 0 ? Number(form.spread_years) : null
      };

      console.log("SENDING PAYLOAD TO SERVER:", JSON.stringify(payload, null, 2));
      
      // בדיקה אם אנחנו במצב עריכה או יצירה חדשה
      if (editingAssetId) {
        // עדכון נכס קיים
        console.log(`מעדכן נכס קיים עם מזהה: ${editingAssetId}`);
        const response = await apiFetch(`/clients/${clientId}/capital-assets/${editingAssetId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        console.log("SERVER RESPONSE AFTER UPDATE:", JSON.stringify(response, null, 2));
      } else {
        // יצירת נכס חדש
        const response = await apiFetch(`/clients/${clientId}/capital-assets/`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        console.log("SERVER RESPONSE AFTER CREATE:", JSON.stringify(response, null, 2));
      }

      // איפוס הטופס ומצב העריכה
      resetForm();

      // Call success callback
      onSuccess();
    } catch (e: any) {
      setError(`שגיאה ביצירת נכס הון: ${e?.message || e}`);
    }
  }

  return {
    form,
    setForm,
    editingAssetId,
    error,
    setError,
    resetForm,
    populateForm,
    handleSubmit
  };
}
