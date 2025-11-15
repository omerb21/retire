import React from 'react';
import { formatDateToDDMMYY } from '../../../../utils/dateUtils';
import { formatCurrency } from '../../../../lib/validation';

interface IncomeDetailsProps {
  pensionFunds: any[];
  additionalIncomes: any[];
  capitalAssets: any[];
}

export const IncomeDetails: React.FC<IncomeDetailsProps> = ({
  pensionFunds,
  additionalIncomes,
  capitalAssets
}) => {
  return (
    <div style={{ marginBottom: '30px' }}>
      <h3>פירוט מקורות הכנסה</h3>
      
      {/* קצבאות */}
      {pensionFunds.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4>קצבאות ({pensionFunds.length})</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>שם הקרן</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>מקדם קצבה</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>קצבה חודשית</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תאריך התחלה</th>
              </tr>
            </thead>
            <tbody>
              {pensionFunds.map((fund, index) => (
                <tr key={index}>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>{fund.fund_name}</td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {fund.annuity_factor || fund.pension_coefficient || fund.coefficient || '-'}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {formatCurrency(parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0)}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {fund.pension_start_date ? formatDateToDDMMYY(fund.pension_start_date) : fund.start_date ? formatDateToDDMMYY(fund.start_date) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* הכנסות נוספות */}
      {additionalIncomes.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4>הכנסות נוספות ({additionalIncomes.length})</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תיאור</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>סכום חודשי</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תאריך התחלה</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תאריך סיום</th>
              </tr>
            </thead>
            <tbody>
              {additionalIncomes.map((income, index) => (
                <tr key={index}>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>{income.description}</td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {formatCurrency((() => {
                      const amount = parseFloat(income.amount) || 0;
                      if (income.frequency === 'monthly') return amount;
                      if (income.frequency === 'quarterly') return amount / 3;
                      if (income.frequency === 'annually') return amount / 12;
                      return amount;
                    })())}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {income.start_date ? formatDateToDDMMYY(income.start_date) : '-'}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {income.end_date ? formatDateToDDMMYY(income.end_date) : 'ללא הגבלה'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* נכסי הון */}
      {capitalAssets.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4>נכסי הון ({capitalAssets.length})</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תיאור</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>ערך נוכחי</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תשלום חד פעמי</th>
                <th style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'right' }}>תאריך תשלום</th>
              </tr>
            </thead>
            <tbody>
              {capitalAssets.map((asset, index) => (
                <tr key={index}>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {asset.asset_name || asset.description}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {formatCurrency(parseFloat(asset.current_value) || 0)}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {formatCurrency(parseFloat(asset.monthly_income) || 0)}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                    {asset.start_date ? formatDateToDDMMYY(asset.start_date) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
