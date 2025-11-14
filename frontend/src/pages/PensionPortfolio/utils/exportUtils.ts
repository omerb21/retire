import { PensionAccount } from '../types';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';

/**
 * פונקציה ליצירת דוח Excel של הטבלה
 */
export function generateExcelReport(pensionData: PensionAccount[], clientId: string): void {
  if (pensionData.length === 0) {
    throw new Error("אין נתונים לייצוא לאקסל");
  }

  // יצירת נתוני CSV
  const headers = [
    'מספר חשבון',
    'שם תכנית', 
    'חברה מנהלת',
    'יתרה',
    'תאריך נכונות יתרה',
    'תאריך התחלה',
    'סוג מוצר',
    'מעסיקים היסטוריים',
    'פיצויים מעסיק נוכחי',
    'פיצויים לאחר התחשבנות',
    'פיצויים שלא עברו התחשבנות',
    'פיצויים מעסיקים קודמים (זכויות)',
    'פיצויים מעסיקים קודמים (קצבה)',
    'תגמולי עובד עד 2000',
    'תגמולי עובד אחרי 2000',
    'תגמולי עובד אחרי 2008 (לא משלמת)',
    'תגמולי מעביד עד 2000',
    'תגמולי מעביד אחרי 2000',
    'תגמולי מעביד אחרי 2008 (לא משלמת)',
    'סך תגמולים (כל התקופות)',
    'סך פיצויים (כל הרכיבים)',
    'סה"כ רכיבים (תגמולים + פיצויים)',
    'פער יתרה מול רכיבים',
    'קובץ מקור',
    'תאריך עיבוד'
  ];

  const csvContent = [
    headers.join(','),
    ...pensionData.map(account => [
      `"${account.מספר_חשבון}"`,
      `"${account.שם_תכנית}"`,
      `"${account.חברה_מנהלת}"`,
      account.יתרה || 0,
      `"${account.תאריך_נכונות_יתרה}"`,
      `"${account.תאריך_התחלה || ''}"`,
      `"${account.סוג_מוצר}"`,
      `"${account.מעסיקים_היסטוריים || ''}"`,
      account.פיצויים_מעסיק_נוכחי || 0,
      account.פיצויים_לאחר_התחשבנות || 0,
      account.פיצויים_שלא_עברו_התחשבנות || 0,
      account.פיצויים_ממעסיקים_קודמים_רצף_זכויות || 0,
      account.פיצויים_ממעסיקים_קודמים_רצף_קצבה || 0,
      account.תגמולי_עובד_עד_2000 || 0,
      account.תגמולי_עובד_אחרי_2000 || 0,
      account.תגמולי_עובד_אחרי_2008_לא_משלמת || 0,
      account.תגמולי_מעביד_עד_2000 || 0,
      account.תגמולי_מעביד_אחרי_2000 || 0,
      account.תגמולי_מעביד_אחרי_2008_לא_משלמת || 0,
      account.סך_תגמולים || 0,
      account.סך_פיצויים || 0,
      account.סך_רכיבים || 0,
      account.פער_יתרה_מול_רכיבים || 0,
      `"${account.קובץ_מקור || ''}"`,
      `"${account.processed_at || ''}"`
    ].join(','))
  ].join('\n');

  // הוספת BOM עבור תמיכה בעברית
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
  
  // יצירת קישור להורדה
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `pension_portfolio_client_${clientId}_${formatDateToDDMMYY(new Date()).replace(/\//g, '_')}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
