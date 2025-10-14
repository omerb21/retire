import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type Scenario = {
  id?: number;
  name: string;
  description?: string;
  retirement_age?: number;
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
    retirement_age: 67,
  });
  const [showCashflow, setShowCashflow] = useState(false);

  async function loadScenarios() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      // שימוש בפנייה ישירה לשרת במקום apiFetch
      const response = await fetch(`/api/v1/clients/${clientId}/scenarios`);
      
      if (!response.ok) {
        if (response.status === 404) {
          // If no scenarios found, create empty array instead of showing error
          setScenarios([]);
          setError(""); // Clear error for 404 - it's normal to have no scenarios initially
          return;
        }
        throw new Error(`HTTP Error: ${response.status}`);
      }
      
      const data = await response.json();
      // Handle both direct array and wrapped response formats
      const scenarios = Array.isArray(data) ? data : (data?.scenarios || data?.items || []);
      setScenarios(scenarios);
    } catch (e: any) {
      // If no scenarios found, create empty array instead of showing error
      if (e?.message?.includes('Not Found') || e?.status === 404) {
        setScenarios([]);
        setError(""); // Clear error for 404 - it's normal to have no scenarios initially
      } else {
        setError(`שגיאה בטעינת תרחישים: ${e?.message || e}`);
      }
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
    setLoading(true);
    
    try {
      // Basic validation
      if (!form.name || form.name.trim() === "") {
        throw new Error("חובה למלא שם תרחיש");
      }

      const payload = {
        name: form.name.trim(),
        description: form.description?.trim() || "",
        retirement_age: form.retirement_age || 67,
      };

      // שימוש בפנייה ישירה לשרת במקום apiFetch
      const response = await fetch(`/api/v1/clients/${clientId}/scenarios`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `שגיאה ${response.status}`);
      }
      
      const newScenario = await response.json();

      // Reset form
      setForm({
        name: "",
        description: "",
        retirement_age: 67,
      });

      // Reload scenarios and select the newly created one
      await loadScenarios();
      
      // Select the newly created scenario if available
      if (newScenario && newScenario.id) {
        setSelectedScenarioId(newScenario.id);
      }
    } catch (e: any) {
      setError(`שגיאה ביצירת תרחיש: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleIntegrateIncomes() {
    if (!clientId || !selectedScenarioId) {
      setError("יש לבחור תרחיש לפני שילוב");
      return;
    }

    setError("");
    setShowCashflow(false);
    setLoading(true);
    
    try {
      // First get the scenario cashflow
      const scenarioResponse = await fetch(`/api/v1/scenarios/${selectedScenarioId}/cashflow`);
      if (!scenarioResponse.ok) {
        throw new Error(`שגיאה בקבלת תזרים: ${scenarioResponse.status}`);
      }
      const scenarioData = await scenarioResponse.json();
      
      // Then integrate incomes with the cashflow
      const response = await fetch(`/api/v1/clients/${clientId}/cashflow/integrate-incomes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(scenarioData?.cashflow || [])
      });
      
      if (!response.ok) {
        throw new Error(`שגיאה בשילוב הכנסות: ${response.status}`);
      }
      
      const data = await response.json();
      setCashflow(data || []);
      setShowCashflow(true);
    } catch (e: any) {
      setError(`שגיאה בשילוב הכנסות: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleIntegrateAssets() {
    if (!clientId || !selectedScenarioId) {
      setError("יש לבחור תרחיש לפני שילוב");
      return;
    }

    setError("");
    setShowCashflow(false);
    setLoading(true);
    
    try {
      // First get the scenario cashflow
      const scenarioResponse = await fetch(`/api/v1/scenarios/${selectedScenarioId}/cashflow`);
      if (!scenarioResponse.ok) {
        throw new Error(`שגיאה בקבלת תזרים: ${scenarioResponse.status}`);
      }
      const scenarioData = await scenarioResponse.json();
      
      // Then integrate assets with the cashflow
      const response = await fetch(`/api/v1/clients/${clientId}/cashflow/integrate-assets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(scenarioData?.cashflow || [])
      });
      
      if (!response.ok) {
        throw new Error(`שגיאה בשילוב נכסים: ${response.status}`);
      }
      
      const data = await response.json();
      setCashflow(data || []);
      setShowCashflow(true);
    } catch (e: any) {
      setError(`שגיאה בשילוב נכסים: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleIntegrateAll() {
    if (!clientId || !selectedScenarioId) {
      setError("יש לבחור תרחיש לפני שילוב");
      return;
    }

    setError("");
    setShowCashflow(false);
    setLoading(true);
    
    try {
      // First get the scenario cashflow
      const scenarioResponse = await fetch(`/api/v1/scenarios/${selectedScenarioId}/cashflow`);
      if (!scenarioResponse.ok) {
        throw new Error(`שגיאה בקבלת תזרים: ${scenarioResponse.status}`);
      }
      const scenarioData = await scenarioResponse.json();
      
      // Then integrate all with the cashflow
      const response = await fetch(`/api/v1/clients/${clientId}/cashflow/integrate-all`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(scenarioData?.cashflow || [])
      });
      
      if (!response.ok) {
        throw new Error(`שגיאה בשילוב כולל: ${response.status}`);
      }
      
      const data = await response.json();
      setCashflow(data || []);
      setShowCashflow(true);
    } catch (e: any) {
      setError(`שגיאה בשילוב כולל: ${e?.message || e}`);
    } finally {
      setLoading(false);
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

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label htmlFor="retirement-age" style={{ minWidth: "100px" }}>גיל פרישה:</label>
            <input
              id="retirement-age"
              type="number"
              min="50"
              max="75"
              value={form.retirement_age || 67}
              onChange={(e) => setForm({ ...form, retirement_age: parseInt(e.target.value) || 67 })}
              style={{ padding: 8, width: "80px" }}
            />
            <span style={{ fontSize: "14px", color: "#666" }}>(50-75)</span>
          </div>

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
                  {scenario.retirement_age && (
                    <div><strong>גיל פרישה:</strong> {scenario.retirement_age}</div>
                  )}
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
