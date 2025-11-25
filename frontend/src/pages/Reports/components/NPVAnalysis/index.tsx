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
    <div className="reports-section reports-section--npv">
      <h3>ניתוח ערך נוכחי נקי (NPV)</h3>
      
      {/* NPV של תזרים */}
      <div className="reports-card reports-card--npv-flow">
        <h4>NPV תזרים (קצבאות והכנסות)</h4>
        <div className="reports-card-grid reports-card-grid--npv-main">
          <div>
            <strong>עם פטור:</strong>
            <div className="reports-card-value reports-card-value--positive">
              {formatCurrency(npvComparison.withExemption)}
            </div>
          </div>
          <div>
            <strong>ללא פטור:</strong>
            <div className="reports-card-value reports-card-value--negative">
              {formatCurrency(npvComparison.withoutExemption)}
            </div>
          </div>
          <div>
            <strong>חיסכון מקיבוע:</strong>
            <div className="reports-card-value reports-card-value--primary">
              {formatCurrency(npvComparison.savings)}
            </div>
          </div>
        </div>
      </div>

      {/* NPV של נכסי הון */}
      {totalCapitalValue > 0 && (
        <div className="reports-card reports-card--npv-capital">
          <h4>ערך נוכחי נכסי הון</h4>
          <div className="reports-card-grid reports-card-grid--npv-capital">
            <div>
              <strong>סך נכסי הון:</strong>
              <div className="reports-card-value reports-card-value--positive">
                {formatCurrency(totalCapitalValue)}
              </div>
              <div className="reports-card-note">
                נכסים אלו לא מופיעים בתזרים החודשי
              </div>
            </div>
            <div>
              <strong>סה"כ ערך כולל (תזרים + נכסים):</strong>
              <div className="reports-card-value reports-card-value--primary">
                {formatCurrency(npvComparison.withExemption + totalCapitalValue)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
