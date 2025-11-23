import React, { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { API_BASE, apiFetch, handleApiError } from "../lib/api";
import { formatCurrency } from "../lib/validation";
import RetirementScenarioCharts from "../components/retirement/RetirementScenarioCharts";
import {
  saveSeveranceDistribution,
  setTerminationConfirmed,
  isTerminationConfirmed,
  restoreSeveranceToPension,
  clearTerminationState,
} from "./SimpleCurrentEmployer/utils/storageHelpers";
import { loadPensionFunds, deleteCommutation, deletePensionFund, updatePensionFund } from "./PensionFunds/api";
import { restorePensionFromCommutation, recalculateClientPensionStartDate } from "./PensionFunds/handlers";
import { CapitalAsset } from "../types/capitalAsset";

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

// מנקה את כל טורי היתרות בתיק הפנסיוני ב-localStorage לאחר ביצוע תרחיש בפועל,
// כך שניתן לראות שהיתרות הומרו, אך לשמור את החשבונות עצמם לתיעוד.
const clearPensionPortfolioBalancesAfterScenario = (
  clientId: string,
  options?: { includeCurrentEmployerTermination?: boolean }
) => {
  const storageKey = `pensionData_${clientId}`;
  const stored = localStorage.getItem(storageKey);

  if (!stored) {
    return;
  }

  try {
    const pensionData = JSON.parse(stored);

    const includeCurrentEmployerTermination =
      options?.includeCurrentEmployerTermination ?? false;

    const numericFields = [
      "יתרה",
      "פיצויים_מעסיק_נוכחי",
      "פיצויים_לאחר_התחשבנות",
      "פיצויים_שלא_עברו_התחשבנות",
      "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
      "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
      "תגמולי_עובד_עד_2000",
      "תגמולי_עובד_אחרי_2000",
      "תגמולי_עובד_אחרי_2008_לא_משלמת",
      "תגמולי_מעביד_עד_2000",
      "תגמולי_מעביד_אחרי_2000",
      "תגמולי_מעביד_אחרי_2008_לא_משלמת",
      "תגמולים",
    ];

    const summaryFields = [
      "סך_תגמולים",
      "סך_פיצויים",
      "סך_רכיבים",
      "פער_יתרה_מול_רכיבים",
    ];

    const updated = (Array.isArray(pensionData) ? pensionData : []).map((account: any) => {
      const updatedAccount = { ...account };

      numericFields.forEach((field) => {
        if (field === "פיצויים_מעסיק_נוכחי" && !includeCurrentEmployerTermination) {
          return;
        }
        if (field in updatedAccount) {
          updatedAccount[field] = 0;
        }
      });

      summaryFields.forEach((field) => {
        if (field in updatedAccount) {
          updatedAccount[field] = 0;
        }
      });

      // איפוס סימונים ידניים לאחר ביצוע בפועל
      updatedAccount.selected = false;
      updatedAccount.selected_amounts = {};

      return updatedAccount;
    });

    localStorage.setItem(storageKey, JSON.stringify(updated));
  } catch (e) {
    console.error("Failed to clear pension portfolio balances after scenario execution", e);
  }
};

export default function RetirementScenarios() {
  const { id: clientId } = useParams<{ id: string }>();
  const navigate = useNavigate();
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
        `${API_BASE}/clients/${clientId}/retirement-scenarios?retirement_age=${retirementAge}`
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

  const restoreSnapshotBeforeScenario = async (): Promise<boolean> => {
    if (!clientId) {
      setError("מזהה לקוח חסר");
      return false;
    }

    const storageKey = `snapshot_client_${clientId}`;
    const stored = localStorage.getItem(storageKey);

    if (!stored) {
      setError("לא נמצא מצב שמור (snapshot). אנא שמור מצב לפני ביצוע תרחיש.");
      return false;
    }

    let snapshotData: any;
    try {
      snapshotData = JSON.parse(stored);
    } catch (e) {
      console.error("Failed to parse snapshot from localStorage before scenario execution", e);
      setError("שגיאה בקריאת מצב שמור. אנא שמור מצב מחדש לפני ביצוע תרחיש.");
      return false;
    }

    try {
      const response = await fetch(`${API_BASE}/clients/${clientId}/snapshot/restore`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(snapshotData),
      });

      if (!response.ok) {
        let errorMessage = `שגיאה בשחזור מצב לפני ביצוע התרחיש: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          const textError = await response.text();
          errorMessage = textError || errorMessage;
        }
        setError(errorMessage);
        return false;
      }
      try {
        await response.json();
      } catch {
      }

      const pensionPortfolio = snapshotData.pension_portfolio;
      if (Array.isArray(pensionPortfolio)) {
        localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(pensionPortfolio));
      } else {
        localStorage.removeItem(`pensionData_${clientId}`);
      }

      if (snapshotData.converted_accounts) {
        localStorage.setItem(`convertedAccounts_${clientId}`, JSON.stringify(snapshotData.converted_accounts));
      } else {
        localStorage.removeItem(`convertedAccounts_${clientId}`);
      }

      return true;
    } catch (err: any) {
      console.error("Snapshot restore before scenario execution failed:", err);
      setError(err.message || "שגיאה בשחזור מצב לפני ביצוע התרחיש");
      return false;
    }
  };

  const resetStateWithoutSnapshot = async (): Promise<boolean> => {
    if (!clientId) {
      setError("מזהה לקוח חסר");
      return false;
    }

    try {
      if (isTerminationConfirmed(clientId)) {
        await apiFetch(`/clients/${clientId}/delete-termination`, {
          method: "DELETE",
        });

        restoreSeveranceToPension(clientId);
        clearTerminationState(clientId);
      }

      const { funds, commutations } = await loadPensionFunds(clientId);

      for (const commutation of commutations) {
        if (!commutation.id) {
          continue;
        }

        const relatedFund = funds.find((f) => f.id === commutation.pension_fund_id);

        if (!relatedFund) {
          await restorePensionFromCommutation(clientId, commutation);
          await deleteCommutation(clientId, commutation.id);
          continue;
        }

        const currentBalance = relatedFund.balance || 0;
        const commutationAmount = commutation.exempt_amount || 0;
        const newBalance = currentBalance + commutationAmount;
        const annuityFactor = relatedFund.annuity_factor || 200;
        const newMonthlyAmount = Math.round(newBalance / annuityFactor);

        await updatePensionFund(relatedFund.id!, {
          fund_name: relatedFund.fund_name,
          fund_type: relatedFund.fund_type,
          input_mode: relatedFund.input_mode,
          balance: newBalance,
          pension_amount: newMonthlyAmount,
          annuity_factor: annuityFactor,
          pension_start_date: relatedFund.pension_start_date,
          indexation_method: relatedFund.indexation_method || "none",
        });

        await deleteCommutation(clientId, commutation.id);
      }

      const { funds: fundsAfterCommutations } = await loadPensionFunds(clientId);

      for (const fund of fundsAfterCommutations) {
        if (!fund.id) {
          continue;
        }

        const deleteResponse = await deletePensionFund(clientId, fund.id);
        const restoration = deleteResponse?.restoration;

        if (restoration && restoration.reason === "pension_portfolio") {
          const accountNumber = restoration.account_number;
          const balanceToRestore = restoration.balance_to_restore;
          const storageKey = `pensionData_${clientId}`;
          const storedData = localStorage.getItem(storageKey);

          if (storedData) {
            try {
              const pensionData = JSON.parse(storedData);
              const accountIndex = pensionData.findIndex((acc: any) => acc.מספר_חשבון === accountNumber);

              if (accountIndex !== -1) {
                const account = pensionData[accountIndex];

                if (restoration.specific_amounts && Object.keys(restoration.specific_amounts).length > 0) {
                  Object.entries(restoration.specific_amounts).forEach(([field, amount]: [string, any]) => {
                    if (Object.prototype.hasOwnProperty.call(account, field)) {
                      account[field] = (parseFloat(account[field]) || 0) + parseFloat(amount);
                    }
                  });
                } else {
                  account.תגמולים = (parseFloat(account.תגמולים) || 0) + balanceToRestore;
                }

                const restoreAmount = Number(balanceToRestore) || 0;
                if (restoreAmount > 0) {
                  account.יתרה = (Number(account.יתרה) || 0) + restoreAmount;
                }

                localStorage.setItem(storageKey, JSON.stringify(pensionData));
                window.dispatchEvent(new Event("storage"));
              }
            } catch (e) {
              console.error("Error restoring balance to localStorage for pension fund:", e);
            }
          }
        }
      }

      try {
        await recalculateClientPensionStartDate(clientId);
      } catch (updateError) {
        console.error("Error updating client pension start date after reset:", updateError);
      }

      const assets = await apiFetch<CapitalAsset[]>(`/clients/${clientId}/capital-assets/`);

      for (const asset of assets) {
        if (!asset.id) {
          continue;
        }

        const deleteResponse = await apiFetch<any>(`/clients/${clientId}/capital-assets/${asset.id}`, {
          method: "DELETE",
        });

        const restoration = deleteResponse?.restoration;
        if (restoration && restoration.reason === "pension_portfolio") {
          const accountNumber = restoration.account_number;
          const balanceToRestore = restoration.balance_to_restore;
          const storageKey = `pensionData_${clientId}`;
          const storedData = localStorage.getItem(storageKey);

          if (storedData && asset) {
            try {
              const pensionData = JSON.parse(storedData);
              const accountIndex = pensionData.findIndex((acc: any) => acc.מספר_חשבון === accountNumber);

              if (accountIndex !== -1) {
                const account = pensionData[accountIndex];

                if (restoration.specific_amounts && Object.keys(restoration.specific_amounts).length > 0) {
                  Object.entries(restoration.specific_amounts).forEach(([field, amount]: [string, any]) => {
                    if (Object.prototype.hasOwnProperty.call(account, field)) {
                      account[field] = (parseFloat(account[field]) || 0) + parseFloat(amount);
                    }
                  });
                } else {
                  account.תגמולים = (parseFloat(account.תגמולים) || 0) + balanceToRestore;
                }

                const restoreAmount = Number(balanceToRestore) || 0;
                if (restoreAmount > 0) {
                  account.יתרה = (Number(account.יתרה) || 0) + restoreAmount;
                }

                localStorage.setItem(storageKey, JSON.stringify(pensionData));
                window.dispatchEvent(new Event("storage"));
              }
            } catch (e) {
              console.error("Error restoring balance to localStorage from capital asset:", e);
            }
          }
        }
      }

      return true;
    } catch (err: any) {
      console.error("State reset before scenarios failed:", err);
      setError(err.message || "שגיאה באיפוס המצב לפני חישוב תרחישים");
      return false;
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
      // לפני ביצוע התרחיש בפועל, לבצע שחזור מצב מלא בדיוק כמו כפתור "שחזר מצב"
      const restored = await restoreSnapshotBeforeScenario();
      if (!restored) {
        setExecuting(null);
        return;
      }

      // שמירת התפלגות הפיצויים מתיק פנסיוני לפני ביצוע תרחיש בפועל,
      // כדי לאפשר החזרת היתרות במקרה של מחיקת העזיבה (delete-termination).
      saveSeveranceDistribution(clientId);

      const response = await fetch(
        `${API_BASE}/clients/${clientId}/retirement-scenarios/${scenarioId}/execute`,
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

      const includeTermination = !!data.include_current_employer_termination;

      // איפוס כל טורי היתרות בתיק הפנסיוני עבור הלקוח לאחר ביצוע התרחיש בפועל,
      // כדי להראות שהיתרות הומרו במערכת ולא ניתנות להמרה פעם נוספת מהטבלה.
      clearPensionPortfolioBalancesAfterScenario(clientId, {
        includeCurrentEmployerTermination: includeTermination,
      });

      // סימון העזיבה כמאושרת גם ב-localStorage, כדי שמסך המעסיק
      // יוכל לאפשר מחיקה והחזרת היתרות (restoreSeveranceToPension).
      if (includeTermination) {
        setTerminationConfirmed(clientId, true);
      }

      // ניווט חזרה למסך פרטי הלקוח במקום רענון מלא של הדף
      navigate(`/clients/${clientId}`);
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

    try {
      setError("");
      setSuccessMessage("");
      setResults(null);

      // אם קיים snapshot שמור, נבצע שחזור אוטומטי לפני חישוב התרחישים
      const snapshotKey = `snapshot_client_${clientId}`;
      const storedSnapshot = localStorage.getItem(snapshotKey);
      if (storedSnapshot) {
        const restored = await restoreSnapshotBeforeScenario();
        if (!restored) {
          return;
        }
      } else {
        const resetOk = await resetStateWithoutSnapshot();
        if (!resetOk) {
          return;
        }
      }

      setLoading(true);

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

      if (Array.isArray(pensionPortfolio)) {
        const unresolvedSeveranceTotal = pensionPortfolio.reduce((sum: number, account: any) => {
          return sum + (Number(account["פיצויים_שלא_עברו_התחשבנות"]) || 0);
        }, 0);

        const rightsSequenceTotal = pensionPortfolio.reduce((sum: number, account: any) => {
          return sum + (Number(account["פיצויים_ממעסיקים_קודמים_רצף_זכויות"]) || 0);
        }, 0);

        if (unresolvedSeveranceTotal > 0 || rightsSequenceTotal > 0) {
          setError(
            "לא ניתן להמשיך בתרחישי פרישה כל עוד קיימות יתרות בעמודות 'פיצויים שלא עברו התחשבנות' או 'רצף פיצויים מעסיקים קודמים (זכויות)' בתיק הפנסיוני. נא לבצע התחשבנות ולרוקן עמודות אלו לפני חישוב התרחישים."
          );
          setLoading(false);
          return;
        }
      }

      // שאלת המשתמש האם לכלול בתרחישים סיום עבודה מהמעסיק הנוכחי
      let includeCurrentEmployerTermination = false;
      try {
        const includeTerminationAnswer = window.confirm(
          "האם לכלול בתרחישי הפרישה סיום עבודה מהמעסיק הנוכחי?\n\nלחיצה על 'אישור' תחשב תרחישים כולל מימוש פיצויים דרך מסך מעסיק נוכחי.\nלחיצה על 'ביטול' תחשב תרחישים מבלי לבצע כעת סיום עבודה בפועל."
        );

        if (includeTerminationAnswer) {
          includeCurrentEmployerTermination = true;

          // ולידציה בסיסית: קיום מעסיק נוכחי במערכת
          try {
            await apiFetch(`/clients/${clientId}/current-employer`, {
              method: "GET",
            });
          } catch (error: any) {
            console.error("Current employer validation failed before scenarios:", error);
            setError(handleApiError(error));
            setLoading(false);
            return;
          }
        }
      } catch (promptError) {
        console.error("Error during termination inclusion prompt:", promptError);
      }

      // במידה ולא בוצע סיום עבודה (includeCurrentEmployerTermination=false), נשלח לשרת עותק של התיק
      // שבו עמודת 'פיצויים_מעסיק_נוכחי' מאופסת, מבלי לשנות את ה-localStorage בפועל.
      let requestPensionPortfolio = pensionPortfolio;
      if (!includeCurrentEmployerTermination && Array.isArray(pensionPortfolio)) {
        requestPensionPortfolio = pensionPortfolio.map((account: any) => ({
          ...account,
          ["פיצויים_מעסיק_נוכחי"]: 0,
        }));
      }

      const response = await fetch(
        `${API_BASE}/clients/${clientId}/retirement-scenarios`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            retirement_age: retirementAge,
            pension_portfolio: requestPensionPortfolio,
            include_current_employer_termination: includeCurrentEmployerTermination,
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
                </tr>
              </tbody>
            </table>
          </div>

          <RetirementScenarioCharts
            scenarios={results.scenarios}
            formatCurrency={formatCurrency}
          />
        </div>
      )}
    </div>
  );
}
