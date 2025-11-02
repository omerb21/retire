import * as XLSX from 'xlsx';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { YearlyProjection, ASSET_TYPES } from '../types/reportTypes';
import { calculateNPV } from '../calculations/npvCalculations';

/**
 * יוצר דוח Excel
 */
export function generateExcelReport(
  yearlyProjection: YearlyProjection[],
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  clientData: any
) {
  const workbook = XLSX.utils.book_new();
  
  // גיליון 1: תזרים מזומנים מפורט
  const cashflowData = [
    // כותרות עמודות
    ['שנה', 'הכנסות פנסיה', 'הכנסות נוספות', 'הכנסות מנכסים', 'סך הכנסה', 'סך מס', 'נטו חודשי', 'נטו שנתי'],
    // נתונים
    ...yearlyProjection.slice(0, 30).map(year => [
      year.year.toString(),
      Math.round(year.totalMonthlyIncome * 0.6).toLocaleString(), // הערכה של הכנסות פנסיה
      Math.round(year.totalMonthlyIncome * 0.3).toLocaleString(), // הערכה של הכנסות נוספות  
      Math.round(year.totalMonthlyIncome * 0.1).toLocaleString(), // הערכה של הכנסות מנכסים
      year.totalMonthlyIncome.toLocaleString(),
      year.totalMonthlyTax.toLocaleString(),
      year.netMonthlyIncome.toLocaleString(),
      (year.netMonthlyIncome * 12).toLocaleString()
    ])
  ];
  
  // חישוב NPV
  const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
  const npv = calculateNPV(annualNetCashFlows, 0.03);
  
  // הוספת NPV וסיכומים לגיליון
  cashflowData.push(['', '', '', '', '', '', '', '']);
  cashflowData.push(['סיכום:', '', '', '', '', '', '', '']);
  cashflowData.push(['ערך נוכחי נקי (NPV):', '', '', '', '', '', '', Math.round(npv).toLocaleString()]);
  cashflowData.push(['סך שנות תחזית:', '', '', '', '', '', '', yearlyProjection.length.toString()]);
  
  const cashflowSheet = XLSX.utils.aoa_to_sheet(cashflowData);
  XLSX.utils.book_append_sheet(workbook, cashflowSheet, 'תזרים מזומנים');
  
  // גיליון 2: נכסי הון מפורט
  if (capitalAssets.length > 0) {
    const capitalAssetsData = [
      ['תיאור', 'סוג נכס', 'ערך נוכחי (₪)', 'תשלום  (₪)', 'תשואה שנתית %', 'יחס למס', 'תאריך תשלום', 'תאריך סיום'],
      ...capitalAssets.map(asset => [
        asset.description || asset.asset_name || 'ללא תיאור',
        ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type || 'לא צוין',
        `₪${(asset.current_value || 0).toLocaleString()}`,
        `₪${(asset.monthly_income || 0).toLocaleString()}`,
        `${((asset.annual_return_rate || 0) * 100).toFixed(1)}%`, 
        asset.tax_treatment === 'exempt' ? 'פטור ממס' : 'חייב במס',
        asset.start_date || 'לא צוין',
        asset.end_date || 'ללא הגבלה'
      ])
    ];
    
    // הוספת סיכום נכסי הון
    const totalValue = capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0);
    const totalMonthlyIncome = capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.monthly_income) || 0), 0);
    
    capitalAssetsData.push(['', '', '', '', '', '', '', '']);
    capitalAssetsData.push(['סך ערך נכסים:', '', '', totalValue.toLocaleString(), '', '', '', '']);
    capitalAssetsData.push(['סך הכנסה חודשית:', '', totalMonthlyIncome.toLocaleString(), '', '', '', '', '']);
    
    const capitalAssetsSheet = XLSX.utils.aoa_to_sheet(capitalAssetsData);
    XLSX.utils.book_append_sheet(workbook, capitalAssetsSheet, 'נכסי הון');
  }
  
  // גיליון 3: קצבאות מפורט
  if (pensionFunds.length > 0) {
    const pensionData = [
      ['שם הקרן', 'סוג קרן', 'מקדם קצבה', 'הפקדה חודשית', 'תשואה שנתית %', 'קצבה חודשית', 'תאריך התחלה', 'גיל פרישה'],
      ...pensionFunds.map(fund => [
        fund.fund_name || 'ללא שם',
        fund.fund_type || 'לא צוין',
        (fund.annuity_factor || 0).toFixed(2),
        (fund.monthly_deposit || 0).toLocaleString(),
        ((fund.annual_return_rate || 0) * 100).toFixed(1) + '%',
        (fund.pension_amount || fund.computed_monthly_amount || 0).toLocaleString(),
        fund.start_date || 'לא צוין',
        (fund.retirement_age || 67).toString()
      ])
    ];
    
    // הוספת סיכום קצבאות
    const totalCoefficient = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.annuity_factor) || 0), 0);
    const totalMonthlyDeposit = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.monthly_deposit) || 0), 0);
    const totalPensionAmount = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0);
    
    pensionData.push(['', '', '', '', '', '', '', '']);
    pensionData.push(['סך מקדמים:', '', totalCoefficient.toFixed(2), '', '', '', '', '']);
    pensionData.push(['סך הפקדות חודשיות:', '', '', totalMonthlyDeposit.toLocaleString(), '', '', '', '']);
    pensionData.push(['סך קצבאות חודשיות:', '', '', '', '', totalPensionAmount.toLocaleString(), '', '']);
    
    const pensionSheet = XLSX.utils.aoa_to_sheet(pensionData);
    XLSX.utils.book_append_sheet(workbook, pensionSheet, 'קצבאות');
  }
  
  // גיליון 4: הכנסות נוספות מפורט
  if (additionalIncomes.length > 0) {
    const additionalIncomesData = [
      ['תיאור', 'סוג הכנסה', 'סכום חודשי', 'סכום שנתי', 'יחס למס', 'תאריך התחלה', 'תאריך סיום', 'הצמדה'],
      ...additionalIncomes.map(income => {
        const amount = income.amount || 0;
        let monthlyAmount = 0;
        let annualAmount = 0;
        
        if (income.frequency === 'monthly') {
          monthlyAmount = amount;
          annualAmount = amount * 12;
        } else if (income.frequency === 'quarterly') {
          monthlyAmount = amount / 3;
          annualAmount = amount * 4;
        } else if (income.frequency === 'annually') {
          monthlyAmount = amount / 12;
          annualAmount = amount;
        }
        
        return [
          income.description || 'ללא תיאור',
          income.source_type || 'אחר',
          monthlyAmount.toLocaleString(),
          annualAmount.toLocaleString(),
          income.tax_treatment === 'exempt' ? 'פטור ממס' : 'חייב במס',
          income.start_date || 'לא צוין',
          income.end_date || 'ללא הגבלה',
          income.indexation_rate ? `${(income.indexation_rate * 100).toFixed(1)}%` : 'ללא'
        ];
      })
    ];
    
    // הוספת סיכום הכנסות נוספות
    const totalMonthlyIncome = additionalIncomes.reduce((sum, income) => {
      const amount = parseFloat(income.amount) || 0;
      if (income.frequency === 'monthly') return sum + amount;
      if (income.frequency === 'quarterly') return sum + (amount / 3);
      if (income.frequency === 'annually') return sum + (amount / 12);
      return sum + amount;
    }, 0);
    const totalAnnualIncome = additionalIncomes.reduce((sum, income) => {
      const amount = parseFloat(income.amount) || 0;
      if (income.frequency === 'monthly') return sum + (amount * 12);
      if (income.frequency === 'quarterly') return sum + (amount * 4);
      if (income.frequency === 'annually') return sum + amount;
      return sum + (amount * 12);
    }, 0);
    
    additionalIncomesData.push(['', '', '', '', '', '', '', '']);
    additionalIncomesData.push(['סך הכנסה חודשית:', '', totalMonthlyIncome.toLocaleString(), '', '', '', '', '']);
    additionalIncomesData.push(['סך הכנסה שנתית:', '', '', totalAnnualIncome.toLocaleString(), '', '', '', '']);
    
    const additionalIncomesSheet = XLSX.utils.aoa_to_sheet(additionalIncomesData);
    XLSX.utils.book_append_sheet(workbook, additionalIncomesSheet, 'הכנסות נוספות');
  }
  
  // גיליון 5: סיכום כללי
  const summaryData = [
    ['סיכום תכנון פרישה מקיף', '', ''],
    ['', '', ''],
    ['פרטי לקוח:', '', ''],
    ['שם:', clientData?.first_name + ' ' + (clientData?.last_name || ''), ''],
    ['תאריך לידה:', clientData?.birth_date || 'לא צוין', ''],
    ['תאריך דוח:', formatDateToDDMMYY(new Date()), ''],
    ['', '', ''],
    ['סיכום כספי:', '', ''],
    ['סך מקדמי קצבה:', pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.annuity_factor) || 0), 0).toFixed(2), ''],
    ['סך נכסי הון:', capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0).toLocaleString(), '₪'],
    ['הכנסה חודשית מפנסיה:', pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0).toLocaleString(), '₪'],
    ['הכנסות נוספות חודשיות:', additionalIncomes.reduce((sum, income) => sum + (parseFloat(income.monthly_amount) || 0), 0).toLocaleString(), '₪'],
    ['הכנסה חודשית מנכסי הון:', capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.monthly_income) || 0), 0).toLocaleString(), '₪'],
    ['', '', ''],
    ['ניתוח NPV:', '', ''],
    ['ערך נוכחי נקי:', Math.round(npv).toLocaleString(), '₪'],
    ['תקופת תחזית:', yearlyProjection.length.toString(), 'שנים'],
    ['שיעור היוון:', '3%', '']
  ];
  
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryData);
  XLSX.utils.book_append_sheet(workbook, summarySheet, 'סיכום כללי');
  
  // שמירת הקובץ
  const fileName = `דוח_פנסיוני_${clientData?.first_name || 'לקוח'}_${formatDateToDDMMYY(new Date()).replace(/\//g, '_')}.xlsx`;
  XLSX.writeFile(workbook, fileName);
}
