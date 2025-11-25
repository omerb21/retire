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
    <div className="reports-section reports-section--income-details">
      <h3>פירוט מקורות הכנסה</h3>
      
      {/* קצבאות */}
      {pensionFunds.length > 0 && (
        <div className="reports-income-group">
          <h4>קצבאות ({pensionFunds.length})</h4>
          <table className="reports-table reports-table--income">
            <thead>
              <tr className="reports-table-header-row--income">
                <th className="reports-table-header-cell--income">שם הקרן</th>
                <th className="reports-table-header-cell--income">מקדם קצבה</th>
                <th className="reports-table-header-cell--income">קצבה חודשית</th>
                <th className="reports-table-header-cell--income">תאריך התחלה</th>
              </tr>
            </thead>
            <tbody>
              {pensionFunds.map((fund, index) => (
                <tr key={index}>
                  <td className="reports-table-cell--income">{fund.fund_name}</td>
                  <td className="reports-table-cell--income">
                    {fund.annuity_factor || fund.pension_coefficient || fund.coefficient || '-'}
                  </td>
                  <td className="reports-table-cell--income">
                    {formatCurrency(parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0)}
                  </td>
                  <td className="reports-table-cell--income">
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
        <div className="reports-income-group">
          <h4>הכנסות נוספות ({additionalIncomes.length})</h4>
          <table className="reports-table reports-table--income">
            <thead>
              <tr className="reports-table-header-row--income">
                <th className="reports-table-header-cell--income">תיאור</th>
                <th className="reports-table-header-cell--income">סכום חודשי</th>
                <th className="reports-table-header-cell--income">תאריך התחלה</th>
                <th className="reports-table-header-cell--income">תאריך סיום</th>
              </tr>
            </thead>
            <tbody>
              {additionalIncomes.map((income, index) => (
                <tr key={index}>
                  <td className="reports-table-cell--income">{income.description}</td>
                  <td className="reports-table-cell--income">
                    {formatCurrency((() => {
                      const amount = parseFloat(income.amount) || 0;
                      if (income.frequency === 'monthly') return amount;
                      if (income.frequency === 'quarterly') return amount / 3;
                      if (income.frequency === 'annually') return amount / 12;
                      return amount;
                    })())}
                  </td>
                  <td className="reports-table-cell--income">
                    {income.start_date ? formatDateToDDMMYY(income.start_date) : '-'}
                  </td>
                  <td className="reports-table-cell--income">
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
        <div className="reports-income-group">
          <h4>נכסי הון ({capitalAssets.length})</h4>
          <table className="reports-table reports-table--income">
            <thead>
              <tr className="reports-table-header-row--income">
                <th className="reports-table-header-cell--income">תיאור</th>
                <th className="reports-table-header-cell--income">ערך נוכחי</th>
                <th className="reports-table-header-cell--income">תשלום חד פעמי</th>
                <th className="reports-table-header-cell--income">תאריך תשלום</th>
              </tr>
            </thead>
            <tbody>
              {capitalAssets.map((asset, index) => (
                <tr key={index}>
                  <td className="reports-table-cell--income">
                    {asset.asset_name || asset.description}
                  </td>
                  <td className="reports-table-cell--income">
                    {formatCurrency(parseFloat(asset.current_value) || 0)}
                  </td>
                  <td className="reports-table-cell--income">
                    {formatCurrency(parseFloat(asset.monthly_income) || 0)}
                  </td>
                  <td className="reports-table-cell--income">
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
