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
    
    if (fixationData && fixationData.exemption_summary) {
      const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year;
      
      if (year >= eligibilityYear) {
        const remainingExemptCapital = fixationData.exemption_summary.remaining_exempt_capital || 0;
        const remainingMonthlyExemption = fixationData.exemption_summary.remaining_monthly_exemption || (remainingExemptCapital / 180);
        const pensionCeilingEligibility = getPensionCeiling(eligibilityYear);
        
        const correctExemptionPercentage = pensionCeilingEligibility > 0 
          ? remainingMonthlyExemption / pensionCeilingEligibility 
          : 0;
        
        if (year === eligibilityYear) {
          monthlyExemptPension = remainingMonthlyExemption;
        } else {
          const pensionCeiling = getPensionCeiling(year);
          monthlyExemptPension = correctExemptionPercentage * pensionCeiling;
        }
      }
    }
    
    // חישוב מס - לוגיקה נכונה: ניכוי הקצבה הפטורה מההכנסה החייבת
    const taxBreakdown: number[] = [];
    
    // שלב 1: חישוב סך ההכנסה החייבת לפני פטור
    let totalTaxableAnnualIncome = 0;
    incomeBreakdown.forEach((monthlyIncome, index) => {
      const annualIncome = monthlyIncome * 12;
      
      // בדיקה אם המקור פטור לחלוטין
      let isFullyExempt = false;
      
      // הכנסות נוספות פטורות
      if (index >= pensionFunds.length && index < pensionFunds.length + additionalIncomes.length) {
        const additionalIncomeIndex = index - pensionFunds.length;
        const additionalIncome = additionalIncomes[additionalIncomeIndex];
        if (additionalIncome && additionalIncome.tax_treatment === 'exempt') {
          isFullyExempt = true;
        }
      }
      
      // נכסי הון פטורים
      if (index >= pensionFunds.length + additionalIncomes.length) {
        const capitalAssetIndex = index - pensionFunds.length - additionalIncomes.length;
        const capitalAsset = capitalAssets[capitalAssetIndex];
        if (capitalAsset && capitalAsset.tax_treatment === 'exempt') {
          isFullyExempt = true;
        }
      }
      
      if (!isFullyExempt) {
        totalTaxableAnnualIncome += annualIncome;
      }
    });
    
    // שלב 2: ניכוי הקצבה הפטורה מההכנסה החייבת
    const annualExemptPension = monthlyExemptPension * 12;
    const taxableIncomeAfterExemption = Math.max(0, totalTaxableAnnualIncome - annualExemptPension);
    
    // שלב 3: חישוב המס הכולל על ההכנסה החייבת (אחרי פטור)
    let totalAnnualTax = calculateTaxByBrackets(taxableIncomeAfterExemption, year);
    
    // הפחתת נקודות זיכוי
    if (client?.tax_credit_points) {
      totalAnnualTax = Math.max(0, totalAnnualTax - (client.tax_credit_points * 2904));
    }
    
    // שלב 4: חלוקת המס בין המקורות
    // חישוב הכנסה בסיסית (ללא נכסי הון עם טיפול מיוחד)
    let baseAnnualIncome = 0;
    incomeBreakdown.forEach((monthlyIncome, index) => {
      const annualIncome = monthlyIncome * 12;
      
      // דלג על נכסי הון - הם מטופלים בנפרד
      if (index >= pensionFunds.length + additionalIncomes.length) {
        return;
      }
      
      // דלג על הכנסות נוספות עם fixed_rate או exempt
      if (index >= pensionFunds.length) {
        const additionalIncomeIndex = index - pensionFunds.length;
        const additionalIncome = additionalIncomes[additionalIncomeIndex];
        if (additionalIncome && (additionalIncome.tax_treatment === 'exempt' || additionalIncome.tax_treatment === 'fixed_rate')) {
          return;
        }
      }
      
      baseAnnualIncome += annualIncome;
    });
    
    baseAnnualIncome = Math.max(0, baseAnnualIncome - annualExemptPension);
    
    // התחל עם המס הרגיל מהקצבאות וההכנסות הרגילות
    const regularMonthlyTax = totalAnnualTax / 12;
    totalMonthlyTax = regularMonthlyTax;
    
    // חלוקת המס לפי סוג ההכנסה
    
    incomeBreakdown.forEach((monthlyIncome, index) => {
      if (monthlyIncome === 0) {
        taxBreakdown.push(0);
        return;
      }
      
      const annualIncome = monthlyIncome * 12;
      
      // הכנסות נוספות - בדיקת יחס מס
      if (index >= pensionFunds.length && index < pensionFunds.length + additionalIncomes.length) {
        const additionalIncomeIndex = index - pensionFunds.length;
        const additionalIncome = additionalIncomes[additionalIncomeIndex];
        
        if (additionalIncome) {
          if (additionalIncome.tax_treatment === 'exempt') {
            taxBreakdown.push(0);
            return;
          } else if (additionalIncome.tax_treatment === 'fixed_rate') {
            // מס קבוע (כמו שכירות מדירה 10%)
            const monthlyTax = monthlyIncome * ((additionalIncome.tax_rate || 0) / 100);
            taxBreakdown.push(Math.round(monthlyTax));
            totalMonthlyTax += monthlyTax;
            return;
          }
        }
      }
      
      // נכסי הון - טיפול מיוחד לפי יחס מס
      if (index >= pensionFunds.length + additionalIncomes.length) {
        const capitalAssetIndex = index - pensionFunds.length - additionalIncomes.length;
        const capitalAsset = activeCapitalAssets[capitalAssetIndex];
        
        if (capitalAsset) {
          if (capitalAsset.tax_treatment === 'exempt') {
            taxBreakdown.push(0);
            return;
          } else if (capitalAsset.tax_treatment === 'fixed_rate') {
            // מס קבוע
            const monthlyTax = monthlyIncome * ((capitalAsset.tax_rate || 0) / 100);
            taxBreakdown.push(Math.round(monthlyTax));
            totalMonthlyTax += monthlyTax;
            return;
          } else if (capitalAsset.tax_treatment === 'tax_spread') {
            // פריסת מס - חישוב מס שולי עם פריסה
            const spreadYears = capitalAsset.spread_years || 1;
            const totalPayment = annualIncome;
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
            return;
          } else if (capitalAsset.tax_treatment === 'capital_gains') {
            // רווח הון - 25% על הרווח הריאלי
            const realReturnRate = Math.max(0, (capitalAsset.annual_return_rate || 0) - 2);
            const realGain = annualIncome * (realReturnRate / (capitalAsset.annual_return_rate || 1));
            const monthlyTax = (realGain * 0.25) / 12;
            taxBreakdown.push(Math.round(monthlyTax));
            totalMonthlyTax += monthlyTax;
            return;
          } else {
            // taxable - מס שולי רגיל
            const totalIncomeWithAsset = baseAnnualIncome + annualIncome;
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
            return;
          }
        }
      }
      
      // קצבאות והכנסות נוספות רגילות - חלוקה פרופורציונלית
      const taxableBaseIncome = baseAnnualIncome + annualExemptPension;
      const taxRatio = taxableBaseIncome > 0 ? annualIncome / taxableBaseIncome : 0;
      const monthlyTaxForSource = regularMonthlyTax * taxRatio;
      taxBreakdown.push(Math.round(monthlyTaxForSource));
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
