import { YearlyProjection } from '../types/reportTypes';
import { getPensionCeiling } from './pensionCalculations';
import { calculateTaxByBrackets } from './taxCalculations';

/**
 * מייצר תחזית שנתית של תזרים מזומנים
 * הפונקציה מציגה רק שנים עתידיות בתזרים, החל מהשנה הנוכחית
 */
export function generateYearlyProjection(
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  client: any,
  fixationData: any
): YearlyProjection[] {
  console.log('generateYearlyProjection called');
  console.log('Available data:', { 
    pensionFunds: pensionFunds.length, 
    additionalIncomes: additionalIncomes.length, 
    capitalAssets: capitalAssets.length,
    client: !!client
  });
  
  // קביעת שנת התחלה של התזרים - תמיד מתחיל משנת 2025 (השנה הנוכחית)
  const currentYear = new Date().getFullYear();
  const projectionStartYear = currentYear;
  const clientBirthYear = client?.birth_year || 1957;
  const maxAge = 90;
  const maxYear = clientBirthYear + maxAge;
  const projectionYears = Math.min(maxYear - projectionStartYear + 1, 40);
  
  const yearlyData: YearlyProjection[] = [];
  
  for (let i = 0; i < projectionYears; i++) {
    const year = projectionStartYear + i;
    const clientAge = year - clientBirthYear;
    
    const incomeBreakdown: number[] = [];
    let totalMonthlyIncome: number = 0;
    
    // Add pension fund incomes
    pensionFunds.forEach(fund => {
      let fundStartYear = currentYear;
      let fundStartMonth = 1;
      
      if (fund.pension_start_date) {
        const dateParts = fund.pension_start_date.split('-');
        fundStartYear = parseInt(dateParts[0]);
        fundStartMonth = parseInt(dateParts[1]);
      } else if (fund.start_date) {
        const dateParts = fund.start_date.split('-');
        fundStartYear = parseInt(dateParts[0]);
        fundStartMonth = parseInt(dateParts[1]);
      }
      
      const monthlyAmount = parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0;
      const yearsActive = year >= fundStartYear ? year - fundStartYear : 0;
      const indexationRate = fund.indexation_rate !== undefined ? fund.indexation_rate : 0;
      
      let adjustedAmount = 0;
      if (year > fundStartYear) {
        adjustedAmount = monthlyAmount * Math.pow(1 + indexationRate, yearsActive);
      } else if (year === fundStartYear) {
        const monthsInFirstYear = 13 - fundStartMonth;
        adjustedAmount = (monthlyAmount * monthsInFirstYear) / 12;
      }
      
      incomeBreakdown.push(Math.round(adjustedAmount));
      totalMonthlyIncome += adjustedAmount;
    });
    
    // Add additional incomes
    additionalIncomes.forEach(income => {
      let incomeStartYear = currentYear;
      
      if (income.start_date) {
        incomeStartYear = parseInt(income.start_date.split('-')[0]);
      }
      
      const incomeEndYear = income.end_date ? parseInt(income.end_date.split('-')[0]) : maxYear;
      let monthlyAmount = 0;
      
      if (income.monthly_amount) {
        monthlyAmount = parseFloat(income.monthly_amount);
      } else if (income.amount) {
        const amount = parseFloat(income.amount);
        if (income.frequency === 'monthly') {
          monthlyAmount = amount;
        } else if (income.frequency === 'quarterly') {
          monthlyAmount = amount / 3;
        } else if (income.frequency === 'annually') {
          monthlyAmount = amount / 12;
        } else {
          monthlyAmount = amount;
        }
      } else if (income.annual_amount) {
        monthlyAmount = parseFloat(income.annual_amount) / 12;
      }
      
      const amount: number = (year >= incomeStartYear && year <= incomeEndYear) ? monthlyAmount : 0;
      incomeBreakdown.push(Math.round(amount));
      totalMonthlyIncome += amount;
    });

    // Add capital assets income - only assets with payment > 0
    const activeCapitalAssets = capitalAssets.filter(asset => (parseFloat(asset.monthly_income) || 0) > 0);
    
    activeCapitalAssets.forEach(asset => {
      const paymentAmount = parseFloat(asset.monthly_income) || 0;
      let assetStartYear = currentYear;
      
      if (asset.start_date) {
        assetStartYear = parseInt(asset.start_date.split('-')[0]);
      }
      
      if (year === assetStartYear) {
        const monthlyAmount = paymentAmount / 12;
        incomeBreakdown.push(Math.round(monthlyAmount));
        totalMonthlyIncome += monthlyAmount;
      } else {
        incomeBreakdown.push(0);
      }
    });
    
    // Calculate tax
    let totalMonthlyTax = 0;
    let monthlyExemptPension = 0;
    
    // חישוב קצבה פטורה לפי הלוגיקה הנכונה מהגדרות המערכת:
    // קצבה פטורה = אחוז פטור מקיבוע × תקרת קצבה של השנה הראשונה בתזרים
    if (fixationData && fixationData.exemption_summary) {
      const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year;
      
      if (year >= eligibilityYear) {
        // אחוז הקצבה הפטורה שחושב במסך קיבוע זכויות (פעם אחת!)
        const exemptPensionPercentage = fixationData.exemption_summary.exempt_pension_percentage || 0;
        
        // תקרת קצבה של השנה הנוכחית (השנה הראשונה בתזרים)
        const currentYearCeiling = getPensionCeiling(currentYear);
        
        // קצבה פטורה = אחוז פטור מקיבוע × תקרת השנה הנוכחית
        monthlyExemptPension = exemptPensionPercentage * currentYearCeiling;
        
        console.log(`DEBUG Exempt Pension: ${exemptPensionPercentage} × ${currentYearCeiling} = ${monthlyExemptPension}`);
      }
    }
    
    // חישוב מס - לוגיקה נכונה: ניכוי הקצבה הפטורה מההכנסה החייבת
    const taxBreakdown: number[] = [];
    
    // שלב 1: חישוב סך ההכנסה החייבת
    // ⚠️ CRITICAL: הכנסות עם fixed_rate לא נכללות בחישוב המס המתקדם!
    // ⚠️ CRITICAL: קצבה פטורה מופחתת רק מהכנסה מפנסיה, לא מהכנסה מעבודה!
    let totalTaxableAnnualIncome = 0;
    let totalPensionAnnualIncome = 0; // סה"כ הכנסה מפנסיה בלבד
    
    incomeBreakdown.forEach((monthlyIncome, index) => {
      const annualIncome = monthlyIncome * 12;
      
      // בדיקה אם המקור פטור או עם מס קבוע (שלא צריך להיכלל)
      let shouldExclude = false;
      
      // הכנסות נוספות פטורות או עם מס קבוע
      if (index >= pensionFunds.length && index < pensionFunds.length + additionalIncomes.length) {
        const additionalIncomeIndex = index - pensionFunds.length;
        const additionalIncome = additionalIncomes[additionalIncomeIndex];
        if (additionalIncome && (additionalIncome.tax_treatment === 'exempt' || additionalIncome.tax_treatment === 'fixed_rate')) {
          shouldExclude = true;
        }
      }
      
      // נכסי הון פטורים או עם מס קבוע
      if (index >= pensionFunds.length + additionalIncomes.length) {
        const capitalAssetIndex = index - pensionFunds.length - additionalIncomes.length;
        const capitalAsset = capitalAssets[capitalAssetIndex];
        if (capitalAsset && (capitalAsset.tax_treatment === 'exempt' || capitalAsset.tax_treatment === 'fixed_rate')) {
          shouldExclude = true;
        }
      }
      
      if (!shouldExclude) {
        totalTaxableAnnualIncome += annualIncome;
        
        // אם זו הכנסה מקרן פנסיה, נוסיף אותה גם לסה"כ הכנסה מפנסיה
        if (index < pensionFunds.length) {
          totalPensionAnnualIncome += annualIncome;
        }
      }
    });
    
    // שלב 2: ניכוי הקצבה הפטורה רק מהכנסה מפנסיה
    const annualExemptPension = monthlyExemptPension * 12;
    const taxablePensionAfterExemption = Math.max(0, totalPensionAnnualIncome - annualExemptPension);
    
    // סה"כ הכנסה חייבת = הכנסה מפנסיה (אחרי פטור) + הכנסות אחרות
    const taxableIncomeAfterExemption = taxablePensionAfterExemption + (totalTaxableAnnualIncome - totalPensionAnnualIncome);
    
    // שלב 3: חישוב המס הכולל על ההכנסה החייבת (אחרי פטור)
    let totalAnnualTax = calculateTaxByBrackets(taxableIncomeAfterExemption, year);
    
    // הפחתת נקודות זיכוי
    if (client?.tax_credit_points) {
      totalAnnualTax = Math.max(0, totalAnnualTax - (client.tax_credit_points * 2904));
    }
    
    // שלב 4: קיזוז הקצבה הפטורה מהקצבאות (כמו בגרסה המקורית)
    const pensionIncomes = incomeBreakdown.slice(0, pensionFunds.length);
    const pensionAfterExemption = [...pensionIncomes];
    let remainingExemption = monthlyExemptPension;
    
    // מיון הקצבאות לפי גובה (מהגבוה לנמוך) וקיזוז הפטור
    const sortedPensions = pensionIncomes
      .map((income, index) => ({ income, index }))
      .filter(item => item.income > 0)
      .sort((a, b) => b.income - a.income);
    
    for (const pension of sortedPensions) {
      if (remainingExemption <= 0) break;
      const exemptionToApply = Math.min(pension.income, remainingExemption);
      pensionAfterExemption[pension.index] -= exemptionToApply;
      remainingExemption -= exemptionToApply;
    }
    
    // חישוב סך ההכנסה החייבת במס (אחרי קיזוז פטור) - לחלוקה פרופורציונלית
    let monthlyTaxableIncome = 0;
    pensionAfterExemption.forEach(income => {
      monthlyTaxableIncome += Math.max(0, income);
    });
    
    let monthlyTaxableAdditionalIncome = 0;
    let monthlyTaxableCapitalIncome = 0;
    
    // הכנסות נוספות חייבות במס (לא fixed_rate, לא exempt)
    incomeBreakdown.slice(pensionFunds.length, pensionFunds.length + additionalIncomes.length).forEach((income, index) => {
      const additionalIncome = additionalIncomes[index];
      if (additionalIncome && additionalIncome.tax_treatment !== 'exempt' && additionalIncome.tax_treatment !== 'fixed_rate') {
        monthlyTaxableAdditionalIncome += income;
      }
    });
    
    // נכסי הון חייבים במס רגיל (לא tax_spread, לא fixed_rate, לא exempt)
    activeCapitalAssets.forEach(asset => {
      const paymentAmount = parseFloat(asset.monthly_income) || 0;
      let assetStartYear = currentYear;
      if (asset.start_date) {
        assetStartYear = parseInt(asset.start_date.split('-')[0]);
      }
      if (year === assetStartYear && asset.tax_treatment === 'taxable') {
        monthlyTaxableCapitalIncome += paymentAmount / 12;
      }
    });
    
    const taxableTotalMonthlyIncome = monthlyTaxableIncome + monthlyTaxableAdditionalIncome + monthlyTaxableCapitalIncome;
    const baseAnnualIncome = Math.max(0, taxableIncomeAfterExemption - (monthlyTaxableCapitalIncome * 12));
    
    // התחל עם המס הרגיל
    const regularMonthlyTax = totalAnnualTax / 12;
    totalMonthlyTax = regularMonthlyTax;
    
    // חלוקת המס לפי סוג ההכנסה - פרופורציונלי
    
    // חלוקת המס לקצבאות - פרופורציונלי לפי הכנסה אחרי פטור
    pensionFunds.forEach((fund, index) => {
      const taxableIncomeAmount = pensionAfterExemption[index] || 0;
      const taxPortion = taxableTotalMonthlyIncome > 0 ? (taxableIncomeAmount / taxableTotalMonthlyIncome) * regularMonthlyTax : 0;
      taxBreakdown.push(Math.round(taxPortion));
    });
    
    // חלוקת המס להכנסות נוספות
    additionalIncomes.forEach((income, index) => {
      const incomeIndex = pensionFunds.length + index;
      const incomeAmount = incomeBreakdown[incomeIndex] || 0;
      
      if (income.tax_treatment === 'exempt') {
        taxBreakdown.push(0);
      } else if (income.tax_treatment === 'fixed_rate') {
        // מס קבוע - מוצג בטור המס אבל לא נכלל בסה"כ המס!
        const taxRate = (income.tax_rate || 0) / 100;
        const fixedTax = incomeAmount * taxRate;
        taxBreakdown.push(Math.round(fixedTax));
        // לא מוסיפים ל-totalMonthlyTax!
      } else {
        const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * regularMonthlyTax : 0;
        taxBreakdown.push(Math.round(taxPortion));
      }
    });
    
    // חלוקת המס לנכסי הון
    let capitalAssetIncomeIndex = 0;
    capitalAssets.forEach((asset, assetIndex) => {
      const paymentAmount = parseFloat(asset.monthly_income) || 0;
      if (paymentAmount === 0) return;
      
      const annualIncome = incomeBreakdown[pensionFunds.length + additionalIncomes.length + capitalAssetIncomeIndex] || 0;
      capitalAssetIncomeIndex++;
      
      if (annualIncome === 0) {
        taxBreakdown.push(0);
        return;
      }
      
      if (asset.tax_treatment === 'exempt') {
        taxBreakdown.push(0);
      } else if (asset.tax_treatment === 'fixed_rate') {
        // מס קבוע - מוצג בטור המס אבל לא נכלל בסה"כ המס!
        const taxRate = (asset.tax_rate || 0) / 100;
        const fixedTax = annualIncome * taxRate;
        taxBreakdown.push(Math.round(fixedTax));
        // לא מוסיפים ל-totalMonthlyTax!
      } else if (asset.tax_treatment === 'tax_spread') {
        // פריסת מס - חישוב מס שולי עם פריסה על מספר שנים
        const spreadYears = asset.spread_years || 1;
        const totalPayment = annualIncome * 12;
        const annualPortion = totalPayment / spreadYears;
        
        let totalSpreadTax = 0;
        for (let spreadYear = 0; spreadYear < spreadYears; spreadYear++) {
          const targetYear = year + spreadYear;
          const totalIncomeWithSpread = baseAnnualIncome + annualPortion;
          let taxWithSpread = calculateTaxByBrackets(totalIncomeWithSpread, targetYear);
          let taxWithoutSpread = baseAnnualIncome > 0 ? calculateTaxByBrackets(baseAnnualIncome, targetYear) : 0;
          
          if (client?.tax_credit_points) {
            const creditAmount = client.tax_credit_points * 2904;
            taxWithSpread = Math.max(0, taxWithSpread - creditAmount);
            taxWithoutSpread = Math.max(0, taxWithoutSpread - creditAmount);
          }
          
          const marginalTax = taxWithSpread - taxWithoutSpread;
          totalSpreadTax += marginalTax;
        }
        
        const monthlyTax = totalSpreadTax / 12;
        taxBreakdown.push(Math.round(monthlyTax));
        totalMonthlyTax += monthlyTax;
      } else if (asset.tax_treatment === 'taxable') {
        const annualPayment = annualIncome * 12;
        const totalIncomeWithAsset = baseAnnualIncome + annualPayment;
        let taxWithAsset = calculateTaxByBrackets(totalIncomeWithAsset, year);
        let taxWithoutAsset = baseAnnualIncome > 0 ? calculateTaxByBrackets(baseAnnualIncome, year) : 0;
        
        if (client?.tax_credit_points) {
          const creditAmount = client.tax_credit_points * 2904;
          taxWithAsset = Math.max(0, taxWithAsset - creditAmount);
          taxWithoutAsset = Math.max(0, taxWithoutAsset - creditAmount);
        }
        
        const marginalTax = taxWithAsset - taxWithoutAsset;
        const monthlyTax = marginalTax / 12;
        taxBreakdown.push(Math.round(monthlyTax));
        totalMonthlyTax += monthlyTax;
      }
    });
    
    yearlyData.push({
      year,
      clientAge,
      totalMonthlyIncome: Math.round(totalMonthlyIncome),
      totalMonthlyTax: Math.round(totalMonthlyTax),
      netMonthlyIncome: Math.round(totalMonthlyIncome - totalMonthlyTax),
      incomeBreakdown,
      taxBreakdown,
      exemptPension: Math.round(monthlyExemptPension)
    });
  }
  
  return yearlyData;
}
