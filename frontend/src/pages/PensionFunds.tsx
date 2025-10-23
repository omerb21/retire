import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import axios from 'axios';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

type PensionFund = {
  id?: number;
  fund_name?: string;
  fund_number?: string;
  fund_type?: string;
  calculation_mode?: "calculated" | "manual"; // לתאימות לאחור
  input_mode?: "calculated" | "manual";
  current_balance?: number;
  balance?: number;
  commutable_balance?: number; // יתרה להיוון - השדה החשוב!
  annuity_factor?: number;
  monthly_amount?: number;
  monthly?: number; // שדה נוסף מהשרת
  pension_amount?: number;
  computed_monthly_amount?: number;
  pension_start_date?: string;
  start_date?: string; // לתאימות לאחור
  end_date?: string;
  indexation_method?: "none" | "fixed" | "cpi";
  indexation_rate?: number;
  fixed_index_rate?: number;
  employer_contributions?: number;
  employee_contributions?: number;
  annual_return_rate?: number;
  deduction_file?: string; // תיק ניכויים
  tax_treatment?: "taxable" | "exempt" | "capital_gains"; // יחס למס
};

type Commutation = {
  id?: number;
  pension_fund_id?: number;
  exempt_amount?: number;
  commutation_date?: string;
  commutation_type?: "exempt" | "taxable"; // פטור ממס או חייב במס
};

