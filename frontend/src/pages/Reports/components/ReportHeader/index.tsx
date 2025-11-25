import React from 'react';
import { getPensionCeiling } from '../../../../components/reports/calculations/pensionCalculations';
import { formatCurrency } from '../../../../lib/validation';

interface Client {
  id: number;
  name?: string;
  first_name?: string;
  last_name?: string;
  id_number?: string;
  birth_year?: number;
  birth_date?: string;
  tax_credit_points?: number;
}

interface FixationData {
  fixation_year?: number;
  eligibility_year?: number;
  exemption_summary?: {
    eligibility_year?: number;
    exempt_capital_initial?: number;
    remaining_exempt_capital?: number;
    remaining_monthly_exemption?: number;
    exempt_pension_percentage?: number;
  };
}

interface ReportHeaderProps {
  client: Client | null;
  fixationData?: FixationData | null;
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({ client, fixationData }) => {
  if (!client) return null;

  const clientName = `${client.first_name || ''} ${client.last_name || ''}`.trim() || client.name || '-';
  const birthYear = client.birth_year || (client.birth_date ? new Date(client.birth_date).getFullYear() : '-');

  return (
    <>
      {/* פרטי לקוח */}
      <div className="report-header-client">
        <h3>פרטי לקוח</h3>
        <div className="report-header-grid">
          <div><strong>שם:</strong> {clientName}</div>
          <div><strong>תעודת זהות:</strong> {client.id_number || '-'}</div>
          <div><strong>שנת לידה:</strong> {birthYear}</div>
          <div><strong>נקודות זיכוי:</strong> {client.tax_credit_points || 0}</div>
        </div>
      </div>

      {/* פרטי קיבוע זכויות */}
      {fixationData && fixationData.exemption_summary && (
        <div className="report-header-fixation">
          <h3>פרטי קיבוע זכויות</h3>
          <div className="report-header-grid">
            <div>
              <strong>שנת קיבוע:</strong> {fixationData.fixation_year || fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || '-'}
            </div>
            <div>
              <strong>הון פטור ראשוני:</strong> {formatCurrency(fixationData.exemption_summary.exempt_capital_initial || 0)}
            </div>
            <div>
              <strong>הון פטור נותר:</strong> {formatCurrency(fixationData.exemption_summary.remaining_exempt_capital || 0)}
            </div>
            <div>
              <strong>קצבה פטורה מקיבוע ({fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || '-'}):</strong> {formatCurrency(fixationData.exemption_summary.remaining_monthly_exemption || ((fixationData.exemption_summary.remaining_exempt_capital || 0) / 180))}
            </div>
            <div>
              <strong>אחוז קצבה פטורה:</strong> {((fixationData.exemption_summary.exempt_pension_percentage || 0) * 100).toFixed(2)}%
            </div>
            <div>
              <strong>קצבה פטורה לשנת התזרים ({new Date().getFullYear()}):</strong> {formatCurrency((fixationData.exemption_summary.exempt_pension_percentage || 0) * getPensionCeiling(new Date().getFullYear()))}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
