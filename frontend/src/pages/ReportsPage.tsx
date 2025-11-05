import React, { useMemo, useRef, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { formatDateToDDMMYY } from '../utils/dateUtils';
import { getTaxBracketsLegacyFormat, calculateTaxByBrackets } from '../components/reports/calculations/taxCalculations';

// ייבוא מקבצים מפוצלים
import { useReportData } from '../components/reports/hooks/useReportData';
import { generateYearlyProjection } from '../components/reports/calculations/cashflowCalculations';
import { getPensionCeiling, getExemptCapitalPercentage } from '../components/reports/calculations/pensionCalculations';
import { generatePDFReport } from '../components/reports/generators/PDFGenerator';
import { generateExcelReport } from '../components/reports/generators/ExcelGenerator';
import { YearlyProjection } from '../components/reports/types/reportTypes';
import { ASSET_TYPES_MAP, PENSION_PRODUCT_TYPES, generateCashflowOperationsDetails } from '../components/reports/utils/reportUtils';
import { calculateNPVComparison } from '../components/reports/calculations/npvCalculations';

const ReportsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  // שימוש ב-hook המפוצל לטעינת נתונים
  const {
    loading,
    error,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    client,
    fixationData
  } = useReportData(id);

  // חישוב תחזית שנתית באמצעות הפונקציה המפוצלת
  const yearlyProjection = useMemo(() => {
    if (!client || pensionFunds.length === 0) {
      return [];
    }
    return generateYearlyProjection(pensionFunds, additionalIncomes, capitalAssets, client, fixationData);
  }, [pensionFunds, additionalIncomes, capitalAssets, client, fixationData]);

  // חישוב NPV
  const npvComparison = useMemo(() => {
    if (yearlyProjection.length === 0) return null;
    return calculateNPVComparison(yearlyProjection, 0.03);
  }, [yearlyProjection]);


  // פונקציות ייצוא
  const handleGeneratePDF = async () => {
    try {
      await generatePDFReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, client);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('שגיאה ביצירת דוח PDF');
    }
  };

  const handleGenerateExcel = async () => {
    try {
      await generateExcelReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, client);
    } catch (error) {
      console.error('Error generating Excel:', error);
      alert('שגיאה ביצירת דוח Excel');
    }
  };

  const handleGenerateHTML = () => {
    const htmlContent = generateHTMLReport();
    const reportWindow = window.open('', '_blank');

    if (!reportWindow) {
      alert('יש לאפשר פתיחת חלונות קופצים להצגת הדוח');
      return;
    }

    reportWindow.document.open();
    reportWindow.document.write(htmlContent);
    reportWindow.document.close();
    reportWindow.focus();
  };

  const handleGenerateFixationDocuments = async () => {
    if (!fixationData || !client) {
      alert('אין נתוני קיבוע זכויות');
      return;
    }
    try {
      const response = await fetch(`/api/v1/fixation/${client.id}/package`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `מסמכי_קיבוע_${client?.name || 'לקוח'}.zip`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const errorText = await response.text();
        console.error('Server error:', errorText);
        alert('שגיאה בהפקת מסמכי קיבוע: ' + errorText);
      }
    } catch (error) {
      console.error('Error generating fixation documents:', error);
      alert('שגיאה בהפקת מסמכי קיבוע');
    }
  };

  const generateHTMLReport = (): string => {
    return `
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>דוח פנסיוני - ${client?.name || 'לקוח'}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; direction: rtl; }
    h1, h2, h3 { color: #007bff; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { border: 1px solid #dee2e6; padding: 10px; text-align: right; }
    th { background-color: #007bff; color: white; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    .summary { background-color: #e7f3ff; padding: 20px; border-radius: 8px; margin: 20px 0; }
    .client-info { background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }
    .print-button {
      position: fixed;
      top: 20px;
      left: 20px;
      background-color: #007bff;
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
      z-index: 1000;
    }
    @media print {
      .print-button { display: none; }
    }
  </style>
</head>
<body>
  <button class="print-button" onclick="window.print()">הדפס דוח</button>
  <h1>דוח פנסיוני מקיף - ${client?.name || 'לקוח'}</h1>
  <p>תאריך: ${new Date().toLocaleDateString('he-IL')}</p>
  
  <div class="client-info">
    <h2>פרטי לקוח</h2>
    <p><strong>שם:</strong> ${`${client?.first_name || ''} ${client?.last_name || ''}`.trim() || client?.name || ''}</p>
    <p><strong>תעודת זהות:</strong> ${client?.id_number || ''}</p>
    <p><strong>שנת לידה:</strong> ${client?.birth_year || (client?.birth_date ? new Date(client.birth_date).getFullYear() : '')}</p>
    <p><strong>נקודות זיכוי:</strong> ${client?.tax_credit_points || 0}</p>
  </div>

  ${fixationData ? `
  <div class="summary">
    <h2>פרטי קיבוע זכויות</h2>
    <p><strong>שנת קיבוע:</strong> ${fixationData.fixation_year || fixationData.eligibility_year || fixationData.exemption_summary?.eligibility_year || ''}</p>
    <p><strong>הון פטור ראשוני:</strong> ₪${(fixationData.exemption_summary?.exempt_capital_initial || 0).toLocaleString()}</p>
    <p><strong>הון פטור נותר:</strong> ₪${(fixationData.exemption_summary?.remaining_exempt_capital || 0).toLocaleString()}</p>
    <p><strong>קצבה פטורה חודשית:</strong> ₪${(fixationData.exemption_summary?.remaining_monthly_exemption || ((fixationData.exemption_summary?.remaining_exempt_capital || 0) / 180)).toLocaleString()}</p>
  </div>
  ` : ''}

  <div class="summary">
    <h2>סיכום כספי</h2>
    <p><strong>סך יתרות קצבאות:</strong> ₪${totalPensionBalance.toLocaleString()}</p>
    <p><strong>סך נכסי הון:</strong> ₪${totalCapitalValue.toLocaleString()}</p>
    <p><strong>הכנסה חודשית צפויה:</strong> ₪${totalMonthlyIncome.toLocaleString()}</p>
  </div>

  <h2>תחזית תזרים שנתי</h2>
  <table>
    <thead>
      <tr>
        <th>שנה</th>
        <th>גיל</th>
        <th>הכנסה חודשית</th>
        <th>מס חודשי</th>
        <th>נטו חודשי</th>
      </tr>
    </thead>
    <tbody>
      ${yearlyProjection.map(proj => `
        <tr>
          <td>${proj.year}</td>
          <td>${proj.clientAge}</td>
          <td>₪${proj.totalMonthlyIncome.toLocaleString()}</td>
          <td>₪${proj.totalMonthlyTax.toLocaleString()}</td>
          <td>₪${proj.netMonthlyIncome.toLocaleString()}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>

  <h2>פירוט קצבאות</h2>
  <table>
    <thead>
      <tr>
        <th>שם קרן</th>
        <th>מקדם קצבה</th>
        <th>קצבה חודשית</th>
        <th>תאריך תחילה</th>
      </tr>
    </thead>
    <tbody>
      ${pensionFunds.map(fund => `
        <tr>
          <td>${fund.fund_name}</td>
          <td>${fund.annuity_factor || fund.pension_coefficient || fund.coefficient || '-'}</td>
          <td>₪${(parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0).toLocaleString()}</td>
          <td>${fund.pension_start_date ? formatDateToDDMMYY(fund.pension_start_date) : '-'}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>

  ${additionalIncomes.length > 0 ? `
  <h2>הכנסות נוספות</h2>
  <table>
    <thead>
      <tr>
        <th>תיאור</th>
        <th>סכום חודשי</th>
        <th>תאריך התחלה</th>
        <th>תאריך סיום</th>
      </tr>
    </thead>
    <tbody>
      ${additionalIncomes.map(income => `
        <tr>
          <td>${income.description}</td>
          <td>₪${(() => {
            const amount = parseFloat(income.amount) || 0;
            if (income.frequency === 'monthly') return amount;
            if (income.frequency === 'quarterly') return amount / 3;
            if (income.frequency === 'annually') return amount / 12;
            return amount;
          })().toLocaleString()}</td>
          <td>${income.start_date ? formatDateToDDMMYY(income.start_date) : '-'}</td>
          <td>${income.end_date ? formatDateToDDMMYY(income.end_date) : 'ללא הגבלה'}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>
  ` : ''}

  ${capitalAssets.length > 0 ? `
  <h2>נכסי הון</h2>
  <table>
    <thead>
      <tr>
        <th>תיאור</th>
        <th>ערך נוכחי</th>
        <th>תשלום חד פעמי</th>
        <th>תאריך תשלום</th>
      </tr>
    </thead>
    <tbody>
      ${capitalAssets.map(asset => `
        <tr>
          <td>${asset.asset_name || asset.description}</td>
          <td>₪${(parseFloat(asset.current_value) || 0).toLocaleString()}</td>
          <td>₪${(parseFloat(asset.monthly_income) || 0).toLocaleString()}</td>
          <td>${asset.start_date ? formatDateToDDMMYY(asset.start_date) : '-'}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>
  ` : ''}

  ${npvComparison ? `
  <div class="summary">
    <h2>ניתוח ערך נוכחי נקי (NPV)</h2>
    <h3>NPV תזרים (קצבאות והכנסות)</h3>
    <p><strong>עם פטור:</strong> ₪${npvComparison.withExemption.toLocaleString()}</p>
    <p><strong>ללא פטור:</strong> ₪${npvComparison.withoutExemption.toLocaleString()}</p>
    <p><strong>חיסכון מקיבוע:</strong> ₪${npvComparison.savings.toLocaleString()}</p>
    ${totalCapitalValue > 0 ? `
    <h3>ערך נוכחי נכסי הון</h3>
    <p><strong>סך נכסי הון:</strong> ₪${totalCapitalValue.toLocaleString()}</p>
    <p><strong>סה"כ ערך כולל (תזרים + נכסים):</strong> ₪${(npvComparison.withExemption + totalCapitalValue).toLocaleString()}</p>
    <p style="font-size: 12px; color: #6c757d;">נכסים אלו לא מופיעים בתזרים החודשי</p>
    ` : ''}
  </div>
  ` : ''}

  <h2>תחזית תזרים מפורט - פירוט לפי מקור</h2>
  <table style="font-size: 11px;">
    <thead>
      <tr>
        <th>שנה</th>
        <th>גיל</th>
        ${pensionFunds.map(fund => `
          <th colspan="2" style="background-color: #007bff;">${fund.fund_name}</th>
        `).join('')}
        ${additionalIncomes.map(income => `
          <th colspan="2" style="background-color: #28a745;">${income.description}</th>
        `).join('')}
        ${capitalAssets.filter(asset => parseFloat(asset.monthly_income) > 0).map(asset => `
          <th colspan="2" style="background-color: #ffc107;">${asset.asset_name || asset.description}</th>
        `).join('')}
      </tr>
      <tr>
        <th></th>
        <th></th>
        ${pensionFunds.map(() => `
          <th style="background-color: #007bff;">הכנסה</th>
          <th style="background-color: #0056b3;">מס</th>
        `).join('')}
        ${additionalIncomes.map(() => `
          <th style="background-color: #28a745;">הכנסה</th>
          <th style="background-color: #1e7e34;">מס</th>
        `).join('')}
        ${capitalAssets.filter(asset => parseFloat(asset.monthly_income) > 0).map(() => `
          <th style="background-color: #ffc107;">הכנסה</th>
          <th style="background-color: #e0a800;">מס</th>
        `).join('')}
      </tr>
    </thead>
    <tbody>
      ${yearlyProjection.map(proj => `
        <tr>
          <td>${proj.year}</td>
          <td>${proj.clientAge}</td>
          ${proj.incomeBreakdown.map((income, idx) => `
            <td>₪${income.toLocaleString()}</td>
            <td>₪${(proj.taxBreakdown[idx] || 0).toLocaleString()}</td>
          `).join('')}
        </tr>
      `).join('')}
    </tbody>
  </table>

</body>
</html>
    `;
  };

  // טעינה
  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <div>טוען נתונים...</div>
      </div>
    );
  }

  // שגיאה
  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <div style={{ color: 'red', marginBottom: '20px' }}>שגיאה: {error}</div>
        <Link to={`/clients/${id}`}>חזרה לפרטי לקוח</Link>
      </div>
    );
  }

  // אם אין נתונים
  if (!pensionFunds.length && !additionalIncomes.length && !capitalAssets.length) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h3>אין מספיק נתונים ליצירת דוח</h3>
        <p>אנא הוסף קצבאות, הכנסות נוספות או נכסי הון</p>
        <div style={{ marginTop: '10px' }}>
          <Link to={`/clients/${id}/pension-funds`} style={{ color: '#007bff', marginRight: '15px' }}>
            הוסף קצבאות ←
          </Link>
          <Link to={`/clients/${id}/additional-incomes`} style={{ color: '#007bff', marginRight: '15px' }}>
            הוסף הכנסות נוספות ←
          </Link>
          <Link to={`/clients/${id}/capital-assets`} style={{ color: '#007bff' }}>
            הוסף נכסי הון ←
          </Link>
        </div>
      </div>
    );
  }

  // חישוב סיכומים
  const totalPensionBalance = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.balance) || 0), 0);
  const totalMonthlyPension = pensionFunds.reduce((sum, fund) => 
    sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
  const totalAdditionalIncome = additionalIncomes.reduce((sum, income) => {
    const amount = parseFloat(income.amount) || 0;
    let monthlyAmount = amount;
    if (income.frequency === 'quarterly') monthlyAmount = amount / 3;
    else if (income.frequency === 'annually') monthlyAmount = amount / 12;
    return sum + monthlyAmount;
  }, 0);
  const totalCapitalValue = capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0);
  const totalMonthlyIncome = totalMonthlyPension + totalAdditionalIncome;
  

  return (
    <div style={{ padding: '20px', direction: 'rtl' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>דוחות פנסיה - {client?.name}</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={handleGenerateExcel}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#28a745', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            📊 דוח -Excel
          </button>
          <button 
            onClick={handleGenerateHTML}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#FF0000', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            🌐דוח PDF מלא
          </button>
          {fixationData && (
            <button 
              onClick={handleGenerateFixationDocuments}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#6f42c1', 
                color: 'white', 
                border: 'none', 
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              📋 מסמכי קיבוע
            </button>
          )}
        </div>
      </div>

      {/* פרטי לקוח */}
      {client && (
        <div style={{ 
          backgroundColor: '#f8f9fa', 
          padding: '20px', 
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          <h3>פרטי לקוח</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px' }}>
            <div><strong>שם:</strong> {`${client.first_name || ''} ${client.last_name || ''}`.trim() || client.name || '-'}</div>
            <div><strong>תעודת זהות:</strong> {client.id_number || '-'}</div>
            <div><strong>שנת לידה:</strong> {client.birth_year || (client.birth_date ? new Date(client.birth_date).getFullYear() : '-')}</div>
            <div><strong>נקודות זיכוי:</strong> {client.tax_credit_points || 0}</div>
          </div>
        </div>
      )}

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
            <div><strong>שנת קיבוע:</strong> {fixationData.fixation_year || fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || '-'}</div>
            <div><strong>הון פטור ראשוני:</strong> ₪{(fixationData.exemption_summary.exempt_capital_initial || 0).toLocaleString()}</div>
            <div><strong>הון פטור נותר:</strong> ₪{(fixationData.exemption_summary.remaining_exempt_capital || 0).toLocaleString()}</div>
            <div><strong>קצבה פטורה חודשית:</strong> ₪{(fixationData.exemption_summary.remaining_monthly_exemption || ((fixationData.exemption_summary.remaining_exempt_capital || 0) / 180)).toLocaleString()}</div>
          </div>
        </div>
      )}


      {/* טבלת תזרים שנתי - סיכום */}
      {yearlyProjection.length > 0 && (
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
      )}

      {/* טבלת תזרים מפורט - טור לכל מקור הכנסה */}
      {yearlyProjection.length > 0 && (
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
      )}

      {/* חישוב NPV */}
      {npvComparison && (
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
                  ₪{npvComparison.withExemption.toLocaleString()}
                </div>
              </div>
              <div>
                <strong>ללא פטור:</strong>
                <div style={{ fontSize: '20px', color: '#dc3545' }}>
                  ₪{npvComparison.withoutExemption.toLocaleString()}
                </div>
              </div>
              <div>
                <strong>חיסכון מקיבוע:</strong>
                <div style={{ fontSize: '20px', color: '#007bff' }}>
                  ₪{npvComparison.savings.toLocaleString()}
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
                    ₪{totalCapitalValue.toLocaleString()}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6c757d', marginTop: '5px' }}>
                    נכסים אלו לא מופיעים בתזרים החודשי
                  </div>
                </div>
                <div>
                  <strong>סה"כ ערך כולל (תזרים + נכסים):</strong>
                  <div style={{ fontSize: '20px', color: '#007bff' }}>
                    ₪{(npvComparison.withExemption + totalCapitalValue).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* פירוט מקורות הכנסה */}
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
                      ₪{(parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0).toLocaleString()}
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
                      ₪{(() => {
                        const amount = parseFloat(income.amount) || 0;
                        if (income.frequency === 'monthly') return amount;
                        if (income.frequency === 'quarterly') return amount / 3;
                        if (income.frequency === 'annually') return amount / 12;
                        return amount;
                      })().toLocaleString()}
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
                      ₪{(parseFloat(asset.current_value) || 0).toLocaleString()}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>
                      ₪{(parseFloat(asset.monthly_income) || 0).toLocaleString()}
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

      <div style={{ marginTop: '30px', textAlign: 'center' }}>
        <Link to={`/clients/${id}`} style={{ 
          padding: '10px 20px', 
          backgroundColor: '#6c757d', 
          color: 'white', 
          textDecoration: 'none',
          borderRadius: '4px',
          display: 'inline-block'
        }}>
          חזרה לפרטי לקוח
        </Link>
      </div>
    </div>
  );
};

export default ReportsPage;
