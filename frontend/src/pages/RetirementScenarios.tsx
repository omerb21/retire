import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { formatCurrency } from "../lib/validation";

interface ExecutionAction {
  type: string;
  details: string;
  from: string;
  to: string;
  amount: number;
}

interface ScenarioResult {
  scenario_name: string;
  total_pension_monthly: number;
  total_capital: number;
  total_additional_income_monthly: number;
  estimated_npv: number;
  pension_funds_count: number;
  capital_assets_count: number;
  additional_incomes_count: number;
  execution_plan?: ExecutionAction[];
}

interface ScenariosResponse {
  success: boolean;
  client_id: number;
  retirement_age: number;
  scenarios: {
    scenario_1_max_pension: ScenarioResult;
    scenario_2_max_capital: ScenarioResult;
    scenario_3_max_npv: ScenarioResult;
  };
}

export default function RetirementScenarios() {
  const { id: clientId } = useParams<{ id: string }>();
  const [retirementAge, setRetirementAge] = useState<number>(67);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<number | null>(null);
  const [error, setError] = useState<string>("");
  const [results, setResults] = useState<ScenariosResponse | null>(null);
  const [successMessage, setSuccessMessage] = useState<string>("");

  // טעינת תרחישים שמורים בעת טעינת הדף
  useEffect(() => {
    if (clientId) {
      loadSavedScenarios();
    }
  }, [clientId]);

  const loadSavedScenarios = async () => {
    try {
      const response = await fetch(
        `/api/v1/clients/${clientId}/retirement-scenarios?retirement_age=${retirementAge}`
      );
      
      if (response.ok) {
        const data = await response.json();
        if (data.scenarios) {
          console.log('📥 Loaded saved scenarios:', data);
          setResults(data);
        }
      }
    } catch (err) {
      console.warn('No saved scenarios found or error loading:', err);
    }
  };

  const handleExecuteScenario = async (scenarioId: number, scenarioName: string) => {
    if (!clientId) {
      setError("מזהה לקוח חסר");
      return;
    }

    if (!window.confirm(`האם אתה בטוח שברצונך לבצע את התרחיש "${scenarioName}"?\n\nפעולה זו תשנה את המצב בפועל במערכת!`)) {
      return;
    }

    setExecuting(scenarioId);
    setError("");
    setSuccessMessage("");

    try {
      const response = await fetch(
        `/api/v1/clients/${clientId}/retirement-scenarios/${scenarioId}/execute`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        let errorMessage = `שגיאה: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          const textError = await response.text();
          errorMessage = textError || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setSuccessMessage(`✅ ${data.message || 'התרחיש בוצע בהצלחה!'}`);
      
      // רענון הדף אחרי 2 שניות
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err: any) {
      console.error("Scenario execution error:", err);
      setError(err.message || "שגיאה לא צפויה בביצוע התרחיש");
    } finally {
      setExecuting(null);
    }
  };

  const handleGenerateScenarios = async () => {
    if (!clientId) {
      setError("מזהה לקוח חסר");
      return;
    }

    setLoading(true);
    setError("");
    setSuccessMessage("");
    setResults(null);

    try {
      // קריאת נתוני תיק פנסיוני מ-localStorage
      const pensionDataStr = localStorage.getItem(`pensionData_${clientId}`);
      let pensionPortfolio = null;
      
      if (pensionDataStr) {
        try {
          pensionPortfolio = JSON.parse(pensionDataStr);
          console.log('📦 Loaded pension portfolio from localStorage:', pensionPortfolio.length, 'accounts');
        } catch (e) {
          console.warn('Failed to parse pension portfolio from localStorage:', e);
        }
      }

      const response = await fetch(
        `/api/v1/clients/${clientId}/retirement-scenarios`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            retirement_age: retirementAge,
            pension_portfolio: pensionPortfolio,
          }),
        }
      );

      if (!response.ok) {
        let errorMessage = `שגיאה: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          // אם לא ניתן לפרסר JSON, השתמש בהודעה הכללית
          const textError = await response.text();
          errorMessage = textError || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setResults(data);
    } catch (err: any) {
      console.error("Scenarios generation error:", err);
      setError(err.message || "שגיאה לא צפויה");
    } finally {
      setLoading(false);
    }
  };

  const renderScenarioCard = (scenario: ScenarioResult, rank: number) => {
    const getBestBadge = () => {
      if (!results) return null;

      const scenarios = [
        results.scenarios.scenario_1_max_pension,
        results.scenarios.scenario_2_max_capital,
        results.scenarios.scenario_3_max_npv,
      ];

      const maxNPV = Math.max(...scenarios.map((s) => s.estimated_npv));
      if (scenario.estimated_npv === maxNPV) {
        return (
          <div
            style={{
              position: "absolute",
              top: "10px",
              right: "10px",
              backgroundColor: "#28a745",
              color: "white",
              padding: "4px 12px",
              borderRadius: "12px",
              fontSize: "12px",
              fontWeight: "bold",
            }}
          >
            ⭐ מומלץ
          </div>
        );
      }
      return null;
    };

    return (
      <div
        key={rank}
        style={{
          position: "relative",
          border: "2px solid #dee2e6",
          borderRadius: "8px",
          padding: "20px",
          backgroundColor: "#f8f9fa",
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
        }}
      >
        {getBestBadge()}
        <h3 style={{ marginTop: 0, color: "#0066cc", fontSize: "18px" }}>
          {scenario.scenario_name}
        </h3>

        <div style={{ marginTop: "15px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "10px",
              marginBottom: "15px",
            }}
          >
            <div>
              <div style={{ fontSize: "12px", color: "#6c757d" }}>
                קצבה חודשית
              </div>
              <div style={{ fontSize: "18px", fontWeight: "bold" }}>
                {formatCurrency(scenario.total_pension_monthly)}
              </div>
            </div>

            <div>
              <div style={{ fontSize: "12px", color: "#6c757d" }}>סך הון</div>
              <div style={{ fontSize: "18px", fontWeight: "bold" }}>
                {formatCurrency(scenario.total_capital)}
              </div>
            </div>

            <div>
              <div style={{ fontSize: "12px", color: "#6c757d" }}>
                הכנסה נוספת חודשית
              </div>
              <div style={{ fontSize: "18px", fontWeight: "bold" }}>
                {formatCurrency(scenario.total_additional_income_monthly)}
              </div>
            </div>

            <div>
              <div style={{ fontSize: "12px", color: "#6c757d" }}>
                NPV משוער
              </div>
              <div
                style={{
                  fontSize: "18px",
                  fontWeight: "bold",
                  color: "#28a745",
                }}
              >
                {formatCurrency(scenario.estimated_npv)}
              </div>
            </div>
          </div>

          <div
            style={{
              borderTop: "1px solid #dee2e6",
              paddingTop: "10px",
              fontSize: "12px",
              color: "#6c757d",
            }}
          >
            <div>קצבאות: {scenario.pension_funds_count}</div>
            <div>נכסי הון: {scenario.capital_assets_count}</div>
            <div>מקורות הכנסה נוספים: {scenario.additional_incomes_count}</div>
          </div>

          {/* Execution Plan */}
          {scenario.execution_plan && scenario.execution_plan.length > 0 && (
            <details style={{ marginTop: "15px", fontSize: "13px" }}>
              <summary style={{ cursor: "pointer", fontWeight: "bold", color: "#0066cc" }}>
                📋 מפרט ביצוע ({scenario.execution_plan.length} פעולות)
              </summary>
              <div style={{ marginTop: "10px", backgroundColor: "#f1f3f5", padding: "10px", borderRadius: "4px" }}>
                {scenario.execution_plan.map((action, idx) => (
                  <div key={idx} style={{ marginBottom: "8px", borderBottom: "1px solid #dee2e6", paddingBottom: "8px" }}>
                    <div style={{ fontWeight: "bold" }}>{idx + 1}. {action.details}</div>
                    {action.from && <div style={{ fontSize: "12px", color: "#6c757d" }}>מקור: {action.from}</div>}
                    {action.to && <div style={{ fontSize: "12px", color: "#6c757d" }}>יעד: {action.to}</div>}
                    {action.amount > 0 && <div style={{ fontSize: "12px", color: "#6c757d" }}>סכום: {formatCurrency(action.amount)}</div>}
                  </div>
                ))}
              </div>
            </details>
          )}

          {/* Execute Button */}
          {(scenario as any).scenario_id && (
            <button
              onClick={() => handleExecuteScenario((scenario as any).scenario_id, scenario.scenario_name)}
              disabled={executing !== null}
              style={{
                marginTop: "15px",
                width: "100%",
                backgroundColor: executing === (scenario as any).scenario_id ? "#6c757d" : "#28a745",
                color: "white",
                border: "none",
                padding: "12px",
                borderRadius: "4px",
                fontSize: "14px",
                fontWeight: "bold",
                cursor: executing !== null ? "not-allowed" : "pointer",
              }}
            >
              {executing === (scenario as any).scenario_id ? "⏳ מבצע תרחיש..." : "⚡ בצע תרחיש זה"}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
      <div style={{ marginBottom: "20px" }}>
        <Link
          to={`/clients/${clientId}`}
          style={{
            color: "#0066cc",
            textDecoration: "none",
            fontSize: "14px",
          }}
        >
          ← חזרה לפרטי לקוח
        </Link>
      </div>

      <h1 style={{ marginBottom: "10px" }}>תרחישי פרישה אוטומטיים</h1>
      <p style={{ color: "#6c757d", marginBottom: "30px" }}>
        הזן גיל פרישה ובחן 3 תרחישים אוטומטיים: מקסימום קצבה, מקסימום הון, ומקסימום
        NPV
      </p>

      {/* Input Section */}
      <div
        style={{
          backgroundColor: "white",
          border: "1px solid #dee2e6",
          borderRadius: "8px",
          padding: "20px",
          marginBottom: "30px",
        }}
      >
        <div style={{ marginBottom: "20px" }}>
          <label
            style={{
              display: "block",
              marginBottom: "8px",
              fontWeight: "bold",
              fontSize: "14px",
            }}
          >
            גיל פרישה
          </label>
          <input
            type="number"
            min="50"
            max="80"
            value={retirementAge}
            onChange={(e) => setRetirementAge(Number(e.target.value))}
            disabled={loading}
            style={{
              width: "200px",
              padding: "8px 12px",
              border: "1px solid #ced4da",
              borderRadius: "4px",
              fontSize: "14px",
            }}
          />
          <span style={{ marginRight: "10px", color: "#6c757d", fontSize: "12px" }}>
            (בין 50 ל-80)
          </span>
        </div>

        <button
          onClick={handleGenerateScenarios}
          disabled={loading}
          style={{
            backgroundColor: loading ? "#6c757d" : "#0066cc",
            color: "white",
            border: "none",
            padding: "12px 24px",
            borderRadius: "4px",
            fontSize: "16px",
            fontWeight: "bold",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "🔄 מחשב תרחישים..." : "🎯 חשב תרחישי פרישה"}
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div
          style={{
            backgroundColor: "#f8d7da",
            color: "#721c24",
            border: "1px solid #f5c6cb",
            borderRadius: "4px",
            padding: "12px",
            marginBottom: "20px",
          }}
        >
          ❌ {error}
        </div>
      )}

      {/* Success Message */}
      {successMessage && (
        <div
          style={{
            backgroundColor: "#d4edda",
            color: "#155724",
            border: "1px solid #c3e6cb",
            borderRadius: "4px",
            padding: "12px",
            marginBottom: "20px",
          }}
        >
          {successMessage}
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div>
          <h2 style={{ marginBottom: "20px" }}>
            תוצאות לגיל פרישה {results.retirement_age}
          </h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(350px, 1fr))",
              gap: "20px",
              marginBottom: "30px",
            }}
          >
            {renderScenarioCard(results.scenarios.scenario_1_max_pension, 1)}
            {renderScenarioCard(results.scenarios.scenario_2_max_capital, 2)}
            {renderScenarioCard(results.scenarios.scenario_3_max_npv, 3)}
          </div>

          {/* Summary Table */}
          <div
            style={{
              backgroundColor: "white",
              border: "1px solid #dee2e6",
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <h3 style={{ marginTop: 0 }}>טבלת השוואה</h3>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ backgroundColor: "#f8f9fa" }}>
                  <th style={{ padding: "10px", textAlign: "right", border: "1px solid #dee2e6" }}>
                    תרחיש
                  </th>
                  <th style={{ padding: "10px", textAlign: "right", border: "1px solid #dee2e6" }}>
                    קצבה חודשית
                  </th>
                  <th style={{ padding: "10px", textAlign: "right", border: "1px solid #dee2e6" }}>
                    סך הון
                  </th>
                  <th style={{ padding: "10px", textAlign: "right", border: "1px solid #dee2e6" }}>
                    NPV משוער
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {results.scenarios.scenario_1_max_pension.scenario_name}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {formatCurrency(
                      results.scenarios.scenario_1_max_pension.total_pension_monthly
                    )}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {formatCurrency(
                      results.scenarios.scenario_1_max_pension.total_capital
                    )}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6", fontWeight: "bold" }}>
                    {formatCurrency(
                      results.scenarios.scenario_1_max_pension.estimated_npv
                    )}
                  </td>
                </tr>
                <tr>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {results.scenarios.scenario_2_max_capital.scenario_name}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {formatCurrency(
                      results.scenarios.scenario_2_max_capital.total_pension_monthly
                    )}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {formatCurrency(
                      results.scenarios.scenario_2_max_capital.total_capital
                    )}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6", fontWeight: "bold" }}>
                    {formatCurrency(
                      results.scenarios.scenario_2_max_capital.estimated_npv
                    )}
                  </td>
                </tr>
                <tr>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {results.scenarios.scenario_3_max_npv.scenario_name}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {formatCurrency(
                      results.scenarios.scenario_3_max_npv.total_pension_monthly
                    )}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6" }}>
                    {formatCurrency(results.scenarios.scenario_3_max_npv.total_capital)}
                  </td>
                  <td style={{ padding: "10px", border: "1px solid #dee2e6", fontWeight: "bold" }}>
                    {formatCurrency(results.scenarios.scenario_3_max_npv.estimated_npv)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            style={{
              marginTop: "20px",
              padding: "15px",
              backgroundColor: "#e7f3ff",
              border: "1px solid #b3d9ff",
              borderRadius: "4px",
              fontSize: "14px",
            }}
          >
            <strong>💡 הערה:</strong> NPV (Net Present Value) הוא ערך נוכחי נקי המשקלל
            את כל תזרימי המזומנים העתידיים. התרחיש עם ה-NPV הגבוה ביותר הוא התרחיש
            המומלץ מבחינה כלכלית.
          </div>
        </div>
      )}
    </div>
  );
}
