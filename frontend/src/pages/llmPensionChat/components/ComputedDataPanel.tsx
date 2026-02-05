import React from "react";

import { ComputedDataPayload, ComputedPensionData, MonthlyPensionComputedData } from "../types";

type Props = {
  computedData: ComputedDataPayload;
};

export default function ComputedDataPanel({ computedData }: Props) {
  const isMonthlyPension = (data: any): data is MonthlyPensionComputedData => {
    return !!(data && typeof data === "object" && data.monthly_pension && data.today);
  };

  const isTargetPension = (data: any): data is ComputedPensionData => {
    return !!(data && typeof data === "object" && Array.isArray(data.sources));
  };

  if (!computedData) {
    return null;
  }

  if (isMonthlyPension(computedData)) {
    const mp = computedData.monthly_pension;
    const current = mp.current;
    const future = mp.future;

    const rows = [
      ...(current.items || []).map((it) => ({ ...it, _bucket: "current" as const })),
      ...(future.items || []).map((it) => ({ ...it, _bucket: "future" as const })),
    ];

    return (
      <div className="llm-computed-data-panel" dir="rtl">
        <div className="llm-computed-data-header">
          <h3>📊 קצבה חודשית מהמערכת</h3>
          <span className="llm-computed-data-badge">Client {computedData.client_id}</span>
        </div>

        <div className="llm-computed-data-summary">
          <div className="llm-computed-data-stat">
            <span className="stat-label">קצבאות נוכחיות:</span>
            <span className="stat-value">
              {current.count.toLocaleString()} (סה"כ {current.sum.toLocaleString()} ₪)
            </span>
          </div>
          <div className="llm-computed-data-stat">
            <span className="stat-label">חייב:</span>
            <span className="stat-value">{current.taxable.sum.toLocaleString()} ₪</span>
          </div>
          <div className="llm-computed-data-stat">
            <span className="stat-label">פטור:</span>
            <span className="stat-value">{current.exempt.sum.toLocaleString()} ₪</span>
          </div>
          <div className="llm-computed-data-stat">
            <span className="stat-label">קצבאות עתידיות:</span>
            <span className="stat-value">
              {future.count.toLocaleString()} (סה"כ {future.sum.toLocaleString()} ₪)
            </span>
          </div>
        </div>

        <table className="llm-computed-data-table">
          <thead>
            <tr>
              <th>Bucket</th>
              <th>ID</th>
              <th>תאריך התחלה</th>
              <th>סכום (₪)</th>
              <th>מיסוי</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.id}-${idx}`}>
                <td>{row._bucket === "current" ? "נוכחית" : "עתידית"}</td>
                <td>{row.id}</td>
                <td>{row.start_date || "-"}</td>
                <td>{Number(row.amount || 0).toLocaleString()}</td>
                <td>
                  {String(row.tax_treatment || "") === "exempt"
                    ? "פטור"
                    : String(row.tax_treatment || "") === "taxable"
                      ? "חייב"
                      : String(row.tax_treatment || "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="llm-computed-data-note">💡 הנתונים למעלה מחושבים ישירות מהמערכת ולא מומצאים על ידי ה-AI</div>
      </div>
    );
  }

  if (!isTargetPension(computedData) || !computedData.sources || computedData.sources.length === 0) {
    return null;
  }

  return (
    <div className="llm-computed-data-panel" dir="rtl">
      <div className="llm-computed-data-header">
        <h3>📊 נתונים מחושבים מהמערכת (לא מה-AI)</h3>
        <span className="llm-computed-data-badge">
          {computedData.target_achieved ? "✅ יעד הושג" : "⚠️ יעד לא הושג"}
        </span>
      </div>

      <div className="llm-computed-data-summary">
        <div className="llm-computed-data-stat">
          <span className="stat-label">🎯 יעד קצבה:</span>
          <span className="stat-value">
            {computedData.target_monthly_pension.toLocaleString()} ₪/חודש
          </span>
        </div>
        <div className="llm-computed-data-stat">
          <span className="stat-label">קצבה מצטברת:</span>
          <span
            className="stat-value"
            style={{ color: computedData.target_achieved ? "#16a34a" : "#dc2626" }}
          >
            {computedData.accumulated_pension.toLocaleString()} ₪/חודש
          </span>
        </div>
        {!computedData.target_achieved && (
          <div className="llm-computed-data-stat">
            <span className="stat-label">פער מהיעד:</span>
            <span className="stat-value" style={{ color: "#dc2626" }}>
              {(computedData.target_monthly_pension - computedData.accumulated_pension).toLocaleString()} ₪
            </span>
          </div>
        )}
        <div className="llm-computed-data-stat">
          <span className="stat-label">הון נותר:</span>
          <span className="stat-value">{computedData.remaining_capital.toLocaleString()} ₪</span>
        </div>
        <div className="llm-computed-data-stat">
          <span className="stat-label">גיל פרישה:</span>
          <span className="stat-value">{computedData.retirement_age}</span>
        </div>
      </div>

      <table className="llm-computed-data-table">
        <thead>
          <tr>
            <th>מוצר</th>
            <th>סוג</th>
            <th>יתרה (₪)</th>
            <th>קצבה חודשית (₪)</th>
            <th>מקדם</th>
            <th>מיסוי</th>
          </tr>
        </thead>
        <tbody>
          {computedData.sources.map((source, idx) => (
            <tr
              key={idx}
              className={source.source_type === "pension" ? "pension-row" : "capital-row"}
            >
              <td>{source.source_name}</td>
              <td>{source.source_type === "pension" ? "קצבה" : "הון"}</td>
              <td>{source.balance.toLocaleString()}</td>
              <td className={source.monthly_pension > 0 ? "highlight-pension" : ""}>
                {source.monthly_pension > 0 ? source.monthly_pension.toLocaleString() : "-"}
              </td>
              <td>{source.annuity_factor > 0 ? source.annuity_factor.toFixed(1) : "-"}</td>
              <td>
                {source.tax_treatment === "exempt"
                  ? "פטור"
                  : source.tax_treatment === "taxable"
                    ? "חייב"
                    : source.tax_treatment}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="llm-computed-data-note">
        💡 הנתונים למעלה מחושבים ישירות מהמערכת ולא מומצאים על ידי ה-AI
      </div>
    </div>
  );
}
