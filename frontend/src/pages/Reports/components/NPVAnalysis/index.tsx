import React from 'react';
import { formatCurrency } from '../../../../lib/validation';

interface NPVComparison {
  withExemption: number;
  withoutExemption: number;
  savings: number;
}
interface NPVBreakdown {
  recurringNpv: number;
  projectedOneTimeNpv: number;
  reconciliationNpv: number;
  futureCapitalNpv: number;
  oneTimeNpv: number;
  remainingCapitalValue: number;
  cashflowNpv: number;
  totalEconomicValue: number;
  warnings: string[];
}
interface NPVAnalysisProps {
  npvComparison: NPVComparison | null;
  npvBreakdown: NPVBreakdown | null;
}

export const NPVAnalysis: React.FC<NPVAnalysisProps> = ({ npvComparison, npvBreakdown }) => {
  if (!npvComparison) return null;
  return (
    <div className="reports-section reports-section--npv">
      <h3>ניתוח ערך נוכחי (NPV)</h3>
      <div className="reports-card reports-card--npv-flow">
        <h4>NPV התזרים הכולל לפי החישוב הקיים</h4>
        <div className="reports-card-grid reports-card-grid--npv-main">
          <div><strong>עם פטור:</strong><div className="reports-card-value reports-card-value--positive">{formatCurrency(npvComparison.withExemption)}</div></div>
          <div><strong>ללא פטור:</strong><div className="reports-card-value reports-card-value--negative">{formatCurrency(npvComparison.withoutExemption)}</div></div>
          <div><strong>חיסכון מקיבוע:</strong><div className="reports-card-value reports-card-value--primary">{formatCurrency(npvComparison.savings)}</div></div>
        </div>
      </div>
      {npvBreakdown && (
        <div className="reports-card reports-card--npv-capital">
          <h4>פירוט הערך לפי סוג התקבול</h4>
          <div className="reports-card-grid reports-card-grid--npv-capital">
            <div><strong>NPV הכנסות חוזרות:</strong><div className="reports-card-value">{formatCurrency(npvBreakdown.recurringNpv)}</div></div>
            <div><strong>NPV תקבולים חד-פעמיים שנכללו בתזרים:</strong><div className="reports-card-value">{formatCurrency(npvBreakdown.projectedOneTimeNpv)}</div></div>
            {Math.abs(npvBreakdown.reconciliationNpv) > 0.01 && (
              <div><strong>הפרש התאמה בין פירוט המקורות לנטו הכולל (דורש בדיקה):</strong><div className="reports-card-value">{formatCurrency(npvBreakdown.reconciliationNpv)}</div></div>
            )}
            <div><strong>PV תקבולים הוניים עתידיים מחוץ לתזרים (לפני מס שלא חושב):</strong><div className="reports-card-value">{formatCurrency(npvBreakdown.futureCapitalNpv)}</div></div>
            <div><strong>יתרות נכסים שאינן בתזרים (ערך רשום, לא מהוון):</strong><div className="reports-card-value">{formatCurrency(npvBreakdown.remainingCapitalValue)}</div></div>
            <div><strong>שווי משולב (בסיסי מס ושווי כמפורט):</strong><div className="reports-card-value reports-card-value--primary">{formatCurrency(npvBreakdown.totalEconomicValue)}</div></div>
          </div>
          <div className="reports-card-note">הסיווגים והפטורים הם לפי נתוני התרחיש ואינם מהווים אישור פקיד שומה. השווי המשולב אינו כולו נטו ממס.</div>
          {npvBreakdown.warnings.length > 0 && (
            <div className="reports-card-note" role="alert">
              {npvBreakdown.warnings.map((warning, i) => <div key={i}>{warning}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
