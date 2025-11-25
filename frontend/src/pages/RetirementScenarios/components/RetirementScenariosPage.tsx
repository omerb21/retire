import React from "react";
import { Link, useParams } from "react-router-dom";
import { formatCurrency } from "../../../lib/validation";
import { useRetirementScenarios } from "../hooks/useRetirementScenarios";
import { ScenarioCard } from "./ScenarioCard";
import { ScenariosSummaryTable } from "./ScenariosSummaryTable";
import "../../RetirementScenarios.css";

const RetirementScenarioCharts = React.lazy(
  () => import("../../../components/retirement/RetirementScenarioCharts")
);

const RetirementScenariosPage: React.FC = () => {
  const { id: clientId } = useParams<{ id: string }>();

  const {
    retirementAge,
    setRetirementAge,
    loading,
    executing,
    error,
    results,
    successMessage,
    handleGenerateScenarios,
    handleExecuteScenario,
  } = useRetirementScenarios(clientId);

  return (
    <div className="retirement-scenarios-container">
      <div className="retirement-scenarios-back-row">
        <Link
          to={`/clients/${clientId}`}
          className="retirement-scenarios-back-link"
        >
          ← חזרה לפרטי לקוח
        </Link>
      </div>

      <h1 className="retirement-scenarios-title">תרחישי פרישה אוטומטיים</h1>
      <p className="retirement-scenarios-subtitle">
        הזן גיל פרישה ובחן 3 תרחישים אוטומטיים: מקסימום קצבה, מקסימום הון, ומקסימום
        NPV
      </p>

      <div className="retirement-scenarios-input-card">
        <div className="retirement-scenarios-input-row">
          <label className="retirement-scenarios-label">גיל פרישה</label>
          <input
            type="number"
            min="50"
            max="80"
            value={retirementAge}
            onChange={(e) => setRetirementAge(Number(e.target.value))}
            disabled={loading}
            className="retirement-scenarios-age-input"
          />
          <span className="retirement-scenarios-age-hint">(בין 50 ל-80)</span>
        </div>

        <button
          onClick={handleGenerateScenarios}
          disabled={loading}
          className="retirement-scenarios-primary-button"
        >
          {loading ? "🔄 מחשב תרחישים..." : "🎯 חשב תרחישי פרישה"}
        </button>
      </div>

      {error && (
        <div className="retirement-scenarios-error">❌ {error}</div>
      )}

      {successMessage && (
        <div className="retirement-scenarios-success">{successMessage}</div>
      )}

      {results && (
        <div>
          <h2 className="retirement-scenarios-results-title">
            תוצאות לגיל פרישה {results.retirement_age}
          </h2>

          <div className="retirement-scenarios-cards-grid">
            <ScenarioCard
              scenario={results.scenarios.scenario_1_max_pension}
              rank={1}
              executingId={executing}
              formatCurrencyFn={formatCurrency}
              onExecute={handleExecuteScenario}
            />
            <ScenarioCard
              scenario={results.scenarios.scenario_2_max_capital}
              rank={2}
              executingId={executing}
              formatCurrencyFn={formatCurrency}
              onExecute={handleExecuteScenario}
            />
            <ScenarioCard
              scenario={results.scenarios.scenario_3_max_npv}
              rank={3}
              executingId={executing}
              formatCurrencyFn={formatCurrency}
              onExecute={handleExecuteScenario}
            />
          </div>

          <ScenariosSummaryTable
            scenarios={results.scenarios}
            formatCurrencyFn={formatCurrency}
          />

          <RetirementScenarioCharts
            scenarios={results.scenarios}
            formatCurrency={formatCurrency}
          />
        </div>
      )}
    </div>
  );
};

export default RetirementScenariosPage;
