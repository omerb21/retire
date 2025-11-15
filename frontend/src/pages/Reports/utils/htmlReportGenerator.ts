import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { getPensionCeiling } from '../../../components/reports/calculations/pensionCalculations';
import { YearlyProjection } from '../../../components/reports/types/reportTypes';

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
    <p><strong>הון פטור ראשוני:</strong> ₪${(fixationData.exemption_summary?.exempt_capital_initial || 0).toLocaleString()}</p>
    <p><strong>הון פטור נותר:</strong> ₪${(fixationData.exemption_summary?.remaining_exempt_capital || 0).toLocaleString()}</p>
    <p><strong>קצבה פטורה מקיבוע (${fixationData.eligibility_year || fixationData.exemption_summary?.eligibility_year || ''}):</strong> ₪${(fixationData.exemption_summary?.remaining_monthly_exemption || ((fixationData.exemption_summary?.remaining_exempt_capital || 0) / 180)).toLocaleString()}</p>
    <p><strong>אחוז קצבה פטורה:</strong> ${((fixationData.exemption_summary?.exempt_pension_percentage || 0) * 100).toFixed(2)}%</p>
    <p><strong>קצבה פטורה לשנת התזרים (${new Date().getFullYear()}):</strong> ₪${((fixationData.exemption_summary?.exempt_pension_percentage || 0) * getPensionCeiling(new Date().getFullYear())).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
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
