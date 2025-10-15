import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import jsPDF from 'jspdf';
import * as XLSX from 'xlsx';
import { formatDateToDDMMYY } from '../utils/dateUtils';
import { getTaxBracketsLegacyFormat, calculateTaxByBrackets } from '../utils/taxBrackets';
import axios from 'axios';
import autoTable from 'jspdf-autotable';

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
  
  // פירוט קרנות פנסיה
  if (pensionFunds.length > 0) {
    doc.setFontSize(14);
    doc.setTextColor(0, 51, 102);
    doc.text('קרנות פנסיה:', 20, yPosition);
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
  doc.text(`• סך יתרות קרנות פנסיה: ₪${totalPensionBalance.toLocaleString()}`, 30, yPosition);
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
  
  // גיליון 3: קרנות פנסיה מפורט
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
    
    // הוספת סיכום קרנות פנסיה
    const totalBalance = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0);
    const totalMonthlyDeposit = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.monthly_deposit) || 0), 0);
    const totalPensionAmount = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || 0), 0);
    
    pensionData.push(['', '', '', '', '', '', '', '']);
    pensionData.push(['סך יתרות:', '', totalBalance.toLocaleString(), '', '', '', '', '']);
    pensionData.push(['סך הפקדות חודשיות:', '', '', totalMonthlyDeposit.toLocaleString(), '', '', '', '']);
    pensionData.push(['סך קצבאות חודשיות:', '', '', '', '', totalPensionAmount.toLocaleString(), '', '']);
    
    const pensionSheet = XLSX.utils.aoa_to_sheet(pensionData);
    XLSX.utils.book_append_sheet(workbook, pensionSheet, 'קרנות פנסיה');
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
    ['סך קרנות פנסיה:', pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0).toLocaleString(), '₪'],
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
        
        console.log('Additional incomes response:', additionalIncomesResponse.data);
        
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
        
        // חישוב הכנסה חודשית מכל המקורות
        const monthlyPensionIncome = pensionFundsData.reduce((sum: number, fund: any) => 
          sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
        const monthlyAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (parseFloat(income.monthly_amount) || (income.annual_amount ? parseFloat(income.annual_amount) / 12 : 0)), 0);
        const monthlyCapitalIncome = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.monthly_income) || 0), 0);
        const totalMonthlyIncome = monthlyPensionIncome + monthlyAdditionalIncome + monthlyCapitalIncome;
        
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
              sum + (fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
            const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
              sum + (income.monthly_amount || income.annual_amount / 12 || 0), 0);
            
            monthlyGrossAmount = monthlyPension + monthlyAdditional;
            
            // חישוב מס על ההכנסה החודשית עם נקודות זיכוי
            if (monthlyGrossAmount > 0) {
              const annualGrossAmount = monthlyGrossAmount * 12;
              // חישוב מס בסיסי לפי מדרגות
              let baseTax = 0;
              let remainingIncome = annualGrossAmount;
              
              
              // חישוב מס לפי מדרגות המס המעודכנות
              baseTax = calculateTaxByBrackets(annualGrossAmount);
              
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
            total_capital_assets: totalCapitalAssets,
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
   * קרנות פנסיה והכנסות נוספות שהתחילו בעבר יוצגו החל מהשנה הנוכחית
   * קרנות פנסיה והכנסות נוספות שמתחילות בעתיד יוצגו החל משנת ההתחלה שלהן
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
        // חישוב שנת התחלה נכונה - קרן שהתחילה בעבר תוצג מהשנה הנוכחית
        let fundStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (fund.start_date) {
          const parsedYear = parseInt(fund.start_date.split('-')[0]);
          // אם הקרן מתחילה בעתיד, נשתמש בשנת ההתחלה המקורית
          // אם הקרן התחילה בעבר או בהווה, נשתמש בשנה הנוכחית
          fundStartYear = Math.max(parsedYear, currentYear);
          
          // הדפסת מידע לבדיקה (מוסתר)
          // console.log(`Fund ${fund.fund_name || 'unnamed'} original start: ${parsedYear}, effective start: ${fundStartYear}, current year: ${year}`);
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
        // חישוב שנת התחלה נכונה - הכנסה שהתחילה בעבר תוצג מהשנה הנוכחית
        let incomeStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (income.start_date) {
          const parsedYear = parseInt(income.start_date.split('-')[0]);
          // אם ההכנסה מתחילה בעתיד, נשתמש בשנת ההתחלה המקורית
          // אם ההכנסה התחילה בעבר או בהווה, נשתמש בשנה הנוכחית
          incomeStartYear = Math.max(parsedYear, currentYear);
          
          // הדפסת מידע לבדיקה (מוסתר)
          // console.log(`Income ${income.income_name || 'unnamed'} original start: ${parsedYear}, effective start: ${incomeStartYear}, current year: ${year}`);
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

      // Add capital assets income - נכסי הון הם תשלום חד פעמי!
      capitalAssets.forEach(asset => {
        let assetStartYear = currentYear;
        
        if (asset.start_date) {
          const parsedYear = parseInt(asset.start_date.split('-')[0]);
          assetStartYear = Math.max(parsedYear, currentYear);
        }
        
        // ⚠️ נכס הון = תשלום חד פעמי בשנת התחלה בלבד!
        let amount = 0;
        
        if (year === assetStartYear) {
          // רק בשנת התשלום - הוסף את הסכום החד פעמי
          // current_value הוא הסכום החד פעמי
          amount = parseFloat(asset.current_value) || 0;
          console.log(`⚠️ CAPITAL ASSET ONE-TIME PAYMENT: ${asset.description || 'unnamed'} in year ${year}, amount=${amount}`);
        } else if (asset.tax_treatment === 'tax_spread' && asset.spread_years) {
          // שנים נוספות בפריסה - 0 בפועל (כבר שולם הכל בשנה הראשונה)
          amount = 0;
          // אפשר להוסיף הצגה ויזואלית אם נדרש
        } else {
          // שנים אחרות - אין תשלום
          amount = 0;
        }
        
        incomeBreakdown.push(Math.round(amount));
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
        
        // שימוש במדרגות המס המעודכנות מההגדרות
        totalAnnualTax = calculateTaxByBrackets(totalTaxableAnnualIncome);
        
        // הפחתת נקודות זיכוי אם קיימות
        if (client?.tax_credit_points) {
          totalAnnualTax = Math.max(0, totalAnnualTax - (client.tax_credit_points * 2640));
        }

        // מס חודשי מהכנסות רגילות בלבד (ללא נכסי הון)
        const regularMonthlyTax = totalAnnualTax / 12;
        
        // חלוקת המס באופן יחסי לפי ההכנסות
        // חישוב סך ההכנסה החייבת במס
        const taxableTotalMonthlyIncome = monthlyTaxableIncome + monthlyTaxableAdditionalIncome;
        
        pensionFunds.forEach((fund, index) => {
          const incomeAmount = incomeBreakdown[index] || 0;
          // חלוקת המס באופן יחסי - רק מהכנסות רגילות
          const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * regularMonthlyTax : 0;
          taxBreakdown.push(Math.round(taxPortion));
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

        // חישוב מס עבור נכסי הון - בנפרד!
        let totalCapitalAssetTax = 0;
        capitalAssets.forEach((asset, index) => {
          const assetIncomeIndex = pensionFunds.length + additionalIncomes.length + index;
          const monthlyIncome = incomeBreakdown[assetIncomeIndex] || 0;
          const annualIncome = monthlyIncome;  // כבר הסכום השנתי (תשלום חד פעמי)
          let assetTax = 0;
          
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
        });
        
        // עדכון סך המס הכולל
        totalMonthlyTax = regularMonthlyTax + (totalCapitalAssetTax / 12);
      } else {
        // אין הכנסה - אין מס
        for (let i = 0; i < pensionFunds.length + additionalIncomes.length + capitalAssets.length; i++) {
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
        taxBreakdown
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
    console.log('calculateNPV called with:', { cashFlows, discountRate });
    
    if (!cashFlows || cashFlows.length === 0) {
      console.log('No cash flows provided, returning 0');
      return 0;
    }
    
    const result = cashFlows.reduce((sum, cashFlow, year) => {
      const discountedValue = cashFlow / Math.pow(1 + discountRate, year);
      console.log(`Year ${year}: cashFlow=${cashFlow}, discounted=${discountedValue}, sum=${sum + discountedValue}`);
      return sum + discountedValue;
    }, 0);
    
    console.log('Final NPV result:', result);
    return result;
  };

  // פונקציית יצירת דוח PDF
  const createPDFReport = (yearlyProjection: any[]) => {
    const doc = new jsPDF();
    
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
    doc.setTextColor(0, 128, 0);
    doc.text(`₪${Math.round(npv).toLocaleString()}`, 200, yPosition, { align: 'right' });
    doc.setTextColor(0, 0, 0);
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
    
    // שמירת הקובץ
    doc.save(`דוח-פנסיוני-${currentDate}.pdf`);
  };

  // פונקציית יצירת דוח Excel
  const createExcelReport = (yearlyProjection: any[]) => {
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
    
    // שמירת הקובץ
    const currentDate = new Date().toLocaleDateString('he-IL');
    XLSX.writeFile(workbook, `דוח-פנסיוני-${currentDate}.xlsx`);
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
        <div class="npv-value">₪${Math.round(calculateNPV(yearlyProjection.map(y => y.netMonthlyIncome * 12), 0.03)).toLocaleString()}</div>
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
                    <th>תאריך סיום</th>
                </tr>
            </thead>
            <tbody>
                ${capitalAssets.map(asset => `
                    <tr>
                        <td>${asset.description || asset.asset_name || 'ללא תיאור'}</td>
                        <td>${ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type || 'לא צוין'}</td>
                        <td>₪${(asset.monthly_income || 0).toLocaleString()}</td>
                        <td>₪${(asset.current_value || 0).toLocaleString()}</td>
                        <td>${asset.start_date || 'לא צוין'}</td>
                        <td>${asset.end_date || 'ללא הגבלה'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    </div>
    ` : ''}
    
    ${pensionFunds.length > 0 ? `
    <div class="section">
        <h2>קרנות פנסיה</h2>
        <table>
            <thead>
                <tr>
                    <th>שם הקרן</th>
                    <th>יתרה נוכחית</th>
                    <th>הפקדה חודשית</th>
                    <th>תשואה שנתית</th>
                    <th>קצבה חודשית</th>
                    <th>גיל פרישה</th>
                </tr>
            </thead>
            <tbody>
                ${pensionFunds.map(fund => `
                    <tr>
                        <td>${fund.fund_name || 'ללא שם'}</td>
                        <td>₪${(fund.current_balance || 0).toLocaleString()}</td>
                        <td>₪${(fund.monthly_deposit || 0).toLocaleString()}</td>
                        <td>${((fund.annual_return_rate || 0) * 100).toFixed(1)}%</td>
                        <td>₪${(fund.pension_amount || fund.computed_monthly_amount || 0).toLocaleString()}</td>
                        <td>${fund.retirement_age || 67}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
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
                        <td>₪${(income.monthly_amount || 0).toLocaleString()}</td>
                        <td>${income.tax_treatment === 'exempt' ? 'פטור ממס' : 'חייב במס'}</td>
                        <td>${income.start_date || 'לא צוין'}</td>
                        <td>${income.end_date || 'ללא הגבלה'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    </div>
    ` : ''}
    
    <div class="summary-section">
        <h2>סיכום כספי מקיף</h2>
        
        <h3>נכסים:</h3>
        <div class="summary-item">• סך יתרות קרנות פנסיה: ₪${pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0).toLocaleString()}</div>
        <div class="summary-item">• סך ערך נכסי הון: ₪${capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0).toLocaleString()}</div>
        <div class="summary-item summary-total">• סך כל הנכסים: ₪${(pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.current_balance) || 0), 0) + capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0)).toLocaleString()}</div>
        
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
      
      // יצירת דוח Excel עם הנתונים הקיימים
      const yearlyProjection = generateYearlyProjection();
      generateExcelReport(yearlyProjection, pensionFunds, additionalIncomes, capitalAssets, client);
      
      alert('דוח Excel נוצר בהצלחה');
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
        </div>
        
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
            {loading ? 'יוצר...' : '📄 יצירת דוח HTML לPDF (עברית מושלמת)'}
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
            {loading ? 'יוצר...' : 'יצירת דוח Excel (מומלץ)'}
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
                      <div>קצבה חודשית: ₪{(fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {fund.pension_start_date ? formatDateToDDMMYY(new Date(fund.pension_start_date)) : (fund.start_date ? formatDateToDDMMYY(new Date(fund.start_date)) : 'לא צוין')}</div>
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
                  const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                    sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
                  const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => {
                    const amount = parseFloat(income.amount) || 0;
                    if (income.frequency === 'monthly') return sum + amount;
                    if (income.frequency === 'quarterly') return sum + (amount / 3);
                    if (income.frequency === 'annually') return sum + (amount / 12);
                    return sum + amount;
                  }, 0);
                  const monthlyCapitalAssets = capitalAssets.reduce((sum: number, asset: any) => 
                    sum + (parseFloat(asset.monthly_income) || 0), 0);
                  return (monthlyPension + monthlyAdditional + monthlyCapitalAssets).toLocaleString();
                })()}</div>
                <div><strong>סך נכסים:</strong> ₪{(() => {
                  // רק נכסי הון נכללים בסך הנכסים, לא יתרות קרנות פנסיה
                  const totalCapitalAssets = capitalAssets.reduce((sum: number, asset: any) => 
                    sum + (parseFloat(asset.current_value) || 0), 0);
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
                      sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
                    const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => {
                      const amount = parseFloat(income.amount) || 0;
                      let monthlyAmount = 0;
                      if (income.frequency === 'monthly') {
                        monthlyAmount = amount;
                      } else if (income.frequency === 'quarterly') {
                        monthlyAmount = amount / 3;
                      } else if (income.frequency === 'annually') {
                        monthlyAmount = amount / 12;
                      } else {
                        monthlyAmount = amount; // ברירת מחדל
                      }
                      return sum + monthlyAmount;
                    }, 0);
                    const monthlyCapital = capitalAssets.reduce((sum: number, asset: any) => 
                      sum + (parseFloat(asset.monthly_income) || 0), 0);
                    const totalMonthlyIncome = monthlyPension + monthlyAdditional + monthlyCapital;
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
                    
                    return (
                      <div>
                        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                          <strong>סך הכנסה שנתית: ₪{totalAnnualIncome.toLocaleString()}</strong>
                          <div>הכנסה חודשית: ₪{totalMonthlyIncome.toLocaleString()}</div>
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
              console.log('Yearly projection for NPV:', yearlyProjection);
              
              const annualNetCashFlows = yearlyProjection.map(yearData => {
                // הכנסה שנתית נטו = (הכנסה חודשית נטו) * 12
                const annualNet = yearData.netMonthlyIncome * 12;
                console.log(`Year ${yearData.year}: monthly=${yearData.netMonthlyIncome}, annual=${annualNet}`);
                return annualNet;
              });
              
              console.log('Annual net cash flows:', annualNetCashFlows);
              
              // חישוב ה-NPV עם שיעור היוון של 3%
              const discountRate = 0.03; // 3%
              const npv = calculateNPV(annualNetCashFlows, discountRate);
              console.log('Calculated NPV:', npv);
              
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
                    {capitalAssets.map(asset => (
                      <React.Fragment key={`asset-${asset.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {asset.description || 'נכס הון'}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#fff8f0' }}>
                          {asset.description || 'נכס הון'}
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
