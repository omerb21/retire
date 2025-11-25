import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { getPensionCeiling } from '../../../components/reports/calculations/pensionCalculations';
import { YearlyProjection } from '../../../components/reports/types/reportTypes';
import { formatCurrency } from '../../../lib/validation';

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

interface NPVComparison {
  withExemption: number;
  withoutExemption: number;
  savings: number;
}

export const generateHTMLReport = (
  client: Client | null,
  fixationData: FixationData | null | undefined,
  yearlyProjection: YearlyProjection[],
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  npvComparison: NPVComparison | null,
  totalPensionBalance: number,
  totalCapitalValue: number,
  totalMonthlyIncome: number
): string => {
  return `
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>דוח פנסיוני - ${client?.name || 'לקוח'}</title>
  <style>
    :root {
      --brand-primary: #007bff;
      --brand-secondary: #6c757d;
      --brand-success: #28a745;
      --brand-warning: #ffc107;
      --brand-danger: #dc3545;
      --brand-info: #17a2b8;
      --gray-100: #f8f9fa;
      --gray-700: #495057;
      --radius: 8px;
      --radius-sm: 4px;
    }
    body { font-family: Arial, sans-serif; margin: 20px; direction: rtl; color: var(--gray-700); }
    h1, h2, h3 { color: var(--brand-primary); margin-top: 0; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { border: 1px solid #dee2e6; padding: 8px 10px; text-align: right; }
    th { background-color: var(--brand-primary); color: white; }
    tr:nth-child(even) { background-color: var(--gray-100); }
    .summary { background-color: #e7f3ff; padding: 16px; border-radius: var(--radius); margin: 20px 0; }
    .client-info { background-color: #f8f9fa; padding: 15px; border-radius: var(--radius); margin: 20px 0; }
    .npv-note { font-size: 12px; color: var(--brand-secondary); }
    .detailed-cashflow-table { font-size: 10px; }
    .th-pension-group-header { background-color: var(--brand-primary); }
    .th-additional-income-group-header { background-color: var(--brand-success); }
    .th-capital-asset-group-header { background-color: var(--brand-warning); }
    .th-pension-income-header { background-color: var(--brand-primary); }
    .th-pension-tax-header { background-color: #0056b3; }
    .th-additional-income-header { background-color: var(--brand-success); }
    .th-additional-tax-header { background-color: #1e7e34; }
    .th-asset-income-header { background-color: var(--brand-warning); }
    .th-asset-tax-header { background-color: #e0a800; }
    .print-button {
      position: fixed;
      top: 20px;
      left: 20px;
      background-color: var(--brand-primary);
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: var(--radius-sm);
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
  <p>תאריך: ${formatDateToDDMMYY(new Date())}</p>
  
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
    <p><strong>הון פטור ראשוני:</strong> ${formatCurrency(fixationData.exemption_summary?.exempt_capital_initial || 0)}</p>
    <p><strong>הון פטור נותר:</strong> ${formatCurrency(fixationData.exemption_summary?.remaining_exempt_capital || 0)}</p>
    <p><strong>קצבה פטורה מקיבוע (${fixationData.eligibility_year || fixationData.exemption_summary?.eligibility_year || ''}):</strong> ${formatCurrency(fixationData.exemption_summary?.remaining_monthly_exemption || ((fixationData.exemption_summary?.remaining_exempt_capital || 0) / 180))}</p>
    <p><strong>אחוז קצבה פטורה:</strong> ${((fixationData.exemption_summary?.exempt_pension_percentage || 0) * 100).toFixed(2)}%</p>
    <p><strong>קצבה פטורה לשנת התזרים (${new Date().getFullYear()}):</strong> ${formatCurrency((fixationData.exemption_summary?.exempt_pension_percentage || 0) * getPensionCeiling(new Date().getFullYear()))}</p>
  </div>
  ` : ''}

  <div class="summary">
    <h2>סיכום כספי</h2>
    <p><strong>סך יתרות קצבאות:</strong> ${formatCurrency(totalPensionBalance)}</p>
    <p><strong>סך נכסי הון:</strong> ${formatCurrency(totalCapitalValue)}</p>
    <p><strong>הכנסה חודשית צפויה:</strong> ${formatCurrency(totalMonthlyIncome)}</p>
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
          <td>${formatCurrency(proj.totalMonthlyIncome)}</td>
          <td>${formatCurrency(proj.totalMonthlyTax)}</td>
          <td>${formatCurrency(proj.netMonthlyIncome)}</td>
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
          <td>${formatCurrency(Number(fund.pension_amount) || Number(fund.computed_monthly_amount) || Number(fund.monthly_amount) || 0)}</td>
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
          <td>${formatCurrency((() => {
            const amount = parseFloat(income.amount) || 0;
            if (income.frequency === 'monthly') return amount;
            if (income.frequency === 'quarterly') return amount / 3;
            if (income.frequency === 'annually') return amount / 12;
            return amount;
          })())}</td>
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
          <td>${formatCurrency(parseFloat(asset.current_value) || 0)}</td>
          <td>${formatCurrency(parseFloat(asset.monthly_income) || 0)}</td>
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
    <p><strong>עם פטור:</strong> ${formatCurrency(npvComparison.withExemption)}</p>
    <p><strong>ללא פטור:</strong> ${formatCurrency(npvComparison.withoutExemption)}</p>
    <p><strong>חיסכון מקיבוע:</strong> ${formatCurrency(npvComparison.savings)}</p>
    ${totalCapitalValue > 0 ? `
    <h3>ערך נוכחי נכסי הון</h3>
    <p><strong>סך נכסי הון:</strong> ${formatCurrency(totalCapitalValue)}</p>
    <p><strong>סה"כ ערך כולל (תזרים + נכסים):</strong> ${formatCurrency(npvComparison.withExemption + totalCapitalValue)}</p>
    <p class="npv-note">נכסים אלו לא מופיעים בתזרים החודשי</p>
    ` : ''}
  </div>
  ` : ''}
  <h2>תחזית תזרים מפורט - פירוט לפי מקור</h2>
  <table class="detailed-cashflow-table">
    <thead>
      <tr>
        <th>שנה</th>
        <th>גיל</th>
        ${pensionFunds.map(fund => `
          <th colspan="2" class="th-pension-group-header">${fund.fund_name}</th>
        `).join('')}
        ${additionalIncomes.map(income => `
          <th colspan="2" class="th-additional-income-group-header">${income.description}</th>
        `).join('')}
        ${capitalAssets.filter(asset => parseFloat(asset.monthly_income) > 0).map(asset => `
          <th colspan="2" class="th-capital-asset-group-header">${asset.asset_name || asset.description}</th>
        `).join('')}
      </tr>
      <tr>
        <th></th>
        <th></th>
        ${pensionFunds.map(() => `
          <th class="th-pension-income-header">הכנסה</th>
          <th class="th-pension-tax-header">מס</th>
        `).join('')}
        ${additionalIncomes.map(() => `
          <th class="th-additional-income-header">הכנסה</th>
          <th class="th-additional-tax-header">מס</th>
        `).join('')}
        ${capitalAssets.filter(asset => parseFloat(asset.monthly_income) > 0).map(() => `
          <th class="th-asset-income-header">הכנסה</th>
          <th class="th-asset-tax-header">מס</th>
        `).join('')}
      </tr>
    </thead>
    <tbody>
      ${yearlyProjection.map(proj => `
        <tr>
          <td>${proj.year}</td>
          <td>${proj.clientAge}</td>
          ${proj.incomeBreakdown.map((income, idx) => `
            <td>${formatCurrency(income)}</td>
            <td>${formatCurrency(proj.taxBreakdown[idx] || 0)}</td>
          `).join('')}
        </tr>
      `).join('')}
    </tbody>
  </table>

</body>
</html>
    `;
};
