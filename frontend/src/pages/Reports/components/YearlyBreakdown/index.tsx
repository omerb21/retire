import React from 'react';
import { YearlyProjection } from '../../../../components/reports/types/reportTypes';

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
      <div style={{ marginBottom: '30px' }}>
        <h3>תחזית תזרים שנתי - סיכום</h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ 
            width: '100%', 
            borderCollapse: 'collapse',
            backgroundColor: 'white',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}>
            <thead>
              <tr style={{ backgroundColor: '#007bff', color: 'white' }}>
                <th style={{ padding: '12px', border: '1px solid #dee2e6' }}>שנה</th>
                <th style={{ padding: '12px', border: '1px solid #dee2e6' }}>גיל</th>
                <th style={{ padding: '12px', border: '1px solid #dee2e6' }}>הכנסה חודשית</th>
                <th style={{ padding: '12px', border: '1px solid #dee2e6' }}>מס חודשי</th>
                <th style={{ padding: '12px', border: '1px solid #dee2e6' }}>נטו חודשי</th>
              </tr>
            </thead>
            <tbody>
              {yearlyProjection.map((proj, index) => (
                <tr key={index} style={{ backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'center' }}>{proj.year}</td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'center' }}>{proj.clientAge}</td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'left' }}>
                    ₪{proj.totalMonthlyIncome.toLocaleString()}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'left' }}>
                    ₪{proj.totalMonthlyTax.toLocaleString()}
                  </td>
                  <td style={{ padding: '10px', border: '1px solid #dee2e6', textAlign: 'left' }}>
                    ₪{proj.netMonthlyIncome.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* טבלת תזרים מפורט - טור לכל מקור הכנסה */}
      <div style={{ marginBottom: '30px' }}>
        <h3>תחזית תזרים מפורט - פירוט לפי מקור</h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ 
            width: '100%', 
            borderCollapse: 'collapse',
            backgroundColor: 'white',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            fontSize: '12px'
          }}>
            <thead>
              <tr style={{ backgroundColor: '#007bff', color: 'white' }}>
                <th style={{ padding: '8px', border: '1px solid #dee2e6', position: 'sticky', right: 0, backgroundColor: '#007bff' }}>שנה</th>
                <th style={{ padding: '8px', border: '1px solid #dee2e6', position: 'sticky', right: '60px', backgroundColor: '#007bff' }}>גיל</th>
                {pensionFunds.map((fund, idx) => (
                  <React.Fragment key={`pension-${idx}`}>
                    <th style={{ padding: '8px', border: '1px solid #dee2e6', minWidth: '100px', backgroundColor: '#007bff', color: 'white' }}>
                      {fund.fund_name}
                    </th>
                    <th style={{ padding: '8px', border: '1px solid #dee2e6', minWidth: '80px', backgroundColor: '#0056b3', color: 'white' }}>
                      מס
                    </th>
                  </React.Fragment>
                ))}
                {additionalIncomes.map((income, idx) => (
                  <React.Fragment key={`income-${idx}`}>
                    <th style={{ padding: '8px', border: '1px solid #dee2e6', minWidth: '100px', backgroundColor: '#28a745', color: 'white' }}>
                      {income.description}
                    </th>
                    <th style={{ padding: '8px', border: '1px solid #dee2e6', minWidth: '80px', backgroundColor: '#1e7e34', color: 'white' }}>
                      מס
                    </th>
                  </React.Fragment>
                ))}
                {capitalAssets.filter(asset => parseFloat(asset.monthly_income) > 0).map((asset, idx) => (
                  <React.Fragment key={`asset-${idx}`}>
                    <th style={{ padding: '8px', border: '1px solid #dee2e6', minWidth: '100px', backgroundColor: '#ffc107', color: 'black' }}>
                      {asset.asset_name || asset.description}
                    </th>
                    <th style={{ padding: '8px', border: '1px solid #dee2e6', minWidth: '80px', backgroundColor: '#e0a800', color: 'black' }}>
                      מס
                    </th>
                  </React.Fragment>
                ))}
                <th style={{ padding: '8px', border: '1px solid #dee2e6', backgroundColor: '#17a2b8', color: 'white' }}>סה"כ הכנסה</th>
                <th style={{ padding: '8px', border: '1px solid #dee2e6', backgroundColor: '#dc3545', color: 'white' }}>מס</th>
                <th style={{ padding: '8px', border: '1px solid #dee2e6', backgroundColor: '#28a745', color: 'white' }}>נטו</th>
              </tr>
            </thead>
            <tbody>
              {yearlyProjection.map((proj, yearIndex) => (
                <tr key={yearIndex} style={{ backgroundColor: yearIndex % 2 === 0 ? '#f8f9fa' : 'white' }}>
                  <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'center', fontWeight: 'bold', position: 'sticky', right: 0, backgroundColor: yearIndex % 2 === 0 ? '#f8f9fa' : 'white' }}>
                    {proj.year}
                  </td>
                  <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'center', position: 'sticky', right: '60px', backgroundColor: yearIndex % 2 === 0 ? '#f8f9fa' : 'white' }}>
                    {proj.clientAge}
                  </td>
                  {proj.incomeBreakdown.slice(0, pensionFunds.length).map((amount, idx) => (
                    <React.Fragment key={`pension-${idx}`}>
                      <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left' }}>
                        {amount > 0 ? `₪${amount.toLocaleString()}` : '-'}
                      </td>
                      <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left', color: '#dc3545' }}>
                        {proj.taxBreakdown && proj.taxBreakdown[idx] > 0 ? `₪${proj.taxBreakdown[idx].toLocaleString()}` : '-'}
                      </td>
                    </React.Fragment>
                  ))}
                  {proj.incomeBreakdown.slice(pensionFunds.length, pensionFunds.length + additionalIncomes.length).map((amount, idx) => (
                    <React.Fragment key={`income-${idx}`}>
                      <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left' }}>
                        {amount > 0 ? `₪${amount.toLocaleString()}` : '-'}
                      </td>
                      <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left', color: '#dc3545' }}>
                        {proj.taxBreakdown && proj.taxBreakdown[pensionFunds.length + idx] > 0 ? `₪${proj.taxBreakdown[pensionFunds.length + idx].toLocaleString()}` : '-'}
                      </td>
                    </React.Fragment>
                  ))}
                  {proj.incomeBreakdown.slice(pensionFunds.length + additionalIncomes.length).map((amount, idx) => (
                    <React.Fragment key={`asset-${idx}`}>
                      <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left' }}>
                        {amount > 0 ? `₪${amount.toLocaleString()}` : '-'}
                      </td>
                      <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left', color: '#dc3545' }}>
                        {proj.taxBreakdown && proj.taxBreakdown[pensionFunds.length + additionalIncomes.length + idx] > 0 ? `₪${proj.taxBreakdown[pensionFunds.length + additionalIncomes.length + idx].toLocaleString()}` : '-'}
                      </td>
                    </React.Fragment>
                  ))}
                  <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left', fontWeight: 'bold' }}>
                    ₪{proj.totalMonthlyIncome.toLocaleString()}
                  </td>
                  <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left', color: '#dc3545' }}>
                    ₪{proj.totalMonthlyTax.toLocaleString()}
                  </td>
                  <td style={{ padding: '6px', border: '1px solid #dee2e6', textAlign: 'left', fontWeight: 'bold', color: '#28a745' }}>
                    ₪{proj.netMonthlyIncome.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: '10px', fontSize: '12px', color: '#6c757d' }}>
          <strong>הסבר צבעים:</strong> 
          <span style={{ marginRight: '15px' }}>🔵 קצבאות</span>
          <span style={{ marginRight: '15px' }}>🟢 הכנסות נוספות</span>
          <span style={{ marginRight: '15px' }}>🟡 נכסי הון</span>
        </div>
      </div>
    </>
  );
};
