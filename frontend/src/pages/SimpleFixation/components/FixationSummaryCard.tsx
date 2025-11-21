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
    <div
      style={{
        marginBottom: '30px',
        padding: '20px',
        border: '1px solid #007bff',
        borderRadius: '4px',
        backgroundColor: '#f8f9ff'
      }}
    >
      <div style={{ marginBottom: '20px' }}>
        <h3>סיכום קיבוע זכויות</h3>
        {clientData && (
          <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
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

      <div
        style={{
          marginBottom: '20px',
          padding: '15px',
          backgroundColor: '#fff3cd',
          borderRadius: '4px',
          border: '1px solid #ffc107'
        }}
      >
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

        <label
          style={{
            display: 'block',
            marginBottom: '8px',
            fontWeight: 'bold',
            color: '#856404'
          }}
        >
          מענק עתידי משוריין (נומינלי):
        </label>
        <input
          type="number"
          value={futureGrantReserved || ''}
          onChange={(e) => setFutureGrantReserved(parseFloat(e.target.value) || 0)}
          placeholder="הזן סכום מענק עתידי"
          style={{
            width: '100%',
            padding: '10px',
            fontSize: '16px',
            border: '2px solid #ffc107',
            borderRadius: '4px',
            backgroundColor: 'white',
            fontFamily: 'monospace'
          }}
        />
        <div
          style={{
            marginTop: '8px',
            fontSize: '13px',
            color: '#856404',
            fontStyle: 'italic'
          }}
        >
          הערך יוכפל ב-1.35 ויופחת מיתרת ההון הפטורה
        </div>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            backgroundColor: 'white',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}
        >
          <thead>
            <tr style={{ backgroundColor: '#343a40', color: 'white' }}>
              <th
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'right',
                  fontWeight: 'bold'
                }}
              >
                תיאור
              </th>
              <th
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontWeight: 'bold'
                }}
              >
                סכום (₪)
              </th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ backgroundColor: '#d1ecf1' }}>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 'bold'
                }}
              >
                יתרת הון פטורה לשנת הזכאות
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontWeight: 'bold',
                  fontFamily: 'monospace'
                }}
              >
                {formatMoney(summary.exempt_amount)}
              </td>
            </tr>
            <tr>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500
                }}
              >
                סך נומינאלי של מענקי הפרישה
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace'
                }}
              >
                {formatMoney(summary.total_grants)}
              </td>
            </tr>
            <tr>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500
                }}
              >
                סך המענקים הרלוונטים לאחר הוצמדה
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace'
                }}
              >
                {formatMoney(summary.total_indexed)}
              </td>
            </tr>
            <tr>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500
                }}
              >
                סך הכל פגיעה בפטור בגין מענקים פטורים
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace'
                }}
              >
                {formatMoney(summary.used_exemption)}
              </td>
            </tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500,
                  color: '#6c757d'
                }}
              >
                מענק עתידי משוריין (נומינלי)
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace',
                  color: '#6c757d'
                }}
              >
                {formatMoney(summary.future_grant_reserved)}
              </td>
            </tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500,
                  color: '#6c757d'
                }}
              >
                השפעת מענק עתידי (×1.35)
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace',
                  color: '#6c757d'
                }}
              >
                {formatMoney(summary.future_grant_impact)}
              </td>
            </tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500,
                  color: '#6c757d'
                }}
              >
                סך היוונים
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace',
                  color: '#6c757d'
                }}
              >
                {formatMoney(summary.total_discounts)}
              </td>
            </tr>
            <tr>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500
                }}
              >
                יתרת הון פטורה לאחר קיזוזים
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace',
                  color: '#28a745'
                }}
              >
                {formatMoney(summary.remaining_exemption)}
              </td>
            </tr>
            <tr style={{ backgroundColor: '#fff3cd' }}>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 500
                }}
              >
                תקרת קצבה מזכה
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace'
                }}
              >
                {formatMoney(summary.pension_ceiling)}
              </td>
            </tr>
            <tr style={{ backgroundColor: '#d4edda' }}>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  fontWeight: 'bold'
                }}
              >
                קצבה פטורה מחושבת
              </td>
              <td
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  textAlign: 'left',
                  fontFamily: 'monospace',
                  fontWeight: 'bold'
                }}
              >
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
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '20px',
            marginBottom: '20px',
            padding: '15px',
            backgroundColor: '#f8f9fa',
            borderRadius: '4px'
          }}
        >
          <div>
            <div style={{ marginBottom: '8px', fontSize: '14px' }}>
              <strong>שנת זכאות:</strong> {fixationData.eligibility_year}
            </div>
            <div style={{ marginBottom: '8px', fontSize: '14px' }}>
              <strong>תאריך זכאות:</strong>{' '}
              {formatDateToDDMMYYYY(fixationData.eligibility_date)}
            </div>
          </div>

          <div>
            <div style={{ marginBottom: '8px', fontSize: '14px' }}>
              <strong>גיל פרישה:</strong> {retirementAge}
            </div>
            <div style={{ marginBottom: '8px', fontSize: '14px' }}>
              <strong>תאריך חישוב:</strong> {'9.10.2025'}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'center', marginTop: '20px', gap: '12px' }}>
        <button
          onClick={onCalculateFixation}
          disabled={loading}
          style={{
            backgroundColor: loading ? '#6c757d' : '#28a745',
            color: 'white',
            border: 'none',
            padding: '12px 40px',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '16px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => {
            if (!loading) e.currentTarget.style.transform = 'translateY(-2px)';
          }}
          onMouseOut={(e) => {
            if (!loading) e.currentTarget.style.transform = 'translateY(0)';
          }}
        >
          {loading ? 'שומר...' : '💾 שמור קיבוע זכויות'}
        </button>
        <button
          onClick={onDeleteFixation}
          disabled={loading}
          style={{
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            padding: '12px 24px',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '16px'
          }}
        >
          🗑 מחק קיבוע זכויות שמור
        </button>
      </div>
    </div>
  );
};
