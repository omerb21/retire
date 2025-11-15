import React from 'react';
import { formatCurrency } from '../../../../lib/validation';

interface NPVComparison {
  withExemption: number;
  withoutExemption: number;
  savings: number;
}

interface NPVAnalysisProps {
  npvComparison: NPVComparison | null;
  totalCapitalValue: number;
}

export const NPVAnalysis: React.FC<NPVAnalysisProps> = ({ npvComparison, totalCapitalValue }) => {
  if (!npvComparison) return null;

  return (
    <div style={{ marginBottom: '30px' }}>
      <h3>ניתוח ערך נוכחי נקי (NPV)</h3>
      
      {/* NPV של תזרים */}
      <div style={{ 
        backgroundColor: '#e7f3ff', 
        padding: '20px', 
        borderRadius: '8px',
        marginBottom: '15px'
      }}>
        <h4>NPV תזרים (קצבאות והכנסות)</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
          <div>
            <strong>עם פטור:</strong>
            <div style={{ fontSize: '20px', color: '#28a745' }}>
              {formatCurrency(npvComparison.withExemption)}
            </div>
          </div>
          <div>
            <strong>ללא פטור:</strong>
            <div style={{ fontSize: '20px', color: '#dc3545' }}>
              {formatCurrency(npvComparison.withoutExemption)}
            </div>
          </div>
          <div>
            <strong>חיסכון מקיבוע:</strong>
            <div style={{ fontSize: '20px', color: '#007bff' }}>
              {formatCurrency(npvComparison.savings)}
            </div>
          </div>
        </div>
      </div>

      {/* NPV של נכסי הון */}
      {totalCapitalValue > 0 && (
        <div style={{ 
          backgroundColor: '#fff3cd', 
          padding: '20px', 
          borderRadius: '8px'
        }}>
          <h4>ערך נוכחי נכסי הון</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '20px' }}>
            <div>
              <strong>סך נכסי הון:</strong>
              <div style={{ fontSize: '20px', color: '#28a745' }}>
                {formatCurrency(totalCapitalValue)}
              </div>
              <div style={{ fontSize: '12px', color: '#6c757d', marginTop: '5px' }}>
                נכסים אלו לא מופיעים בתזרים החודשי
              </div>
            </div>
            <div>
              <strong>סה"כ ערך כולל (תזרים + נכסים):</strong>
              <div style={{ fontSize: '20px', color: '#007bff' }}>
                {formatCurrency(npvComparison.withExemption + totalCapitalValue)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
