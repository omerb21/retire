import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type Scenario = {
  id?: number;
  name: string;
  description?: string;
  created_at?: string;
};

type CashflowEntry = {
  date: string;
  amount: number;
  source: string;
};

export default function Scenarios() {
  const { id: clientId } = useParams<{ id: string }>();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [cashflow, setCashflow] = useState<CashflowEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<Scenario>>({
    name: "",
    description: "",
  });
  const [showCashflow, setShowCashflow] = useState(false);

  async function loadScenarios() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const data = await apiFetch<Scenario[]>(`/clients/${clientId}/scenarios`);
      setScenarios(data || []);
    } catch (e: any) {
      setError(`שגיאה בטעינת תרחישים: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadScenarios();
  }, [clientId]);
  
  // Set the first scenario as selected when scenarios are loaded
  useEffect(() => {
    if (scenarios.length > 0 && !selectedScenarioId) {
      setSelectedScenarioId(scenarios[0].id || null);
    }
  }, [scenarios]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      // Basic validation
      if (!form.name || form.name.trim() === "") {
        throw new Error("חובה למלא שם תרחיש");
      }

      const payload = {
        name: form.name.trim(),
        description: form.description?.trim() || "",
      };

      const newScenario = await apiFetch<Scenario>(`/clients/${clientId}/scenarios`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // Reset form
      setForm({
        name: "",
        description: "",
      });

      // Reload scenarios and select the newly created one
      await loadScenarios();
      
      // Select the newly created scenario if available
      if (newScenario && newScenario.id) {
        setSelectedScenarioId(newScenario.id);
      }
    } catch (e: any) {
      setError(`שגיאה ביצירת תרחיש: ${e?.message || e}`);
    }
  }

  async function handleIntegrateIncomes() {
    if (!clientId || !selectedScenarioId) {
      setError("יש לבחור תרחיש לפני שילוב");
      return;
    }

    setError("");
    setShowCashflow(false);
    
    try {
      const data = await apiFetch<CashflowEntry[]>(`/clients/${clientId}/cashflow/integrate-incomes?scenario_id=${selectedScenarioId}`, {
        method: "POST",
      });
      
      setCashflow(data || []);
      setShowCashflow(true);
    } catch (e: any) {
      setError(`שגיאה בשילוב הכנסות: ${e?.message || e}`);
    }
  }

  async function handleIntegrateAssets() {
    if (!clientId || !selectedScenarioId) {
      setError("יש לבחור תרחיש לפני שילוב");
      return;
    }

    setError("");
    setShowCashflow(false);
    
    try {
      const data = await apiFetch<CashflowEntry[]>(`/clients/${clientId}/cashflow/integrate-assets?scenario_id=${selectedScenarioId}`, {
        method: "POST",
      });
      
      setCashflow(data || []);
      setShowCashflow(true);
    } catch (e: any) {
      setError(`שגיאה בשילוב נכסים: ${e?.message || e}`);
    }
  }

  async function handleIntegrateAll() {
    if (!clientId || !selectedScenarioId) {
      setError("יש לבחור תרחיש לפני שילוב");
      return;
    }

    setError("");
    setShowCashflow(false);
    
    try {
      const data = await apiFetch<CashflowEntry[]>(`/clients/${clientId}/cashflow/integrate-all?scenario_id=${selectedScenarioId}`, {
        method: "POST",
      });
      
      setCashflow(data || []);
      setShowCashflow(true);
    } catch (e: any) {
      setError(`שגיאה בשילוב כולל: ${e?.message || e}`);
    }
  }

  if (loading) return <div>טוען תרחישים...</div>;

  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to={`/clients/${clientId}`}>← חזרה לפרטי לקוח</Link>
      </div>
      
      <h2>תרחישים ואינטגרציה</h2>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Create Scenario Form */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>צור תרחיש חדש</h3>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 400 }}>
          <input
            type="text"
            placeholder="שם התרחיש"
            value={form.name || ""}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            style={{ padding: 8 }}
          />

          <textarea
            placeholder="תיאור (אופציונלי)"
            value={form.description || ""}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            style={{ padding: 8, minHeight: 60 }}
          />

          <button type="submit" style={{ padding: "10px 16px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}>
            צור תרחיש
          </button>
        </form>
      </section>

      {/* Integration Controls */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>שילוב תזרים מזומנים</h3>
        {!selectedScenarioId && scenarios.length > 0 && (
          <div style={{ marginBottom: 12, color: "#856404", backgroundColor: "#fff3cd", padding: 8, borderRadius: 4 }}>
            יש לבחור תרחיש מהרשימה למטה לפני שילוב
          </div>
        )}
        {scenarios.length === 0 && (
          <div style={{ marginBottom: 12, color: "#721c24", backgroundColor: "#f8d7da", padding: 8, borderRadius: 4 }}>
            יש ליצור תרחיש חדש לפני שילוב
          </div>
        )}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={handleIntegrateIncomes}
            style={{ padding: "10px 16px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: 4 }}
          >
            שלב הכנסות נוספות
          </button>
          
          <button
            type="button"
            onClick={handleIntegrateAssets}
            style={{ padding: "10px 16px", backgroundColor: "#17a2b8", color: "white", border: "none", borderRadius: 4 }}
          >
            שלב נכסי הון
          </button>
          
          <button
            type="button"
            onClick={handleIntegrateAll}
            style={{ padding: "10px 16px", backgroundColor: "#6f42c1", color: "white", border: "none", borderRadius: 4 }}
          >
            שלב הכל
          </button>
        </div>
      </section>

      {/* Cashflow Display */}
      {showCashflow && (
        <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
          <h3>תזרים מזומנים משולב</h3>
          {cashflow.length === 0 ? (
            <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
              אין נתוני תזרים
            </div>
          ) : (
            <div style={{ maxHeight: 400, overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ backgroundColor: "#f8f9fa" }}>
                    <th style={{ padding: 8, border: "1px solid #ddd", textAlign: "right" }}>תאריך</th>
                    <th style={{ padding: 8, border: "1px solid #ddd", textAlign: "right" }}>סכום</th>
                    <th style={{ padding: 8, border: "1px solid #ddd", textAlign: "right" }}>מקור</th>
                  </tr>
                </thead>
                <tbody>
                  {cashflow.map((entry, index) => (
                    <tr key={index}>
                      <td style={{ padding: 8, border: "1px solid #ddd" }}>{entry.date}</td>
                      <td style={{ padding: 8, border: "1px solid #ddd", textAlign: "left" }}>
                        ₪{entry.amount.toLocaleString()}
                      </td>
                      <td style={{ padding: 8, border: "1px solid #ddd" }}>{entry.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Scenarios List */}
      <section>
        <h3>רשימת תרחישים</h3>
        {scenarios.length === 0 ? (
          <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
            אין תרחישים
          </div>
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            {scenarios.map((scenario, index) => (
              <div 
                key={scenario.id || index} 
                style={{ 
                  padding: 16, 
                  border: "1px solid #ddd", 
                  borderRadius: 4,
                  backgroundColor: selectedScenarioId === scenario.id ? "#e6f7ff" : "transparent"
                }}
                onClick={() => setSelectedScenarioId(scenario.id || null)}
              >
                <div style={{ display: "grid", gap: 8 }}>
                  <div><strong>שם:</strong> {scenario.name}</div>
                  {scenario.description && <div><strong>תיאור:</strong> {scenario.description}</div>}
                  {scenario.created_at && (
                    <div><strong>נוצר:</strong> {new Date(scenario.created_at).toLocaleDateString('he-IL')}</div>
                  )}
                  {selectedScenarioId === scenario.id && (
                    <div style={{ color: "#0066cc", fontWeight: "bold" }}>✓ נבחר לשילוב</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
