import React from 'react';
import { YearlyProjection } from '../../../../components/reports/types/reportTypes';
import { formatCurrency } from '../../../../lib/validation';

interface YearlyBreakdownProps {
  yearlyProjection: YearlyProjection[];
  pensionFunds: any[];
  additionalIncomes: any[];
  capitalAssets: any[];
}

export const YearlyBreakdown: React.FC<YearlyBreakdownProps> = ({
  yearlyProjection,
  pensionFunds,
  additionalIncomes,
  capitalAssets
}) => {
  if (yearlyProjection.length === 0) return null;

  return (
    <>
      {/* טבלת תזרים שנתי - סיכום */}
      <div className="reports-section">
        <h3>תחזית תזרים שנתי - סיכום</h3>
        <div className="reports-table-wrapper">
          <table className="reports-table reports-table--summary">
            <thead>
              <tr className="reports-table-header-row reports-table-header-row--summary">
                <th className="reports-table-header-cell">שנה</th>
                <th className="reports-table-header-cell">גיל</th>
                <th className="reports-table-header-cell">הכנסה חודשית</th>
                <th className="reports-table-header-cell">מס חודשי</th>
                <th className="reports-table-header-cell">נטו חודשי</th>
              </tr>
            </thead>
            <tbody>
              {yearlyProjection.map((proj, index) => (
                <tr
                  key={index}
                  className={index % 2 === 0 ? 'reports-table-row reports-table-row--alt' : 'reports-table-row'}
                >
                  <td className="reports-table-cell reports-table-cell--center">{proj.year}</td>
                  <td className="reports-table-cell reports-table-cell--center">{proj.clientAge}</td>
                  <td className="reports-table-cell reports-table-cell--left">
                    {formatCurrency(proj.totalMonthlyIncome)}
                  </td>
                  <td className="reports-table-cell reports-table-cell--left">
                    {formatCurrency(proj.totalMonthlyTax)}
                  </td>
                  <td className="reports-table-cell reports-table-cell--left">
                    {formatCurrency(proj.netMonthlyIncome)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* טבלת תזרים מפורט - טור לכל מקור הכנסה */}
      <div className="reports-section">
        <h3>תחזית תזרים מפורט - פירוט לפי מקור</h3>
        <div className="reports-table-wrapper">
          <table className="reports-table reports-table--detailed">
            <thead>
              <tr className="reports-table-header-row reports-table-header-row--detailed">
                <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--sticky-year">שנה</th>
                <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--sticky-age">גיל</th>
                {pensionFunds.map((fund, idx) => (
                  <React.Fragment key={`pension-${idx}`}>
                    <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--pension-title">
                      {fund.fund_name}
                    </th>
                    <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--pension-tax">
                      מס
                    </th>
                  </React.Fragment>
                ))}
                {additionalIncomes.map((income, idx) => (
                  <React.Fragment key={`income-${idx}`}>
                    <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--income-title">
                      {income.description}
                    </th>
                    <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--income-tax">
                      מס
                    </th>
                  </React.Fragment>
                ))}
                {capitalAssets.filter(asset => parseFloat(asset.monthly_income) > 0).map((asset, idx) => (
                  <React.Fragment key={`asset-${idx}`}>
                    <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--asset-title">
                      {asset.asset_name || asset.description}
                    </th>
                    <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--asset-tax">
                      מס
                    </th>
                  </React.Fragment>
                ))}
                <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--total-income">סה"כ הכנסה</th>
                <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--total-tax">מס</th>
                <th className="reports-table-header-cell reports-table-header-cell--small reports-table-header-cell--total-net">נטו</th>
              </tr>
            </thead>
            <tbody>
              {yearlyProjection.map((proj, yearIndex) => (
                <tr
                  key={yearIndex}
                  className={yearIndex % 2 === 0 ? 'reports-table-row reports-table-row--alt' : 'reports-table-row'}
                >
                  <td className="reports-table-cell reports-table-cell--small reports-table-cell--center reports-table-cell--bold reports-table-cell--sticky-year">
                    {proj.year}
                  </td>
                  <td className="reports-table-cell reports-table-cell--small reports-table-cell--center reports-table-cell--sticky-age">
                    {proj.clientAge}
                  </td>
                  {proj.incomeBreakdown.slice(0, pensionFunds.length).map((amount, idx) => (
                    <React.Fragment key={`pension-${idx}`}>
                      <td className="reports-table-cell reports-table-cell--small reports-table-cell--left">
                        {amount > 0 ? formatCurrency(amount) : '-'}
                      </td>
                      <td className="reports-table-cell reports-table-cell--small reports-table-cell--left reports-table-cell--tax">
                        {proj.taxBreakdown && proj.taxBreakdown[idx] > 0 ? formatCurrency(proj.taxBreakdown[idx]) : '-'}
                      </td>
                    </React.Fragment>
                  ))}
                  {proj.incomeBreakdown.slice(pensionFunds.length, pensionFunds.length + additionalIncomes.length).map((amount, idx) => (
                    <React.Fragment key={`income-${idx}`}>
                      <td className="reports-table-cell reports-table-cell--small reports-table-cell--left">
                        {amount > 0 ? formatCurrency(amount) : '-'}
                      </td>
                      <td className="reports-table-cell reports-table-cell--small reports-table-cell--left reports-table-cell--tax">
                        {proj.taxBreakdown && proj.taxBreakdown[pensionFunds.length + idx] > 0 ? formatCurrency(proj.taxBreakdown[pensionFunds.length + idx]) : '-'}
                      </td>
                    </React.Fragment>
                  ))}
                  {proj.incomeBreakdown.slice(pensionFunds.length + additionalIncomes.length).map((amount, idx) => (
                    <React.Fragment key={`asset-${idx}`}>
                      <td className="reports-table-cell reports-table-cell--small reports-table-cell--left">
                        {amount > 0 ? formatCurrency(amount) : '-'}
                      </td>
                      <td className="reports-table-cell reports-table-cell--small reports-table-cell--left reports-table-cell--tax">
                        {proj.taxBreakdown && proj.taxBreakdown[pensionFunds.length + additionalIncomes.length + idx] > 0 ? formatCurrency(proj.taxBreakdown[pensionFunds.length + additionalIncomes.length + idx]) : '-'}
                      </td>
                    </React.Fragment>
                  ))}
                  <td className="reports-table-cell reports-table-cell--small reports-table-cell--left reports-table-cell--bold">
                    {formatCurrency(proj.totalMonthlyIncome)}
                  </td>
                  <td className="reports-table-cell reports-table-cell--small reports-table-cell--left reports-table-cell--tax">
                    {formatCurrency(proj.totalMonthlyTax)}
                  </td>
                  <td className="reports-table-cell reports-table-cell--small reports-table-cell--left reports-table-cell--bold reports-table-cell--net">
                    {formatCurrency(proj.netMonthlyIncome)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="reports-color-legend">
          <strong>הסבר צבעים:</strong> 
          <span className="reports-color-legend-item">🔵 קצבאות</span>
          <span className="reports-color-legend-item">🟢 הכנסות נוספות</span>
          <span className="reports-color-legend-item">🟡 נכסי הון</span>
        </div>
      </div>
    </>
  );
}
;
