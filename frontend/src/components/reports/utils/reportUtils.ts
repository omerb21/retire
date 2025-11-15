import { formatCurrency } from '../../../lib/validation';

// ======= קבועים ומיפויים =======

export const ASSET_TYPES_MAP: Record<string, string> = {
  rental_property: "דירה להשכרה",
  investment: "השקעות",
  stocks: "מניות",
  bonds: "אגרות חוב",
  mutual_funds: "קרנות נאמנות",
  real_estate: "נדלן",
  savings: "חיסכון",
  deposits: "פיקדונות",
  savings_account: "חשבון חיסכון",
  other: "אחר"
};

export const PENSION_PRODUCT_TYPES: Record<string, string> = {
  pension_fund: "קרן פנסיה",
  insurance: "ביטוח מנהלים",
  provident_fund: "קופת גמל",
  old_provident: "קופת גמל ותיקה",
  study_fund: "קרן השתלמות",
  severance: "פיצויים",
  capital: "הון",
  annuity: "קצבה"
};

const formatMoney = (value: number): string => {
  const formatted = formatCurrency(value);
  return formatted.replace('₪', '').trim();
};

// ======= פונקציה ליצירת פרוט פעולות תזרים =======
export function generateCashflowOperationsDetails(
  pensions: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  fixationData: any,
  currentYear: number
): string[] {
  const operations: string[] = [];
  
  // 1. פרוט קצבאות פנסיוניות
  if (pensions && pensions.length > 0) {
    operations.push('📊 **מוצרים פנסיונים:**\n');
    pensions.forEach((pension, idx) => {
      const productType = PENSION_PRODUCT_TYPES[pension.product_type] || pension.product_type;
      const startDate = pension.start_date || 'לא צוין';
      const monthlyAmount = pension.monthly_pension || 0;
      
      if (monthlyAmount > 0) {
        operations.push(
          `${idx + 1}. **${pension.fund_name || 'מוצר פנסיוני'}** (${productType})\n` +
          `   - סכום חודשי: ₪${formatMoney(monthlyAmount)}\n` +
          `   - תאריך התחלת משיכה: ${startDate}\n` +
          `   - משך: לכל החיים (קצבה)\n`
        );
      }
    });
    operations.push('\n');
  }
  
  // 2. פרוט הכנסות נוספות
  if (additionalIncomes && additionalIncomes.length > 0) {
    operations.push('💰 **הכנסות נוספות:**\n');
    additionalIncomes.forEach((income, idx) => {
      const startDate = income.start_date || 'לא צוין';
      const endDate = income.end_date || 'ללא הגבלה';
      const monthlyAmount = income.monthly_amount || 0;
      
      operations.push(
        `${idx + 1}. **${income.description || 'הכנסה נוספת'}**\n` +
        `   - סכום חודשי: ₪${formatMoney(monthlyAmount)}\n` +
        `   - תקופה: ${startDate} עד ${endDate}\n`
      );
    });
    operations.push('\n');
  }
  
  // 3. פרוט נכסי הון
  if (capitalAssets && capitalAssets.length > 0) {
    operations.push('🏠 **נכסי הון:**\n');
    capitalAssets.forEach((asset, idx) => {
      const assetType = ASSET_TYPES_MAP[asset.asset_type] || asset.asset_type;
      const startDate = asset.start_date || 'לא צוין';
      const endDate = asset.end_date || 'ללא הגבלה';
      const monthlyIncome = asset.monthly_income || 0;
      const currentValue = asset.current_value || 0;
      
      if (monthlyIncome > 0) {
        operations.push(
          `${idx + 1}. **${asset.asset_name || assetType}**\n` +
          `   - הכנסה חודשית: ₪${formatMoney(monthlyIncome)}\n` +
          `   - ערך נוכחי: ₪${formatMoney(currentValue)}\n` +
          `   - תקופה: ${startDate} עד ${endDate}\n`
        );
      } else if (currentValue > 0) {
        operations.push(
          `${idx + 1}. **${asset.asset_name || assetType}**\n` +
          `   - ערך נוכחי: ₪${formatMoney(currentValue)}\n` +
          `   - תשואה שנתית משוערת: ${asset.annual_return_rate || 0}%\n` +
          `   - נכס הון (לא מופיע בתזרים החודשי)\n`
        );
      }
    });
    operations.push('\n');
  }
  
  // 4. פרוט פטורים
  if (fixationData) {
    operations.push('🛡️ **פטורים ממס:**\n');
    const monthlyExemption = (fixationData.remaining_exempt_capital || 0) / 180;
    const exemptionPercentage = ((fixationData.exemption_percentage || 0) * 100).toFixed(2);
    
    operations.push(
      `- קצבה פטורה חודשית (שנת קיבוע ${fixationData.fixation_year || currentYear}): ₪${formatMoney(monthlyExemption)}\n` +
      `- אחוז פטור: ${exemptionPercentage}%\n` +
      `- יתרת הון פטורה ראשונית: ₪${formatMoney(fixationData.exempt_capital_initial || 0)}\n` +
      `- יתרה אחרי קיזוזים: ₪${formatMoney(fixationData.remaining_exempt_capital || 0)}\n`
    );
  }
  
  return operations;
}

// ======= פונקציה ליצירת נתוני גרף עוגה =======
export function generatePieChartData(pensions: any[]): { labels: string[]; values: number[] } {
  const dataByType: Record<string, number> = {};
  
  pensions.forEach(pension => {
    const productType = PENSION_PRODUCT_TYPES[pension.product_type] || pension.product_type || 'לא צוין';
    const value = parseFloat(pension.current_balance || pension.balance || 0);
    
    if (value > 0) {
      dataByType[productType] = (dataByType[productType] || 0) + value;
    }
  });
  
  const labels = Object.keys(dataByType);
  const values = Object.values(dataByType);
  
  return { labels, values };
}
