import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE, apiFetch, handleApiError } from "../../../lib/api";
import { ScenariosResponse } from "../types";
import { clearPensionPortfolioBalancesAfterScenario } from "../services/pensionPortfolioStorage";
import { loadPensionDataFromStorage } from "../../PensionPortfolio/services/pensionPortfolioStorageService";
import {
  restoreSnapshotBeforeScenario,
  resetStateWithoutSnapshot,
} from "../services/snapshotService";
import {
  saveSeveranceDistribution,
  setTerminationConfirmed,
  getEmployerCompletionPreference,
} from "../../SimpleCurrentEmployer/utils/storageHelpers";
import { loadSnapshotRawFromStorage } from "../../../services/snapshotStorageService";

export function useRetirementScenarios(clientId: string | undefined) {
  const navigate = useNavigate();

  const [retirementAge, setRetirementAge] = useState<number>(67);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<number | null>(null);
  const [error, setError] = useState<string>("");
  const [results, setResults] = useState<ScenariosResponse | null>(null);
  const [successMessage, setSuccessMessage] = useState<string>("");

  const loadSavedScenarios = async () => {
    if (!clientId) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE}/clients/${clientId}/retirement-scenarios?retirement_age=${retirementAge}`
      );

      if (response.ok) {
        const data = await response.json();
        if (data.scenarios) {
          console.log("📥 Loaded saved scenarios:", data);
          setResults(data);
        }
      }
    } catch (err) {
      console.warn("No saved scenarios found or error loading:", err);
    }
  };

  useEffect(() => {
    if (clientId) {
      void loadSavedScenarios();
    }
  }, [clientId]);

  const handleExecuteScenario = async (
    scenarioId: number,
    scenarioName: string
  ) => {
    if (!clientId) {
      setError("מזהה לקוח חסר");
      return;
    }

    const confirmed = window.confirm(
      `האם אתה בטוח שברצונך לבצע את התרחיש "${scenarioName}"?\n\nפעולה זו תשנה את המצב בפועל במערכת!`
    );
    if (!confirmed) {
      return;
    }

    setExecuting(scenarioId);
    setError("");
    setSuccessMessage("");

    try {
      const restored = await restoreSnapshotBeforeScenario(clientId, setError);
      if (!restored) {
        setExecuting(null);
        return;
      }

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
          errorMessage = (errorData as any).detail || errorMessage;
        } catch {
          const textError = await response.text();
          errorMessage = textError || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setSuccessMessage(`✅ ${data.message || "התרחיש בוצע בהצלחה!"}`);

      const includeTermination = !!data.include_current_employer_termination;

      clearPensionPortfolioBalancesAfterScenario(clientId, {
        includeCurrentEmployerTermination: includeTermination,
      });

      if (includeTermination) {
        setTerminationConfirmed(clientId, true);
      }

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

      const storedSnapshot = loadSnapshotRawFromStorage(clientId);
      if (storedSnapshot) {
        const restored = await restoreSnapshotBeforeScenario(clientId, setError);
        if (!restored) {
          return;
        }
      } else {
        const resetOk = await resetStateWithoutSnapshot(clientId, setError);
        if (!resetOk) {
          return;
        }
      }

      setLoading(true);
      const pensionPortfolio = loadPensionDataFromStorage(clientId);

      if (Array.isArray(pensionPortfolio)) {
        console.log(
          "📦 Loaded pension portfolio from storage:",
          pensionPortfolio.length,
          "accounts"
        );
        const unresolvedSeveranceTotal = pensionPortfolio.reduce(
          (sum: number, account: any) => {
            return sum + (Number(account["פיצויים_שלא_עברו_התחשבנות"]) || 0);
          },
          0
        );

        const rightsSequenceTotal = pensionPortfolio.reduce(
          (sum: number, account: any) => {
            return sum + (Number(account["פיצויים_ממעסיקים_קודמים_רצף_זכויות"]) || 0);
          },
          0
        );

        if (unresolvedSeveranceTotal > 0 || rightsSequenceTotal > 0) {
          setError(
            "לא ניתן להמשיך בתרחישי פרישה כל עוד קיימות יתרות בעמודות 'פיצויים שלא עברו התחשבנות' או 'רצף פיצויים מעסיקים קודמים (זכויות)' בתיק הפנסיוני. נא לבצע התחשבנות ולרוקן עמודות אלו לפני חישוב התרחישים."
          );
          setLoading(false);
          return;
        }
      }

      // קביעת הכללת עזיבת המעסיק הנוכחי לפי העדפה שנקבעה במסך המעסיק
      let includeCurrentEmployerTermination = false;
      try {
        includeCurrentEmployerTermination = getEmployerCompletionPreference(clientId);

        if (includeCurrentEmployerTermination) {
          try {
            await apiFetch(`/clients/${clientId}/current-employer`, {
              method: "GET",
            });
          } catch (error: any) {
            console.error(
              "Current employer validation failed before scenarios:",
              error
            );
            setError(handleApiError(error));
            setLoading(false);
            return;
          }
        }
      } catch (prefError) {
        console.error("Error loading employer completion preference:", prefError);
      }

      let requestPensionPortfolio = pensionPortfolio;
      if (!includeCurrentEmployerTermination && Array.isArray(pensionPortfolio)) {
        requestPensionPortfolio = pensionPortfolio.map((account: any) => ({
          ...account,
          ["פיצויים_מעסיק_נוכחי"]: 0,
        }));
      }

      const response = await fetch(`${API_BASE}/clients/${clientId}/retirement-scenarios`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          retirement_age: retirementAge,
          pension_portfolio: requestPensionPortfolio,
          include_current_employer_termination: includeCurrentEmployerTermination,
        }),
      });

      if (!response.ok) {
        let errorMessage = `שגיאה: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = (errorData as any).detail || errorMessage;
        } catch {
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

  return {
    retirementAge,
    setRetirementAge,
    loading,
    executing,
    error,
    results,
    successMessage,
    handleGenerateScenarios,
    handleExecuteScenario,
  };
}
