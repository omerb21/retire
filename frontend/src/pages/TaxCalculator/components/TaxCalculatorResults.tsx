import React from 'react';
import { formatCurrency } from '../../../lib/validation';
import { TaxCalculationResult } from '../hooks/useTaxCalculator';

interface TaxCalculatorResultsProps {
  result: TaxCalculationResult | null;
}

export const TaxCalculatorResults: React.FC<TaxCalculatorResultsProps> = ({
  result,
}) => {
  if (!result) {
    return null;
  }

  return (
    <>
      <h2>תוצאות חישוב המס</h2>

      <div className="tax-calculator-summary-card">
        <h3>סיכום כללי</h3>
        <div>
          <strong>סך הכנסה:</strong> {formatCurrency(result.total_income)}
        </div>
        <div>
          <strong>הכנסה חייבת:</strong> {formatCurrency(result.taxable_income)}
        </div>
        <div>
          <strong>הכנסה פטורה:</strong> {formatCurrency(result.exempt_income)}
        </div>
        <div className="tax-calculator-text-negative">
          <strong>מס נטו לתשלום:</strong> {formatCurrency(result.net_tax)}
        </div>
        <div className="tax-calculator-text-positive">
          <strong>הכנסה נטו:</strong> {formatCurrency(result.net_income)}
        </div>
        <div>
          <strong>שיעור מס אפקטיבי:</strong>{' '}
          {result.effective_tax_rate.toFixed(2)}%
        </div>
      </div>

      <div className="tax-calculator-detail-card">
        <h3>פירוט מסים</h3>
        <div>
          <strong>מס הכנסה:</strong> {formatCurrency(result.income_tax)}
        </div>
        <div>
          <strong>ביטוח לאומי:</strong> {formatCurrency(result.national_insurance)}
        </div>
        <div>
          <strong>מס בריאות:</strong> {formatCurrency(result.health_tax)}
        </div>
        <div>
          <strong>סך מסים:</strong> {formatCurrency(result.total_tax)}
        </div>
        <div className="tax-calculator-text-positive">
          <strong>זיכויים:</strong> {formatCurrency(result.tax_credits_amount)}
        </div>
      </div>

      {result.applied_credits.length > 0 && (
        <div className="tax-calculator-credits-card">
          <h3>נקודות זיכוי</h3>
          {result.applied_credits.map((credit, index) => (
            <div key={index}>
              <strong>{credit.description}:</strong> {formatCurrency(credit.amount)}
            </div>
          ))}
        </div>
      )}

      {result.tax_breakdown.length > 0 && (
        <div className="tax-calculator-detail-card">
          <h3>מדרגות מס</h3>
          <table className="tax-calculator-tax-table">
            <thead>
              <tr className="tax-calculator-tax-table-header-row">
                <th className="tax-calculator-tax-header-cell">מדרגה</th>
                <th className="tax-calculator-tax-header-cell">שיעור</th>
                <th className="tax-calculator-tax-header-cell">סכום חייב</th>
                <th className="tax-calculator-tax-header-cell">מס</th>
              </tr>
            </thead>
            <tbody>
              {result.tax_breakdown.map((bracket, index) => (
                <tr key={index}>
                  <td className="tax-calculator-tax-cell">
                    {formatCurrency(bracket.bracket_min)} -{' '}
                    {bracket.bracket_max
                      ? formatCurrency(bracket.bracket_max)
                      : 'ומעלה'}
                  </td>
                  <td className="tax-calculator-tax-cell">
                    {(bracket.rate * 100).toFixed(1)}%
                  </td>
                  <td className="tax-calculator-tax-cell">
                    {formatCurrency(bracket.taxable_amount)}
                  </td>
                  <td className="tax-calculator-tax-cell">
                    {formatCurrency(bracket.tax_amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
};
