import React, { useEffect, useState } from "react";
import { ScenarioResult } from "../types";

interface ScenarioCardProps {
  scenario: ScenarioResult;
  rank: number;
  executingId: number | null;
  previewScenarioId: number | null;
  formatCurrencyFn: (value: number) => string;
  onPreview: (scenarioId: number, scenarioName: string) => void;
  onApply: (scenarioId: number, scenarioName: string) => void;
}

export const ScenarioCard: React.FC<ScenarioCardProps> = ({
  scenario,
  rank,
  executingId,
  previewScenarioId,
  formatCurrencyFn,
  onPreview,
  onApply,
}) => {
  const scenarioId = scenario.scenario_id;
  const isExecuting = executingId !== null && executingId === scenarioId;
  const isPreviewVisible =
    typeof scenarioId === "number" && previewScenarioId !== null && previewScenarioId === scenarioId;

  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    if (isPreviewVisible) {
      setDetailsOpen(true);
    }
  }, [isPreviewVisible, scenario.execution_plan]);

  const actionCount = Array.isArray(scenario.execution_plan) ? scenario.execution_plan.length : 0;

  return (
    <div
      key={rank}
      className={`retirement-scenarios-card ${isPreviewVisible ? "retirement-scenarios-card--preview" : ""}`}
    >
      <h3 className="retirement-scenarios-card-title">
        {scenario.scenario_name}
      </h3>

      <div className="retirement-scenarios-card-body">
        <div className="retirement-scenarios-card-grid">
          <div>
            <div className="retirement-scenarios-card-label">קצבה חודשית</div>
            <div className="retirement-scenarios-card-value">
              {formatCurrencyFn(scenario.total_pension_monthly)}
            </div>
          </div>

          <div>
            <div className="retirement-scenarios-card-label">סך הון</div>
            <div className="retirement-scenarios-card-value">
              {formatCurrencyFn(scenario.total_capital)}
            </div>
          </div>

          <div>
            <div className="retirement-scenarios-card-label">הכנסה נוספת חודשית</div>
            <div className="retirement-scenarios-card-value">
              {formatCurrencyFn(scenario.total_additional_income_monthly)}
            </div>
          </div>

          <div>
            <div className="retirement-scenarios-card-label">
              NPV משוער (לפני מס)
            </div>
            <div className="retirement-scenarios-card-value">
              {formatCurrencyFn(scenario.estimated_npv)}
            </div>
          </div>
        </div>

        <div className="retirement-scenarios-card-footer">
          <div>קצבאות: {scenario.pension_funds_count}</div>
          <div>נכסי הון: {scenario.capital_assets_count}</div>
          <div>מקורות הכנסה נוספים: {scenario.additional_incomes_count}</div>
        </div>

        {isPreviewVisible && (
          <>
            <div className="retirement-scenarios-preview-badge">
              Preview נטען{actionCount > 0 ? ` • ${actionCount} פעולות` : ""}
            </div>

            <details
              className="retirement-scenarios-execution-details"
              open={detailsOpen}
              onToggle={(e) => setDetailsOpen((e.target as HTMLDetailsElement).open)}
            >
              <summary className="retirement-scenarios-execution-summary">
                📋 מפרט ביצוע{actionCount > 0 ? ` (${actionCount} פעולות)` : ""}
              </summary>

              <div className="retirement-scenarios-execution-list">
                {actionCount > 0 ? (
                  scenario.execution_plan!.map((action, idx) => (
                    <div
                      key={idx}
                      className="retirement-scenarios-execution-item"
                    >
                      <div className="retirement-scenarios-execution-item-title">
                        {idx + 1}. {action.details}
                      </div>
                      {action.from && (
                        <div className="retirement-scenarios-execution-item-meta">
                          מקור: {action.from}
                        </div>
                      )}
                      {action.to && (
                        <div className="retirement-scenarios-execution-item-meta">
                          יעד: {action.to}
                        </div>
                      )}
                      {action.amount > 0 && (
                        <div className="retirement-scenarios-execution-item-meta">
                          סכום: {formatCurrencyFn(action.amount)}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="retirement-scenarios-execution-empty">
                    אין פעולות להצגה ב-Preview של תרחיש זה.
                  </div>
                )}
              </div>
            </details>
          </>
        )}

        {typeof scenarioId === "number" && (
          <div className="retirement-scenarios-card-actions">
            <button
              onClick={() => onPreview(scenarioId, scenario.scenario_name)}
              disabled={executingId !== null}
              className={`retirement-scenarios-execute-button ${
                isExecuting
                  ? "retirement-scenarios-execute-button--executing"
                  : ""
              }`}
            >
              {isExecuting ? "⏳ מריץ Preview..." : "👁️ Preview"}
            </button>
            <button
              onClick={() => onApply(scenarioId, scenario.scenario_name)}
              disabled={executingId !== null}
              className="retirement-scenarios-apply-button"
            >
              החל (Apply)
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
