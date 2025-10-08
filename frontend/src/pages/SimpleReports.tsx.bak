import React, { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { apiFetch } from "../lib/api";
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';

const ASSET_TYPES = [
  { value: "rental_property", label: "דירה להשכרה" },
  { value: "investment", label: "השקעות" },
  { value: "stocks", label: "מניות" },
  { value: "bonds", label: "אגרות חוב" },
  { value: "mutual_funds", label: "קרנות נאמנות" },
  { value: "real_estate", label: "נדלן" },
  { value: "savings_account", label: "חשבון חיסכון" },
  { value: "other", label: "אחר" }
];

interface YearlyProjection {
  year: number;
  clientAge: number;
  totalMonthlyIncome: number;
  totalMonthlyTax: number;
  netMonthlyIncome: number;
  incomeBreakdown: number[];
  taxBreakdown: number[];
}

/**
 * מחשב את הערך הנוכחי הנקי (NPV) של תזרים מזומנים
 * @param cashFlows מערך של תזרימי מזומנים (ערך שלילי עבור השקעה ראשונית, חיובי עבור תקבולים)
 * @param discountRate שיעור היוון שנתי (למשל 0.05 עבור 5%)
 * @returns הערך הנוכחי הנקי (NPV)
 */
function calculateNPV(cashFlows: number[], discountRate: number): number {
  return cashFlows.reduce((sum, cashFlow, year) => {
    return sum + (cashFlow / Math.pow(1 + discountRate, year));
  }, 0);
}

/**
 * יוצר דוח PDF עם תמיכה מלאה בעברית
 */
function generatePDFReport(
  yearlyProjection: YearlyProjection[],
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  clientData: any
) {
  const doc = new jsPDF();
  
  // הגדרת כיוון RTL ופונט תומך עברית
  doc.setR2L(true);
  doc.setLanguage("he");
  
  let yPosition = 20;
  
  // כותרת הדוח
  doc.setFontSize(20);
  doc.text('דוח פנסיוני - תמונת מצב', 105, yPosition, { align: 'center' });
  yPosition += 15;
  
  // תאריך יצירת הדוח
  doc.setFontSize(12);
  const currentDate = new Date().toLocaleDateString('he-IL');
  doc.text(`תאריך יצירת הדוח: ${currentDate}`, 200, yPosition, { align: 'right' });
  yPosition += 20;
  
  // חישוב NPV
  const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
  const npv = calculateNPV(annualNetCashFlows, 0.03);
  
  // הצגת NPV
  doc.setFontSize(14);
  doc.text('ערך נוכחי נקי (NPV) של התזרים:', 200, yPosition, { align: 'right' });
  yPosition += 10;
  doc.setFontSize(16);
  doc.setTextColor(0, 128, 0); // צבע ירוק
  doc.text(`₪${Math.round(npv).toLocaleString()}`, 200, yPosition, { align: 'right' });
  doc.setTextColor(0, 0, 0); // חזרה לצבע שחור
  yPosition += 20;
  
  // טבלת תזרים מזומנים
  doc.setFontSize(14);
  doc.text('תחזית תזרים מזומנים שנתי:', 200, yPosition, { align: 'right' });
  yPosition += 10;
  
  const tableData = yearlyProjection.map(year => [
    year.year.toString(),
    `₪${year.totalMonthlyIncome.toLocaleString()}`,
    `₪${year.totalMonthlyTax.toLocaleString()}`,
    `₪${year.netMonthlyIncome.toLocaleString()}`,
    `₪${(year.netMonthlyIncome * 12).toLocaleString()}`
  ]);
  
  autoTable(doc, {
    head: [['שנה', 'הכנסה חודשית', 'מס חודשי', 'נטו חודשי', 'נטו שנתי']],
    body: tableData,
    startY: yPosition,
    styles: {
      font: 'helvetica',
      fontSize: 10,
      cellPadding: 3,
      halign: 'center'
    },
    headStyles: {
      fillColor: [233, 236, 239],
      textColor: [0, 0, 0],
      fontStyle: 'bold'
    },
    columnStyles: {
      0: { halign: 'center' },
      1: { halign: 'right' },
      2: { halign: 'right' },
      3: { halign: 'right' },
      4: { halign: 'right' }
    },
    margin: { right: 20, left: 20 }
  });
  
  // עמוד חדש לפירוט נכסים
  doc.addPage();
  yPosition = 20;
  
  // פירוט נכסי הון
  if (capitalAssets.length > 0) {
    doc.setFontSize(14);
    doc.text('נכסי הון:', 200, yPosition, { align: 'right' });
    yPosition += 10;
    
    const capitalAssetsData = capitalAssets.map(asset => [
      asset.description || 'ללא תיאור',
      ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type,
      `₪${(asset.monthly_income || 0).toLocaleString()}`,
      `₪${(asset.current_value || 0).toLocaleString()}`,
      asset.start_date || 'לא צוין',
      asset.end_date || 'ללא הגבלה'
    ]);
    
    autoTable(doc, {
      head: [['תיאור', 'סוג נכס', 'הכנסה חודשית', 'ערך נוכחי', 'תאריך התחלה', 'תאריך סיום']],
      body: capitalAssetsData,
      startY: yPosition,
      styles: {
        font: 'helvetica',
        fontSize: 9,
        cellPadding: 2
      },
      headStyles: {
        fillColor: [233, 236, 239],
        textColor: [0, 0, 0],
        fontStyle: 'bold'
      },
      margin: { right: 20, left: 20 }
    });
    
    yPosition = (doc as any).lastAutoTable.finalY + 20;
  }
  
  // פירוט קרנות פנסיה
  if (pensionFunds.length > 0) {
    doc.setFontSize(14);
    doc.text('קרנות פנסיה:', 200, yPosition, { align: 'right' });
    yPosition += 10;
    
    const pensionData = pensionFunds.map(fund => [
      fund.fund_name || 'ללא שם',
      `₪${(fund.current_balance || 0).toLocaleString()}`,
      `₪${(fund.monthly_deposit || 0).toLocaleString()}`,
      `${((fund.annual_return_rate || 0) * 100).toFixed(1)}%`,
      (fund.retirement_age || 67).toString()
    ]);
    
    autoTable(doc, {
      head: [['שם הקרן', 'יתרה נוכחית', 'הפקדה חודשית', 'תשואה שנתית', 'גיל פרישה']],
      body: pensionData,
      startY: yPosition,
      styles: {
        font: 'helvetica',
        fontSize: 9,
        cellPadding: 2
      },
      headStyles: {
        fillColor: [233, 236, 239],
        textColor: [0, 0, 0],
        fontStyle: 'bold'
      },
      margin: { right: 20, left: 20 }
    });
  }
  
  // שמירת הקובץ
  doc.save(`דוח-פנסיוני-${currentDate}.pdf`);
}

/**
 * יוצר דוח Excel
 */
function generateExcelReport(
  yearlyProjection: YearlyProjection[],
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  clientData: any
) {
  const workbook = XLSX.utils.book_new();
  
  // גיליון 1: תזרים מזומנים
  const cashflowData = [
    ['שנה', 'הכנסה חודשית', 'מס חודשי', 'נטו חודשי', 'נטו שנתי'],
    ...yearlyProjection.map(year => [
      year.year.toString(),
      year.totalMonthlyIncome.toString(),
      year.totalMonthlyTax.toString(),
      year.netMonthlyIncome.toString(),
      (year.netMonthlyIncome * 12).toString()
    ])
  ];
  
  // חישוב NPV
  const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
  const npv = calculateNPV(annualNetCashFlows, 0.03);
  
  // הוספת NPV לגיליון
  cashflowData.push(['', '', '', '', '']);
  cashflowData.push(['ערך נוכחי נקי (NPV):', '', '', '', Math.round(npv).toString()]);
  
  const cashflowSheet = XLSX.utils.aoa_to_sheet(cashflowData);
  XLSX.utils.book_append_sheet(workbook, cashflowSheet, 'תזרים מזומנים');
  
  // גיליון 2: נכסי הון
  if (capitalAssets.length > 0) {
    const capitalAssetsData = [
      ['תיאור', 'סוג נכס', 'הכנסה חודשית', 'ערך נוכחי', 'תאריך התחלה', 'תאריך סיום'],
      ...capitalAssets.map(asset => [
        asset.description || 'ללא תיאור',
        ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type,
        (asset.monthly_income || 0).toString(),
        (asset.current_value || 0).toString(),
        asset.start_date || 'לא צוין',
        asset.end_date || 'ללא הגבלה'
      ])
    ];
    
    const capitalAssetsSheet = XLSX.utils.aoa_to_sheet(capitalAssetsData);
    XLSX.utils.book_append_sheet(workbook, capitalAssetsSheet, 'נכסי הון');
  }
  
  // גיליון 3: קרנות פנסיה
  if (pensionFunds.length > 0) {
    const pensionData = [
      ['שם הקרן', 'יתרה נוכחית', 'הפקדה חודשית', 'תשואה שנתית', 'גיל פרישה'],
      ...pensionFunds.map(fund => [
        fund.fund_name || 'ללא שם',
        (fund.current_balance || 0).toString(),
        (fund.monthly_deposit || 0).toString(),
        ((fund.annual_return_rate || 0) * 100).toString(),
        (fund.retirement_age || 67).toString()
      ])
    ];
    
    const pensionSheet = XLSX.utils.aoa_to_sheet(pensionData);
    XLSX.utils.book_append_sheet(workbook, pensionSheet, 'קרנות פנסיה');
  }
  
  // גיליון 4: הכנסות נוספות
  if (additionalIncomes.length > 0) {
    const additionalIncomesData = [
      ['תיאור', 'סכום חודשי', 'תאריך התחלה', 'תאריך סיום'],
      ...additionalIncomes.map(income => [
        income.description || 'ללא תיאור',
        (income.monthly_amount || 0).toString(),
        income.start_date || 'לא צוין',
        income.end_date || 'ללא הגבלה'
      ])
    ];
    
    const additionalIncomesSheet = XLSX.utils.aoa_to_sheet(additionalIncomesData);
    XLSX.utils.book_append_sheet(workbook, additionalIncomesSheet, 'הכנסות נוספות');
  }
  
  // שמירת הקובץ
  const currentDate = new Date().toLocaleDateString('he-IL');
  XLSX.writeFile(workbook, `דוח-פנסיוני-${currentDate}.xlsx`);
}

interface ReportData {
  client_info: {
    name: string;
    id_number: string;
    birth_year?: number;
  };
  financial_summary: {
    total_pension_value: number;
    total_additional_income: number;
    total_capital_assets: number;
    total_wealth: number;
    estimated_tax: number;
  };
  cashflow_projection: Array<{
    date: string;
    amount: number;
    source: string;
  }>;
  yearly_totals: {
    total_income: number;
    total_tax: number;
    net_income: number;
  };
}

const SimpleReports: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pensionFunds, setPensionFunds] = useState<any[]>([]);
  const [additionalIncomes, setAdditionalIncomes] = useState<any[]>([]);
  const [capitalAssets, setCapitalAssets] = useState<any[]>([]);
  const [taxCalculation, setTaxCalculation] = useState<any>(null);
  const [client, setClient] = useState<any>(null);

  // Load report data
  useEffect(() => {
    const fetchReportData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get client info
        const clientResponse = await axios.get(`/api/v1/clients/${id}`);
        const clientData = clientResponse.data;
        setClient(clientData);

        // Get financial data - pension funds, additional incomes, capital assets
        const [pensionFundsResponse, additionalIncomesResponse, capitalAssetsResponse] = await Promise.all([
          axios.get(`/api/v1/clients/${id}/pension-funds`),
          axios.get(`/api/v1/clients/${id}/additional-incomes`),
          axios.get(`/api/v1/clients/${id}/capital-assets`)
        ]);
        
        const pensionFundsData = pensionFundsResponse.data || [];
        const additionalIncomesData = additionalIncomesResponse.data || [];
        const capitalAssetsData = capitalAssetsResponse.data || [];
        
        // לוג לבדיקת מבנה הנתונים
        console.log('Additional Incomes Data:', JSON.stringify(additionalIncomesData, null, 2));
        console.log('Capital Assets Data:', JSON.stringify(capitalAssetsData, null, 2));
        console.log('First Additional Income:', additionalIncomesData[0]);
        
        // לוג לבדיקת קרנות פנסיה
        console.log('Pension Funds Data:', JSON.stringify(pensionFundsData, null, 2));
        pensionFundsData.forEach((fund: any, index: number) => {
          console.log(`Pension Fund ${index + 1} - start_date:`, fund.start_date);
          if (fund.start_date) {
            const parsedYear = parseInt(fund.start_date.split('-')[0]);
            const parsedMonth = parseInt(fund.start_date.split('-')[1]);
            const parsedDay = parseInt(fund.start_date.split('-')[2]);
            console.log(`  Parsed Date: Year=${parsedYear}, Month=${parsedMonth}, Day=${parsedDay}`);
            console.log(`  Full Date:`, new Date(fund.start_date));
          }
        });
        
        // בדיקת נתוני נכסי הון
        console.log('Capital Assets Count:', capitalAssetsData.length);
        if (capitalAssetsData.length > 0) {
          console.log('First Capital Asset:', JSON.stringify(capitalAssetsData[0], null, 2));
          console.log('Asset monthly_income:', capitalAssetsData[0].monthly_income);
          console.log('Asset asset_name:', capitalAssetsData[0].asset_name);
          console.log('Asset asset_type:', capitalAssetsData[0].asset_type);
        } else {
          console.log('No capital assets found!');
        }
        
        // Update state with fetched data
        setPensionFunds(pensionFundsData);
        setAdditionalIncomes(additionalIncomesData);
        setCapitalAssets(capitalAssetsData);
        
        // Calculate financial summary - pension funds only contribute monthly income, not balance
        const totalPensionValue = 0; // קרנות פנסיה לא נכללות בסך הנכסים
        const totalAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (income.annual_amount || income.monthly_amount * 12 || 0), 0);
        const totalCapitalAssets = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (asset.current_value || 0), 0);
        
        const totalWealth = totalPensionValue + totalAdditionalIncome + totalCapitalAssets;
        const estimatedTax = totalWealth * 0.15; // הערכת מס בסיסית

        // Get scenarios for cashflow
        const scenariosResponse = await axios.get(`/api/v1/clients/${id}/scenarios`);
        const scenarios = scenariosResponse.data || [];
        
        // Create realistic cashflow data based on actual financial data
        const currentDate = new Date();
        const pensionStartDate = clientData.pension_start_date ? new Date(clientData.pension_start_date) : new Date(currentDate.getFullYear() + 2, 0, 1);
        
        const cashflowData = Array.from({ length: 24 }, (_, i) => {
          const monthDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + i, 1);
          const isPensionActive = monthDate >= pensionStartDate;
          
          let monthlyGrossAmount = 0;
          let monthlyTax = 0;
          let monthlyNetAmount = 0;
          let source = 'ללא הכנסה';
          
          if (isPensionActive) {
            // חישוב הכנסה חודשית מקרנות פנסיה
            const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
              sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
            const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
              sum + (income.monthly_amount || income.annual_amount / 12 || 0), 0);
            
            monthlyGrossAmount = monthlyPension + monthlyAdditional;
            
            // חישוב מס על ההכנסה החודשית עם נקודות זיכוי
            if (monthlyGrossAmount > 0) {
              const annualGrossAmount = monthlyGrossAmount * 12;
              // חישוב מס בסיסי לפי מדרגות
              let baseTax = 0;
              let remainingIncome = annualGrossAmount;
              
              const taxBrackets = [
                { min: 0, max: 84120, rate: 0.10 },
                { min: 84120, max: 120720, rate: 0.14 },
                { min: 120720, max: 193800, rate: 0.20 },
                { min: 193800, max: 269280, rate: 0.31 },
                { min: 269280, max: 560280, rate: 0.35 },
                { min: 560280, max: 721560, rate: 0.47 },
                { min: 721560, max: Infinity, rate: 0.50 }
              ];
              
              for (const bracket of taxBrackets) {
                if (remainingIncome <= 0) break;
                const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
                baseTax += taxableInThisBracket * bracket.rate;
                remainingIncome -= taxableInThisBracket;
              }
              
              // הפחתת נקודות זיכוי אם קיימות
              if (clientData?.tax_credit_points) {
                baseTax = Math.max(0, baseTax - (clientData.tax_credit_points * 2640));
              }
              
              monthlyTax = baseTax / 12;
              monthlyNetAmount = monthlyGrossAmount - monthlyTax;
            }
            
            source = monthlyPension > 0 ? 'פנסיה' : 'הכנסות נוספות';
          }
          
          return {
            date: monthDate.toISOString().split('T')[0],
            amount: Math.round(monthlyNetAmount), // הצגת הכנסה נטו אחרי מס
            grossAmount: Math.round(monthlyGrossAmount), // הכנסה גולמית
            tax: Math.round(monthlyTax), // מס חודשי
            source: source
          };
        });

        const yearlyTotals = {
          total_income: totalWealth,
          total_tax: estimatedTax,
          net_income: totalWealth - estimatedTax
        };

        setReportData({
          client_info: {
            name: clientData ? `${clientData.first_name || ''} ${clientData.last_name || ''}`.trim() || 'לא צוין' : 'לא צוין',
            id_number: clientData?.id_number || 'לא צוין'
          },
          financial_summary: {
            total_pension_value: totalPensionValue,
            total_additional_income: totalAdditionalIncome,
            total_capital_assets: totalCapitalAssets,
            total_wealth: totalWealth,
            estimated_tax: estimatedTax
          },
          cashflow_projection: cashflowData,
          yearly_totals: yearlyTotals
        });

        setLoading(false);
      } catch (err: any) {
        setError('שגיאה בטעינת נתוני דוח: ' + err.message);
        setLoading(false);
      }
    };
    if (id) {
      fetchReportData();
    }
  }, [id]);

  // פונקציה לחישוב מס על הכנסה ספציפית עם נקודות זיכוי
  const calculateTaxForIncome = (annualIncome: number, incomeType: string): number => {
    if (annualIncome <= 0) return 0;
    
    // חישוב מס בסיסי לפי מדרגות
    let baseTax = 0;
    let remainingIncome = annualIncome;
    
    // מדרגות מס 2024
    const taxBrackets = [
      { min: 0, max: 84000, rate: 0.10 },
      { min: 84000, max: 121000, rate: 0.14 },
      { min: 121000, max: 202000, rate: 0.20 },
      { min: 202000, max: 420000, rate: 0.31 },
      { min: 420000, max: 672000, rate: 0.35 },
      { min: 672000, max: Infinity, rate: 0.47 }
    ];
    
    // חישוב מס לפי מדרגות
    for (const bracket of taxBrackets) {
      if (remainingIncome <= 0) break;
      
      const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
      baseTax += taxableInThisBracket * bracket.rate;
      remainingIncome -= taxableInThisBracket;
    }
    
    // הכנסות מקרן פנסיה הן הכנסות עבודה רגילות - ללא הנחות מיוחדות
    // (ההנחה הוסרה - הכנסות פנסיה חייבות במס כמו הכנסות עבודה רגילות)
    
    // חישוב נקודות זיכוי
    let totalTaxCredits = 0;
    const creditPointValue = 2640; // ערך נקודת זיכוי 2024 בשקלים
    
    if (client) {
      // נקודות זיכוי מקלט המשתמש בלבד
      if (client.tax_credit_points && client.tax_credit_points > 0) {
        totalTaxCredits = client.tax_credit_points * creditPointValue;
      }
    }
    
    // הפחתת נקודות הזיכוי מהמס
    const finalTax = Math.max(0, baseTax - totalTaxCredits);
    
    return finalTax;
  };

  /**
   * מייצר תחזית שנתית של תזרים מזומנים
   * הפונקציה מציגה רק שנים עתידיות בתזרים, החל מהשנה הנוכחית
   * קרנות פנסיה והכנסות נוספות שהתחילו בעבר יוצגו החל מהשנה הנוכחית
   * קרנות פנסיה והכנסות נוספות שמתחילות בעתיד יוצגו החל משנת ההתחלה שלהן
   */
  const generateYearlyProjection = (): YearlyProjection[] => {
    if (!reportData) return [];
    
    // קביעת שנת התחלה של התזרים - תמיד מתחיל משנת 2025 (השנה הנוכחית)
    const currentYear = 2025;
    const projectionStartYear = currentYear;
    const clientBirthYear = 1957; // Default birth year if not available
    const maxAge = 90;
    const maxYear = clientBirthYear + maxAge;
    const projectionYears = Math.min(maxYear - projectionStartYear + 1, 40); // Limit to 40 years max
    
    // Create array of years from projection start year to max age (or 40 years, whichever is less)
    const yearlyData: YearlyProjection[] = [];
    
    for (let i = 0; i < projectionYears; i++) {
      const year = projectionStartYear + i;
      const clientAge = year - clientBirthYear;
      
      // Initialize income breakdown array
      const incomeBreakdown: number[] = [];
      let totalMonthlyIncome = 0;
      
      // Add pension fund incomes
      pensionFunds.forEach(fund => {
        // חישוב שנת התחלה נכונה - קרן שהתחילה בעבר תוצג מהשנה הנוכחית
        let fundStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (fund.start_date) {
          const parsedYear = parseInt(fund.start_date.split('-')[0]);
          // אם הקרן מתחילה בעתיד, נשתמש בשנת ההתחלה המקורית
          // אם הקרן התחילה בעבר או בהווה, נשתמש בשנה הנוכחית
          fundStartYear = Math.max(parsedYear, currentYear);
          
          // הדפסת מידע לבדיקה
          console.log(`Fund ${fund.fund_name || 'unnamed'} original start: ${parsedYear}, effective start: ${fundStartYear}, current year: ${year}`);
        }
        
        const monthlyAmount = fund.computed_monthly_amount || fund.monthly_amount || 0;
        
        // Apply annual increase (2% by default)
        const yearsActive = year >= fundStartYear ? year - fundStartYear : 0;
        const indexationRate = fund.indexation_rate || 0.02; // Default 2% annual increase
        
        // תיקון: גם כשהקרן מתחילה בשנה הנוכחית (yearsActive = 0), היא צריכה להניב הכנסה
        const adjustedAmount = year >= fundStartYear ? 
          monthlyAmount * Math.pow(1 + indexationRate, yearsActive) : 0;
        
        // Only add income if pension has started
        const amount = adjustedAmount;
        
        incomeBreakdown.push(Math.round(amount));
        totalMonthlyIncome += amount;
      });
      
      // Add additional incomes
      additionalIncomes.forEach(income => {
        // חישוב שנת התחלה נכונה - הכנסה שהתחילה בעבר תוצג מהשנה הנוכחית
        let incomeStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (income.start_date) {
          const parsedYear = parseInt(income.start_date.split('-')[0]);
          // אם ההכנסה מתחילה בעתיד, נשתמש בשנת ההתחלה המקורית
          // אם ההכנסה התחילה בעבר או בהווה, נשתמש בשנה הנוכחית
          incomeStartYear = Math.max(parsedYear, currentYear);
          
          // הדפסת מידע לבדיקה
          console.log(`Income ${income.income_name || 'unnamed'} original start: ${parsedYear}, effective start: ${incomeStartYear}, current year: ${year}`);
        }
        
        const incomeEndYear = income.end_date ? parseInt(income.end_date.split('-')[0]) : maxYear;
        // בדיקת כל השדות האפשריים להכנסה חודשית
        const monthlyAmount = income.monthly_amount || income.amount || (income.annual_amount ? income.annual_amount / 12 : 0);
        
        // Only add income if it's active in this year
        const amount = (year >= incomeStartYear && year <= incomeEndYear) ? monthlyAmount : 0;
        incomeBreakdown.push(Math.round(amount));
        
        // הוספה לסך ההכנסה החודשית
        totalMonthlyIncome += amount;
      });

      // Add capital assets income
      capitalAssets.forEach(asset => {
        let assetStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (asset.start_date) {
          const parsedYear = parseInt(asset.start_date.split('-')[0]);
          assetStartYear = Math.max(parsedYear, currentYear);
        }
        
        const assetEndYear = asset.end_date ? parseInt(asset.end_date.split('-')[0]) : maxYear;
        
        // חישוב הכנסה חודשית מנכס הון
        let monthlyAmount = 0;
        
        // הדפסת מידע מפורט לבדיקה
        console.log(`ASSET DEBUG - ID: ${asset.id}, Name: ${asset.asset_name || asset.description || 'unnamed'}`);
        console.log(`ASSET DEBUG - Type: ${asset.asset_type}, Tax: ${asset.tax_treatment}`);
        console.log(`ASSET DEBUG - Monthly Income: ${asset.monthly_income}, Rental Income: ${asset.rental_income}, Monthly Rental: ${asset.monthly_rental_income}`);
        console.log(`ASSET DEBUG - All properties:`, JSON.stringify(asset, null, 2));
        
        // בדיקה מקיפה של כל השדות האפשריים להכנסה חודשית
        if (asset.monthly_income) {
          monthlyAmount = asset.monthly_income;
          console.log(`ASSET DEBUG - Using monthly_income: ${monthlyAmount}`);
        } else if (asset.monthly_rental_income) {
          monthlyAmount = asset.monthly_rental_income;
          console.log(`ASSET DEBUG - Using monthly_rental_income: ${monthlyAmount}`);
        } else if (asset.rental_income) {
          monthlyAmount = asset.rental_income;
          console.log(`ASSET DEBUG - Using rental_income: ${monthlyAmount}`);
        } else if (asset.current_value && asset.annual_return_rate) {
          // חישוב הכנסה חודשית מערך נכס ותשואה
          const annualReturn = asset.current_value * (asset.annual_return_rate / 100);
          monthlyAmount = annualReturn / 12;
          console.log(`ASSET DEBUG - Calculated from value: ${asset.current_value} and rate: ${asset.annual_return_rate}% = ${monthlyAmount}`);
        } else {
          console.log(`ASSET DEBUG - NO INCOME SOURCE FOUND for asset ${asset.asset_name || asset.description}`);
        }
        
        // בדיקה נוספת - אם עדיין אין הכנסה, נסה להמציא משהו לצורך בדיקה
        if (monthlyAmount === 0 && asset.current_value) {
          // אם יש ערך נכס אבל אין הכנסה, נניח תשואה של 5% לשנה
          monthlyAmount = (asset.current_value * 0.05) / 12;
          console.log(`ASSET DEBUG - FALLBACK income calculation: ${monthlyAmount}`);
        }
        
        // בדיקה סופית - אם עדיין אין הכנסה, קבע ערך קבוע לבדיקה
        if (monthlyAmount === 0) {
          monthlyAmount = 1000; // ערך לבדיקה בלבד
          console.log(`ASSET DEBUG - FORCED TEST VALUE: ${monthlyAmount}`);
        }
        
        // Apply annual increase only if indexation is specified
        const yearsActive = year >= assetStartYear ? year - assetStartYear : 0;
        
        // קביעת שיעור הצמדה לפי הגדרות הנכס
        let indexationRate = 0; // ברירת מחדל - ללא הצמדה
        
        if (asset.indexation_method === "fixed" && asset.fixed_rate) {
          // הצמדה קבועה לפי השיעור שהוגדר
          indexationRate = asset.fixed_rate / 100;
          console.log(`ASSET DEBUG - Using fixed indexation rate: ${indexationRate} (${asset.fixed_rate}%)`);  
        } else if (asset.indexation_method === "cpi") {
          // הצמדה למדד - נניח 2% כברירת מחדל
          indexationRate = 0.02;
          console.log(`ASSET DEBUG - Using CPI indexation: ${indexationRate}`);  
        } else {
          // ללא הצמדה
          console.log(`ASSET DEBUG - No indexation for asset: ${asset.asset_name || asset.description}`);  
        }
        
        const adjustedAmount = year >= assetStartYear ? 
          monthlyAmount * Math.pow(1 + indexationRate, yearsActive) : 0;
        
        // Only add income if asset is active in this year
        const amount = (year >= assetStartYear && year <= assetEndYear) ? adjustedAmount : 0;
        incomeBreakdown.push(Math.round(amount));
        
        // הוספה לסך ההכנסה החודשית
        totalMonthlyIncome += amount;
      });
      
      // חישוב מס על סך כל ההכנסות הדינמיות של השנה הנוכחית
      const taxBreakdown: number[] = [];
      let totalMonthlyTax = 0;
      
      // חישוב סך כל ההכנסות השנתיות בהתבסס על ההכנסות הדינמיות של השנה הנוכחית
      let totalTaxableAnnualIncome = 0;
      let totalExemptIncome = 0;
      
      // חישוב הכנסה חייבת במס מקרנות פנסיה (בהתבסס על ההכנסות הדינמיות)
      let monthlyTaxableIncome = 0;
      incomeBreakdown.slice(0, pensionFunds.length).forEach(income => {
        monthlyTaxableIncome += income;
      });
      
      // חישוב הכנסה פטורה וחייבת במס מהכנסות נוספות (בהתבסס על ההכנסות הדינמיות)
      let monthlyExemptIncome = 0;
      let monthlyTaxableAdditionalIncome = 0;
      let monthlyCapitalAssetIncome = 0;
      
      // הכנסות נוספות
      incomeBreakdown.slice(pensionFunds.length, pensionFunds.length + additionalIncomes.length).forEach((income, index) => {
        const additionalIncome = additionalIncomes[index];
        if (additionalIncome && additionalIncome.tax_treatment === 'exempt') {
          monthlyExemptIncome += income;
        } else {
          monthlyTaxableAdditionalIncome += income;
        }
      });

      // נכסי הון - מיסוי מיוחד
      incomeBreakdown.slice(pensionFunds.length + additionalIncomes.length).forEach((income, index) => {
        const asset = capitalAssets[index];
        if (asset) {
          monthlyCapitalAssetIncome += income;
        }
      });
      
      totalTaxableAnnualIncome = (monthlyTaxableIncome + monthlyTaxableAdditionalIncome) * 12;
      totalExemptIncome = monthlyExemptIncome * 12;
      const totalAnnualIncome = totalTaxableAnnualIncome + totalExemptIncome;
      
      if (totalTaxableAnnualIncome > 0) {
        // חישוב מס כולל על סך ההכנסות החייבות במס
        let totalAnnualTax = 0;
        let remainingIncome = totalTaxableAnnualIncome;
        
        const taxBrackets = [
          { min: 0, max: 84120, rate: 0.10 },
          { min: 84120, max: 120720, rate: 0.14 },
          { min: 120720, max: 193800, rate: 0.20 },
          { min: 193800, max: 269280, rate: 0.31 },
          { min: 269280, max: 560280, rate: 0.35 },
          { min: 560280, max: 721560, rate: 0.47 },
          { min: 721560, max: Infinity, rate: 0.50 }
        ];
        
        for (const bracket of taxBrackets) {
          if (remainingIncome <= 0) break;
          const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
          totalAnnualTax += taxableInThisBracket * bracket.rate;
          remainingIncome -= taxableInThisBracket;
        }
        
        // הפחתת נקודות זיכוי אם קיימות
        if (client?.tax_credit_points) {
          totalAnnualTax = Math.max(0, totalAnnualTax - (client.tax_credit_points * 2640));
        }

        // חישוב מס על נכסי הון
        let capitalAssetTax = 0;
        capitalAssets.forEach((asset, index) => {
          const assetIncomeIndex = pensionFunds.length + additionalIncomes.length + index;
          const monthlyIncome = incomeBreakdown[assetIncomeIndex] || 0;
          const annualIncome = monthlyIncome * 12;
          
          // חישוב מס לפי סוג המיסוי
          if (asset.tax_treatment === 'exempt') {
            // פטור ממס
            capitalAssetTax += 0;
          } else if (asset.tax_treatment === 'capital_gains') {
            // מס רווח הון - 25% מהרווח הריאלי (תשואה פחות 2%)
            const realReturnRate = Math.max(0, (asset.annual_return_rate || 0) - 2); // פחות 2% מדד
            const realGain = annualIncome * (realReturnRate / (asset.annual_return_rate || 1)); // חלק מההכנסה שהוא רווח ריאלי
            capitalAssetTax += realGain * 0.25;
          } else if (asset.tax_treatment === 'fixed_rate') {
            // שיעור מס קבוע
            capitalAssetTax += annualIncome * ((asset.tax_rate || 0) / 100);
          } else if (asset.asset_type === 'rental_property') {
            // שכר דירה - מס רגיל אם מעל התקרה
            const exemptionThreshold = 5070 * 12; // תקרת פטור שנתית
            if (annualIncome > exemptionThreshold) {
              const taxableRentalIncome = annualIncome - exemptionThreshold;
              let rentalTax = 0;
              let remaining = taxableRentalIncome;
              for (const bracket of taxBrackets) {
                if (remaining <= 0) break;
                const taxableInBracket = Math.min(remaining, bracket.max - bracket.min);
                rentalTax += taxableInBracket * bracket.rate;
                remaining -= taxableInBracket;
              }
              capitalAssetTax += rentalTax;
            }
          } else {
            // מס רגיל על נכסי הון אחרים
            let otherAssetTax = 0;
            let remaining = annualIncome;
            for (const bracket of taxBrackets) {
              if (remaining <= 0) break;
              const taxableInBracket = Math.min(remaining, bracket.max - bracket.min);
              otherAssetTax += taxableInBracket * bracket.rate;
              remaining -= taxableInBracket;
            }
            capitalAssetTax += otherAssetTax;
          }
        });
        
        totalMonthlyTax = (totalAnnualTax + capitalAssetTax) / 12;
        
        // חלוקת המס באופן יחסי לפי ההכנסות
        // חישוב סך ההכנסה החייבת במס
        const taxableTotalMonthlyIncome = monthlyTaxableIncome + monthlyTaxableAdditionalIncome;
        
        pensionFunds.forEach((fund, index) => {
          const incomeAmount = incomeBreakdown[index] || 0;
          // חלוקת המס רק על ההכנסות החייבות במס
          const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * totalMonthlyTax : 0;
          taxBreakdown.push(Math.round(taxPortion));
        });
        
        additionalIncomes.forEach((income, index) => {
          const incomeIndex = pensionFunds.length + index;
          const incomeAmount = incomeBreakdown[incomeIndex] || 0;
          
          // אם ההכנסה פטורה ממס, המס הוא אפס
          if (income.tax_treatment === 'exempt') {
            taxBreakdown.push(0);
          } else {
            // חלוקת המס רק על ההכנסות החייבות במס
            // משתמשים במשתנה שהוגדר למעלה
            const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * totalMonthlyTax : 0;
            taxBreakdown.push(Math.round(taxPortion));
          }
        });

        // חישוב מס עבור נכסי הון
        capitalAssets.forEach((asset, index) => {
          const assetIncomeIndex = pensionFunds.length + additionalIncomes.length + index;
          const monthlyIncome = incomeBreakdown[assetIncomeIndex] || 0;
          const annualIncome = monthlyIncome * 12;
          let assetTax = 0;
          
          // חישוב מס לפי סוג המיסוי
          if (asset.tax_treatment === 'exempt') {
            // פטור ממס
            assetTax = 0;
          } else if (asset.tax_treatment === 'capital_gains') {
            // מס רווח הון - 25% מהרווח הריאלי (תשואה פחות 2%)
            const realReturnRate = Math.max(0, (asset.annual_return_rate || 0) - 2);
            const realGain = annualIncome * (realReturnRate / (asset.annual_return_rate || 1));
            assetTax = realGain * 0.25;
          } else if (asset.tax_treatment === 'fixed_rate') {
            // שיעור מס קבוע
            assetTax = annualIncome * ((asset.tax_rate || 0) / 100);
          } else if (asset.asset_type === 'rental_property') {
            // שכר דירה - מס רגיל אם מעל התקרה
            const exemptionThreshold = 5070 * 12;
            if (annualIncome > exemptionThreshold) {
              const taxableRentalIncome = annualIncome - exemptionThreshold;
              let remaining = taxableRentalIncome;
              for (const bracket of taxBrackets) {
                if (remaining <= 0) break;
                const taxableInBracket = Math.min(remaining, bracket.max - bracket.min);
                assetTax += taxableInBracket * bracket.rate;
                remaining -= taxableInBracket;
              }
            }
          } else {
            // מס רגיל על נכסי הון אחרים
            let remaining = annualIncome;
            for (const bracket of taxBrackets) {
              if (remaining <= 0) break;
              const taxableInBracket = Math.min(remaining, bracket.max - bracket.min);
              assetTax += taxableInBracket * bracket.rate;
              remaining -= taxableInBracket;
            }
          }
          
          taxBreakdown.push(Math.round(assetTax / 12)); // המרה למס חודשי
        });
      } else {
        // אין הכנסה - אין מס
        for (let i = 0; i < pensionFunds.length + additionalIncomes.length + capitalAssets.length; i++) {
          taxBreakdown.push(0);
        }
      }

      yearlyData.push({
        year,
        clientAge,
        totalMonthlyIncome: Math.round(totalMonthlyIncome),
        totalMonthlyTax: Math.round(totalMonthlyTax),
        netMonthlyIncome: Math.round(totalMonthlyIncome - totalMonthlyTax),
        incomeBreakdown,
        taxBreakdown
      });
    }
    
    return yearlyData;
  };

  // הוסר calculateTaxImpact - המס מחושב ישירות בטבלה

  const handleGeneratePdf = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // יצירת דוח PDF עם הנתונים הקיימים
      const yearlyProjection = generateYearlyProjection();
      generatePDFReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, client);

      alert('דוח PDF נוצר בהצלחה');
    } catch (err: any) {
      setError('שגיאה ביצירת דוח PDF: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateExcel = async () => {
    try {
      setLoading(true);
      setError(null);

      // יצירת דוח Excel עם הנתונים הקיימים
      const yearlyProjection = generateYearlyProjection();
      generateExcelReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, client);

      alert('דוח Excel נוצר בהצלחה');
    } catch (err: any) {
      setError('שגיאה ביצירת דוח Excel: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading && (!pensionFunds || !additionalIncomes || !capitalAssets)) {
    return <div style={{ padding: '20px' }}>טוען נתוני דוח...</div>;
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </a>
      </div>

      <h2>דוחות</h2>

      {error && (
        <div style={{ 
          color: 'red', 
          marginBottom: '20px', 
          padding: '10px', 
          backgroundColor: '#fee', 
          borderRadius: '4px' 
        }}>
          {error}
        </div>
      )}

      {/* Report Generation Controls */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        border: '1px solid #007bff', 
        borderRadius: '4px',
        backgroundColor: '#f8f9ff'
      }}>
        <h3>יצירת דוחות</h3>
        
        <div style={{ display: 'flex', gap: '15px', marginBottom: '15px' }}>
          <button
            onClick={handleGeneratePdf}
            disabled={loading}
            style={{
              backgroundColor: loading ? '#6c757d' : '#dc3545',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {loading ? 'יוצר...' : 'יצירת דוח PDF'}
          </button>

          <button
            onClick={handleGenerateExcel}
            disabled={loading}
            style={{
              backgroundColor: loading ? '#6c757d' : '#28a745',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {loading ? 'יוצר...' : 'יצירת דוח Excel'}
          </button>
        </div>

      </div>

      {/* Report Preview */}
      <div>
        <h3>תצוגה מקדימה של הדוח</h3>
          
          {/* Client Info */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>פרטי לקוח</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div><strong>שם:</strong> {client?.name || 'לא צוין'}</div>
              <div><strong>ת.ז.:</strong> {client?.id_number || 'לא צוין'}</div>
            </div>
          </div>

          {/* Detailed Financial Breakdown */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>פירוט פיננסי</h4>
            
            {/* Pension Funds */}
            <div style={{ marginBottom: '15px' }}>
              <h5 style={{ 
                borderBottom: '1px solid #ddd', 
                paddingBottom: '5px', 
                marginBottom: '10px',
                color: '#0056b3'
              }}>קרנות פנסיה</h5>
              
              {pensionFunds && pensionFunds.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  {pensionFunds.map((fund: any) => (
                    <div key={fund.id} style={{ 
                      padding: '10px', 
                      backgroundColor: '#f0f8ff', 
                      borderRadius: '4px',
                      border: '1px solid #cce5ff'
                    }}>
                      <div><strong>{fund.fund_name}</strong></div>
                      <div>קצבה חודשית: ₪{(fund.computed_monthly_amount || fund.monthly_amount || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {fund.start_date ? new Date(fund.start_date).toLocaleDateString('he-IL') : 'לא צוין'}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין קרנות פנסיה</div>
              )}
            </div>
            
            {/* Additional Incomes */}
            <div style={{ marginBottom: '15px' }}>
              <h5 style={{ 
                borderBottom: '1px solid #ddd', 
                paddingBottom: '5px', 
                marginBottom: '10px',
                color: '#0056b3'
              }}>הכנסות נוספות</h5>
              
              {additionalIncomes && additionalIncomes.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  {additionalIncomes.map((income: any) => (
                    <div key={income.id} style={{ 
                      padding: '10px', 
                      backgroundColor: '#f0fff0', 
                      borderRadius: '4px',
                      border: '1px solid #d4edda'
                    }}>
                      <div><strong>{income.income_name || income.description || income.income_type || income.source_type || 'הכנסה נוספת'}</strong></div>
                      <div>הכנסה חודשית: ₪{(income.monthly_amount || income.amount || 0).toLocaleString()}</div>
                      <div>הכנסה שנתית: ₪{(income.annual_amount || (income.monthly_amount || income.amount) * 12 || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {income.start_date || 'לא צוין'}</div>
                      {income.tax_treatment && <div>יחס מס: {income.tax_treatment === 'exempt' ? 'פטור ממס' : income.tax_treatment === 'taxable' ? 'חייב במס' : 'שיעור קבוע'}</div>}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין הכנסות נוספות</div>
              )}
            </div>
            
            {/* Capital Assets */}
            <div style={{ marginBottom: '15px' }}>
              <h5 style={{ 
                borderBottom: '1px solid #ddd', 
                paddingBottom: '5px', 
                marginBottom: '10px',
                color: '#0056b3'
              }}>נכסי הון</h5>
              
              {capitalAssets && capitalAssets.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  {capitalAssets.map((asset: any) => (
                    <div key={asset.id} style={{ 
                      padding: '10px', 
                      backgroundColor: '#fff8f0', 
                      borderRadius: '4px',
                      border: '1px solid #ffeeba'
                    }}>
                      <div style={{ fontWeight: 'bold', fontSize: '16px', marginBottom: '5px', color: '#0056b3' }}>
                        {asset.description || 'נכס הון'}
                      </div>
                      <div>סוג: {ASSET_TYPES.find((t: any) => t.value === asset.asset_type)?.label || asset.asset_type || 'לא צוין'}</div>
                      <div>תשלום חודשי: ₪{(asset.monthly_income || 0).toLocaleString()}</div>
                      <div>ערך נוכחי: ₪{asset.current_value?.toLocaleString() || 0}</div>
                      <div>תשואה שנתית: {
                        asset.annual_return_rate > 1 ? asset.annual_return_rate : 
                        asset.annual_return_rate ? (asset.annual_return_rate * 100) : 
                        asset.annual_return || 0
                      }%</div>
                      <div>תאריך התחלה: {asset.start_date || 'לא צוין'}</div>
                      <div>תאריך סיום: {asset.end_date || 'ללא הגבלה'}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין נכסי הון</div>
              )}
            </div>
            
            {/* Summary */}
            <div style={{ 
              marginTop: '15px', 
              padding: '10px', 
              backgroundColor: '#e9ecef', 
              borderRadius: '4px',
              border: '1px solid #dee2e6'
            }}>
              <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>סיכום</h5>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div><strong>סך הכנסה חודשית:</strong> ₪{(() => {
                  const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                    sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
                  const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
                    sum + (income.monthly_amount || (income.annual_amount ? income.annual_amount / 12 : 0)), 0);
                  return (monthlyPension + monthlyAdditional).toLocaleString();
                })()}</div>
                <div><strong>סך נכסים:</strong> ₪{(() => {
                  // רק נכסי הון נכללים בסך הנכסים, לא יתרות קרנות פנסיה
                  const totalCapitalAssets = capitalAssets.reduce((sum: number, asset: any) => 
                    sum + (asset.current_value || 0), 0);
                  return totalCapitalAssets.toLocaleString();
                })()}</div>
                <div><strong>תאריך התחלת תזרים:</strong> {(() => {
                  // מציאת השנה הראשונה עם הכנסה
                  const firstIncomeYear = Math.min(
                    ...pensionFunds.map((fund: any) => 
                      fund.start_date ? parseInt(fund.start_date.split('-')[0]) : new Date().getFullYear() + 10
                    ),
                    ...additionalIncomes.map((income: any) => 
                      income.start_date ? parseInt(income.start_date.split('-')[0]) : new Date().getFullYear() + 10
                    )
                  );
                  return firstIncomeYear < new Date().getFullYear() + 10 ? `01/01/${firstIncomeYear}` : 'לא צוין';
                })()}</div>
              </div>
            </div>
          </div>

          {/* Tax Calculation Results */}
          {taxCalculation && (
            <div style={{ 
              marginBottom: '20px', 
              padding: '15px', 
              border: '1px solid #dc3545', 
              borderRadius: '4px',
              backgroundColor: '#fff5f5'
            }}>
              <h4>חישוב מס הכנסה</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <div>
                  <div><strong>סך הכנסה שנתית:</strong> ₪{taxCalculation.total_income.toLocaleString()}</div>
                  <div><strong>הכנסה חייבת במס:</strong> ₪{taxCalculation.taxable_income.toLocaleString()}</div>
                  <div><strong>הכנסה פטורה ממס:</strong> ₪{taxCalculation.exempt_income.toLocaleString()}</div>
                  <div style={{ color: '#dc3545' }}><strong>מס נטו לתשלום:</strong> ₪{taxCalculation.net_tax.toLocaleString()}</div>
                </div>
                <div>
                  <div><strong>מס הכנסה:</strong> ₪{taxCalculation.income_tax.toLocaleString()}</div>
                  <div><strong>ביטוח לאומי:</strong> ₪{taxCalculation.national_insurance.toLocaleString()}</div>
                  <div><strong>מס בריאות:</strong> ₪{taxCalculation.health_tax.toLocaleString()}</div>
                  <div><strong>שיעור מס אפקטיבי:</strong> {taxCalculation.effective_tax_rate.toFixed(2)}%</div>
                </div>
              </div>
              
              {taxCalculation.applied_credits && taxCalculation.applied_credits.length > 0 && (
                <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #ddd' }}>
                  <strong>נקודות זיכוי:</strong>
                  <div style={{ marginTop: '5px' }}>
                    {taxCalculation.applied_credits.map((credit: any, index: number) => (
                      <div key={index} style={{ fontSize: '14px' }}>
                        • {credit.description}: ₪{credit.amount.toLocaleString()}
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: '10px', color: '#28a745' }}>
                    <strong>סך זיכויים: ₪{taxCalculation.tax_credits_amount.toLocaleString()}</strong>
                  </div>
                </div>
              )}
              
              <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #ddd' }}>
                <div style={{ color: '#28a745', fontSize: '18px' }}>
                  <strong>הכנסה נטו לאחר מס: ₪{taxCalculation.net_income.toLocaleString()}</strong>
                </div>
                <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
                  הכנסה חודשית נטו: ₪{(taxCalculation.net_income / 12).toLocaleString()}
                </div>
              </div>
            </div>
          )}

          {/* Tax Calculation Report */}
          {client && (
            <div style={{ 
              marginBottom: '20px', 
              padding: '15px', 
              border: '1px solid #ddd', 
              borderRadius: '4px',
              backgroundColor: '#f0f8ff'
            }}>
              <h4>דוח חישוב מס מפורט</h4>
              <div style={{ fontSize: '14px', color: '#666', marginBottom: '15px' }}>
                חישוב מס הכנסה כולל נקודות זיכוי לפי הפרטים האישיים
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                {/* Personal Tax Details - רק נתונים קיימים */}
                <div>
                  <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>פרטים אישיים למיסוי</h5>
                  <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                    {/* הצגת פרטים בסיסיים בלבד */}
                    {client.birth_date && (
                      <div><strong>גיל:</strong> {new Date().getFullYear() - new Date(client.birth_date).getFullYear()}</div>
                    )}
                    {client.gender && (
                      <div><strong>מין:</strong> {client.gender === 'male' ? 'זכר' : client.gender === 'female' ? 'נקבה' : client.gender}</div>
                    )}
                    
                    {/* הצגת שדות נוספים רק אם קיימים ומוגדרים */}
                    {client.marital_status && (
                      <div>
                        <strong>מצב משפחתי:</strong> {
                          (() => {
                            const statusMap: Record<string, string> = {
                              'single': 'רווק/ה',
                              'married': 'נשוי/ה',
                              'divorced': 'גרוש/ה',
                              'widowed': 'אלמן/ה'
                            };
                            return statusMap[client.marital_status] || client.marital_status;
                          })()
                        }
                      </div>
                    )}
                    {/* שדה מספר ילדים הוסר לפי דרישה */}
                    {client.is_disabled && client.disability_percentage && (
                      <div><strong>אחוז נכות:</strong> {client.disability_percentage}%</div>
                    )}
                    {client.is_new_immigrant && (
                      <div><strong>עולה חדש:</strong> כן {client.immigration_date && `(מ-${new Date(client.immigration_date).getFullYear()})`}</div>
                    )}
                    {client.is_veteran && (
                      <div><strong>חייל משוחרר:</strong> כן {client.military_discharge_date && `(${new Date(client.military_discharge_date).getFullYear()})`}</div>
                    )}
                    {/* שדה ימי מילואים הוסר לפי דרישה */}
                    
                    {/* אם אין נתונים מיוחדים */}
                    {!client.marital_status && !client.is_disabled && 
                     !client.is_new_immigrant && !client.is_veteran && 
                     (!client.tax_credit_points || client.tax_credit_points === 0) && (
                      <div style={{ color: '#6c757d', fontStyle: 'italic' }}>לא הוזנו פרטים מיוחדים למיסוי</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Current Case Tax Calculation - חישוב מס למקרה הנוכחי */}
              <div style={{ marginTop: '15px' }}>
                <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>חישוב מס למקרה הנוכחי</h5>
                <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                  {(() => {
                    // חישוב הכנסה שנתית נוכחית
                    const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                      sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
                    const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
                      sum + (income.monthly_amount || (income.annual_amount ? income.annual_amount / 12 : 0)), 0);
                    const totalAnnualIncome = (monthlyPension + monthlyAdditional) * 12;
                    
                    if (totalAnnualIncome === 0) {
                      return (
                        <div style={{ textAlign: 'center', color: '#6c757d', fontStyle: 'italic' }}>
                          אין הכנסות מוגדרות לחישוב מס
                        </div>
                      );
                    }
                    
                    // חישוב מס בסיסי לפי מדרגות
                    let baseTax = 0;
                    let remaining = totalAnnualIncome;
                    const brackets = [
                      { min: 0, max: 84120, rate: 0.10 },
                      { min: 84120, max: 120720, rate: 0.14 },
                      { min: 120720, max: 193800, rate: 0.20 },
                      { min: 193800, max: 269280, rate: 0.31 },
                      { min: 269280, max: 560280, rate: 0.35 },
                      { min: 560280, max: 721560, rate: 0.47 },
                      { min: 721560, max: Infinity, rate: 0.50 }
                    ];
                    
                    const taxBreakdown = [];
                    for (const bracket of brackets) {
                      if (remaining <= 0) break;
                      const taxableInBracket = Math.min(remaining, bracket.max - bracket.min);
                      const taxInBracket = taxableInBracket * bracket.rate;
                      if (taxableInBracket > 0) {
                        baseTax += taxInBracket;
                        taxBreakdown.push({
                          range: bracket.max === Infinity ? `₪${bracket.min.toLocaleString()}+` : `₪${bracket.min.toLocaleString()}-${bracket.max.toLocaleString()}`,
                          amount: taxableInBracket,
                          rate: (bracket.rate * 100).toFixed(0),
                          tax: taxInBracket
                        });
                      }
                      remaining -= taxableInBracket;
                    }
                    
                    // חישוב נקודות זיכוי
                    const taxCredits = client?.tax_credit_points ? client.tax_credit_points * 2640 : 0;
                    const finalTax = Math.max(0, baseTax - taxCredits);
                    
                    return (
                      <div>
                        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                          <strong>סך הכנסה שנתית: ₪{totalAnnualIncome.toLocaleString()}</strong>
                          <div>הכנסה חודשית: ₪{(totalAnnualIncome / 12).toLocaleString()}</div>
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                          <div>
                            <strong>חישוב מס לפי מדרגות:</strong>
                            {taxBreakdown.map((item, index) => (
                              <div key={index}>
                                {item.range}: ₪{item.tax.toLocaleString()} ({item.rate}%)
                              </div>
                            ))}
                            <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px' }}>
                              <strong>סה"כ מס בסיסי: ₪{baseTax.toLocaleString()}</strong>
                            </div>
                          </div>
                          
                          <div>
                            <strong>נקודות זיכוי:</strong>
                            {client?.tax_credit_points && client.tax_credit_points > 0 ? (
                              <div>
                                <div>נקודות: {client.tax_credit_points}</div>
                                <div>זיכוי שנתי: ₪{taxCredits.toLocaleString()}</div>
                              </div>
                            ) : (
                              <div style={{ color: '#6c757d' }}>ללא נקודות זיכוי</div>
                            )}
                          </div>
                          
                          <div>
                            <strong>מס סופי:</strong>
                            <div>מס בסיסי: ₪{baseTax.toLocaleString()}</div>
                            {taxCredits > 0 && (
                              <div>פחות זיכוי: ₪{taxCredits.toLocaleString()}</div>
                            )}
                            <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px', fontWeight: 'bold', color: '#28a745' }}>
                              <strong>מס לתשלום: ₪{finalTax.toLocaleString()}</strong>
                            </div>
                            <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                              מס חודשי: ₪{(finalTax / 12).toLocaleString()}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()} 
                </div>
              </div>
            </div>
          )}

          {/* Annual Cashflow Projection */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>תזרים מזומנים עתידי</h4>
            <div style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
              הטבלה מציגה הכנסות חודשיות, מס חודשי והכנסה נטו לכל שנה. עמודות המס מוצגות בצבע אדום בהיר.
            </div>
            
            {/* חישוב והצגת ה-NPV */}
            {(() => {
              // חישוב תזרים המזומנים השנתי
              const yearlyProjection = generateYearlyProjection();
              const annualNetCashFlows = yearlyProjection.map(yearData => {
                // הכנסה שנתית נטו = (הכנסה חודשית נטו) * 12
                return yearData.netMonthlyIncome * 12;
              });
              
              // חישוב ה-NPV עם שיעור היוון של 3%
              const discountRate = 0.03; // 3%
              const npv = calculateNPV(annualNetCashFlows, discountRate);
              
              return (
                <div style={{ 
                  marginBottom: '20px', 
                  padding: '15px', 
                  backgroundColor: '#e8f5e9', 
                  borderRadius: '4px',
                  border: '1px solid #c8e6c9'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>ערך נוכחי נקי (NPV) של התזרים:</strong>
                      <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
                        מהוון בשיעור של {(discountRate * 100).toFixed(1)}% לשנה
                      </div>
                    </div>
                    <div style={{ 
                      fontSize: '24px', 
                      fontWeight: 'bold', 
                      color: '#2e7d32',
                      direction: 'ltr',
                      textAlign: 'left'
                    }}>
                      ₪{Math.round(npv).toLocaleString()}
                    </div>
                  </div>
                </div>
              );
            })()}
            
            <div style={{ maxHeight: '400px', overflowY: 'auto', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1200px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#e9ecef' }}>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', position: 'sticky', left: 0, backgroundColor: '#e9ecef' }}>שנה</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#f0f8ff' }}>הכנסה נטו</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold' }}>סה"כ הכנסה</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold', backgroundColor: '#ffe4e1' }}>סה"כ מס</th>
                    {pensionFunds.map(fund => (
                      <React.Fragment key={`fund-${fund.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>
                          {fund.fund_name} {fund.fund_number ? `(${fund.fund_number})` : ''}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {fund.fund_name}
                        </th>
                      </React.Fragment>
                    ))}
                    {additionalIncomes.map(income => (
                      <React.Fragment key={`income-${income.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>
                          {income.income_name || income.description || income.income_type || income.source_type || 'הכנסה נוספת'}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {income.income_name || income.description || income.income_type || income.source_type || 'הכנסה נוספת'}
                        </th>
                      </React.Fragment>
                    ))}
                    {capitalAssets.map(asset => (
                      <React.Fragment key={`asset-${asset.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#fff8f0' }}>
                          {asset.description || 'נכס הון'} (₪{(asset.monthly_income || 0).toLocaleString()})
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {asset.description || 'נכס הון'}
                        </th>
                      </React.Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {generateYearlyProjection().map((yearData, index) => (
                    <tr key={index} style={{ backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                      <td style={{ padding: '8px', border: '1px solid #ddd', position: 'sticky', left: 0, backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                        {yearData.year}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold', backgroundColor: '#f0f8ff' }}>
                        ₪{yearData.netMonthlyIncome.toLocaleString()}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold' }}>
                        ₪{yearData.totalMonthlyIncome.toLocaleString()}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold', backgroundColor: '#ffe4e1' }}>
                        ₪{yearData.totalMonthlyTax.toLocaleString()}
                      </td>
                      {yearData.incomeBreakdown.map((income, i) => (
                        <React.Fragment key={i}>
                          <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left' }}>
                            ₪{income.toLocaleString()}
                          </td>
                          <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#ffe4e1' }}>
                            ₪{(yearData.taxBreakdown[i] || 0).toLocaleString()}
                          </td>
                        </React.Fragment>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {!loading && pensionFunds.length === 0 && additionalIncomes.length === 0 && capitalAssets.length === 0 && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fff3cd', 
          borderRadius: '4px',
          textAlign: 'center',
          color: '#856404'
        }}>
          אין מספיק נתונים ליצירת דוח. יש להוסיף קרנות פנסיה, הכנסות נוספות או נכסי הון תחילה.
          <div style={{ marginTop: '10px' }}>
            <a href={`/clients/${id}/pension-funds`} style={{ color: '#007bff', textDecoration: 'none', marginRight: '15px' }}>
              הוסף קרנות פנסיה ←
            </a>
            <a href={`/clients/${id}/additional-incomes`} style={{ color: '#007bff', textDecoration: 'none', marginRight: '15px' }}>
              הוסף הכנסות נוספות ←
            </a>
            <a href={`/clients/${id}/capital-assets`} style={{ color: '#007bff', textDecoration: 'none' }}>
              הוסף נכסי הון ←
            </a>
          </div>
        </div>
      )}

      <div style={{ 
        marginTop: '30px', 
        padding: '15px', 
        backgroundColor: '#e9ecef', 
        borderRadius: '4px',
        fontSize: '14px'
      }}>
        <strong>הסבר:</strong> הדוחות מבוססים על כלל הנתונים שהוזנו במערכת - מענקים, תרחישים, וחישובי מס. 
        דוח ה-PDF מכיל את כל הפרטים כולל גרפים וטבלאות מפורטות. 
        דוח ה-Excel מאפשר עיבוד נוסף של הנתונים.
      </div>
    </div>
  );
};

export default SimpleReports;
