import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';

// ======= פונקציות עזר לעיצוב דוחות =======

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
          `   - סכום חודשי: ₪${monthlyAmount.toLocaleString()}\n` +
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
        `   - סכום חודשי: ₪${monthlyAmount.toLocaleString()}\n` +
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
          `   - הכנסה חודשית: ₪${monthlyIncome.toLocaleString()}\n` +
          `   - ערך נוכחי: ₪${currentValue.toLocaleString()}\n` +
          `   - תקופה: ${startDate} עד ${endDate}\n`
        );
      } else if (currentValue > 0) {
        operations.push(
          `${idx + 1}. **${asset.asset_name || assetType}**\n` +
          `   - ערך נוכחי: ₪${currentValue.toLocaleString()}\n` +
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
      `- קצבה פטורה חודשית (שנת קיבוע ${fixationData.fixation_year || currentYear}): ₪${monthlyExemption.toLocaleString()}\n` +
      `- אחוז פטור: ${exemptionPercentage}%\n` +
      `- יתרת הון פטורה ראשונית: ₪${(fixationData.exempt_capital_initial || 0).toLocaleString()}\n` +
      `- יתרה אחרי קיזוזים: ₪${(fixationData.remaining_exempt_capital || 0).toLocaleString()}\n`
    );
  }
  
  return operations;
}

// ======= פונקציה לחישוב NPV עם ובלי פטורים =======
export function calculateNPVComparison(
  yearlyProjection: any[],
  discountRate: number = 0.03
): { withExemption: number; withoutExemption: number; savings: number } {
  // NPV עם פטור (מצב נוכחי - המס כבר מחושב עם קיזוז הקצבה הפטורה)
  const withExemption = yearlyProjection.reduce((sum, yearData, year) => {
    const annualNet = yearData.netMonthlyIncome * 12;
    return sum + (annualNet / Math.pow(1 + discountRate, year));
  }, 0);
  
  // NPV ללא פטור - חישוב מחדש של המס ללא קיזוז הקצבה הפטורה
  const withoutExemption = yearlyProjection.reduce((sum, yearData, year) => {
    const grossIncome = yearData.totalMonthlyIncome;
    const currentTax = yearData.totalMonthlyTax;
    const exemptPension = yearData.exemptPension || 0; // הקצבה הפטורה שמקזזת מההכנסה החייבת
    
    // אם אין פטור בשנה זו, ה-NPV זהה
    if (exemptPension === 0) {
      const annualNet = yearData.netMonthlyIncome * 12;
      return sum + (annualNet / Math.pow(1 + discountRate, year));
    }
    
    // חישוב מס נוסף על הקצבה הפטורה (שלא שולם בגלל הפטור)
    // הפטור גרם להפחתת ההכנסה החייבת, כלומר חסכנו מס על הסכום הזה
    // נניח מס שולי ממוצע של 31% (מדרגה רביעית)
    const additionalTax = exemptPension * 0.31;
    
    // הכנסה נטו ללא פטור = הכנסה נטו נוכחית - המס הנוסף שהיינו משלמים
    const netWithoutExemption = yearData.netMonthlyIncome - additionalTax;
    const annualNet = netWithoutExemption * 12;
    
    return sum + (annualNet / Math.pow(1 + discountRate, year));
  }, 0);
  
  return {
    withExemption,
    withoutExemption,
    savings: withExemption - withoutExemption
  };
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

// ======= פונקציה להוספת גרף עוגה ל-PDF (גרסה משופרת) =======
export function drawPieChart(
  doc: jsPDF,
  x: number,
  y: number,
  radius: number,
  data: { labels: string[]; values: number[] }
): void {
  const total = data.values.reduce((sum, val) => sum + val, 0);
  
  if (total === 0) return;
  
  const colors = [
    [54, 162, 235],   // כחול
    [255, 99, 132],   // אדום
    [255, 206, 86],   // צהוב
    [75, 192, 192],   // ירוק-כחול
    [153, 102, 255],  // סגול
    [255, 159, 64],   // כתום
    [201, 203, 207]   // אפור
  ];
  
  let currentAngle = -Math.PI / 2; // מתחילים מלמעלה (12 שעות)
  
  // ציור העיגול החיצוני
  doc.setDrawColor(200, 200, 200);
  doc.setLineWidth(0.5);
  doc.circle(x, y, radius, 'S');
  
  // ציור הפלחים
  data.values.forEach((value, index) => {
    const sliceAngle = (value / total) * 2 * Math.PI;
    const endAngle = currentAngle + sliceAngle;
    const midAngle = currentAngle + sliceAngle / 2;
    
    // צבע הפלח
    const color = colors[index % colors.length];
    doc.setFillColor(color[0], color[1], color[2]);
    doc.setDrawColor(255, 255, 255);
    doc.setLineWidth(1);
    
    // נקודות הפלח
    const points: number[][] = [[x, y]];
    const steps = Math.max(10, Math.ceil(sliceAngle * 20)); // יותר נקודות לפלחים גדולים
    
    for (let i = 0; i <= steps; i++) {
      const angle = currentAngle + (sliceAngle * i / steps);
      const px = x + Math.cos(angle) * radius;
      const py = y + Math.sin(angle) * radius;
      points.push([px, py]);
    }
    
    // ציור הפלח כמצולע
    if (points.length >= 3) {
      doc.lines(
        points.slice(1).map((p, i) => {
          const prev = i === 0 ? points[0] : points[i];
          return [p[0] - prev[0], p[1] - prev[1]];
        }),
        points[0][0],
        points[0][1],
        [1, 1],
        'FD'
      );
    }
    
    // טקסט אחוזים על הפלח (רק לפלחים גדולים)
    const percentage = (value / total) * 100;
    if (percentage > 5) {
      const labelX = x + Math.cos(midAngle) * (radius * 0.65);
      const labelY = y + Math.sin(midAngle) * (radius * 0.65);
      doc.setFontSize(8);
      doc.setTextColor(255, 255, 255);
      doc.text(`${percentage.toFixed(0)}%`, labelX, labelY, { align: 'center' });
    }
    
    currentAngle = endAngle;
  });
  
  // הוספת לגנדה
  let legendY = y + radius + 20;
  const legendX = x - radius;
  
  doc.setFontSize(10);
  doc.setTextColor(0, 0, 0);
  doc.text('פילוח לפי סוג מוצר:', legendX, legendY - 10);
  
  data.labels.forEach((label, index) => {
    const color = colors[index % colors.length];
    const percentage = ((data.values[index] / total) * 100).toFixed(1);
    const value = data.values[index];
    
    // ריבוע צבע
    doc.setFillColor(color[0], color[1], color[2]);
    doc.setDrawColor(0, 0, 0);
    doc.setLineWidth(0.5);
    doc.rect(legendX, legendY - 3, 4, 4, 'FD');
    
    // טקסט
    doc.setFontSize(8);
    doc.setTextColor(0, 0, 0);
    const text = `${label}: ${percentage}% (₪${value.toLocaleString()})`;
    doc.text(text, legendX + 6, legendY);
    
    legendY += 6;
  });
}