export default function PensionFunds() {
  const { id: clientId } = useParams<{ id: string }>();
  const [funds, setFunds] = useState<PensionFund[]>([]);
  const [commutations, setCommutations] = useState<Commutation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [clientData, setClientData] = useState<any>(null);
  const [editingFundId, setEditingFundId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<PensionFund>>({
    fund_name: "",
    calculation_mode: "calculated",
    balance: 0,
    annuity_factor: 0,
    indexation_method: "none",
    indexation_rate: 0,
    deduction_file: "",
    pension_start_date: "",
    tax_treatment: "taxable", // ברירת מחדל: חייב במס
  });
  const [commutationForm, setCommutationForm] = useState<Commutation>({
    pension_fund_id: undefined,
    exempt_amount: 0,
    commutation_date: "",
    commutation_type: "taxable",
  });

  // אוטומטית מעדכן את יחס המס של ההיוון כאשר בוחרים קצבה פטורה ממס
  useEffect(() => {
    if (commutationForm.pension_fund_id) {
      const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
      if (selectedFund?.tax_treatment === "exempt") {
        // אם הקצבה פטורה ממס, כופה את ההיוון להיות פטור ממס
        setCommutationForm(prev => ({ ...prev, commutation_type: "exempt" }));
      }
    }
  }, [commutationForm.pension_fund_id, funds]);

  // פונקציה מרכזית לחישוב היתרה המקורית של קצבה
  function calculateOriginalBalance(fund: PensionFund): number {
    // אם יש שדה commutable_balance (יתרה להיוון) - זה השדה המדויק!
    if (fund.commutable_balance && fund.commutable_balance > 0) {
      return fund.commutable_balance;
    }
    
    // אם יש יתרה בפועל - השתמש בה
    let balance = fund.balance || fund.current_balance || 0;
    
    if (balance > 0) {
      return balance;
    }
    
    // אם אין שום יתרה - החזר 0
    return 0;
  }

  async function loadFunds() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
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
      
      setFunds(mappedFunds);
      
      // טעינת היוונים מנכסים הוניים
      try {
        const capitalAssets = await apiFetch<any[]>(`/clients/${clientId}/capital-assets`);
        console.log("Loaded capital assets:", capitalAssets);
        
        // סינון נכסים שהם היוונים (יש להם COMMUTATION ב-remarks)
        const commutationAssets = (capitalAssets || []).filter(asset => 
          asset.remarks && asset.remarks.includes('COMMUTATION:')
        );
        
        // המרה לפורמט Commutation
        const loadedCommutations: Commutation[] = commutationAssets.map(asset => {
          // חילוץ pension_fund_id מה-remarks
          const match = asset.remarks.match(/pension_fund_id=(\d+)/);
          const pensionFundId = match ? parseInt(match[1]) : undefined;
          
          // חילוץ amount מה-remarks
          const amountMatch = asset.remarks.match(/amount=([\d.]+)/);
          const amount = amountMatch ? parseFloat(amountMatch[1]) : asset.current_value;
          
          return {
            id: asset.id,
            pension_fund_id: pensionFundId,
            exempt_amount: amount,
            commutation_date: asset.start_date || asset.purchase_date,
            commutation_type: asset.tax_treatment === "exempt" ? "exempt" : "taxable"
          };
        });
        
        console.log("Loaded commutations:", loadedCommutations);
        setCommutations(loadedCommutations);
      } catch (commutationError) {
        console.error("Error loading commutations:", commutationError);
        // לא נכשל את כל הטעינה אם יש בעיה בטעינת היוונים
        setCommutations([]);
      }
    } catch (e: any) {
      setError(`שגיאה בטעינת קצבאות: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  // טעינת נתוני לקוח
  useEffect(() => {
    if (clientId) {
      // טען נתוני לקוח לחישוב גיל פרישה
      const fetchClientData = async () => {
        try {
          const data = await apiFetch<any>(`/clients/${clientId}`);
          setClientData(data);
        } catch (error) {
          console.error("Error fetching client data:", error);
        }
      };
      
      fetchClientData();
      loadFunds();
    }
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
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

      // אם המשתמש הזין תאריך התחלת קצבה, השתמש בו
      let earliestStartDate: string;
      
      if (form.pension_start_date) {
        // אם המשתמש הזין תאריך, השתמש בו
        earliestStartDate = form.pension_start_date;
      } else if (funds.length > 0) {
        // אם יש קצבאות קיימות, קח את התאריך המוקדם ביותר
        earliestStartDate = funds.reduce((earliest, fund) => {
          const fundDate = fund.pension_start_date || fund.start_date;
          if (!fundDate) return earliest;
          return !earliest || fundDate < earliest ? fundDate : earliest;
        }, "") || formatDateToDDMMYY(new Date());
      } else if (clientData && clientData.birth_date) {
        // אם אין קצבאות אבל יש תאריך לידה, חשב גיל פרישה דינמי
        try {
          // שימוש ב-API לחישוב גיל פרישה דינמי
          const response = await axios.post('/api/v1/retirement-age/calculate-simple', {
            birth_date: clientData.birth_date,
            gender: clientData.gender || 'female'
          });
          
          const retirementDateISO = response.data.retirement_date;
          const retirementAge = response.data.retirement_age;
          earliestStartDate = formatDateToDDMMYY(new Date(retirementDateISO));
          
          console.log(`חישוב תאריך פרישה דינמי: ${clientData.gender}, גיל פרישה: ${retirementAge}, תאריך: ${earliestStartDate}`);
        } catch (error) {
          console.error("Error calculating retirement date:", error);
          // fallback
          const birthDate = new Date(clientData.birth_date);
          const retirementDate = new Date(birthDate);
          const retirementAge = clientData.gender?.toLowerCase() === "female" ? 65 : 67;
          retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
          earliestStartDate = formatDateToDDMMYY(retirementDate);
        }
      } else {
        // אם אין קצבאות ואין תאריך לידה, השתמש בתאריך היום
        earliestStartDate = formatDateToDDMMYY(new Date());
      }
      
      // Convert pension_start_date to ISO if provided
      const pensionStartDateISO = form.pension_start_date ? convertDDMMYYToISO(form.pension_start_date) : '';
      const finalStartDate = pensionStartDateISO || earliestStartDate;
      
      // Create payload with exact field names matching backend schema
      const payload: Record<string, any> = {
        // Required fields from schema
        client_id: Number(clientId),
        fund_name: form.fund_name?.trim() || "קצבה",
        fund_type: "pension",
        input_mode: form.calculation_mode,
        start_date: finalStartDate,
        pension_start_date: finalStartDate,
        indexation_method: form.indexation_method || "none",
        tax_treatment: form.tax_treatment || "taxable", // יחס למס
        deduction_file: form.deduction_file || ""
      };
      
      // Add mode-specific fields
      if (form.calculation_mode === "calculated") {
        payload.current_balance = Number(form.balance);
        payload.balance = Number(form.balance);
        payload.annuity_factor = Number(form.annuity_factor);
      } else if (form.calculation_mode === "manual") {
        // במצב ידני, שמור את הסכום החודשי בשדה pension_amount
        payload.pension_amount = Number(form.monthly_amount);
        
        // חישוב היתרה המקורית לפי מקדם קצבה בסיסי (200)
        // כדי לאפשר היוון בעתיד
        const defaultAnnuityFactor = 200;
        const calculatedBalance = Number(form.monthly_amount) * defaultAnnuityFactor;
        payload.balance = calculatedBalance;
        payload.annuity_factor = defaultAnnuityFactor;
        
        console.log(`📊 Manual mode: monthly=${form.monthly_amount}, calculated balance=${calculatedBalance}, factor=${defaultAnnuityFactor}`);
      }
      
      // Add indexation rate only if method is fixed
      if (form.indexation_method === "fixed" && form.indexation_rate !== undefined) {
        payload.indexation_rate = Number(form.indexation_rate);
      }
      
      console.log("Sending pension fund payload:", payload);

      // בדיקה אם אנחנו במצב עריכה או יצירה חדשה
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

      // איפוס הטופס ומצב העריכה
      setForm({
        fund_name: "",
        calculation_mode: "calculated",
        balance: 0,
        annuity_factor: 0,
        indexation_method: "none",
        indexation_rate: 0,
        deduction_file: "",
        pension_start_date: "",
      });
      
      // איפוס מצב העריכה
      setEditingFundId(null);

      // Reload funds
      await loadFunds();
      
      // עדכון תאריך הקצבה הראשונה של הלקוח
      try {
        console.log("מתחיל עדכון תאריך הקצבה הראשונה...");
        // מציאת התאריך המוקדם ביותר מבין כל הקצבאות
        const updatedFunds = await apiFetch<PensionFund[]>(`/clients/${clientId}/pension-funds`);
        console.log("קצבאות שנמצאו:", updatedFunds);
        
        if (updatedFunds && updatedFunds.length > 0) {
          // מיון הקצבאות לפי תאריך התחלה
          const sortedFunds = [...updatedFunds].sort((a, b) => {
            const dateA = a.pension_start_date || a.start_date || '';
            const dateB = b.pension_start_date || b.start_date || '';
            return dateA.localeCompare(dateB);
          });
          console.log("קצבאות ממוינות:", sortedFunds);
          
          // לקיחת התאריך המוקדם ביותר
          const earliestDate = sortedFunds[0].pension_start_date || sortedFunds[0].start_date;
          console.log("התאריך המוקדם ביותר:", earliestDate);
          
          if (earliestDate) {
            console.log(`מעדכן תאריך הקצבה הראשונה ללקוח ${clientId} ל-${earliestDate}`);
            // עדכון תאריך הקצבה הראשונה של הלקוח - חייב להשתמש ב-PUT במקום PATCH
            const updateResponse = await apiFetch(`/clients/${clientId}`, {
              method: "PUT",
              body: JSON.stringify({
                pension_start_date: earliestDate
              }),
            });
            console.log("תגובת השרת לעדכון:", updateResponse);
            console.log(`תאריך הקצבה הראשונה עודכן ל-${earliestDate}`);
          }
        }
      } catch (updateError) {
        console.error("שגיאה בעדכון תאריך הקצבה הראשונה:", updateError);
      }
      
      // הודעת הצלחה בקונסול
      console.log("✅ הקצבה נשמרה בהצלחה ותאריך הקצבה הראשונה עודכן!");
    } catch (e: any) {
      setError(`שגיאה ביצירת קצבה: ${e?.message || e}`);
    }
  }

  async function handleCompute(fundId: number) {
    if (!clientId) return;

    try {
      // חישוב הקצבה החודשית על בסיס היתרה והמקדם
      const fund = funds.find(f => f.id === fundId);
      if (!fund) {
        throw new Error("קרן לא נמצאה");
      }
      
      const balance = fund.current_balance || fund.balance || 0;
      const factor = fund.annuity_factor || 0;
      
      if (balance <= 0 || factor <= 0) {
        throw new Error("יתרה ומקדם קצבה חייבים להיות חיוביים");
      }
      
      // חישוב נכון של הקצבה: יתרה חלקי מקדם קצבה
      const computed_monthly_amount = Math.round(balance / factor);
      
      // חישוב ושמירה דרך ה-API המתאים
      await apiFetch(`/clients/${clientId}/pension-funds/${fundId}/compute`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      
      // Reload to get updated computed amount
      await loadFunds();
    } catch (e: any) {
      console.error('Compute error:', e);
      setError(`שגיאה בחישוב: ${e?.message || e}`);
    }
  }

  async function handleDeleteAll() {
    if (!clientId) return;
    
    const totalItems = funds.length + commutations.length;
    
    if (totalItems === 0) {
      alert("אין קצבאות או היוונים למחיקה");
      return;
    }
    
    if (!confirm(`האם אתה בטוח שברצונך למחוק את כל ${funds.length} הקצבאות ו-${commutations.length} ההיוונים? פעולה זו בלתי הפיכה!`)) {
      return;
    }

    try {
      setError("");
      
      // מחיקת כל הקצבאות אחת אחת
      for (const fund of funds) {
        if (fund.id) {
          await apiFetch(`/clients/${clientId}/pension-funds/${fund.id}`, {
            method: 'DELETE'
          });
        }
      }
      
      // מחיקת כל ההיוונים (נכסי הון עם COMMUTATION)
      for (const commutation of commutations) {
        if (commutation.id) {
          await apiFetch(`/clients/${clientId}/capital-assets/${commutation.id}`, {
            method: 'DELETE'
          });
        }
      }
      
      // רענון הרשימה
      await loadFunds();
      alert(`נמחקו ${funds.length} קצבאות ו-${commutations.length} היוונים בהצלחה`);
    } catch (e: any) {
      setError(`שגיאה במחיקה: ${e?.message || e}`);
    }
  }

  async function handleDelete(fundId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את הקצבה?")) {
      return;
    }

    try {
      // קבלת פרטי הקצבה לפני המחיקה
      const fund = funds.find(f => f.id === fundId);
      
      // 🔴 מחיקת כל ההיוונים המקושרים לקצבה זו
      const relatedCommutations = commutations.filter(c => c.pension_fund_id === fundId);
      if (relatedCommutations.length > 0) {
        console.log(`🗑️ Deleting ${relatedCommutations.length} commutations linked to pension fund ${fundId}`);
        for (const commutation of relatedCommutations) {
          if (commutation.id) {
            await apiFetch(`/clients/${clientId}/capital-assets/${commutation.id}`, {
              method: 'DELETE'
            });
            console.log(`✅ Deleted commutation ${commutation.id}`);
          }
        }
      }
      
      // בדיקה אם יש מידע על מקור המרה
      if (fund && (fund as any).conversion_source) {
        try {
          const conversionSource = JSON.parse((fund as any).conversion_source);
          
          // אם זו המרה מתיק פנסיוני - נחזיר את הסכומים למקור
          if (conversionSource.type === 'pension_portfolio') {
            console.log('Restoring amounts to pension portfolio:', conversionSource);
            
            // ✅ מחזירים את הסכום המקורי המלא!
            // כי אנחנו מוחקים גם את הקצבה וגם את כל ההיוונים שלה
            // אז הכסף צריך לחזור במלואו לטבלה
            const currentBalance = parseFloat(fund.balance as any) || 0;
            const totalCommutations = relatedCommutations.reduce((sum, c) => sum + (c.exempt_amount || 0), 0);
            const actualAmountToRestore = conversionSource.amount; // ✅ הסכום המקורי המלא!
            
            console.log(`📊 Original amount: ${conversionSource.amount}`);
            console.log(`📊 Current balance: ${currentBalance}`);
            console.log(`📊 Total commutations deleted: ${totalCommutations}`);
            console.log(`📊 Amount to restore: ${actualAmountToRestore} (full original amount)`);
            
            // קריאה ל-API להחזרת הסכומים
            await apiFetch(`/clients/${clientId}/pension-portfolio/restore`, {
              method: 'POST',
              body: JSON.stringify({
                account_name: conversionSource.account_name,
                company: conversionSource.company,
                account_number: conversionSource.account_number,
                product_type: conversionSource.product_type,
                amount: actualAmountToRestore, // ✅ הסכום המקורי המלא!
                specific_amounts: conversionSource.specific_amounts
              })
            });
            
            // עדכון localStorage - החזרת הסכומים לטבלה
            const storageKey = `pensionData_${clientId}`;
            const storedData = localStorage.getItem(storageKey);
            
            if (storedData) {
              try {
                const pensionData = JSON.parse(storedData);
                
                // חיפוש החשבון המתאים
                const accountIndex = pensionData.findIndex((acc: any) => 
                  acc.שם_תכנית === conversionSource.account_name &&
                  acc.חברה_מנהלת === conversionSource.company &&
                  acc.מספר_חשבון === conversionSource.account_number
                );
                
                if (accountIndex !== -1) {
                  // החזרת הסכומים לשדות הספציפיים
                  if (conversionSource.specific_amounts && Object.keys(conversionSource.specific_amounts).length > 0) {
                    // ✅ מחזירים את הסכומים המקוריים המלאים (ללא יחס)
                    // כי מחקנו גם את הקצבה וגם את ההיוונים
                    Object.entries(conversionSource.specific_amounts).forEach(([key, value]) => {
                      pensionData[accountIndex][key] = (pensionData[accountIndex][key] || 0) + parseFloat(value as string);
                    });
                    console.log('Restored full original specific amounts:', conversionSource.specific_amounts);
                  } else {
                    // אם אין סכומים ספציפיים, מחזירים את הסכום המקורי המלא
                    pensionData[accountIndex].יתרה = (pensionData[accountIndex].יתרה || 0) + conversionSource.amount;
                    console.log('Restored full original amount to יתרה:', conversionSource.amount);
                  }
                  
                  // שמירה חזרה ל-localStorage
                  localStorage.setItem(storageKey, JSON.stringify(pensionData));
                  console.log('Successfully restored amounts to pension portfolio in localStorage');
                } else {
                  console.warn('Account not found in localStorage, amounts not restored to table');
                }
              } catch (storageError) {
                console.error('Error updating localStorage:', storageError);
              }
            }
            
            console.log('Successfully restored amounts to pension portfolio');
          }
        } catch (parseError) {
          console.warn('Could not parse conversion_source:', parseError);
          // ממשיכים עם המחיקה גם אם יש שגיאה בפרסור
        }
      }
      
      // מחיקת הקצבה
      await apiFetch(`/pension-funds/${fundId}`, {
        method: "DELETE",
      });
      
      // Reload funds after deletion
      await loadFunds();
      
      // עדכון תאריך הקצבה הראשונה של הלקוח לאחר מחיקה
      try {
        // מציאת התאריך המוקדם ביותר מבין הקצבאות הנותרות
        const updatedFunds = await apiFetch<PensionFund[]>(`/clients/${clientId}/pension-funds`);
        
        if (updatedFunds && updatedFunds.length > 0) {
          // מיון הקצבאות לפי תאריך התחלה
          const sortedFunds = [...updatedFunds].sort((a, b) => {
            const dateA = a.pension_start_date || a.start_date || '';
            const dateB = b.pension_start_date || b.start_date || '';
            return dateA.localeCompare(dateB);
          });
          
          // לקיחת התאריך המוקדם ביותר
          const earliestDate = sortedFunds[0].pension_start_date || sortedFunds[0].start_date;
          
          if (earliestDate) {
            // עדכון תאריך הקצבה הראשונה של הלקוח - חייב להשתמש ב-PUT במקום PATCH
            await apiFetch(`/clients/${clientId}`, {
              method: "PUT",
              body: JSON.stringify({
                pension_start_date: earliestDate
              }),
            });
            console.log(`תאריך הקצבה הראשונה עודכן ל-${earliestDate}`);
          } else {
            // אם אין תאריך, ננקה את תאריך הקצבה הראשונה
            console.error("לא נמצא תאריך קצבה תקין");
          }
        } else {
          // אם אין קצבאות, ננקה את תאריך הקצבה הראשונה - חייב להשתמש ב-PUT במקום PATCH
          await apiFetch(`/clients/${clientId}`, {
            method: "PUT",
            body: JSON.stringify({
              pension_start_date: null
            }),
          });
          console.log("תאריך הקצבה הראשונה נוקה כי אין קצבאות");
        }
      } catch (updateError) {
        console.error("שגיאה בעדכון תאריך הקצבה הראשונה:", updateError);
      }
    } catch (e: any) {
      setError(`שגיאה במחיקת קצבה: ${e?.message || e}`);
    }
  }

  function handleEdit(fund: PensionFund) {
    // שמירת מזהה הקצבה שעורכים
    setEditingFundId(fund.id || null);
    
    // Populate form with fund data for editing
    setForm({
      fund_name: fund.fund_name || "",
      calculation_mode: fund.input_mode || fund.calculation_mode || "calculated",
      balance: fund.balance || 0,
      annuity_factor: fund.annuity_factor || 0,
      monthly_amount: fund.pension_amount || fund.monthly_amount || 0,
      indexation_method: fund.indexation_method || "none",
      indexation_rate: fund.fixed_index_rate || fund.indexation_rate || 0,
      deduction_file: fund.deduction_file || "",
      pension_start_date: fund.pension_start_date || fund.start_date || "",
      tax_treatment: fund.tax_treatment || "taxable", // יחס למס
    });
    
    // Scroll to form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function handleCommutationSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      // Basic validation
      if (!commutationForm.pension_fund_id) {
        throw new Error("חובה לבחור קצבה");
      }
      if (!commutationForm.exempt_amount || commutationForm.exempt_amount <= 0) {
        throw new Error("חובה למלא סכום חיובי");
      }
      if (!commutationForm.commutation_date) {
        throw new Error("חובה למלא תאריך היוון");
      }

      // מציאת הקצבה
      const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
      if (!selectedFund) {
        throw new Error("קצבה לא נמצאה");
      }

      // חישוב היתרה המקורית באמצעות הפונקציה המרכזית
      const fundBalance = calculateOriginalBalance(selectedFund);
      
      // בדיקה שהסכום אינו עולה על היתרה המקורית
      if (commutationForm.exempt_amount > fundBalance) {
        throw new Error(`סכום ההיוון (${commutationForm.exempt_amount.toLocaleString()}) גדול מהיתרה המקורית של הקצבה (${fundBalance.toLocaleString()})`);
      }

      // אימות יחס מס - לוגיקה מיוחדת לפי סוג הקצבה
      const pensionTaxTreatment = selectedFund.tax_treatment || "taxable";
      
      // אם הקצבה פטורה ממס - ההיוון חייב להיות פטור ממס
      if (pensionTaxTreatment === "exempt" && commutationForm.commutation_type !== "exempt") {
        throw new Error("קצבה פטורה ממס יכולה ליצור רק היוון פטור ממס");
      }
      
      // אם הקצבה חייבת במס - ניתן ליצור היוון עם כל יחס מס
      // (אין הגבלה - המשתמש יכול לבחור חייב או פטור)
      
      const taxTreatment = commutationForm.commutation_type === "exempt" ? "exempt" : "taxable";
      console.log(`🔍 Pension tax: ${pensionTaxTreatment}, User selected: ${commutationForm.commutation_type} → Capital asset will be: ${taxTreatment}`);
      
      // יצירת נכס הוני
      const capitalAssetData = {
        client_id: parseInt(clientId),
        asset_type: "deposits", // מוצג כ"היוון" בפרונטאנד
        description: `היוון של ${selectedFund.fund_name || 'קצבה'}`,
        remarks: `COMMUTATION:pension_fund_id=${selectedFund.id}&amount=${commutationForm.exempt_amount}`, // קישור לקצבה (& ולא ,)
        current_value: 0, // ✅ היוון = ערך נוכחי 0 (כבר שולם)
        purchase_value: commutationForm.exempt_amount,
        purchase_date: commutationForm.commutation_date,
        monthly_income: commutationForm.exempt_amount,
        annual_return: commutationForm.exempt_amount,
        annual_return_rate: 0,
        payment_frequency: "annually" as const, // צריך "annually" ולא "annual"
        start_date: commutationForm.commutation_date,
        indexation_method: "none" as const,
        tax_treatment: taxTreatment
      };

      // שמירת הנכס ההוני ב-DB
      console.log('🟢 Creating capital asset with data:', capitalAssetData);
      const createdAsset = await apiFetch(`/clients/${clientId}/capital-assets/`, {
        method: 'POST',
        body: JSON.stringify(capitalAssetData)
      });
      console.log('🟢 Capital asset created:', createdAsset);

      // קיזוז הסכום מהקצבה או מחיקתה אם זה כל היתרה
      const shouldDeleteFund = commutationForm.exempt_amount >= fundBalance;
      
      if (shouldDeleteFund) {
        // מחיקת הקצבה כולה
        await apiFetch(`/clients/${clientId}/pension-funds/${selectedFund.id}`, {
          method: 'DELETE'
        });
      } else {
        // קיזוז סכום חלקי - חישוב היתרה והקצבה החודשית החדשה
        const newCommutableBalance = fundBalance - commutationForm.exempt_amount;
        const annuityFactor = selectedFund.annuity_factor || 200;
        const newMonthlyAmount = Math.round(newCommutableBalance / annuityFactor);
        
        // עדכון הקצבה עם היתרה והסכום החודשי החדשים
        await apiFetch(`/pension-funds/${selectedFund.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            fund_name: selectedFund.fund_name,
            fund_type: selectedFund.fund_type,
            input_mode: selectedFund.input_mode,
            balance: newCommutableBalance,  // עדכון היתרה המקורית
            pension_amount: newMonthlyAmount,
            annuity_factor: annuityFactor,
            pension_start_date: selectedFund.pension_start_date,
            indexation_method: selectedFund.indexation_method || "none"
          })
        });
        
        // עדכון מקומי של הקצבה
        setFunds(funds.map(f => 
          f.id === selectedFund.id 
            ? { 
                ...f, 
                balance: newCommutableBalance,  // עדכון היתרה
                commutable_balance: newCommutableBalance,  // עדכון יתרה להיוון
                pension_amount: newMonthlyAmount,
                monthly: newMonthlyAmount 
              }
            : f
        ));
      }

      // יצירת אובייקט ההיוון עם ה-ID של ה-capital asset שנוצר
      const newCommutation: Commutation = {
        id: (createdAsset as any).id, // השתמש ב-ID האמיתי מה-capital asset
        pension_fund_id: commutationForm.pension_fund_id,
        exempt_amount: commutationForm.exempt_amount,
        commutation_date: commutationForm.commutation_date,
        commutation_type: commutationForm.commutation_type,
      };
      
      setCommutations([...commutations, newCommutation]);

      // רענון רשימת הקצבאות
      await loadFunds();

      // Reset form
      setCommutationForm({
        pension_fund_id: undefined,
        exempt_amount: 0,
        commutation_date: "",
        commutation_type: "taxable",
      });

      alert(`היוון נוצר בהצלחה!\n${shouldDeleteFund ? 'הקצבה נמחקה כולה' : `נותרה יתרה של ₪${(fundBalance - commutationForm.exempt_amount).toLocaleString()}`}`);
    } catch (e: any) {
      setError(`שגיאה ביצירת היוון: ${e?.message || e}`);
    }
  }

  async function handleCommutationDelete(commutationId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את ההיוון? היתרה תוחזר לקצבה.")) {
      return;
    }
    
    try {
      // מציאת ההיוון שנמחק
      const commutationToDelete = commutations.find(c => c.id === commutationId);
      if (!commutationToDelete) {
        throw new Error("היוון לא נמצא");
      }
      
      // מציאת הקצבה המקורית
      const relatedFund = funds.find(f => f.id === commutationToDelete.pension_fund_id);
      if (!relatedFund) {
        throw new Error("הקצבה המקורית לא נמצאה");
      }
      
      // חישוב היתרה החדשה (החזרת סכום ההיוון)
      const currentBalance = relatedFund.balance || 0;
      const commutationAmount = commutationToDelete.exempt_amount || 0;
      const newBalance = currentBalance + commutationAmount;
      
      // חישוב הקצבה החודשית החדשה
      const annuityFactor = relatedFund.annuity_factor || 200;
      const newMonthlyAmount = Math.round(newBalance / annuityFactor);
      
      // עדכון הקצבה בשרת
      await apiFetch(`/pension-funds/${relatedFund.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          fund_name: relatedFund.fund_name,
          fund_type: relatedFund.fund_type,
          input_mode: relatedFund.input_mode,
          balance: newBalance,  // החזרת היתרה
          pension_amount: newMonthlyAmount,
          annuity_factor: annuityFactor,
          pension_start_date: relatedFund.pension_start_date,
          indexation_method: relatedFund.indexation_method || "none"
        })
      });
      
      // מחיקת ה-capital asset שמייצג את ההיוון
      await apiFetch(`/clients/${clientId}/capital-assets/${commutationId}`, {
        method: 'DELETE'
      });
      
      // עדכון ה-state המקומי של ההיוונים
      setCommutations(commutations.filter(c => c.id !== commutationId));
      
      // עדכון ה-state המקומי של הקצבה
      setFunds(funds.map(f => 
        f.id === relatedFund.id 
          ? { 
              ...f, 
              balance: newBalance,
              commutable_balance: newBalance,
              pension_amount: newMonthlyAmount,
              monthly: newMonthlyAmount 
            }
          : f
      ));
      
      alert(`ההיוון נמחק בהצלחה!\nהיתרה הוחזרה לקצבה: ₪${newBalance.toLocaleString()}\nקצבה חודשית חדשה: ₪${newMonthlyAmount.toLocaleString()}`);
    } catch (e: any) {
      setError(`שגיאה במחיקת היוון: ${e?.message || e}`);
    }
  }

  if (loading) return <div>טוען קצבאות...</div>;

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💰 קצבאות והיוונים</h1>
            <p className="card-subtitle">ניהול קצבאות פנסיוניות והיוונים פטורים ממס</p>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={handleDeleteAll}
              className="btn"
              style={{ 
                backgroundColor: '#dc3545', 
                color: 'white',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
              disabled={funds.length === 0 && commutations.length === 0}
            >
              🗑️ מחק הכל
            </button>
            <Link to={`/clients/${clientId}`} className="btn btn-secondary">
              ← חזרה
            </Link>
          </div>
        </div>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Create Forms - Side by Side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: 32 }}>
        {/* הוסף קצבה */}
        <section style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
          <h3>{editingFundId ? 'ערוך קצבה' : 'הוסף קצבה'}</h3>
        
        {clientData && clientData.birth_date && (
          <div style={{ marginBottom: 10, fontSize: "0.9em", color: "#666" }}>
            <strong>מידע:</strong> אם לא תזין תאריך התחלת קצבה, המערכת תשתמש בתאריך הקצבה המוקדמת ביותר או בגיל פרישה המחושב לפי החוק (משתנה לפי שנת לידה).
          </div>
        )}
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 400 }}>
          <input
            type="text"
            placeholder="שם המשלם"
            value={form.fund_name || ""}
            onChange={(e) => setForm({ ...form, fund_name: e.target.value })}
            style={{ padding: 8 }}
            required
          />
          
          <div>
            <label>מצב חישוב:</label>
            <select
              value={form.calculation_mode}
              onChange={(e) => setForm({ ...form, calculation_mode: e.target.value as "calculated" | "manual" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="calculated">מחושב</option>
              <option value="manual">ידני</option>
            </select>
          </div>

          {form.calculation_mode === "calculated" && (
            <>
              <input
                type="number"
                placeholder="יתרה"
                value={form.balance || ""}
                onChange={(e) => setForm({ ...form, balance: parseFloat(e.target.value) || 0 })}
                style={{ padding: 8 }}
              />
              <input
                type="number"
                step="0.01"
                placeholder="מקדם קצבה"
                value={form.annuity_factor || ""}
                onChange={(e) => setForm({ ...form, annuity_factor: parseFloat(e.target.value) || 0 })}
                style={{ padding: 8 }}
              />
            </>
          )}

          {form.calculation_mode === "manual" && (
            <input
              type="number"
              placeholder="סכום חודשי"
              value={form.monthly_amount || ""}
              onChange={(e) => setForm({ ...form, monthly_amount: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
            />
          )}

          <input
            type="text"
            placeholder="תיק ניכויים"
            value={form.deduction_file || ""}
            onChange={(e) => setForm({ ...form, deduction_file: e.target.value })}
            style={{ padding: 8 }}
          />

          <input
            type="text"
            placeholder="DD/MM/YYYY"
            value={form.pension_start_date || ""}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setForm({ ...form, pension_start_date: formatted });
            }}
            style={{ padding: 8 }}
            maxLength={10}
          />

          <div>
            <label>שיטת הצמדה:</label>
            <select
              value={form.indexation_method}
              onChange={(e) => setForm({ ...form, indexation_method: e.target.value as "none" | "fixed" | "cpi" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="none">ללא הצמדה</option>
              <option value="fixed">הצמדה קבועה</option>
              <option value="cpi">הצמדה למדד</option>
            </select>
          </div>

          {form.indexation_method === "fixed" && (
            <input
              type="number"
              step="0.01"
              placeholder="שיעור הצמדה קבוע (%)"
              value={form.indexation_rate || ""}
              onChange={(e) => setForm({ ...form, indexation_rate: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
            />
          )}

          <div>
            <label>יחס למס:</label>
            <select
              value={form.tax_treatment || "taxable"}
              onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "taxable" | "exempt" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="taxable">חייב במס</option>
              <option value="exempt">פטור ממס</option>
            </select>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button 
              type="submit" 
              style={{ 
                padding: "10px 16px", 
                backgroundColor: "#007bff", 
                color: "white", 
                border: "none", 
                borderRadius: 4,
                flex: 1
              }}
            >
              {editingFundId ? 'שמור שינויים' : 'צור קצבה'}
            </button>
            
            {editingFundId && (
              <button 
                type="button" 
                onClick={() => {
                  setEditingFundId(null);
                  setForm({
                    fund_name: "",
                    calculation_mode: "calculated",
                    balance: 0,
                    annuity_factor: 0,
                    indexation_method: "none",
                    indexation_rate: 0,
                    deduction_file: "",
                    pension_start_date: "",
                    tax_treatment: "taxable",
                  });
                }}
                style={{ 
                  padding: "10px 16px", 
                  backgroundColor: "#6c757d", 
                  color: "white", 
                  border: "none", 
                  borderRadius: 4 
                }}
              >
                בטל עריכה
              </button>
            )}
          </div>
        </form>
        </section>

        {/* הוסף היוון */}
        <section style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
          <h3>הוסף היוון</h3>
          <form onSubmit={handleCommutationSubmit} style={{ display: "grid", gap: 12 }}>
            <div>
              <label>קצבה:</label>
              <select
                value={commutationForm.pension_fund_id || ""}
                onChange={(e) => setCommutationForm({ ...commutationForm, pension_fund_id: parseInt(e.target.value) })}
                style={{ padding: 8, width: "100%" }}
                required
              >
                <option value="">בחר קצבה</option>
                {funds.map((fund) => (
                  <option key={fund.id} value={fund.id}>
                    {fund.fund_name} - יתרה מקורית: ₪{calculateOriginalBalance(fund).toLocaleString()}
                  </option>
                ))}
              </select>
            </div>
            
            <input
              type="number"
              placeholder="סכום היוון"
              value={commutationForm.exempt_amount || ""}
              onChange={(e) => setCommutationForm({ ...commutationForm, exempt_amount: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
              required
            />
            
            <input
              type="date"
              placeholder="תאריך היוון"
              value={commutationForm.commutation_date || ""}
              onChange={(e) => setCommutationForm({ ...commutationForm, commutation_date: e.target.value })}
              style={{ padding: 8 }}
              required
            />
            
            <div>
              <label>יחס מס:</label>
              {(() => {
                const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
                const isExemptPension = selectedFund?.tax_treatment === "exempt";
                
                return (
                  <>
                    <select
                      value={commutationForm.commutation_type}
                      onChange={(e) => setCommutationForm({ ...commutationForm, commutation_type: e.target.value as "exempt" | "taxable" })}
                      style={{ 
                        padding: 8, 
                        width: "100%",
                        backgroundColor: isExemptPension ? "#f0f0f0" : "white",
                        cursor: isExemptPension ? "not-allowed" : "pointer"
                      }}
                      disabled={isExemptPension}
                    >
                      <option value="taxable">חייב במס</option>
                      <option value="exempt">פטור ממס</option>
                    </select>
                    {isExemptPension && (
                      <div style={{ fontSize: "12px", color: "#856404", marginTop: "4px", fontStyle: "italic" }}>
                        קצבה פטורה ממס - ההיוון חייב להיות פטור ממס
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
            
            <button type="submit" style={{ padding: "8px 12px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: 4 }}>
              הוסף היוון
            </button>
          </form>
        </section>
      </div>

      {/* Main Content - Two Columns */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
        {/* Left Column - Pension Funds */}
        <section>
          <h3>רשימת קצבאות</h3>
        {funds.length === 0 ? (
          <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
            אין קצבאות
          </div>
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            {funds.map((fund, index) => (
              <div key={fund.id || index} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
                <div style={{ display: "grid", gap: 8 }}>
                  <div><strong>שם המשלם:</strong> {fund.fund_name || "קצבה"}</div>
                  {fund.deduction_file && <div><strong>תיק ניכויים:</strong> {fund.deduction_file}</div>}
                  <div><strong>מצב:</strong> {fund.input_mode === "calculated" ? "מחושב" : "ידני"}</div>
                  
                  {/* הצגת יתרה שעליה מבוססת הקצבה - תמיד */}
                  <div style={{ 
                    backgroundColor: "#fff3cd", 
                    padding: "8px", 
                    borderRadius: "4px", 
                    border: "1px solid #ffc107",
                    marginTop: "8px",
                    marginBottom: "8px",
                    fontSize: "1.05em"
                  }}>
                    <strong>יתרה שעליה מבוססת הקצבה:</strong> ₪{calculateOriginalBalance(fund).toLocaleString()}
                  </div>
                  
                  {fund.input_mode === "calculated" && (
                    <>
                      {((fund.balance || 0) > 0 || (fund.current_balance || 0) > 0) && (
                        <div><strong>מקדם קצבה:</strong> {fund.annuity_factor}</div>
                      )}
                      {(fund.balance === 0 || fund.balance === undefined) && 
                       (fund.current_balance === 0 || fund.current_balance === undefined) && 
                       (fund.computed_monthly_amount || 0) > 0 && (
                        <div style={{ color: "green", fontWeight: "bold" }}>
                          <strong>היתרה הומרה לקצבה חודשית</strong>
                        </div>
                      )}
                    </>
                  )}
                  
                  <div><strong>תאריך תחילה:</strong> {fund.pension_start_date ? formatDateToDDMMYY(new Date(fund.pension_start_date)) : (fund.start_date ? formatDateToDDMMYY(new Date(fund.start_date)) : "לא צוין")}</div>
                  <div><strong>הצמדה:</strong> {
                    fund.indexation_method === "none" ? "ללא" :
                    fund.indexation_method === "fixed" ? `קבועה ${fund.indexation_rate}%` :
                    "למדד"
                  }</div>
                  <div><strong>יחס למס:</strong> {
                    fund.tax_treatment === "exempt" ? "פטור ממס" :
                    fund.tax_treatment === "capital_gains" ? "מס רווח הון" :
                    "חייב במס"
                  }</div>
                  
                  {/* הצגת סכום חודשי בכל מקרה - מודגש ובולט */}
                  <div style={{ 
                    color: "green", 
                    fontWeight: "bold", 
                    backgroundColor: "#f0fff0", 
                    padding: "8px", 
                    borderRadius: "4px", 
                    border: "1px solid #28a745",
                    marginTop: "10px",
                    marginBottom: "10px",
                    fontSize: "1.1em"
                  }}>
                    <strong>סכום חודשי:</strong> ₪{(
                      // השרת מחזיר את הסכום החודשי הנכון
                      fund.monthly || fund.computed_monthly_amount || fund.pension_amount || fund.monthly_amount || 0
                    ).toLocaleString()}
                  </div>
                  
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    {/* כפתור חישוב - רק למצב מחושב עם יתרה */}
                    {fund.id && (fund.input_mode === "calculated" || fund.calculation_mode === "calculated") && 
                     ((fund.balance || 0) > 0 || (fund.current_balance || 0) > 0) && (
                      <button
                        type="button"
                        onClick={() => handleCompute(fund.id!)}
                        style={{ padding: "8px 12px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: 4 }}
                      >
                        חשב ושמור
                      </button>
                    )}
                    
                    {/* כפתור עריכה - תמיד מוצג */}
                    <button
                      type="button"
                      onClick={() => handleEdit(fund)}
                      style={{ padding: "8px 12px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}
                    >
                      ערוך
                    </button>
                    
                    {/* כפתור מחיקה - רק אם יש ID */}
                    {fund.id && (
                      <button
                        type="button"
                        onClick={() => handleDelete(fund.id!)}
                        style={{ padding: "8px 12px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: 4 }}
                      >
                        מחק
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        </section>

        {/* Right Column - Commutations List */}
        <section>
          <h3>רשימת היוונים</h3>
            {commutations.length === 0 ? (
              <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
                אין היוונים
              </div>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {commutations.map((commutation) => {
                  const relatedFund = funds.find(f => f.id === commutation.pension_fund_id);
                  return (
                    <div key={commutation.id} style={{ padding: 12, border: "1px solid #ddd", borderRadius: 4 }}>
                      <div><strong>קצבה:</strong> {relatedFund?.fund_name || "לא נמצא"}</div>
                      <div><strong>סכום היוון:</strong> ₪{(commutation.exempt_amount || 0).toLocaleString()}</div>
                      <div><strong>תאריך:</strong> {commutation.commutation_date}</div>
                      <div><strong>יחס מס:</strong> {commutation.commutation_type === "exempt" ? "פטור ממס" : "חייב במס"}</div>
                      <button
                        type="button"
                        onClick={() => handleCommutationDelete(commutation.id!)}
                        style={{ padding: "4px 8px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: 4, marginTop: 8 }}
                      >
                        מחק
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
        </section>
      </div>
      </div>
    </div>
  );
}
