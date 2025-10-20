import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import jsPDF from 'jspdf';
import * as XLSX from 'xlsx';
import { formatDateToDDMMYY } from '../utils/dateUtils';
import { getTaxBracketsLegacyFormat, calculateTaxByBrackets } from '../utils/taxBrackets';
import axios from 'axios';
import autoTable from 'jspdf-autotable';
import { 
  ASSET_TYPES_MAP, 
  PENSION_PRODUCT_TYPES, 
  generateCashflowOperationsDetails,
  calculateNPVComparison,
  generatePieChartData,
  drawPieChart
} from '../utils/reportGenerator';

// ניסיון להוסיף תמיכה בעברית
declare module 'jspdf' {
  interface jsPDF {
    addFileToVFS(filename: string, content: string): void;
    addFont(filename: string, fontName: string, fontStyle: string): void;
  }
}
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
  exemptPension?: number;
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
  
  // ניסיון לתמיכה בעברית - נשתמש בפונט שתומך טוב יותר
  try {
    // ננסה עם פונט שתומך בעברית
    doc.setFont('times', 'normal');
  } catch (e) {
    // אם לא עובד, נחזור לפונט בסיסי
    doc.setFont('helvetica');
  }
  
  // נוסיף הערה על בעיות encoding אפשריות
  const addHebrewNote = () => {
    doc.setFontSize(8);
    doc.setTextColor(100, 100, 100);
    doc.text('* אם הטקסט העברי לא מוצג נכון, אנא השתמש בדוח Excel', 20, 280);
    doc.setTextColor(0, 0, 0);
  };
  
  let yPosition = 20;
  
  // כותרת הדוח
  doc.setFontSize(20);
  doc.setTextColor(0, 51, 102);
  doc.text('דוח פנסיוני מקיף - תכנון פרישה', 105, yPosition, { align: 'center' });
  yPosition += 15;
  
  // תאריך יצירת הדוח
  doc.setFontSize(12);
  doc.setTextColor(0, 0, 0);
  const currentDate = new Date().toLocaleDateString('he-IL');
  doc.text(`תאריך יצירת הדוח: ${currentDate}`, 20, yPosition);
  yPosition += 10;
  
  // פרטי לקוח
  if (clientData) {
    doc.text(`שם הלקוח: ${clientData.first_name || ''} ${clientData.last_name || ''}`, 20, yPosition);
    yPosition += 8;
    if (clientData.birth_date) {
      doc.text(`תאריך לידה: ${clientData.birth_date}`, 20, yPosition);
      yPosition += 8;
    }
    if (clientData.id_number) {
      doc.text(`מספר זהות: ${clientData.id_number}`, 20, yPosition);
      yPosition += 8;
    }
  }
  yPosition += 10;
  
  // חישוב NPV
  const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
  const npv = calculateNPV(annualNetCashFlows, 0.03);
  
  // הצגת NPV
  doc.setFontSize(14);
  doc.setTextColor(0, 128, 0);
  doc.text(`ערך נוכחי נקי (NPV): ₪${Math.round(npv).toLocaleString()}`, 20, yPosition);
  doc.setTextColor(0, 0, 0);
  yPosition += 20;
  
  // טבלת תזרים מזומנים
  doc.setFontSize(14);
  doc.setTextColor(0, 51, 102);
  doc.text('תחזית תזרים מזומנים שנתי:', 20, yPosition);
  yPosition += 10;
  
  const tableData = yearlyProjection.slice(0, 20).map(year => [
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
    doc.setTextColor(0, 51, 102);
    doc.text('נכסי הון:', 20, yPosition);
    yPosition += 10;
    
    const capitalAssetsData = capitalAssets.map(asset => [
      asset.description || asset.asset_name || 'ללא תיאור',
      ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type || 'לא צוין',
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
  
  // פירוט קצבאות
  if (pensionFunds.length > 0) {
    doc.setFontSize(14);
    doc.setTextColor(0, 51, 102);
    doc.text('קצבאות:', 20, yPosition);
    yPosition += 10;
    
    const pensionData = pensionFunds.map(fund => [
      fund.fund_name || 'ללא שם',
      `₪${(fund.current_balance || 0).toLocaleString()}`,
      `₪${(fund.monthly_deposit || 0).toLocaleString()}`,
      `${((fund.annual_return_rate || 0) * 100).toFixed(1)}%`,
      `₪${(fund.pension_amount || fund.computed_monthly_amount || 0).toLocaleString()}`,
      (fund.retirement_age || 67).toString()
    ]);
    
    autoTable(doc, {
      head: [['שם הקרן', 'יתרה נוכחית', 'הפקדה חודשית', 'תשואה שנתית', 'קצבה חודשית', 'גיל פרישה']],
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
  
  // הוספת הכנסות נוספות אם קיימות
  if (additionalIncomes.length > 0) {
    yPosition = (doc as any).lastAutoTable?.finalY + 20 || yPosition + 20;
    
    doc.setFontSize(14);
    doc.setTextColor(0, 51, 102);
    doc.text('הכנסות נוספות:', 20, yPosition);
    yPosition += 10;
    
    const additionalIncomesData = additionalIncomes.map(income => [
      income.description || 'ללא תיאור',
      `₪${(income.monthly_amount || 0).toLocaleString()}`,
      income.tax_treatment === 'exempt' ? 'פטור ממס' : 'חייב במס',
      income.start_date || 'לא צוין',
      income.end_date || 'ללא הגבלה'
    ]);
    
    autoTable(doc, {
      head: [['תיאור', 'סכום חודשי', 'יחס למס', 'תאריך התחלה', 'תאריך סיום']],
      body: additionalIncomesData,
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
  
  // עמוד חדש לסיכום כספי
  doc.addPage();
  yPosition = 20;
  
  // סיכום כספי
  doc.setFontSize(16);
  doc.setTextColor(0, 51, 102);
  doc.text('סיכום כספי מקיף:', 20, yPosition);
  yPosition += 20;
  
  // חישוב סיכומים
  const totalPensionBalance = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0);
  const totalCapitalValue = capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0);
  const totalMonthlyPension = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0);
  const totalMonthlyAdditional = additionalIncomes.reduce((sum, income) => {
    const amount = parseFloat(income.amount) || 0;
    if (income.frequency === 'monthly') return sum + amount;
    if (income.frequency === 'quarterly') return sum + (amount / 3);
    if (income.frequency === 'annually') return sum + (amount / 12);
    return sum + amount;
  }, 0);
  const totalMonthlyCapital = capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.monthly_income) || 0), 0);
  
  doc.setFontSize(12);
  doc.setTextColor(0, 0, 0);
  
  // נכסים
  doc.text('נכסים:', 20, yPosition);
  yPosition += 10;
  doc.text(`• סך יתרות קצבאות: ₪${totalPensionBalance.toLocaleString()}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• סך ערך נכסי הון: ₪${totalCapitalValue.toLocaleString()}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• סך כל הנכסים: ₪${(totalPensionBalance + totalCapitalValue).toLocaleString()}`, 30, yPosition);
  yPosition += 15;
  
  // הכנסות חודשיות
  doc.text('הכנסות חודשיות צפויות:', 20, yPosition);
  yPosition += 10;
  doc.text(`• קצבאות פנסיה: ₪${totalMonthlyPension.toLocaleString()}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• הכנסות נוספות: ₪${totalMonthlyAdditional.toLocaleString()}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• הכנסות מנכסי הון: ₪${totalMonthlyCapital.toLocaleString()}`, 30, yPosition);
  yPosition += 8;
  doc.setTextColor(0, 128, 0);
  doc.text(`• סך הכנסה חודשית: ₪${(totalMonthlyPension + totalMonthlyAdditional + totalMonthlyCapital).toLocaleString()}`, 30, yPosition);
  doc.setTextColor(0, 0, 0);
  yPosition += 15;
  
  // ניתוח NPV
  doc.text('ניתוח ערך נוכחי נקי:', 20, yPosition);
  yPosition += 10;
  doc.text(`• NPV של התזרים: ₪${Math.round(npv).toLocaleString()}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• תקופת תחזית: ${yearlyProjection.length} שנים`, 30, yPosition);
  yPosition += 8;
  doc.text(`• שיעור היוון: 3%`, 30, yPosition);
  
  // הוספת הערה על העברית
  addHebrewNote();
  
  // שמירת הקובץ
  const fileName = `דוח_פנסיוני_${clientData?.first_name || 'לקוח'}_${formatDateToDDMMYY(new Date()).replace(/\//g, '_')}.pdf`;
  doc.save(fileName);
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
      ['תיאור', 'סוג נכס', 'הכנסה חודשית', 'ערך נוכחי', 'תשואה שנתית %', 'יחס למס', 'תאריך התחלה', 'תאריך סיום'],
      ...capitalAssets.map(asset => [
        asset.description || asset.asset_name || 'ללא תיאור',
        ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type || 'לא צוין',
        (asset.monthly_income || 0).toLocaleString(),
        (asset.current_value || 0).toLocaleString(),
        ((asset.annual_return_rate || 0) * 100).toFixed(1) + '%',
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
      ['שם הקרן', 'סוג קרן', 'יתרה נוכחית', 'הפקדה חודשית', 'תשואה שנתית %', 'קצבה חודשית', 'תאריך התחלה', 'גיל פרישה'],
      ...pensionFunds.map(fund => [
        fund.fund_name || 'ללא שם',
        fund.fund_type || 'לא צוין',
        (fund.current_balance || 0).toLocaleString(),
        (fund.monthly_deposit || 0).toLocaleString(),
        ((fund.annual_return_rate || 0) * 100).toFixed(1) + '%',
        (fund.pension_amount || fund.computed_monthly_amount || 0).toLocaleString(),
        fund.start_date || 'לא צוין',
        (fund.retirement_age || 67).toString()
      ])
    ];
    
    // הוספת סיכום קצבאות
    const totalBalance = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0);
    const totalMonthlyDeposit = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.monthly_deposit) || 0), 0);
    const totalPensionAmount = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0);
    
    pensionData.push(['', '', '', '', '', '', '', '']);
    pensionData.push(['סך יתרות:', '', totalBalance.toLocaleString(), '', '', '', '', '']);
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
    ['סך קצבאות:', pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0).toLocaleString(), '₪'],
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
    total_monthly_income: number;
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
  const location = useLocation();
  
  // פונקציות עזר לחישובי קצבה פטורה
  const getPensionCeiling = (year: number): number => {
    const ceilings: { [key: number]: number } = {
      2025: 9430, 2024: 9430, 2023: 9120, 2022: 8660,
      2021: 8460, 2020: 8510, 2019: 8480, 2018: 8380
    };
    return ceilings[year] || 9430;
  };
  
  const getExemptCapitalPercentage = (year: number): number => {
    const percentages: { [key: number]: number } = {
      2028: 0.67, 2027: 0.625, 2026: 0.575, 2025: 0.57,
      2024: 0.52, 2023: 0.52, 2022: 0.52, 2021: 0.52, 2020: 0.52,
      2019: 0.49, 2018: 0.49, 2017: 0.49, 2016: 0.49,
      2015: 0.435, 2014: 0.435, 2013: 0.435, 2012: 0.435
    };
    return percentages[year] || 0.67;
  };
  
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pensionFunds, setPensionFunds] = useState<any[]>([]);
  const [additionalIncomes, setAdditionalIncomes] = useState<any[]>([]);
  const [capitalAssets, setCapitalAssets] = useState<any[]>([]);
  const [taxCalculation, setTaxCalculation] = useState<any>(null);
  const [client, setClient] = useState<any>(null);
  const [fixationData, setFixationData] = useState<any>(null);

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

        // Get financial data - pension funds, additional incomes, capital assets, fixation data
        const [pensionFundsResponse, additionalIncomesResponse, capitalAssetsResponse, fixationResponse] = await Promise.all([
          axios.get(`/api/v1/clients/${id}/pension-funds`),
          axios.get(`/api/v1/clients/${id}/additional-incomes`),
          axios.get(`/api/v1/clients/${id}/capital-assets`),
          axios.get(`/api/v1/clients/${id}/fixation`).catch(() => ({ data: null })) // Optional: fixation may not exist
        ]);
        
        console.log('Additional incomes response:', additionalIncomesResponse.data);
        
        const pensionFundsData = pensionFundsResponse.data || [];
        const additionalIncomesData = additionalIncomesResponse.data || [];
        const capitalAssetsData = capitalAssetsResponse.data || [];
        const fixationDataResponse = fixationResponse?.data || null;
        
        // לוג לבדיקת מבנה הנתונים
        console.log('Additional Incomes Data:', JSON.stringify(additionalIncomesData, null, 2));
        console.log('Fixation Data:', fixationDataResponse);
        console.log('Capital Assets Data:', JSON.stringify(capitalAssetsData, null, 2));
        console.log('First Additional Income:', additionalIncomesData[0]);
        
        // לוג לבדיקת קצבאות
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
        setFixationData(fixationDataResponse);
        
        // Calculate financial summary - pension funds only contribute monthly income, not balance
        const totalPensionValue = 0; // קצבאות לא נכללות בסך הנכסים
        const totalAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (income.annual_amount || income.monthly_amount * 12 || 0), 0);
        
        // ✅ סך נכסים = סכום current_value של כל הנכסים
        const totalCapitalAssetsValue = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.current_value) || 0), 0);
        
        // ✅ סך הכנסות חד פעמיות = סכום כל התשלומים (monthly_income), לא current_value!
        const totalCapitalAssetsPayments = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.monthly_income) || 0), 0);
        
        // חישוב הכנסה חודשית מכל המקורות
        const monthlyPensionIncome = pensionFundsData.reduce((sum: number, fund: any) => 
          sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
        const monthlyAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (parseFloat(income.monthly_amount) || (income.annual_amount ? parseFloat(income.annual_amount) / 12 : 0)), 0);
        const monthlyCapitalIncome = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.monthly_income) || 0), 0);
        const totalMonthlyIncome = monthlyPensionIncome + monthlyAdditionalIncome + monthlyCapitalIncome;
        
        const totalWealth = totalPensionValue + totalAdditionalIncome + totalCapitalAssetsValue;
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
            // חישוב הכנסה חודשית מקצבאות - מופרדות לחייבות ופטורות
            const monthlyPensionTaxable = pensionFunds.reduce((sum: number, fund: any) => {
              // רק קצבאות חייבות במס
              if (fund.tax_treatment === 'exempt') return sum;
              return sum + (fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0);
            }, 0);
            
            const monthlyPensionExempt = pensionFunds.reduce((sum: number, fund: any) => {
              // רק קצבאות פטורות ממס
              if (fund.tax_treatment !== 'exempt') return sum;
              return sum + (fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0);
            }, 0);
            
            const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
              sum + (income.monthly_amount || income.annual_amount / 12 || 0), 0);
            
            const monthlyPension = monthlyPensionTaxable + monthlyPensionExempt;
            monthlyGrossAmount = monthlyPension + monthlyAdditional;
            
            // חישוב מס על ההכנסה החודשית עם קיזוז פטור ונקודות זיכוי
            if (monthlyGrossAmount > 0) {
              // קיזוז קצבה פטורה מקיבוע זכויות (נוסף על קצבאות פטורות ממס)
              let monthlyExemptPension = monthlyPensionExempt; // קצבאות שמוגדרות כפטורות ממס
              if (fixationData && fixationData.exemption_summary) {
                const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year;
                const currentYear = monthDate.getFullYear();
                
                if (currentYear >= eligibilityYear) {
                  const exemptionPercentage = fixationData.exemption_summary.exemption_percentage || 0;
                  const remainingExemptCapital = fixationData.exemption_summary.remaining_exempt_capital || 0;
                  
                  if (currentYear === eligibilityYear) {
                    // שנת הקיבוע: יתרה נותרת (אחרי קיזוזים) ÷ 180
                    monthlyExemptPension += remainingExemptCapital / 180;
                  } else {
                    // שנים אחרי הקיבוע: אחוז פטור × יתרת הון תיאורטית ÷ 180
                    const pensionCeiling = getPensionCeiling(currentYear);
                    const capitalPercentage = getExemptCapitalPercentage(currentYear);
                    const theoreticalCapital = pensionCeiling * 180 * capitalPercentage;
                    monthlyExemptPension += (exemptionPercentage * theoreticalCapital) / 180;
                  }
                }
              }
              
              // הכנסה חייבת במס = קצבאות חייבות במס + הכנסות נוספות (קצבאות פטורות כבר הוחרגו)
              const monthlyTaxableIncome = monthlyPensionTaxable + monthlyAdditional;
              const annualTaxableIncome = monthlyTaxableIncome * 12;
              
              // חישוב מס לפי מדרגות המס המעודכנות
              let baseTax = calculateTaxByBrackets(annualTaxableIncome);
              
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
            date: formatDateToDDMMYY(monthDate),
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
            name: clientData && clientData.first_name && clientData.last_name ? `${clientData.first_name} ${clientData.last_name}` : 'לא צוין',
            id_number: clientData?.id_number || 'לא צוין'
          },
          financial_summary: {
            total_pension_value: totalPensionValue,
            total_additional_income: totalAdditionalIncome,
            total_capital_assets: totalCapitalAssetsValue,
            total_capital_payments: totalCapitalAssetsPayments,
            total_wealth: totalWealth,
            estimated_tax: estimatedTax,
            total_monthly_income: totalMonthlyIncome
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
    
    // חישוב מס בסיסי לפי מדרגות המס המעודכנות
    baseTax = calculateTaxByBrackets(annualIncome);
    
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
   * קצבאות והכנסות נוספות שהתחילו בעבר יוצגו החל מהשנה הנוכחית
   * קצבאות והכנסות נוספות שמתחילות בעתיד יוצגו החל משנת ההתחלה שלהן
   */
  const generateYearlyProjection = (): YearlyProjection[] => {
    console.log('generateYearlyProjection called');
    console.log('Available data:', { 
      pensionFunds: pensionFunds.length, 
      additionalIncomes: additionalIncomes.length, 
      capitalAssets: capitalAssets.length,
      client: !!client
    });
    
    // אל תחזיר מערך ריק - תמשיך עם החישוב גם בלי reportData
    
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
      let totalMonthlyIncome: number = 0;
      
      // Add pension fund incomes
      pensionFunds.forEach(fund => {
        // חישוב שנת התחלה - שימוש בתאריך המקורי
        let fundStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (fund.pension_start_date) {
          fundStartYear = parseInt(fund.pension_start_date.split('-')[0]);
        } else if (fund.start_date) {
          fundStartYear = parseInt(fund.start_date.split('-')[0]);
        }
        
        const monthlyAmount = parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0;
        
        // הצמדה שנתית רק אם מוגדרת במפורש
        const yearsActive = year >= fundStartYear ? year - fundStartYear : 0;
        // אם אין הצמדה מוגדרת, ברירת המחדל היא ללא הצמדה (0)
        const indexationRate = fund.indexation_rate !== undefined ? fund.indexation_rate : 0;
        
        // תיקון: גם כשהקרן מתחילה בשנה הנוכחית (yearsActive = 0), היא צריכה להניב הכנסה
        const adjustedAmount = year >= fundStartYear ? 
          monthlyAmount * Math.pow(1 + indexationRate, yearsActive) : 0;
        
        // Only add income if pension has started
        const amount: number = adjustedAmount;
        
        incomeBreakdown.push(Math.round(amount));
        totalMonthlyIncome += amount;
      });
      
      // Add additional incomes
      additionalIncomes.forEach(income => {
        // חישוב שנת התחלה - שימוש בתאריך המקורי
        let incomeStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (income.start_date) {
          incomeStartYear = parseInt(income.start_date.split('-')[0]);
        }
        
        const incomeEndYear = income.end_date ? parseInt(income.end_date.split('-')[0]) : maxYear;
        // בדיקת כל השדות האפשריים להכנסה חודשית
        let monthlyAmount = 0;
        if (income.monthly_amount) {
          monthlyAmount = parseFloat(income.monthly_amount);
        } else if (income.amount) {
          // חישוב לפי תדירות
          const amount = parseFloat(income.amount);
          if (income.frequency === 'monthly') {
            monthlyAmount = amount;
          } else if (income.frequency === 'quarterly') {
            monthlyAmount = amount / 3;
          } else if (income.frequency === 'annually') {
            monthlyAmount = amount / 12;
          } else {
            monthlyAmount = amount; // ברירת מחדל
          }
        } else if (income.annual_amount) {
          monthlyAmount = parseFloat(income.annual_amount) / 12;
        }
        
        // Only add income if it's active in this year
        const amount: number = (year >= incomeStartYear && year <= incomeEndYear) ? monthlyAmount : 0;
        incomeBreakdown.push(Math.round(amount));
        
        // הוספה לסך ההכנסה החודשית
        totalMonthlyIncome += amount;
      });

      // Add capital assets income - רק נכסים עם תשלום חד פעמי (monthly_income > 0)
      capitalAssets.forEach(asset => {
        const paymentAmount = parseFloat(asset.monthly_income) || 0;
        
        // ✅ נכס הון מתבטא בתזרים רק אם monthly_income > 0
        if (paymentAmount > 0) {
          let amount = 0;
          let assetStartYear = currentYear;
          
          if (asset.start_date) {
            assetStartYear = parseInt(asset.start_date.split('-')[0]);
          }
          
          // תשלום חד פעמי רק בשנת start_date
          if (year === assetStartYear) {
            amount = paymentAmount;
            console.log(`💰 CAPITAL ASSET ONE-TIME PAYMENT: ${asset.asset_name || asset.description || 'unnamed'} in year ${year}, amount=${amount}`);
          }
          
          // ✅ רק נכסים עם תשלום נכנסים ל-incomeBreakdown!
          incomeBreakdown.push(Math.round(amount));
          totalMonthlyIncome += amount;
        }
        // אם monthly_income = 0, הנכס לא מוצג בתזרים בכלל (לא נוסף ל-incomeBreakdown)
      });
      
      // חישוב מס על סך כל ההכנסות הדינמיות של השנה הנוכחית
      const taxBreakdown: number[] = [];
      let totalMonthlyTax = 0;
      
      // חישוב סך כל ההכנסות השנתיות בהתבסס על ההכנסות הדינמיות של השנה הנוכחית
      let totalTaxableAnnualIncome = 0;
      let totalExemptIncome = 0;
      
      // חישוב קצבה פטורה מקיבוע זכויות (רק משנת הזכאות ואילך)
      let monthlyExemptPension = 0;
      if (fixationData && fixationData.exemption_summary) {
        console.log(`🔍 Fixation Data for year ${year}:`, JSON.stringify(fixationData.exemption_summary, null, 2));
        
        const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year;
        
        // הפטור חל רק משנת הזכאות ואילך
        if (year >= eligibilityYear) {
          const exemptionPercentage = fixationData.exemption_summary.exemption_percentage || 0;
          const remainingExemptCapital = fixationData.exemption_summary.remaining_exempt_capital || 0;
          
          if (year === eligibilityYear) {
            // שנת הקיבוע: יתרה נותרת (אחרי קיזוזים) ÷ 180
            monthlyExemptPension = remainingExemptCapital / 180;
            console.log(`📊 Year ${year} (ELIGIBILITY YEAR):`);
            console.log(`   Remaining exempt capital: ${remainingExemptCapital.toLocaleString()}`);
            console.log(`   💰 Exempt pension = ${remainingExemptCapital.toLocaleString()} ÷ 180 = ${monthlyExemptPension.toFixed(2)}`);
          } else {
            // שנים אחרי הקיבוע: אחוז פטור × יתרת הון תיאורטית ÷ 180
            const pensionCeiling = getPensionCeiling(year);
            const capitalPercentage = getExemptCapitalPercentage(year);
            const theoreticalCapital = pensionCeiling * 180 * capitalPercentage;
            monthlyExemptPension = (exemptionPercentage * theoreticalCapital) / 180;
            
            console.log(`📊 Year ${year} (POST-ELIGIBILITY):`);
            console.log(`   Pension ceiling: ${pensionCeiling.toLocaleString()}`);
            console.log(`   Capital percentage: ${(capitalPercentage * 100).toFixed(1)}%`);
            console.log(`   Theoretical capital: ${pensionCeiling} × 180 × ${(capitalPercentage * 100).toFixed(1)}% = ${theoreticalCapital.toLocaleString()}`);
            console.log(`   Exemption percentage: ${(exemptionPercentage * 100).toFixed(1)}%`);
            console.log(`   💰 Exempt pension = ${(exemptionPercentage * 100).toFixed(1)}% × ${theoreticalCapital.toLocaleString()} ÷ 180 = ${monthlyExemptPension.toFixed(2)}`);
          }
        } else {
          console.log(`⏰ Year ${year} < eligibility year ${eligibilityYear} - no exemption yet`);
        }
      } else {
        console.log(`❌ No fixation data available for year ${year}`);
      }
      
      // חישוב הכנסה חייבת במס מקצבאות לאחר קיזוז פטור קיבוע זכויות
      let monthlyTaxableIncome = 0;
      const pensionIncomes = incomeBreakdown.slice(0, pensionFunds.length);
      
      // יצירת מערך זוגות (סכום, אינדקס) וסידור לפי סכום יורד
      const sortedPensions = pensionIncomes
        .map((income, index) => ({ income, index }))
        .filter(item => item.income > 0)
        .sort((a, b) => b.income - a.income);
      
      // קיזוז הפטור מהקצבאות הגבוהות ביותר
      console.log(`\n🎯 Starting exemption offset for year ${year}:`);
      console.log(`  Monthly exempt pension: ${monthlyExemptPension.toFixed(2)}`);
      console.log(`  Pension incomes BEFORE offset:`, pensionIncomes.map(p => p.toFixed(2)));
      
      let remainingExemption = monthlyExemptPension;
      const pensionAfterExemption = [...pensionIncomes]; // העתקה
      
      for (const pension of sortedPensions) {
        if (remainingExemption <= 0) break;
        
        const exemptionToApply = Math.min(pension.income, remainingExemption);
        pensionAfterExemption[pension.index] -= exemptionToApply;
        remainingExemption -= exemptionToApply;
        
        console.log(`  ✅ Applying exemption ${exemptionToApply.toFixed(2)} to pension #${pension.index + 1}, after offset: ${pensionAfterExemption[pension.index].toFixed(2)}`);
      }
      
      console.log(`  Pension incomes AFTER offset:`, pensionAfterExemption.map(p => p.toFixed(2)));
      
      // סיכום הכנסה חייבת אחרי קיזוז הפטור
      pensionAfterExemption.forEach(income => {
        monthlyTaxableIncome += Math.max(0, income);
      });
      
      console.log(`  💵 Total monthly taxable income after exemption: ${monthlyTaxableIncome.toFixed(2)}`);
      
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
      
      console.log(`\n💰 Tax calculation summary for year ${year}:`);
      console.log(`  Monthly taxable income (pensions after exemption): ${monthlyTaxableIncome.toFixed(2)}`);
      console.log(`  Monthly taxable additional income: ${monthlyTaxableAdditionalIncome.toFixed(2)}`);
      console.log(`  Total annual taxable income: ${totalTaxableAnnualIncome.toLocaleString()}`);
      console.log(`  Total annual exempt income: ${totalExemptIncome.toLocaleString()}`);
      
      if (totalTaxableAnnualIncome > 0) {
        // חישוב מס כולל על סך ההכנסות החייבות במס
        let totalAnnualTax = 0;
        let remainingIncome = totalTaxableAnnualIncome;
        
        // שימוש במדרגות המס המעודכנות מההגדרות
        totalAnnualTax = calculateTaxByBrackets(totalTaxableAnnualIncome);
        
        console.log(`  Tax before credit: ${totalAnnualTax.toLocaleString()}`);
        
        // הפחתת נקודות זיכוי אם קיימות
        if (client?.tax_credit_points) {
          const creditAmount = client.tax_credit_points * 2640;
          totalAnnualTax = Math.max(0, totalAnnualTax - creditAmount);
          console.log(`  Tax credit applied (${client.tax_credit_points} points × 2640): ${creditAmount.toLocaleString()}`);
        }
        
        console.log(`  Final annual tax: ${totalAnnualTax.toLocaleString()}`);

        // מס חודשי מהכנסות רגילות בלבד (ללא נכסי הון)
        const regularMonthlyTax = totalAnnualTax / 12;
        console.log(`  Monthly tax: ${regularMonthlyTax.toFixed(2)}`);
        
        // חלוקת המס באופן יחסי לפי ההכנסות אחרי קיזוז הפטור
        // חישוב סך ההכנסה החייבת במס
        const taxableTotalMonthlyIncome = monthlyTaxableIncome + monthlyTaxableAdditionalIncome;
        
        console.log(`\n📊 Distributing tax among income sources:`);
        
        pensionFunds.forEach((fund, index) => {
          // שימוש בהכנסה אחרי קיזוז הפטור!
          const taxableIncomeAmount = pensionAfterExemption[index] || 0;
          // חלוקת המס באופן יחסי - רק מהכנסות חייבות במס
          const taxPortion = taxableTotalMonthlyIncome > 0 ? (taxableIncomeAmount / taxableTotalMonthlyIncome) * regularMonthlyTax : 0;
          taxBreakdown.push(Math.round(taxPortion));
          console.log(`  Pension #${index + 1}: taxable=${taxableIncomeAmount.toFixed(2)}, tax=${taxPortion.toFixed(2)}`);
        });
        
        additionalIncomes.forEach((income, index) => {
          const incomeIndex = pensionFunds.length + index;
          const incomeAmount = incomeBreakdown[incomeIndex] || 0;
          
          // אם ההכנסה פטורה ממס, המס הוא אפס
          if (income.tax_treatment === 'exempt') {
            taxBreakdown.push(0);
          } else {
            // חלוקת המס באופן יחסי - רק מהכנסות רגילות
            const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * regularMonthlyTax : 0;
            taxBreakdown.push(Math.round(taxPortion));
          }
        });

        // חישוב מס עבור נכסי הון - בנפרד! רק לנכסים עם תשלום
        let totalCapitalAssetTax = 0;
        let capitalAssetIncomeIndex = pensionFunds.length + additionalIncomes.length;
        
        capitalAssets.forEach((asset) => {
          const paymentAmount = parseFloat(asset.monthly_income) || 0;
          
          // ✅ רק נכסים עם תשלום חד פעמי
          if (paymentAmount > 0) {
            const monthlyIncome = incomeBreakdown[capitalAssetIncomeIndex] || 0;
            const annualIncome = monthlyIncome;  // כבר הסכום השנתי (תשלום חד פעמי)
            let assetTax = 0;
            capitalAssetIncomeIndex++; // מתקדם רק אם יש תשלום!
          
          // חישוב מס לפי סוג המיסוי
          if (asset.tax_treatment === 'exempt') {
            // פטור ממס
            assetTax = 0;
          } else if (asset.tax_treatment === 'tax_spread' && asset.spread_years && asset.spread_years > 0) {
            // 🔥 פריסת מס - חישוב מס לפי מדרגות על מספר שנים
            const taxableAmount = annualIncome; // הסכום החד פעמי
            const annualPortion = taxableAmount / asset.spread_years; // חלוקה שווה
            
            // חישוב מס לכל שנה
            let totalSpreadTax = 0;
            for (let spreadYear = 0; spreadYear < asset.spread_years; spreadYear++) {
              // מס על חלק מהסכום לפי מדרגות
              const taxWithSeverance = calculateTaxByBrackets(annualPortion);
              totalSpreadTax += taxWithSeverance;
            }
            
            // בשנת התשלום - כל המס המצטבר
            assetTax = totalSpreadTax;
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
              assetTax += calculateTaxByBrackets(taxableRentalIncome);
            }
          } else {
            // מס רגיל על נכסי הון אחרים
            assetTax += calculateTaxByBrackets(annualIncome);
          }
          
            totalCapitalAssetTax += assetTax;
            taxBreakdown.push(Math.round(assetTax / 12)); // המרה למס חודשי - המס הספציפי של הנכס!
          }
          // נכס ללא תשלום - לא נכנס לתזרים ולא ל-taxBreakdown
        });
        
        // עדכון סך המס הכולל
        totalMonthlyTax = regularMonthlyTax + (totalCapitalAssetTax / 12);
      } else {
        // אין הכנסה - אין מס
        // מוסיפים 0 לכל פריט ב-incomeBreakdown (שכבר מכיל רק נכסים עם תשלום)
        for (let i = 0; i < incomeBreakdown.length; i++) {
          taxBreakdown.push(0);
        }
      }

      const netIncome = totalMonthlyIncome - totalMonthlyTax;
      
      yearlyData.push({
        year,
        clientAge,
        totalMonthlyIncome: Math.round(totalMonthlyIncome),
        totalMonthlyTax: Math.round(totalMonthlyTax),
        netMonthlyIncome: Math.round(netIncome),
        incomeBreakdown,
        taxBreakdown,
        exemptPension: monthlyExemptPension
      });
    }
    
    console.log('Generated yearly data:', yearlyData.slice(0, 3)); // הצגת 3 השנים הראשונות
    
    // אם אין נתונים, צור נתונים בסיסיים לבדיקה
    if (yearlyData.length === 0) {
      console.log('No yearly data generated, creating basic data for testing');
      for (let i = 0; i < 10; i++) {
        const year = 2025 + i;
        yearlyData.push({
          year,
          clientAge: 68 + i,
          totalMonthlyIncome: 10000,
          totalMonthlyTax: 1500,
          netMonthlyIncome: 8500,
          incomeBreakdown: [10000],
          taxBreakdown: [1500]
        });
      }
    }
    
    return yearlyData;
  };

  // הוסר calculateTaxImpact - המס מחושב ישירות בטבלה

  // פונקציית עזר לחישוב NPV
  const calculateNPV = (cashFlows: number[], discountRate: number): number => {
    if (!cashFlows || cashFlows.length === 0) {
      return 0;
    }
    
    // חישוב NPV: סכום של [תזרים ÷ (1 + היוון)^שנה] לכל השנים
    const result = cashFlows.reduce((sum, cashFlow, year) => {
      const discountedValue = cashFlow / Math.pow(1 + discountRate, year);
      return sum + discountedValue;
    }, 0);
    
    return result;
  };

  /**
   * חישוב NPV של נכסי הון שלא מוצגים בתזרים (monthly_income = 0)
   * נכסים אלו מחושבים לפי: ערך נוכחי, תשואה שנתית, הצמדה ויחס מס
   */
  const calculateCapitalAssetsNPV = (): { asset: any; npv: number; npvAfterTax: number }[] => {
    const results: { asset: any; npv: number; npvAfterTax: number }[] = [];
    
    capitalAssets.forEach(asset => {
      const paymentAmount = parseFloat(asset.monthly_income) || 0;
      
      // רק נכסים ללא תשלום חד פעמי
      if (paymentAmount === 0) {
        const currentValue = parseFloat(asset.current_value) || 0;
        const annualReturnRate = parseFloat(asset.annual_return_rate) || 0;
        const indexationMethod = asset.indexation_method || 'none';
        const fixedRate = parseFloat(asset.fixed_rate) || 0;
        const taxTreatment = asset.tax_treatment || 'taxable';
        const taxRate = parseFloat(asset.tax_rate) || 0;
        
        // חישוב שיעור תשואה כולל (תשואה + הצמדה)
        let totalReturnRate = annualReturnRate;
        if (indexationMethod === 'fixed') {
          totalReturnRate += fixedRate;
        } else if (indexationMethod === 'cpi') {
          totalReturnRate += 0.02; // הנחה: אינפלציה ממוצעת 2%
        }
        
        // חישוב ערך עתידי (לדוגמה: 10 שנים)
        const years = 10;
        const futureValue = currentValue * Math.pow(1 + totalReturnRate, years);
        
        // חישוב NPV (ערך נוכחי של הערך העתידי)
        const discountRate = 0.03; // שיעור היוון 3%
        const npv = futureValue / Math.pow(1 + discountRate, years);
        
        // חישוב מס
        let tax = 0;
        const gain = futureValue - currentValue;
        
        if (taxTreatment === 'exempt') {
          tax = 0;
        } else if (taxTreatment === 'capital_gains') {
          // מס רווח הון - 25% על הרווח הריאלי
          const realGain = gain - (currentValue * 0.02 * years); // ניכוי אינפלציה
          tax = Math.max(0, realGain) * 0.25;
        } else if (taxTreatment === 'fixed_rate') {
          tax = gain * (taxRate / 100);
        } else {
          // מס רגיל לפי מדרגות
          tax = calculateTaxByBrackets(gain);
        }
        
        const npvAfterTax = (futureValue - tax) / Math.pow(1 + discountRate, years);
        
        results.push({
          asset,
          npv: Math.round(npv),
          npvAfterTax: Math.round(npvAfterTax)
        });
        
        console.log(`📊 NPV Calculation for ${asset.asset_name || asset.description}:`);
        console.log(`   Current value: ${currentValue.toLocaleString()}`);
        console.log(`   Return rate: ${(totalReturnRate * 100).toFixed(2)}%`);
        console.log(`   Future value (${years} years): ${futureValue.toLocaleString()}`);
        console.log(`   NPV: ${npv.toLocaleString()}`);
        console.log(`   Tax: ${tax.toLocaleString()}`);
        console.log(`   NPV after tax: ${npvAfterTax.toLocaleString()}`);
      }
    });
    
    return results;
  };

  // פונקציית יצירת דוח PDF מקיף
  const createPDFReport = (yearlyProjection: any[]) => {
    const doc = new jsPDF();
    const currentDate = new Date().toLocaleDateString('he-IL');
    const discountRate = 0.03;
    let yPosition = 20;
    
    // ==== עמוד 1: כותרת ומידע כללי ====
    doc.setFontSize(22);
    doc.setTextColor(0, 51, 102);
    doc.text('דוח פנסיוני מקיף', 105, yPosition, { align: 'center' });
    yPosition += 10;
    doc.setFontSize(14);
    doc.setTextColor(100, 100, 100);
    doc.text('תכנון פרישה ואופטימיזציה פנסיונית', 105, yPosition, { align: 'center' });
    yPosition += 15;
    
    // תאריך ופרטי לקוח
    doc.setFontSize(11);
    doc.setTextColor(0, 0, 0);
    doc.text(`תאריך יצירת הדוח: ${currentDate}`, 20, yPosition);
    yPosition += 7;
    
    if (client) {
      doc.text(`שם הלקוח: ${client.first_name || ''} ${client.last_name || ''}`, 20, yPosition);
      yPosition += 7;
      if (client.birth_date) {
        doc.text(`תאריך לידה: ${client.birth_date}`, 20, yPosition);
        yPosition += 7;
      }
    }
    yPosition += 10;
    
    // ==== חלק 1: NPV ופטורים ====
    doc.setFillColor(240, 248, 255);
    doc.rect(15, yPosition, 180, 50, 'F');
    yPosition += 10;
    
    doc.setFontSize(14);
    doc.setTextColor(0, 51, 102);
    doc.text('ערך נוכחי נקי (NPV)', 20, yPosition);
    yPosition += 10;
    
    // חישוב NPV עם ובלי פטורים
    const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
    const cashflowNPV = calculateNPV(annualNetCashFlows, discountRate);
    const capitalAssetsNPVResults = calculateCapitalAssetsNPV();
    const capitalNPV = capitalAssetsNPVResults.reduce((sum, item) => sum + item.npvAfterTax, 0);
    const npvComparison = calculateNPVComparison(yearlyProjection, discountRate);
    
    doc.setFontSize(10);
    doc.setTextColor(0, 0, 0);
    doc.text(`NPV תזרים: ₪${Math.round(cashflowNPV).toLocaleString()}`, 25, yPosition);
    yPosition += 6;
    doc.text(`NPV נכסי הון: ₪${Math.round(capitalNPV).toLocaleString()}`, 25, yPosition);
    yPosition += 6;
    doc.setFontSize(12);
    doc.setTextColor(0, 128, 0);
    doc.text(`סה"כ NPV: ₪${Math.round(cashflowNPV + capitalNPV).toLocaleString()}`, 25, yPosition);
    yPosition += 10;
    
    // פרוט פטורים
    if (fixationData) {
      doc.setFontSize(10);
      doc.setTextColor(0, 0, 0);
      const monthlyExemption = (fixationData.remaining_exempt_capital || 0) / 180;
      doc.text(`קצבה פטורה חודשית: ₪${monthlyExemption.toLocaleString()}`, 25, yPosition);
      yPosition += 6;
      doc.text(`חיסכון ממס (NPV): ₪${Math.round(npvComparison.savings).toLocaleString()}`, 25, yPosition);
    }
    
    yPosition += 15;
    
    // ==== עמוד חדש: טבלת מוצרים פנסיונים ====
    doc.addPage();
    yPosition = 20;
    
    doc.setFontSize(16);
    doc.setTextColor(0, 51, 102);
    doc.text('טבלת מוצרים פנסיונים', 105, yPosition, { align: 'center' });
    yPosition += 15;
    
    if (pensionFunds && pensionFunds.length > 0) {
      const pensionData = pensionFunds.map(p => [
        p.fund_name || 'לא צוין',
        PENSION_PRODUCT_TYPES[p.product_type] || p.product_type,
        p.company || 'לא צוין',
        `₪${(p.current_balance || 0).toLocaleString()}`,
        `₪${(p.monthly_pension || 0).toLocaleString()}`
      ]);
      
      autoTable(doc, {
        head: [['שם תכנית', 'סוג מוצר', 'חברה', 'יתרה', 'קצבה חודשית']],
        body: pensionData,
        startY: yPosition,
        styles: { font: 'helvetica', fontSize: 9, cellPadding: 3 },
        headStyles: { fillColor: [0, 51, 102], textColor: [255, 255, 255] },
        alternateRowStyles: { fillColor: [245, 247, 250] },
        margin: { right: 15, left: 15 }
      });
      
      yPosition = (doc as any).lastAutoTable.finalY + 15;
    }
    
    // גרף עוגה של פילוח מוצרים
    if (pensionFunds && pensionFunds.length > 0) {
      const pieData = generatePieChartData(pensionFunds);
      if (pieData.values.length > 0) {
        doc.setFontSize(14);
        doc.setTextColor(0, 51, 102);
        doc.text('פילוח מוצרים פנסיונים', 105, yPosition, { align: 'center' });
        yPosition += 10;
        
        drawPieChart(doc, 105, yPosition + 30, 30, pieData);
      }
    }
    
    // ==== עמוד חדש: פרוט פעולות תזרים ====
    doc.addPage();
    yPosition = 20;
    
    doc.setFontSize(16);
    doc.setTextColor(0, 51, 102);
    doc.text('פרוט פעולות תזרים', 105, yPosition, { align: 'center' });
    yPosition += 15;
    
    const operations = generateCashflowOperationsDetails(
      pensionFunds,
      additionalIncomes,
      capitalAssets,
      fixationData,
      new Date().getFullYear()
    );
    
    doc.setFontSize(9);
    doc.setTextColor(0, 0, 0);
    operations.forEach(line => {
      if (yPosition > 270) {
        doc.addPage();
        yPosition = 20;
      }
      doc.text(line, 20, yPosition);
      yPosition += 5;
    });
    
    // ==== עמוד חדש: טבלת תזרים מזומנים ====
    doc.addPage();
    yPosition = 20;
    
    doc.setFontSize(16);
    doc.setTextColor(0, 51, 102);
    doc.text('תחזית תזרים מזומנים', 105, yPosition, { align: 'center' });
    yPosition += 15;
    
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
      styles: { font: 'helvetica', fontSize: 9, cellPadding: 3 },
      headStyles: { fillColor: [0, 51, 102], textColor: [255, 255, 255] },
      alternateRowStyles: { fillColor: [245, 247, 250] },
      columnStyles: {
        1: { halign: 'right' },
        2: { halign: 'right', textColor: [220, 53, 69] },
        3: { halign: 'right' },
        4: { halign: 'right' }
      },
      margin: { right: 15, left: 15 }
    });
    
    // שמירת הקובץ
    doc.save(`דוח-פנסיוני-מקיף-${currentDate}.pdf`);
  };

  // פונקציית יצירת דוח Excel מקיף
  const createExcelReport = (yearlyProjection: any[]) => {
    const workbook = XLSX.utils.book_new();
    const currentDate = new Date().toLocaleDateString('he-IL');
    const discountRate = 0.03;
    
    // ==== גיליון 1: תזרים מזומנים ====
    const cashflowData = [
      ['שנה', 'הכנסה חודשית', 'מס חודשי', 'נטו חודשי', 'נטו שנתי'],
      ...yearlyProjection.map(year => [
        year.year,
        year.totalMonthlyIncome,
        year.totalMonthlyTax,
        year.netMonthlyIncome,
        year.netMonthlyIncome * 12
      ])
    ];
    
    // חישוב NPV
    const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
    const cashflowNPV = calculateNPV(annualNetCashFlows, discountRate);
    const capitalAssetsNPVResults = calculateCapitalAssetsNPV();
    const capitalNPV = capitalAssetsNPVResults.reduce((sum, item) => sum + item.npvAfterTax, 0);
    const npvComparison = calculateNPVComparison(yearlyProjection, discountRate);
    
    // הוספת NPV
    cashflowData.push(['', '', '', '', '']);
    cashflowData.push(['NPV תזרים:', '', '', '', Math.round(cashflowNPV)]);
    cashflowData.push(['NPV נכסי הון:', '', '', '', Math.round(capitalNPV)]);
    cashflowData.push(['סה"כ NPV:', '', '', '', Math.round(cashflowNPV + capitalNPV)]);
    cashflowData.push(['חיסכון ממס (NPV):', '', '', '', Math.round(npvComparison.savings)]);
    
    const cashflowSheet = XLSX.utils.aoa_to_sheet(cashflowData);
    XLSX.utils.book_append_sheet(workbook, cashflowSheet, 'תזרים מזומנים');
    
    // ==== גיליון 2: מוצרים פנסיונים ====
    if (pensionFunds && pensionFunds.length > 0) {
      const pensionData = [
        ['שם תכנית', 'סוג מוצר', 'חברה', 'יתרה', 'קצבה חודשית', 'תאריך התחלה'],
        ...pensionFunds.map(p => [
          p.fund_name || '',
          PENSION_PRODUCT_TYPES[p.product_type] || p.product_type || '',
          p.company || '',
          p.current_balance || 0,
          p.monthly_pension || 0,
          p.start_date || ''
        ])
      ];
      
      // סיכום
      const totalBalance = pensionFunds.reduce((sum, p) => sum + (p.current_balance || 0), 0);
      const totalMonthly = pensionFunds.reduce((sum, p) => sum + (p.monthly_pension || 0), 0);
      
      pensionData.push(['', '', '', '', '', '']);
      pensionData.push(['סה"כ', '', '', totalBalance, totalMonthly, '']);
      
      const pensionSheet = XLSX.utils.aoa_to_sheet(pensionData);
      XLSX.utils.book_append_sheet(workbook, pensionSheet, 'מוצרים פנסיונים');
    }
    
    // ==== גיליון 3: נכסי הון ====
    if (capitalAssets && capitalAssets.length > 0) {
      const assetsData = [
        ['שם נכס', 'סוג', 'ערך נוכחי', 'הכנסה חודשית', 'תשואה שנתית', 'תאריך התחלה', 'תאריך סיום'],
        ...capitalAssets.map(asset => [
          asset.asset_name || asset.description || '',
          ASSET_TYPES_MAP[asset.asset_type] || asset.asset_type || '',
          asset.current_value || 0,
          asset.monthly_income || 0,
          asset.annual_return_rate || 0,
          asset.start_date || '',
          asset.end_date || ''
        ])
      ];
      
      const totalValue = capitalAssets.reduce((sum, a) => sum + (a.current_value || 0), 0);
      const totalIncome = capitalAssets.reduce((sum, a) => sum + (a.monthly_income || 0), 0);
      
      assetsData.push(['', '', '', '', '', '', '']);
      assetsData.push(['סה"כ', '', totalValue, totalIncome, '', '', '']);
      
      const assetsSheet = XLSX.utils.aoa_to_sheet(assetsData);
      XLSX.utils.book_append_sheet(workbook, assetsSheet, 'נכסי הון');
    }
    
    // ==== גיליון 4: פרוט פעולות תזרים ====
    const operations = generateCashflowOperationsDetails(
      pensionFunds,
      additionalIncomes,
      capitalAssets,
      fixationData,
      new Date().getFullYear()
    );
    
    const operationsData = [
      ['פרוט פעולות תזרים'],
      [''],
      ...operations.map(line => [line])
    ];
    
    const operationsSheet = XLSX.utils.aoa_to_sheet(operationsData);
    XLSX.utils.book_append_sheet(workbook, operationsSheet, 'פרוט פעולות');
    
    // ==== גיליון 5: פטורים ממס ====
    if (fixationData) {
      const monthlyExemption = (fixationData.remaining_exempt_capital || 0) / 180;
      const exemptionPercentage = (fixationData.exemption_percentage || 0) * 100;
      
      const exemptionsData = [
        ['פרט', 'ערך'],
        ['שנת קיבוע', fixationData.fixation_year || ''],
        ['יתרת הון פטורה ראשונית', fixationData.exempt_capital_initial || 0],
        ['יתרה אחרי קיזוזים', fixationData.remaining_exempt_capital || 0],
        ['קצבה פטורה חודשית', monthlyExemption],
        ['אחוז פטור', exemptionPercentage],
        [''],
        ['השוואת NPV'],
        ['NPV עם פטור', Math.round(npvComparison.withExemption)],
        ['NPV ללא פטור', Math.round(npvComparison.withoutExemption)],
        ['חיסכון ממס', Math.round(npvComparison.savings)]
      ];
      
      const exemptionsSheet = XLSX.utils.aoa_to_sheet(exemptionsData);
      XLSX.utils.book_append_sheet(workbook, exemptionsSheet, 'פטורים ממס');
    }
    
    // שמירת הקובץ
    XLSX.writeFile(workbook, `דוח-פנסיוני-מקיף-${currentDate}.xlsx`);
  };

  const handleGeneratePdf = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // יצירת דוח HTML להדפסה
      generateHTMLReport();
      
    } catch (err: any) {
      console.error('שגיאה ביצירת דוח HTML:', err);
      setError('שגיאה ביצירת דוח HTML: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const generateHTMLReport = () => {
    console.log('📊 Generating HTML Report with current state data:');
    console.log('  Pension Funds:', pensionFunds);
    console.log('  Capital Assets:', capitalAssets);
    console.log('  Additional Incomes:', additionalIncomes);
    console.log('  Fixation Data:', fixationData);
    console.log('  Client:', client);
    
    // בדיקת נתונים
    if (!pensionFunds || pensionFunds.length === 0) {
      console.warn('⚠️ WARNING: No pension funds data!');
      alert('אזהרה: לא נמצאו נתוני קצבאות. אנא וודא שהנתונים נטענו במסך התוצאות.');
      return;
    }
    
    const yearlyProjection = generateYearlyProjection();
    
    // יצירת HTML עם כל הנתונים
    const htmlContent = `
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>דוח פנסיוני מקיף - ${client?.first_name || 'לקוח'}</title>
    <style>
        @media print {
            .no-print { display: none !important; }
            body { margin: 0; }
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            line-height: 1.6;
            color: #333;
            direction: rtl;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
        }
        
        .header h1 {
            color: #007bff;
            margin: 0;
            font-size: 28px;
        }
        
        .header .date {
            color: #666;
            margin-top: 10px;
        }
        
        .client-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        
        .client-info h2 {
            color: #007bff;
            margin-top: 0;
        }
        
        .npv-section {
            background: #d4edda;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            text-align: center;
        }
        
        .npv-value {
            font-size: 24px;
            font-weight: bold;
            color: #155724;
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section h2 {
            color: #007bff;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: right;
        }
        
        th {
            background-color: #007bff;
            color: white;
            font-weight: bold;
        }
        
        tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .summary-section {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 8px;
            margin-top: 30px;
        }
        
        .summary-item {
            margin-bottom: 10px;
            font-size: 16px;
        }
        
        .summary-total {
            font-weight: bold;
            color: #1976d2;
            font-size: 18px;
        }
        
        .print-button {
            position: fixed;
            top: 20px;
            left: 20px;
            background: #28a745;
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            z-index: 1000;
        }
        
        .print-button:hover {
            background: #218838;
        }
    </style>
</head>
<body>
    <button class="print-button no-print" onclick="window.print()">🖨️ הדפס לPDF</button>
    
    <div class="header">
        <h1>דוח פנסיוני מקיף - תכנון פרישה</h1>
        <div class="date">תאריך יצירת הדוח: ${formatDateToDDMMYY(new Date())}</div>
    </div>
    
    <div class="client-info">
        <h2>פרטי הלקוח</h2>
        <div><strong>שם הלקוח:</strong> ${client?.first_name || ''} ${client?.last_name || ''}</div>
        ${client?.birth_date ? `<div><strong>תאריך לידה:</strong> ${client.birth_date}</div>` : ''}
        ${client?.id_number ? `<div><strong>מספר זהות:</strong> ${client.id_number}</div>` : ''}
    </div>
    
    <div class="npv-section">
        <h2>ערך נוכחי נקי (NPV)</h2>
        <div class="npv-value">
            <div>NPV תזרים: ₪${Math.round(calculateNPV(yearlyProjection.map(y => y.netMonthlyIncome * 12), 0.03)).toLocaleString()}</div>
            <div>NPV נכסי הון: ₪${Math.round(calculateCapitalAssetsNPV().reduce((sum, item) => sum + item.npvAfterTax, 0)).toLocaleString()}</div>
            <div style="border-top: 2px solid #155724; margin-top: 10px; padding-top: 10px;">
                סה"כ NPV: ₪${Math.round(calculateNPV(yearlyProjection.map(y => y.netMonthlyIncome * 12), 0.03) + calculateCapitalAssetsNPV().reduce((sum, item) => sum + item.npvAfterTax, 0)).toLocaleString()}
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>תחזית תזרים מזומנים שנתי</h2>
        <table>
            <thead>
                <tr>
                    <th>שנה</th>
                    <th>הכנסה חודשית</th>
                    <th>מס חודשי</th>
                    <th>נטו חודשי</th>
                    <th>נטו שנתי</th>
                </tr>
            </thead>
            <tbody>
                ${yearlyProjection.slice(0, 20).map(year => `
                    <tr>
                        <td>${year.year}</td>
                        <td>₪${year.totalMonthlyIncome.toLocaleString()}</td>
                        <td>₪${year.totalMonthlyTax.toLocaleString()}</td>
                        <td>₪${year.netMonthlyIncome.toLocaleString()}</td>
                        <td>₪${(year.netMonthlyIncome * 12).toLocaleString()}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    </div>
    
    ${capitalAssets.length > 0 ? `
    <div class="section">
        <h2>נכסי הון</h2>
        <table>
            <thead>
                <tr>
                    <th>תיאור</th>
                    <th>סוג נכס</th>
                    <th>הכנסה חודשית</th>
                    <th>ערך נוכחי</th>
                    <th>תאריך התחלה</th>
                </tr>
            </thead>
            <tbody>
                ${capitalAssets.map(asset => `
                    <tr>
                        <td>${asset.description || asset.asset_name || 'ללא תיאור'}</td>
                        <td>${(() => {
                            const typeMap: Record<string, string> = {
                                rental_property: "דירה להשכרה",
                                investment: "השקעות",
                                stocks: "מניות",
                                bonds: "אגרות חוב",
                                mutual_funds: "קרנות נאמנות",
                                real_estate: "נדלן",
                                savings_account: "חשבון חיסכון",
                                deposits: "היוון",
                                provident_fund: "קופת גמל",
                                education_fund: "קרן השתלמות",
                                other: "אחר"
                            };
                            return typeMap[asset.asset_type] || asset.asset_type || 'לא צוין';
                        })()}</td>
                        <td>₪${(asset.monthly_income || 0).toLocaleString()}</td>
                        <td>₪${(asset.current_value || 0).toLocaleString()}</td>
                        <td>${asset.start_date || 'לא צוין'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    </div>
    ` : ''}
    
    ${pensionFunds.length > 0 ? `
    <div class="section">
        <h2>📊 קצבאות</h2>
        <table>
            <thead>
                <tr>
                    <th>שם תכנית</th>
                    <th>יתרה נוכחית</th>
                    <th>קצבה חודשית</th>
                    <th>תאריך התחלה</th>
                </tr>
            </thead>
            <tbody>
                ${pensionFunds.map(fund => `
                    <tr>
                        <td>${fund.fund_name || 'ללא שם'}</td>
                        <td>₪${(fund.current_balance || 0).toLocaleString()}</td>
                        <td>₪${(fund.monthly_pension || fund.pension_amount || fund.computed_monthly_amount || 0).toLocaleString()}</td>
                        <td>${fund.pension_start_date ? new Date(fund.pension_start_date).toLocaleDateString('he-IL') : (fund.start_date ? new Date(fund.start_date).toLocaleDateString('he-IL') : 'לא צוין')}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <div style="margin-top: 10px; font-weight: bold;">
            סה"כ יתרה: ₪${pensionFunds.reduce((sum, f) => sum + (parseFloat(f.current_balance) || 0), 0).toLocaleString()} | 
            סה"כ קצבה חודשית: ₪${pensionFunds.reduce((sum, f) => sum + (parseFloat(f.monthly_pension) || parseFloat(f.pension_amount) || parseFloat(f.computed_monthly_amount) || 0), 0).toLocaleString()}
        </div>
    </div>
    ` : ''}
    
    ${additionalIncomes.length > 0 ? `
    <div class="section">
        <h2>הכנסות נוספות</h2>
        <table>
            <thead>
                <tr>
                    <th>תיאור</th>
                    <th>סכום חודשי</th>
                    <th>יחס למס</th>
                    <th>תאריך התחלה</th>
                    <th>תאריך סיום</th>
                </tr>
            </thead>
            <tbody>
                ${additionalIncomes.map(income => `
                    <tr>
                        <td>${income.description || 'ללא תיאור'}</td>
                        <td>₪${(income.computed_monthly_amount || income.amount || 0).toLocaleString()}</td>
                        <td>${income.tax_treatment === 'exempt' ? 'פטור ממס' : 'חייב במס'}</td>
                        <td>${income.start_date || 'לא צוין'}</td>
                        <td>${income.end_date || 'ללא הגבלה'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    </div>
    ` : ''}
    
    ${fixationData && fixationData.exemption_summary ? `
    <div class="section">
        <h2>🛡️ פרוט פטורים ממס</h2>
        <div style="background: #fff3cd; padding: 20px; border-radius: 8px;">
            <div><strong>שנת קיבוע:</strong> ${fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || new Date().getFullYear()}</div>
            <div><strong>יתרת הון פטורה ראשונית:</strong> ₪${(fixationData.exemption_summary.exempt_capital_initial || 0).toLocaleString()}</div>
            <div><strong>יתרה אחרי קיזוזים:</strong> ₪${(fixationData.exemption_summary.remaining_exempt_capital || 0).toLocaleString()}</div>
            <div><strong>קצבה פטורה חודשית (שנת קיבוע):</strong> ₪${((fixationData.exemption_summary.remaining_exempt_capital || 0) / 180).toLocaleString()}</div>
            <div><strong>אחוז פטור:</strong> ${(() => {
                const remaining = fixationData.exemption_summary.remaining_exempt_capital || 0;
                const exemptPension = remaining / 180;
                const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year || new Date().getFullYear();
                // תקרת קצבה לפי שנה
                const pensionCeilings = {
                    2012: 6790, 2013: 6790, 2014: 6790, 2015: 6790,
                    2016: 7640, 2017: 7640, 2018: 7640, 2019: 7640,
                    2020: 8120, 2021: 8120, 2022: 8120, 2023: 8120, 2024: 8120,
                    2025: 9430, 2026: 9430, 2027: 9430, 2028: 9430
                };
                const pensionCeiling = pensionCeilings[eligibilityYear] || 9430;
                const calculatedPercentage = pensionCeiling > 0 ? (exemptPension / pensionCeiling) * 100 : 0;
                return calculatedPercentage.toFixed(2);
            })()}%</div>
            <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid #856404;">
                <strong>השוואת NPV:</strong><br>
                NPV עם פטור: ₪${Math.round(calculateNPVComparison(yearlyProjection, 0.03).withExemption).toLocaleString()}<br>
                NPV ללא פטור: ₪${Math.round(calculateNPVComparison(yearlyProjection, 0.03).withoutExemption).toLocaleString()}<br>
                <strong style="color: #155724;">חיסכון ממס (NPV): ₪${Math.round(calculateNPVComparison(yearlyProjection, 0.03).savings).toLocaleString()}</strong>
            </div>
        </div>
    </div>
    ` : ''}
    
    <div class="summary-section">
        <h2>סיכום כספי מקיף</h2>
        
        <h3>נכסים:</h3>
        <div class="summary-item">• סך ערך נכסי הון: ₪${capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0).toLocaleString()}</div>
        
        <h3>הכנסות חודשיות צפויות:</h3>
        <div class="summary-item">• קצבאות פנסיה: ₪${pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0).toLocaleString()}</div>
        <div class="summary-item">• הכנסות נוספות: ₪${additionalIncomes.reduce((sum, income) => sum + (parseFloat(income.monthly_amount) || 0), 0).toLocaleString()}</div>
        <div class="summary-item">• הכנסות מנכסי הון: ₪${capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.monthly_income) || 0), 0).toLocaleString()}</div>
        <div class="summary-item summary-total">• סך הכנסה חודשית: ₪${(pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0) + additionalIncomes.reduce((sum, income) => sum + (parseFloat(income.monthly_amount) || 0), 0) + capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.monthly_income) || 0), 0)).toLocaleString()}</div>
        
        <h3>ניתוח NPV:</h3>
        <div class="summary-item">• NPV של התזרים: ₪${Math.round(calculateNPV(yearlyProjection.map(y => y.netMonthlyIncome * 12), 0.03)).toLocaleString()}</div>
        <div class="summary-item">• NPV של נכסי הון: ₪${(() => {
          // חישוב NPV של נכסי הון - ערך נוכחי + תשואות עתידיות
          const capitalNPV = capitalAssets.reduce((sum, asset) => {
            const currentValue = parseFloat(asset.current_value) || 0;
            const annualReturn = currentValue * (parseFloat(asset.annual_return_rate) || 0) / 100;
            const futureReturns = Array(yearlyProjection.length).fill(annualReturn);
            const returnNPV = calculateNPV(futureReturns, 0.03);
            return sum + currentValue + returnNPV;
          }, 0);
          return Math.round(capitalNPV).toLocaleString();
        })()}</div>
        <div class="summary-item">• תקופת תחזית: ${yearlyProjection.length} שנים</div>
        <div class="summary-item">• שיעור היוון: 3%</div>
    </div>
    
    <!-- תזרים מזומנים מפורט -->
    <div class="section" style="page-break-before: always;">
        <h2>תזרים מזומנים מפורט - פירוט מלא</h2>
        <div style="overflow-x: auto;">
            <table style="font-size: 9px; width: 100%;">
                <thead>
                    <tr style="background: #003366; color: white;">
                        <th style="padding: 8px; border: 1px solid #ddd;">שנה</th>
                        <th style="padding: 8px; border: 1px solid #ddd; background: #f0f8ff;">נטו חודשי</th>
                        <th style="padding: 8px; border: 1px solid #ddd; background: #ffe4e1;">סה"כ מס</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">סה"כ הכנסה</th>
                        ${pensionFunds.map(f => `
                            <th style="padding: 8px; border: 1px solid #ddd; background: #ffe4e1; font-size: 8px;">מס ${(f.fund_name || 'קצבה').substring(0, 12)}</th>
                            <th style="padding: 8px; border: 1px solid #ddd; font-size: 8px;">${(f.fund_name || 'קצבה').substring(0, 12)}</th>
                        `).join('')}
                        ${additionalIncomes.map(i => `
                            <th style="padding: 8px; border: 1px solid #ddd; background: #ffe4e1; font-size: 8px;">מס ${(i.description || 'הכנסה').substring(0, 12)}</th>
                            <th style="padding: 8px; border: 1px solid #ddd; font-size: 8px;">${(i.description || 'הכנסה').substring(0, 12)}</th>
                        `).join('')}
                        ${capitalAssets.filter(asset => (parseFloat(asset.monthly_income) || 0) > 0).map(asset => `
                            <th style="padding: 8px; border: 1px solid #ddd; background: #ffe4e1; font-size: 8px;">מס ${(asset.description || asset.asset_name || 'נכס').substring(0, 12)}</th>
                            <th style="padding: 8px; border: 1px solid #ddd; background: #fff8f0; font-size: 8px;">${(asset.description || asset.asset_name || 'נכס').substring(0, 12)} (חד פעמי)</th>
                        `).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${yearlyProjection.map((year, index) => `
                        <tr style="background: ${index % 2 === 0 ? '#f8f9fa' : 'white'};">
                            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${year.year}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; background: #f0f8ff;">₪${year.netMonthlyIncome.toLocaleString()}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; background: #ffe4e1;">₪${year.totalMonthlyTax.toLocaleString()}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">₪${year.totalMonthlyIncome.toLocaleString()}</td>
                            ${year.incomeBreakdown.map((income, i) => `
                                <td style="padding: 8px; border: 1px solid #ddd; background: #ffe4e1;">₪${(year.taxBreakdown[i] || 0).toLocaleString()}</td>
                                <td style="padding: 8px; border: 1px solid #ddd;">₪${income.toLocaleString()}</td>
                            `).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <strong>הערות:</strong>
            <ul style="margin: 10px 0;">
                <li>הטבלה מציגה פירוט מלא של כל מקורות ההכנסה והמס החל עליהם</li>
                <li>המס מחושב לפי מדרגות המס הרלוונטיות לכל שנה</li>
                <li>הפטור ממס מופעל אוטומטית על הקצבאות הפנסיוניות</li>
                <li>הערכים מוצגים בשקלים חדשים ללא הצמדה</li>
            </ul>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; color: #666; font-size: 12px;">
        דוח זה נוצר במערכת תכנון פרישה • ${formatDateToDDMMYY(new Date())}
    </div>
</body>
</html>`;

    // פתיחת חלון חדש עם הדוח
    const newWindow = window.open('', '_blank');
    if (newWindow) {
      newWindow.document.write(htmlContent);
      newWindow.document.close();
      alert('דוח HTML נפתח בחלון חדש. לחץ על כפתור "הדפס לPDF" כדי לשמור כקובץ PDF');
    } else {
      alert('לא ניתן לפתוח חלון חדש. אנא אפשר חלונות קופצים');
    }
  };

  const handleGenerateExcel = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // יצירת דוח Excel מקיף עם הנתונים הקיימים
      const yearlyProjection = generateYearlyProjection();
      createExcelReport(yearlyProjection);
      
      alert('דוח Excel מקיף נוצר בהצלחה!');
    } catch (err: any) {
      console.error('שגיאה ביצירת דוח Excel:', err);
      setError('שגיאה ביצירת דוח Excel: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const oldHandleGenerateExcel = async () => {
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

  const handleGenerateFixationPackage = async () => {
    try {
      setLoading(true);
      setError(null);

      console.log(`🔵 Generating fixation package for client ${id}`);
      
      // קריאה ל-API endpoint ליצירת חבילת מסמכים
      const response = await axios.post(`/api/v1/fixation/${id}/package`);
      
      if (response.data.success) {
        const folder = response.data.folder;
        const files = response.data.files || [];
        
        let message = 'חבילת מסמכי קיבוע זכויות נוצרה בהצלחה!\n\n';
        message += `התיקייה: ${folder}\n\n`;
        message += 'קבצים שנוצרו:\n';
        files.forEach((file: string) => {
          message += `• ${file}\n`;
        });
        
        alert(message);
      } else {
        throw new Error('שגיאה ביצירת המסמכים');
      }
    } catch (err: any) {
      console.error('שגיאה ביצירת מסמכי קיבוע זכויות:', err);
      const errorMsg = err.response?.data?.detail?.error || err.message || 'שגיאה לא ידועה';
      setError('שגיאה ביצירת מסמכי קיבוע זכויות: ' + errorMsg);
      alert('שגיאה ביצירת מסמכי קיבוע זכויות: ' + errorMsg);
    } finally {
      setLoading(false);
    }
  };

  if (loading && (!pensionFunds || !additionalIncomes || !capitalAssets)) {
    return <div style={{ padding: '20px' }}>טוען נתוני דוח...</div>;
  }

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">📊 תוצאות</h1>
            <p className="card-subtitle">תזרים מזומנים, חישוב מס ותוצאות פנסיוניות</p>
          </div>
          <button onClick={() => navigate(`/clients/${id}`)} className="btn btn-secondary">
            ← חזרה
          </button>
        </div>

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
        
        {/* הודעה על פתרון HTML לPDF */}
        <div style={{
          backgroundColor: '#d1ecf1',
          border: '1px solid #bee5eb',
          borderRadius: '4px',
          padding: '12px',
          marginBottom: '15px',
          fontSize: '14px'
        }}>
          <strong>🎉 פתרון מושלם!</strong> דוח PDF כעת נוצר כעמוד HTML עם תמיכה מלאה בעברית!
          <br />
          הדוח ייפתח בחלון חדש עם כפתור "הדפס לPDF" - פשוט לחץ עליו כדי לשמור כקובץ PDF.
          <br />
          <strong>דוח Excel</strong> זמין גם כן לניתוח נתונים מפורט.
          <br />
          <strong>📋 מסמכי קיבוע זכויות</strong> - מפיק טופס 161ד רשמי + נספחי מענקים וקצבאות מקצועיים!
        </div>
        
        <div style={{ display: 'flex', gap: '15px', marginBottom: '15px', flexWrap: 'wrap' }}>
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
              fontSize: '16px',
              fontWeight: 'bold'
            }}
          >
            {loading ? 'יוצר...' : '📄 הורד דוח PDF מקיף'}
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
              fontSize: '16px',
              fontWeight: 'bold'
            }}
          >
            {loading ? 'יוצר...' : '📗 הורד דוח Excel מקיף'}
          </button>

          <button
            onClick={() => {
              console.log('🔴🔴🔴 BUTTON CLICKED! 🔴🔴🔴');
              handleGenerateFixationPackage();
            }}
            disabled={loading}
            style={{
              backgroundColor: loading ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px',
              fontWeight: 'bold'
            }}
          >
            {loading ? 'מפיק...' : '📋 הפק מסמכי קיבוע זכויות (טופס 161ד)'}
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
              <div><strong>שם:</strong> {client?.first_name && client?.last_name ? `${client.first_name} ${client.last_name}` : 'לא צוין'}</div>
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
              }}>קצבאות</h5>
              
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
                      <div>קצבה חודשית: ₪{(fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {fund.pension_start_date ? formatDateToDDMMYY(new Date(fund.pension_start_date)) : (fund.start_date ? formatDateToDDMMYY(new Date(fund.start_date)) : 'לא צוין')}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין קצבאות</div>
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
                      <div><strong>{income.description || income.source_type || 'הכנסה נוספת'}</strong></div>
                      <div>הכנסה חודשית: ₪{(() => {
                        const amount = income.amount || 0;
                        if (income.frequency === 'monthly') return amount.toLocaleString();
                        if (income.frequency === 'quarterly') return (amount / 3).toLocaleString();
                        if (income.frequency === 'annually') return (amount / 12).toLocaleString();
                        return amount.toLocaleString();
                      })()}</div>
                      <div>הכנסה שנתית: ₪{(() => {
                        const amount = income.amount || 0;
                        if (income.frequency === 'monthly') return (amount * 12).toLocaleString();
                        if (income.frequency === 'quarterly') return (amount * 4).toLocaleString();
                        if (income.frequency === 'annually') return amount.toLocaleString();
                        return (amount * 12).toLocaleString();
                      })()}</div>
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
                      <div>מיסוי: {asset.tax_treatment === 'tax_spread' ? `פריסת מס (${asset.spread_years || 0} שנים)` : asset.tax_treatment || 'רגיל'}</div>
                      <div>ערך נוכחי: ₪{asset.current_value?.toLocaleString() || 0}</div>
                      <div>תשואה שנתית: {
                        asset.annual_return_rate > 1 ? asset.annual_return_rate : 
                        asset.annual_return_rate ? (asset.annual_return_rate * 100) : 
                        asset.annual_return || 0
                      }%</div>
                      <div>תאריך תשלום: {asset.start_date || 'לא צוין'}</div>
                      <div>תאריך סיום: {asset.end_date || 'לא רלוונטי'}</div>
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
                  // רק קצבאות + הכנסות נוספות חודשיות (ללא נכסי הון)
                  const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                    sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
                  const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => {
                    const amount = parseFloat(income.amount) || 0;
                    // רק הכנסות חודשיות
                    if (income.frequency === 'monthly') return sum + amount;
                    return sum;
                  }, 0);
                  return (monthlyPension + monthlyAdditional).toLocaleString();
                })()}</div>
                <div><strong>סך הנכסים:</strong> ₪{(() => {
                  // רק נכסי הון (ללא יתרות קצבאות)
                  const totalCapitalAssets = capitalAssets.reduce((sum: number, asset: any) => 
                    sum + (parseFloat(asset.current_value) || 0), 0);
                  return totalCapitalAssets.toLocaleString();
                })()}</div>
                <div><strong>תאריך התחלת תזרים:</strong> {(() => {
                  // המאוחר מבין 01/01/השנה הנוכחית או 01/01/שנת הקצבה הראשונה
                  const currentYear = new Date().getFullYear();
                  const firstPensionYear = pensionFunds.length > 0 ? Math.min(
                    ...pensionFunds.map((fund: any) => 
                      fund.start_date ? parseInt(fund.start_date.split('-')[0]) : currentYear + 100
                    )
                  ) : currentYear + 100;
                  const startYear = Math.max(currentYear, firstPensionYear < currentYear + 100 ? firstPensionYear : currentYear);
                  return `01/01/${startYear}`;
                })()}</div>
                <div><strong>סך הכנסות חד פעמיות:</strong> ₪{(() => {
                  // ✅ סך תשלומי נכסי הון (monthly_income), לא current_value!
                  const totalOneTime = capitalAssets.reduce((sum: number, asset: any) => 
                    sum + (parseFloat(asset.monthly_income) || 0), 0);
                  return totalOneTime.toLocaleString();
                })()}</div>
                <div><strong>סך הכנסות בתדירות שנתית:</strong> ₪{(() => {
                  // רק הכנסות נוספות שנתיות
                  const annualIncomes = additionalIncomes.reduce((sum: number, income: any) => {
                    const amount = parseFloat(income.amount) || 0;
                    if (income.frequency === 'annually') return sum + amount;
                    return sum;
                  }, 0);
                  return annualIncomes.toLocaleString();
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
                    // חישוב הכנסה שנתית נוכחית - רק הכנסות חודשיות כפול 12
                    const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                      sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
                    const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => {
                      const amount = parseFloat(income.amount) || 0;
                      // רק הכנסות חודשיות
                      if (income.frequency === 'monthly') {
                        return sum + amount;
                      }
                      return sum;
                    }, 0);
                    const totalMonthlyIncome = monthlyPension + monthlyAdditional;
                    const totalAnnualIncome = totalMonthlyIncome * 12;
                    
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
                    
                    // חישוב קצבה פטורה מקיבוע זכויות לשנה הנוכחית
                    const currentYear = new Date().getFullYear();
                    let currentExemptPension = 0;
                    if (fixationData && fixationData.exemption_summary) {
                      const eligibilityYear = fixationData.eligibility_year || fixationData.exemption_summary.eligibility_year;
                      if (currentYear >= eligibilityYear) {
                        const exemptionPercentage = fixationData.exemption_summary.exemption_percentage || 0;
                        const remainingExemptCapital = fixationData.exemption_summary.remaining_exempt_capital || 0;
                        
                        if (currentYear === eligibilityYear) {
                          // שנת הקיבוע
                          currentExemptPension = remainingExemptCapital / 180;
                        } else {
                          // שנים אחרי הקיבוע
                          const pensionCeiling = getPensionCeiling(currentYear);
                          const capitalPercentage = getExemptCapitalPercentage(currentYear);
                          const theoreticalCapital = pensionCeiling * 180 * capitalPercentage;
                          currentExemptPension = (exemptionPercentage * theoreticalCapital) / 180;
                        }
                      }
                    }
                    
                    return (
                      <div>
                        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                          <strong>סך הכנסה שנתית: ₪{totalAnnualIncome.toLocaleString()}</strong>
                          <div>הכנסה חודשית: ₪{totalMonthlyIncome.toLocaleString()}</div>
                          {currentExemptPension > 0 && (
                            <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#d4edda', borderRadius: '4px', border: '1px solid #c3e6cb' }}>
                              <strong style={{ color: '#155724' }}>קצבה פטורה (קיבוע זכויות): ₪{currentExemptPension.toLocaleString()}</strong>
                              <div style={{ fontSize: '12px', color: '#155724', marginTop: '4px' }}>
                                פטור חודשי המופחת מההכנסה החייבת מקצבאות
                              </div>
                            </div>
                          )}
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
              
              // המרת תזרים חודשי לתזרים שנתי
              const annualNetCashFlows = yearlyProjection.map(yearData => yearData.netMonthlyIncome * 12);
              
              // חישוב ה-NPV עם שיעור היוון של 3%
              const discountRate = 0.03; // 3%
              const cashflowNPV = calculateNPV(annualNetCashFlows, discountRate);
              
              // חישוב NPV של נכסי הון
              const capitalAssetsNPVResults = calculateCapitalAssetsNPV();
              const capitalNPV = capitalAssetsNPVResults.reduce((sum, item) => sum + item.npvAfterTax, 0);
              
              // Debug: הצגת מידע על נכסי הון
              console.log('🏦 Capital Assets Info:');
              console.log('  Number of assets:', capitalAssets?.length || 0);
              if (capitalAssets && capitalAssets.length > 0) {
                capitalAssets.forEach((asset, i) => {
                  console.log(`  Asset ${i + 1}:`, {
                    name: asset.asset_name,
                    type: asset.asset_type,
                    value: asset.current_value,
                    return: asset.annual_return_rate
                  });
                });
              }
              console.log('  Calculated Capital NPV:', capitalNPV);
              
              return (
                <div style={{ marginBottom: '20px' }}>
                  {/* NPV של נכסי הון - מוצג תמיד */}
                  <div style={{ 
                    marginBottom: '10px',
                    padding: '15px', 
                    backgroundColor: '#fff3cd', 
                    borderRadius: '4px',
                    border: '1px solid #ffc107'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>ערך נוכחי נקי (NPV) של נכסי הון:</strong>
                        <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
                          נכסים שאינם מופיעים בתזרים החודשי (מהוון ב-{(discountRate * 100).toFixed(1)}%)
                        </div>
                      </div>
                      <div style={{ 
                        fontSize: '24px', 
                        fontWeight: 'bold', 
                        color: '#856404',
                        direction: 'ltr',
                        textAlign: 'left'
                      }}>
                        ₪{Math.round(capitalNPV).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  
                  {/* NPV של התזרים */}
                  <div style={{ 
                    padding: '15px', 
                    backgroundColor: '#e8f5e9', 
                    borderRadius: '4px',
                    border: '1px solid #c8e6c9'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>ערך נוכחי נקי (NPV) של התזרים:</strong>
                        <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
                          הכנסות חודשיות נטו מהוונות בשיעור של {(discountRate * 100).toFixed(1)}% לשנה
                        </div>
                      </div>
                      <div style={{ 
                        fontSize: '24px', 
                        fontWeight: 'bold', 
                        color: '#2e7d32',
                        direction: 'ltr',
                        textAlign: 'left'
                      }}>
                        ₪{Math.round(cashflowNPV).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  
                  {/* סה"כ NPV - מוצג תמיד */}
                  <div style={{ 
                    marginTop: '10px',
                    padding: '15px', 
                    backgroundColor: '#d1ecf1', 
                    borderRadius: '4px',
                    border: '2px solid #17a2b8'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>סך הכל NPV:</strong>
                        <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
                          סכום של תזרים + נכסי הון
                        </div>
                      </div>
                      <div style={{ 
                        fontSize: '28px', 
                        fontWeight: 'bold', 
                        color: '#0c5460',
                        direction: 'ltr',
                        textAlign: 'left'
                      }}>
                        ₪{Math.round(cashflowNPV + capitalNPV).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  
                  {/* טבלת פירוט נכסי הון שלא בתזרים */}
                  {(() => {
                    const capitalAssetsNPVResults = calculateCapitalAssetsNPV();
                    if (capitalAssetsNPVResults.length > 0) {
                      return (
                        <div style={{ 
                          marginTop: '20px',
                          padding: '15px', 
                          backgroundColor: '#f8f9fa', 
                          borderRadius: '4px',
                          border: '1px solid #dee2e6'
                        }}>
                          <h3 style={{ marginBottom: '15px', color: '#495057' }}>
                            📊 פירוט נכסי הון (לא מוצגים בתזרים)
                          </h3>
                          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                              <tr style={{ backgroundColor: '#e9ecef' }}>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>שם הנכס</th>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>ערך נוכחי</th>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>תשואה שנתית</th>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>הצמדה</th>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>יחס מס</th>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#d4edda' }}>NPV לפני מס</th>
                                <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#c3e6cb' }}>NPV אחרי מס</th>
                              </tr>
                            </thead>
                            <tbody>
                              {capitalAssetsNPVResults.map((result, index) => {
                                const asset = result.asset;
                                const indexationLabel = asset.indexation_method === 'fixed' 
                                  ? `קבוע ${(asset.fixed_rate * 100).toFixed(2)}%`
                                  : asset.indexation_method === 'cpi' 
                                  ? 'מדד'
                                  : 'ללא';
                                const taxLabel = asset.tax_treatment === 'exempt' 
                                  ? 'פטור'
                                  : asset.tax_treatment === 'capital_gains'
                                  ? 'רווח הון'
                                  : asset.tax_treatment === 'fixed_rate'
                                  ? `${(asset.tax_rate || 0).toFixed(1)}%`
                                  : 'רגיל';
                                
                                return (
                                  <tr key={index} style={{ backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa' }}>
                                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                                      {asset.asset_name || asset.description || 'ללא שם'}
                                    </td>
                                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left' }}>
                                      ₪{parseFloat(asset.current_value || 0).toLocaleString()}
                                    </td>
                                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'center' }}>
                                      {((asset.annual_return_rate || 0) * 100).toFixed(2)}%
                                    </td>
                                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'center' }}>
                                      {indexationLabel}
                                    </td>
                                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'center' }}>
                                      {taxLabel}
                                    </td>
                                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#d4edda', fontWeight: 'bold' }}>
                                      ₪{result.npv.toLocaleString()}
                                    </td>
                                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#c3e6cb', fontWeight: 'bold' }}>
                                      ₪{result.npvAfterTax.toLocaleString()}
                                    </td>
                                  </tr>
                                );
                              })}
                              <tr style={{ backgroundColor: '#e9ecef', fontWeight: 'bold' }}>
                                <td colSpan={5} style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                                  סה"כ:
                                </td>
                                <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#d4edda' }}>
                                  ₪{capitalAssetsNPVResults.reduce((sum, r) => sum + r.npv, 0).toLocaleString()}
                                </td>
                                <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#c3e6cb' }}>
                                  ₪{capitalAssetsNPVResults.reduce((sum, r) => sum + r.npvAfterTax, 0).toLocaleString()}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                          <div style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                            * חישוב NPV מבוסס על תחזית 10 שנים עם שיעור היוון של 3%
                          </div>
                        </div>
                      );
                    }
                    return null;
                  })()}
                </div>
              );
            })()}
            
            <div style={{ maxHeight: '400px', overflowY: 'auto', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1200px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#e9ecef' }}>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', position: 'sticky', left: 0, backgroundColor: '#e9ecef' }}>שנה</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#f0f8ff' }}>הכנסה נטו</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold', backgroundColor: '#ffe4e1' }}>סה"כ מס</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold' }}>סה"כ הכנסה</th>
                    {pensionFunds.map(fund => (
                      <React.Fragment key={`fund-${fund.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {fund.fund_name}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>
                          {fund.fund_name} {fund.fund_number ? `(${fund.fund_number})` : ''}
                        </th>
                      </React.Fragment>
                    ))}
                    {additionalIncomes.map(income => (
                      <React.Fragment key={`income-${income.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {income.description || income.source_type || 'הכנסה נוספת'}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>
                          {income.description || income.source_type || 'הכנסה נוספת'}
                        </th>
                      </React.Fragment>
                    ))}
                    {capitalAssets.filter(asset => (parseFloat(asset.monthly_income) || 0) > 0).map(asset => (
                      <React.Fragment key={`asset-${asset.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {asset.description || asset.asset_name || 'נכס הון'}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#fff8f0' }}>
                          {asset.description || asset.asset_name || 'נכס הון'} (תשלום חד פעמי)
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
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold', backgroundColor: '#ffe4e1' }}>
                        ₪{yearData.totalMonthlyTax.toLocaleString()}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold' }}>
                        ₪{yearData.totalMonthlyIncome.toLocaleString()}
                      </td>
                      {yearData.incomeBreakdown.map((income, i) => (
                        <React.Fragment key={i}>
                          <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#ffe4e1' }}>
                            ₪{(yearData.taxBreakdown[i] || 0).toLocaleString()}
                          </td>
                          <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left' }}>
                            ₪{income.toLocaleString()}
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

      {!loading && pensionFunds.length === 0 && additionalIncomes.length === 0 && capitalAssets.length === 0 && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fff3cd', 
          borderRadius: '4px',
          textAlign: 'center',
          color: '#856404'
        }}>
          אין מספיק נתונים ליצירת דוח. יש להוסיף קצבאות, הכנסות נוספות או נכסי הון תחילה.
          <div style={{ marginTop: '10px' }}>
            <a href={`/clients/${id}/pension-funds`} style={{ color: '#007bff', textDecoration: 'none', marginRight: '15px' }}>
              הוסף קצבאות ←
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
    </div>
  );
};

export default SimpleReports;
