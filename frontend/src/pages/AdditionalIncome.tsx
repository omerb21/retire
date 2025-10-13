import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

type AdditionalIncome = {
  id?: number;
  source_type: string;
  income_name: string; // הוספת שדה שם הכנסה
  amount: number;
  frequency: "monthly" | "quarterly" | "annual";
  start_date: string;
  end_date?: string;
  indexation_method: "none" | "fixed" | "cpi";
  fixed_rate?: number;
  tax_treatment: "exempt" | "taxable" | "fixed_rate";
  tax_rate?: number;
  computed_monthly_amount?: number;
};

// מיפוי סוגי הכנסות באנגלית לעברית
const INCOME_TYPE_MAP: Record<string, string> = {
  "rental": "שכירות",
  "dividends": "דיבידנדים",
  "interest": "ריבית",
  "business": "עסק",
  "freelance": "עבודה עצמאית",
  "other": "אחר"
};

// סוגי הכנסות באנגלית (לשימוש בצד השרת)
const INCOME_TYPES = [
  "rental", "dividends", "interest", "business", "freelance", "other"
];

export default function AdditionalIncome() {
  const { id: clientId } = useParams<{ id: string }>();
  const [incomes, setIncomes] = useState<AdditionalIncome[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [editingIncomeId, setEditingIncomeId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<AdditionalIncome>>({
    source_type: "rental",
    income_name: "", // הוספת שדה שם הכנסה
    amount: 0,
    frequency: "monthly",
    start_date: "",
    indexation_method: "none",
    tax_treatment: "taxable",
    fixed_rate: 0,
    tax_rate: 0,
  });

  async function loadIncomes() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const data = await apiFetch<AdditionalIncome[]>(`/clients/${clientId}/additional-incomes/`);
      setIncomes(data || []);
    } catch (e: any) {
      setError(`שגיאה בטעינת הכנסות נוספות: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadIncomes();
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      // Basic validation
      if (!form.source_type) {
        throw new Error("חובה לבחור סוג הכנסה");
      }
      if (!form.amount || form.amount <= 0) {
        throw new Error("חובה למלא סכום חיובי");
      }
      if (!form.start_date) {
        throw new Error("חובה למלא תאריך התחלה");
      }

      if (form.indexation_method === "fixed" && (!form.fixed_rate || form.fixed_rate < 0)) {
        throw new Error("חובה למלא שיעור הצמדה קבוע");
      }

      if (form.tax_treatment === "fixed_rate" && (!form.tax_rate || form.tax_rate < 0 || form.tax_rate > 100)) {
        throw new Error("חובה למלא שיעור מס בין 0-100");
      }

      // Align date to first of month
      const alignedStartDate = new Date(form.start_date);
      alignedStartDate.setDate(1);
      
      let alignedEndDate;
      if (form.end_date) {
        alignedEndDate = new Date(form.end_date);
        alignedEndDate.setDate(1);
      }
      
      const payload = {
        ...form,
        amount: Number(form.amount),
        fixed_rate: form.fixed_rate !== undefined ? Number(form.fixed_rate) : undefined,
        tax_rate: form.tax_rate !== undefined ? Number(form.tax_rate) : undefined,
        start_date: formatDateToDDMMYY(alignedStartDate),
        end_date: alignedEndDate ? formatDateToDDMMYY(alignedEndDate) : null,
      };

      // בדיקה אם אנחנו במצב עריכה או יצירה חדשה
      if (editingIncomeId) {
        // עדכון הכנסה קיימת
        console.log(`מעדכן הכנסה קיימת עם מזהה: ${editingIncomeId}`);
        await apiFetch(`/clients/${clientId}/additional-incomes/${editingIncomeId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        // יצירת הכנסה חדשה
        await apiFetch(`/clients/${clientId}/additional-incomes/`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      // איפוס הטופס ומצב העריכה
      setForm({
        source_type: "rental",
        income_name: "", // הוספת שדה שם הכנסה
        amount: 0,
        frequency: "monthly",
        start_date: "",
        indexation_method: "none",
        tax_treatment: "taxable",
        fixed_rate: 0,
        tax_rate: 0,
      });
      
      // איפוס מצב העריכה
      setEditingIncomeId(null);

      // Reload incomes
      await loadIncomes();
    } catch (e: any) {
      setError(`שגיאה ביצירת הכנסה נוספת: ${e?.message || e}`);
    }
  }

  async function handleDelete(incomeId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את ההכנסה הנוספת?")) {
      return;
    }

    try {
      await apiFetch(`/clients/${clientId}/additional-incomes/${incomeId}`, {
        method: "DELETE",
      });
      
      // Reload incomes after deletion
      await loadIncomes();
    } catch (e: any) {
      setError(`שגיאה במחיקת הכנסה נוספת: ${e?.message || e}`);
    }
  }

  function handleEdit(income: any) {
    // שמירת מזהה ההכנסה שעורכים
    setEditingIncomeId(income.id || null);
    
    // Populate form with income data for editing
    setForm({
      source_type: income.source_type,
      income_name: income.income_name || "", // הוספת שדה שם הכנסה
      amount: income.amount || 0,
      frequency: income.frequency,
      start_date: income.start_date,
      end_date: income.end_date || "",
      indexation_method: income.indexation_method,
      tax_treatment: income.tax_treatment,
      fixed_rate: income.fixed_rate || 0,
      tax_rate: income.tax_rate || 0,
    });
    
    // Scroll to form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (loading) return <div>טוען הכנסות נוספות...</div>;

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to={`/clients/${clientId}`}>← חזרה לפרטי לקוח</Link>
      </div>
      
      <h2>הכנסות נוספות</h2>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Create Form */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>{editingIncomeId ? 'ערוך הכנסה נוספת' : 'הוסף הכנסה נוספת'}</h3>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 500 }}>
          <div>
            <label>סוג הכנסה:</label>
            <select
              value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}
              style={{ padding: 8, width: "100%" }}
            >
              {INCOME_TYPES.map(type => (
                <option key={type} value={type}>{INCOME_TYPE_MAP[type]}</option>
              ))}
            </select>
          </div>

          <div>
            <label>שם הכנסה:</label>
            <input
              type="text"
              placeholder="שם הכנסה"
              value={form.income_name || ""}
              onChange={(e) => setForm({ ...form, income_name: e.target.value })}
              style={{ padding: 8, width: "100%" }}
              required
            />
          </div>

          <input
            type="number"
            placeholder="סכום"
            value={form.amount || ""}
            onChange={(e) => setForm({ ...form, amount: parseFloat(e.target.value) || 0 })}
            style={{ padding: 8 }}
          />

          <div>
            <label>תדירות:</label>
            <select
              value={form.frequency}
              onChange={(e) => setForm({ ...form, frequency: e.target.value as "monthly" | "quarterly" | "annual" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="monthly">חודשי</option>
              <option value="quarterly">רבעוני</option>
              <option value="annual">שנתי</option>
            </select>
          </div>

          <input
            type="text"
            placeholder="DD/MM/YY"
            value={convertISOToDDMMYY(form.start_date || '') || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              const isoDate = convertDDMMYYToISO(formatted);
              setForm({ ...form, start_date: isoDate });
            }}
            style={{ padding: 8 }}
            maxLength={8}
          />

          <input
            type="text"
            placeholder="DD/MM/YY (אופציונלי)"
            value={convertISOToDDMMYY(form.end_date || '') || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              const isoDate = formatted ? convertDDMMYYToISO(formatted) : undefined;
              setForm({ ...form, end_date: isoDate });
            }}
            style={{ padding: 8 }}
            maxLength={8}
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
              value={form.fixed_rate || ""}
              onChange={(e) => setForm({ ...form, fixed_rate: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
            />
          )}

          <div>
            <label>יחס מס:</label>
            <select
              value={form.tax_treatment}
              onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "exempt" | "taxable" | "fixed_rate" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="exempt">פטור ממס</option>
              <option value="taxable">חייב במס</option>
              <option value="fixed_rate">שיעור מס קבוע</option>
            </select>
          </div>

          {form.tax_treatment === "fixed_rate" && (
            <input
              type="number"
              step="0.01"
              placeholder="שיעור מס (%)"
              value={form.tax_rate || ""}
              onChange={(e) => setForm({ ...form, tax_rate: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
            />
          )}

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
              {editingIncomeId ? 'שמור שינויים' : 'צור הכנסה נוספת'}
            </button>
            
            {editingIncomeId && (
              <button 
                type="button" 
                onClick={() => {
                  setEditingIncomeId(null);
                  setForm({
                    source_type: "rental",
                    income_name: "",
                    amount: 0,
                    frequency: "monthly",
                    start_date: "",
                    indexation_method: "none",
                    tax_treatment: "taxable",
                    fixed_rate: 0,
                    tax_rate: 0,
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

      {/* Incomes List */}
      <section>
        <h3>רשימת הכנסות נוספות</h3>
        {incomes.length === 0 ? (
          <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
            אין הכנסות נוספות
          </div>
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            {incomes.map((income, index) => (
              <div key={income.id || index} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
                <div style={{ display: "grid", gap: 8 }}>
                  <div><strong>סוג:</strong> {INCOME_TYPE_MAP[income.source_type] || income.source_type}</div>
                  <div><strong>שם הכנסה:</strong> {income.income_name || ""}</div>
                  <div><strong>סכום:</strong> ₪{income.amount?.toLocaleString()}</div>
                  <div><strong>תדירות:</strong> {
                    income.frequency === "monthly" ? "חודשי" :
                    income.frequency === "quarterly" ? "רבעוני" : "שנתי"
                  }</div>
                  <div><strong>תאריך התחלה:</strong> {formatDateToDDMMYY(new Date(income.start_date))}</div>
                  {income.end_date && <div><strong>תאריך סיום:</strong> {formatDateToDDMMYY(new Date(income.end_date))}</div>}
                  <div><strong>הצמדה:</strong> {
                    income.indexation_method === "none" ? "ללא" :
                    income.indexation_method === "fixed" ? `קבועה ${income.fixed_rate}%` :
                    "למדד"
                  }</div>
                  <div><strong>יחס מס:</strong> {
                    income.tax_treatment === "exempt" ? "פטור ממס" :
                    income.tax_treatment === "taxable" ? "חייב במס" :
                    `שיעור קבוע ${income.tax_rate}%`
                  }</div>
                  
                  {income.computed_monthly_amount && (
                    <div style={{ color: "green", fontWeight: "bold" }}>
                      <strong>סכום חודשי מחושב:</strong> ₪{income.computed_monthly_amount.toLocaleString()}
                    </div>
                  )}
                  
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    {income.id && (
                      <button
                        type="button"
                        onClick={() => handleEdit(income)}
                        style={{ padding: "8px 12px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}
                      >
                        ערוך
                      </button>
                    )}
                    
                    {income.id && (
                      <button
                        type="button"
                        onClick={() => handleDelete(income.id!)}
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
    </div>
  );
}
