import React from 'react';
import { formatDateToDDMMYYYY } from '../../../utils/dateUtils';
import {
  FixationData,
  GrantSummary,
  ExemptionSummary,
  Commutation
} from '../types';
import { calculatePensionSummary, formatMoney } from '../utils/fixationCalculations';

interface FixationSummaryCardProps {
  fixationData: FixationData;
  clientData: any;
  retirementAge: string;
  futureGrantReserved: number;
  setFutureGrantReserved: (value: number) => void;
  loading: boolean;
  grantsSummary: GrantSummary[];
  exemptionSummary: ExemptionSummary | null;
  commutations: Commutation[];
  continuesWorking: boolean;
  setContinuesWorking: (value: boolean) => void;
  workingEmployerName: string;
  setWorkingEmployerName: (value: string) => void;
  workingStartDate: string;
  setWorkingStartDate: (value: string) => void;
  workingEndDate: string;
  setWorkingEndDate: (value: string) => void;
  workingLastSalary: number;
  setWorkingLastSalary: (value: number) => void;
  onCalculateFixation: () => void;
  onDeleteFixation: () => void;
}

export const FixationSummaryCard: React.FC<FixationSummaryCardProps> = ({
  fixationData,
  clientData,
  retirementAge,
  futureGrantReserved,
  setFutureGrantReserved,
  loading,
  grantsSummary,
  exemptionSummary,
  commutations,
  continuesWorking,
  setContinuesWorking,
  workingEmployerName,
  setWorkingEmployerName,
  workingStartDate,
  setWorkingStartDate,
  workingEndDate,
  setWorkingEndDate,
  workingLastSalary,
  setWorkingLastSalary,
  onCalculateFixation,
  onDeleteFixation
}) => {
  const summary = calculatePensionSummary(
    grantsSummary,
    exemptionSummary,
    futureGrantReserved,
    commutations,
    fixationData
  );

  return (
    <div className="fixation-summary-card">
      <div className="fixation-summary-header">
        <h3>סיכום קיבוע זכויות</h3>
        {clientData && (
          <div className="fixation-summary-client-info">
            <strong>לקוח:</strong>{' '}
            {clientData.full_name || `${clientData.first_name} ${clientData.last_name}` || 'לא צוין'} |
            <strong> ת.ז:</strong> {clientData.id_number} |
            <strong> תאריך לידה:</strong>{' '}
            {clientData.birth_date
              ? formatDateToDDMMYYYY(clientData.birth_date)
              : 'לא צוין'}
          </div>
        )}
      </div>

      <div className="fixation-working-box">
        <div className="form-group">
          <label className="form-label">
            <input
              type="checkbox"
              checked={continuesWorking}
              onChange={(e) => setContinuesWorking(e.target.checked)}
            />{' '}
            האם ממשיך לעבוד
          </label>
        </div>

        {continuesWorking && (
          <div className="grid grid-cols-2 gap-2">
            <div className="form-group">
              <label className="form-label">שם מעסיק</label>
              <input
                type="text"
                className="form-input"
                value={workingEmployerName}
                onChange={(e) => setWorkingEmployerName(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">תאריך תחילת עבודה</label>
              <input
                type="text"
                className="form-input"
                placeholder="DD/MM/YYYY"
                value={workingStartDate}
                onChange={(e) => setWorkingStartDate(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">תאריך סיום עבודה</label>
              <input
                type="text"
                className="form-input"
                placeholder="DD/MM/YYYY"
                value={workingEndDate}
                onChange={(e) => setWorkingEndDate(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">משכורת אחרונה</label>
              <input
                type="number"
                className="form-input"
                value={workingLastSalary || ''}
                onChange={(e) =>
                  setWorkingLastSalary(e.target.value ? parseFloat(e.target.value) || 0 : 0)
                }
              />
            </div>
          </div>
        )}

        <label className="fixation-future-grant-label">
          מענק עתידי משוריין (נומינלי):
        </label>
        <input
          type="number"
          value={futureGrantReserved || ''}
          onChange={(e) => setFutureGrantReserved(parseFloat(e.target.value) || 0)}
          placeholder="הזן סכום מענק עתידי"
          className="fixation-future-grant-input"
        />
        <div className="fixation-future-grant-note">
          הערך יוכפל ב-1.35 ויופחת מיתרת ההון הפטורה
        </div>
      </div>

      <div>
        <table className="fixation-summary-table">
          <thead>
            <tr className="fixation-summary-table-header-row">
              <th className="fixation-summary-header-cell fixation-summary-header-cell--right">
                תיאור
              </th>
              <th className="fixation-summary-header-cell fixation-summary-header-cell--left">
                סכום (₪)
              </th>
            </tr>
          </thead>
          <tbody>
            <tr className="fixation-summary-row fixation-summary-row--blue">
              <td className="fixation-summary-cell fixation-summary-cell--label-strong">
                יתרת הון פטורה לשנת הזכאות
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value fixation-summary-cell--value-strong">
                {formatMoney(summary.exempt_amount)}
              </td>
            </tr>
            <tr className="fixation-summary-row">
              <td className="fixation-summary-cell fixation-summary-cell--label">
                סך נומינאלי של מענקי הפרישה
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value">
                {formatMoney(summary.total_grants)}
              </td>
            </tr>
            <tr className="fixation-summary-row">
              <td className="fixation-summary-cell fixation-summary-cell--label">
                סך המענקים הרלוונטים לאחר הוצמדה
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value">
                {formatMoney(summary.total_indexed)}
              </td>
            </tr>
            <tr className="fixation-summary-row">
              <td className="fixation-summary-cell fixation-summary-cell--label">
                סך הכל פגיעה בפטור בגין מענקים פטורים
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value">
                {formatMoney(summary.used_exemption)}
              </td>
            </tr>
            <tr className="fixation-summary-row fixation-summary-row--gray">
              <td className="fixation-summary-cell fixation-summary-cell--label fixation-summary-cell--muted">
                מענק עתידי משוריין (נומינלי)
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value fixation-summary-cell--muted">
                {formatMoney(summary.future_grant_reserved)}
              </td>
            </tr>
            <tr className="fixation-summary-row fixation-summary-row--gray">
              <td className="fixation-summary-cell fixation-summary-cell--label fixation-summary-cell--muted">
                השפעת מענק עתידי (×1.35)
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value fixation-summary-cell--muted">
                {formatMoney(summary.future_grant_impact)}
              </td>
            </tr>
            <tr className="fixation-summary-row fixation-summary-row--gray">
              <td className="fixation-summary-cell fixation-summary-cell--label fixation-summary-cell--muted">
                סך היוונים
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value fixation-summary-cell--muted">
                {formatMoney(summary.total_discounts)}
              </td>
            </tr>
            <tr className="fixation-summary-row">
              <td className="fixation-summary-cell fixation-summary-cell--label">
                יתרת הון פטורה לאחר קיזוזים
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value fixation-summary-cell--success">
                {formatMoney(summary.remaining_exemption)}
              </td>
            </tr>
            <tr className="fixation-summary-row fixation-summary-row--yellow">
              <td className="fixation-summary-cell fixation-summary-cell--label">
                תקרת קצבה מזכה
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value">
                {formatMoney(summary.pension_ceiling)}
              </td>
            </tr>
            <tr className="fixation-summary-row fixation-summary-row--green">
              <td className="fixation-summary-cell fixation-summary-cell--label-strong">
                קצבה פטורה מחושבת
              </td>
              <td className="fixation-summary-cell fixation-summary-cell--value fixation-summary-cell--value-strong">
                {formatMoney(summary.exempt_pension_calculated.base_amount)} ₪ ({
                  summary.exempt_pension_calculated.percentage.toFixed(1)
                }
                %)
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {exemptionSummary && (
        <div className="fixation-exemption-details">
          <div>
            <div className="fixation-exemption-details-row">
              <strong>שנת זכאות:</strong> {fixationData.eligibility_year}
            </div>
            <div className="fixation-exemption-details-row">
              <strong>תאריך זכאות:</strong>{' '}
              {formatDateToDDMMYYYY(fixationData.eligibility_date)}
            </div>
          </div>

          <div>
            <div className="fixation-exemption-details-row">
              <strong>גיל פרישה:</strong> {retirementAge}
            </div>
            <div className="fixation-exemption-details-row">
              <strong>תאריך חישוב:</strong> {'9.10.2025'}
            </div>
          </div>
        </div>
      )}

      <div className="fixation-summary-actions">
        <button
          onClick={onCalculateFixation}
          disabled={loading}
          className="fixation-button fixation-button--primary"
        >
          {loading ? 'שומר...' : '💾 שמור קיבוע זכויות'}
        </button>
        <button
          onClick={onDeleteFixation}
          disabled={loading}
          className="fixation-button fixation-button--danger"
        >
          🗑 מחק קיבוע זכויות שמור
        </button>
      </div>
    </div>
  );
};
