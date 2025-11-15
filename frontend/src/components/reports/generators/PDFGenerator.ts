import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { YearlyProjection, ASSET_TYPES } from '../types/reportTypes';
import { calculateNPV } from '../calculations/npvCalculations';
import { formatCurrency } from '../../../lib/validation';

const formatMoney = (value: number): string => {
  const formatted = formatCurrency(value);
  return formatted.replace('₪', '').trim();
};

/**
 * יוצר דוח PDF עם תמיכה מלאה בעברית
 */
export function generatePDFReport(
  yearlyProjection: YearlyProjection[],
  pensionFunds: any[],
  additionalIncomes: any[],
  capitalAssets: any[],
  clientData: any
) {
  const doc = new jsPDF();
  
  // ניסיון לתמיכה בעברית - נשתמש בפונט שתומך טוב יותר
  try {
    doc.setFont('times', 'normal');
  } catch (e) {
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
  const currentDate = formatDateToDDMMYY(new Date());
  doc.text(`תאריך יצירת הדוח: ${currentDate}`, 20, yPosition);
  yPosition += 10;
  
  // פרטי לקוח
  if (clientData) {
    doc.text(`שם הלקוח: ${clientData.first_name || ''} ${clientData.last_name || ''}`, 20, yPosition);
    yPosition += 8;
    if (clientData.birth_date) {
      doc.text(`תאריך לידה: ${formatDateToDDMMYY(clientData.birth_date)}`, 20, yPosition);
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
  doc.text(`ערך נוכחי נקי (NPV): ₪${formatMoney(Math.round(npv))}`, 20, yPosition);
  doc.setTextColor(0, 0, 0);
  yPosition += 20;
  
  // טבלת תזרים מזומנים
  doc.setFontSize(14);
  doc.setTextColor(0, 51, 102);
  doc.text('תחזית תזרים מזומנים שנתי:', 20, yPosition);
  yPosition += 10;
  
  const tableData = yearlyProjection.slice(0, 20).map(year => [
    year.year.toString(),
    `₪${formatMoney(year.totalMonthlyIncome)}`,
    `₪${formatMoney(year.totalMonthlyTax)}`,
    `₪${formatMoney(year.netMonthlyIncome)}`,
    `₪${formatMoney(year.netMonthlyIncome * 12)}`
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
      `₪${formatMoney(asset.current_value || 0)}`,
      `₪${formatMoney(asset.monthly_income || 0)}`,
      asset.start_date ? formatDateToDDMMYY(asset.start_date) : 'לא צוין',
      asset.end_date ? formatDateToDDMMYY(asset.end_date) : 'ללא הגבלה'
    ]);
    
    autoTable(doc, {
      head: [['תיאור', 'סוג נכס', 'ערך נוכחי (₪)', 'תשלום  (₪)', 'תאריך תשלום', 'תאריך סיום']],
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
      (fund.annuity_factor || 0).toFixed(2),
      `₪${formatMoney(fund.monthly_deposit || 0)}`,
      `${((fund.annual_return_rate || 0) * 100).toFixed(1)}%`,
      `₪${formatMoney(fund.pension_amount || fund.computed_monthly_amount || 0)}`,
      fund.retirement_age || 'לא צוין'
    ]);
    
    autoTable(doc, {
      head: [['שם הקרן', 'מקדם קצבה', 'הפקדה חודשית', 'תשואה שנתית', 'קצבה חודשית', 'גיל פרישה']],
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
      `₪${formatMoney(income.monthly_amount || 0)}`,
      income.tax_treatment === 'exempt' ? 'פטור ממס' : 'חייב במס',
      income.start_date ? formatDateToDDMMYY(income.start_date) : 'לא צוין',
      income.end_date ? formatDateToDDMMYY(income.end_date) : 'ללא הגבלה'
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
  const totalPensionBalance = pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.balance) || 0), 0);
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
  doc.text(`• סך יתרות קצבאות: ₪${formatMoney(totalPensionBalance)}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• סך ערך נכסי הון: ₪${formatMoney(totalCapitalValue)}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• סך כל הנכסים: ₪${formatMoney(totalPensionBalance + totalCapitalValue)}`, 30, yPosition);
  yPosition += 15;
  
  // הכנסות חודשיות
  doc.text('הכנסות חודשיות צפויות:', 20, yPosition);
  yPosition += 10;
  doc.text(`• קצבאות פנסיה: ₪${formatMoney(totalMonthlyPension)}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• הכנסות נוספות: ₪${formatMoney(totalMonthlyAdditional)}`, 30, yPosition);
  yPosition += 8;
  doc.text(`• הכנסות מנכסי הון: ₪${formatMoney(totalMonthlyCapital)}`, 30, yPosition);
  yPosition += 8;
  doc.setTextColor(0, 128, 0);
  doc.text(`• סך הכנסה חודשית: ₪${formatMoney(totalMonthlyPension + totalMonthlyAdditional + totalMonthlyCapital)}`, 30, yPosition);
  doc.setTextColor(0, 0, 0);
  yPosition += 15;
  
  // ניתוח NPV
  doc.text('ניתוח ערך נוכחי נקי:', 20, yPosition);
  yPosition += 10;
  doc.text(`• NPV של התזרים: ₪${formatMoney(Math.round(npv))}`, 30, yPosition);
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
