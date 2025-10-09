import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type PensionFund = {
  id?: number;
  fund_name?: string;
  fund_number?: string;
  fund_type?: string;
  calculation_mode?: "calculated" | "manual"; // לתאימות לאחור
  input_mode?: "calculated" | "manual";
  current_balance?: number;
  balance?: number;
  annuity_factor?: number;
  monthly_amount?: number;
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
};

export default function PensionFunds() {
  const { id: clientId } = useParams<{ id: string }>();
  const [funds, setFunds] = useState<PensionFund[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [form, setForm] = useState<Partial<PensionFund>>({
    fund_name: "",
    calculation_mode: "calculated",
    balance: 0,
    annuity_factor: 0,
    pension_start_date: "",
    indexation_method: "none",
    indexation_rate: 0,
  });

  async function loadFunds() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const data = await apiFetch<PensionFund[]>(`/clients/${clientId}/pension-funds`);
      console.log("Loaded pension funds:", data);
      
      // מיפוי שדות לפורמט אחיד
      const mappedFunds = (data || []).map(fund => ({
        ...fund,
        balance: fund.current_balance || fund.balance,
        pension_start_date: fund.pension_start_date || fund.start_date
      }));
      
      setFunds(mappedFunds);
    } catch (e: any) {
      setError(`שגיאה בטעינת קרנות פנסיה: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadFunds();
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      // Basic validation
      if (!form.fund_name || form.fund_name.trim() === "") {
        throw new Error("חובה למלא שם קרן");
      }
      if (!form.pension_start_date) {
        throw new Error("חובה למלא תאריך תחילת פנסיה");
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

      // Align date to first of month
      const alignedDate = new Date(form.pension_start_date);
      alignedDate.setDate(1);
      
      // Create payload with exact field names matching backend schema
      const payload: Record<string, any> = {
        // Required fields from schema
        client_id: Number(clientId),
        fund_name: form.fund_name?.trim() || "קרן פנסיה",
        fund_type: "pension",
        input_mode: form.calculation_mode,
        start_date: alignedDate.toISOString().split('T')[0],
        pension_start_date: alignedDate.toISOString().split('T')[0],
        indexation_method: form.indexation_method || "none"
      };
      
      // Add mode-specific fields
      if (form.calculation_mode === "calculated") {
        payload.current_balance = Number(form.balance);
        payload.balance = Number(form.balance);
        payload.annuity_factor = Number(form.annuity_factor);
      } else if (form.calculation_mode === "manual") {
        payload.monthly_amount = Number(form.monthly_amount);
      }
      
      // Add indexation rate only if method is fixed
      if (form.indexation_method === "fixed" && form.indexation_rate !== undefined) {
        payload.indexation_rate = Number(form.indexation_rate);
      }
      
      console.log("Sending pension fund payload:", payload);

      await apiFetch(`/clients/${clientId}/pension-funds`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // Reset form
      setForm({
        fund_name: "",
        calculation_mode: "calculated",
        balance: 0,
        annuity_factor: 0,
        pension_start_date: "",
        indexation_method: "none",
        indexation_rate: 0,
      });

      // Reload funds
      await loadFunds();
    } catch (e: any) {
      setError(`שגיאה ביצירת קרן פנסיה: ${e?.message || e}`);
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
      
      // עדכון הקרן עם הסכום המחושב
      await apiFetch(`/clients/${clientId}/pension-funds/${fundId}`, {
        method: "PUT",
        body: JSON.stringify({
          ...fund,
          computed_monthly_amount: computed_monthly_amount,
          monthly_amount: computed_monthly_amount
        }),
      });
      
      // Reload to get updated computed amount
      await loadFunds();
    } catch (e: any) {
      setError(`שגיאה בחישוב: ${e?.message || e}`);
    }
  }

  async function handleDelete(fundId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את קרן הפנסיה?")) {
      return;
    }

    try {
      await apiFetch(`/pension-funds/${fundId}`, {
        method: "DELETE",
      });
      
      // Reload funds after deletion
      await loadFunds();
    } catch (e: any) {
      setError(`שגיאה במחיקת קרן פנסיה: ${e?.message || e}`);
    }
  }

  function handleEdit(fund: PensionFund) {
    // Populate form with fund data for editing
    setForm({
      fund_name: fund.fund_name || "",
      calculation_mode: fund.input_mode || fund.calculation_mode || "calculated",
      balance: fund.balance || 0,
      annuity_factor: fund.annuity_factor || 0,
      monthly_amount: fund.pension_amount || fund.monthly_amount || 0,
      pension_start_date: fund.pension_start_date,
      indexation_method: fund.indexation_method || "none",
      indexation_rate: fund.fixed_index_rate || fund.indexation_rate || 0,
    });
    
    // Scroll to form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (loading) return <div>טוען קרנות פנסיה...</div>;

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to={`/clients/${clientId}`}>← חזרה לפרטי לקוח</Link>
      </div>
      
      <h2>קרנות פנסיה</h2>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Create Form */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>הוסף קרן פנסיה</h3>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 400 }}>
          <input
            type="text"
            placeholder="שם הקרן"
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
            type="date"
            placeholder="תאריך תחילת פנסיה"
            value={form.pension_start_date}
            onChange={(e) => setForm({ ...form, pension_start_date: e.target.value })}
            style={{ padding: 8 }}
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

          <button type="submit" style={{ padding: "10px 16px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}>
            צור קרן פנסיה
          </button>
        </form>
      </section>

      {/* Funds List */}
      <section>
        <h3>רשימת קרנות פנסיה</h3>
        {funds.length === 0 ? (
          <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
            אין קרנות פנסיה
          </div>
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            {funds.map((fund, index) => (
              <div key={fund.id || index} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
                <div style={{ display: "grid", gap: 8 }}>
                  <div><strong>שם הקרן:</strong> {fund.fund_name || "קרן פנסיה"}</div>
                  <div><strong>מצב:</strong> {fund.input_mode === "calculated" ? "מחושב" : "ידני"}</div>
                  
                  {fund.input_mode === "calculated" && (
                    <>
                      <div><strong>יתרה:</strong> ₪{(fund.balance || 0).toLocaleString()}</div>
                      <div><strong>מקדם קצבה:</strong> {fund.annuity_factor}</div>
                    </>
                  )}
                  
                  {fund.input_mode === "manual" && (
                    <div><strong>סכום חודשי:</strong> ₪{(fund.pension_amount || fund.monthly_amount || 0).toLocaleString()}</div>
                  )}
                  
                  <div><strong>תאריך תחילה:</strong> {fund.pension_start_date || fund.start_date || "לא צוין"}</div>
                  <div><strong>הצמדה:</strong> {
                    fund.indexation_method === "none" ? "ללא" :
                    fund.indexation_method === "fixed" ? `קבועה ${fund.indexation_rate}%` :
                    "למדד"
                  }</div>
                  
                  {fund.computed_monthly_amount && (
                    <div style={{ color: "green", fontWeight: "bold" }}>
                      <strong>פנסיה חודשית מחושבת:</strong> ₪{fund.computed_monthly_amount.toLocaleString()}
                    </div>
                  )}
                  
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    {fund.id && (fund.input_mode === "calculated" || fund.calculation_mode === "calculated") && (
                      <button
                        type="button"
                        onClick={() => handleCompute(fund.id!)}
                        style={{ padding: "8px 12px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: 4 }}
                      >
                        חשב ושמור
                      </button>
                    )}
                    
                    {fund.id && (
                      <button
                        type="button"
                        onClick={() => handleEdit(fund)}
                        style={{ padding: "8px 12px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}
                      >
                        ערוך
                      </button>
                    )}
                    
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
    </div>
  );
}
