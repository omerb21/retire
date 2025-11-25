import React from "react";
import { ScenariosResponse } from "../types";

interface ScenariosSummaryTableProps {
  scenarios: ScenariosResponse["scenarios"];
  formatCurrencyFn: (value: number) => string;
}

export const ScenariosSummaryTable: React.FC<ScenariosSummaryTableProps> = ({
  scenarios,
  formatCurrencyFn,
}) => {
  const s1 = scenarios.scenario_1_max_pension;
  const s2 = scenarios.scenario_2_max_capital;
  const s3 = scenarios.scenario_3_max_npv;

  return (
    <div className="retirement-scenarios-summary-card">
      <h3 className="retirement-scenarios-summary-title">טבלת השוואה</h3>
      <table className="retirement-scenarios-summary-table">
        <thead>
          <tr className="retirement-scenarios-summary-header-row">
            <th className="retirement-scenarios-summary-header-cell">תרחיש</th>
            <th className="retirement-scenarios-summary-header-cell">
              קצבה חודשית
            </th>
            <th className="retirement-scenarios-summary-header-cell">סך הון</th>
            <th className="retirement-scenarios-summary-header-cell">
              NPV משוער (לפני מס)
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="retirement-scenarios-summary-cell">
              {s1.scenario_name}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s1.total_pension_monthly)}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s1.total_capital)}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s1.estimated_npv)}
            </td>
          </tr>
          <tr>
            <td className="retirement-scenarios-summary-cell">
              {s2.scenario_name}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s2.total_pension_monthly)}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s2.total_capital)}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s2.estimated_npv)}
            </td>
          </tr>
          <tr>
            <td className="retirement-scenarios-summary-cell">
              {s3.scenario_name}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s3.total_pension_monthly)}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s3.total_capital)}
            </td>
            <td className="retirement-scenarios-summary-cell">
              {formatCurrencyFn(s3.estimated_npv)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};
