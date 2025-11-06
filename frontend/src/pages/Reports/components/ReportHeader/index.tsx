import React from 'react';
import { getPensionCeiling } from '../../../../components/reports/calculations/pensionCalculations';

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
      <div style={{ 
        backgroundColor: '#f8f9fa', 
        padding: '20px', 
        borderRadius: '8px',
        marginBottom: '20px'
      }}>
        <h3>פרטי לקוח</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px' }}>
          <div><strong>שם:</strong> {clientName}</div>
          <div><strong>תעודת זהות:</strong> {client.id_number || '-'}</div>
          <div><strong>שנת לידה:</strong> {birthYear}</div>
          <div><strong>נקודות זיכוי:</strong> {client.tax_credit_points || 0}</div>
        </div>
      </div>

      {/* פרטי קיבוע זכויות */}
      {fixationData && fixationData.exemption_summary && (
        <div style={{ 
          backgroundColor: '#fff3cd', 
          padding: '20px', 
          borderRadius: '8px',
          marginBottom: '20px',
          border: '2px solid #ffc107'
        }}>
          <h3>פרטי קיבוע זכויות</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px' }}>
            <div>
              <strong>שנת קיבוע:</strong> {fixationData.fixation_year || fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || '-'}
            </div>
            <div>
              <strong>הון פטור ראשוני:</strong> ₪{(fixationData.exemption_summary.exempt_capital_initial || 0).toLocaleString()}
            </div>
            <div>
              <strong>הון פטור נותר:</strong> ₪{(fixationData.exemption_summary.remaining_exempt_capital || 0).toLocaleString()}
            </div>
            <div>
              <strong>קצבה פטורה מקיבוע ({fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || '-'}):</strong> ₪{(fixationData.exemption_summary.remaining_monthly_exemption || ((fixationData.exemption_summary.remaining_exempt_capital || 0) / 180)).toLocaleString()}
            </div>
            <div>
              <strong>אחוז קצבה פטורה:</strong> {((fixationData.exemption_summary.exempt_pension_percentage || 0) * 100).toFixed(2)}%
            </div>
            <div>
              <strong>קצבה פטורה לשנת התזרים ({new Date().getFullYear()}):</strong> ₪{((fixationData.exemption_summary.exempt_pension_percentage || 0) * getPensionCeiling(new Date().getFullYear())).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
