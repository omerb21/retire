import { PensionAccount } from '../types';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { calculateInitialTagmulim } from '../utils/pensionCalculations';

/**
 * שירות ליצירת תכנית פנסיונית ידנית באמצעות prompt-ים מהמשתמש
 */
export function promptForManualAccount(): { account: PensionAccount; message: string } | null {
  const name = prompt('שם התכנית:');
  if (!name) return null;

  const balance = prompt('יתרה:', '0');
  if (balance === null) return null;

  const startDate = prompt('תאריך התחלה (DD/MM/YYYY):', formatDateToDDMMYY(new Date()));
  if (startDate === null) return null;

  const productType = prompt('סוג מוצר (קרן השתלמות / קופת גמל):', 'קופת גמל');
  if (productType === null) return null;

  const baseAccount: PensionAccount = {
    מספר_חשבון: `MANUAL-${Date.now()}`,
    שם_תכנית: name,
    חברה_מנהלת: 'הוסף ידני',
    קוד_חברה_מנהלת: '',
    יתרה: parseFloat(balance) || 0,
    תאריך_נכונות_יתרה: formatDateToDDMMYY(new Date()),
    תאריך_התחלה: startDate,
    סוג_מוצר: productType,
    מעסיקים_היסטוריים: '',
    פיצויים_מעסיק_נוכחי: 0,
    פיצויים_לאחר_התחשבנות: 0,
    פיצויים_שלא_עברו_התחשבנות: 0,
    פיצויים_ממעסיקים_קודמים_רצף_זכויות: 0,
    פיצויים_ממעסיקים_קודמים_רצף_קצבה: 0,
    תגמולי_עובד_עד_2000: 0,
    תגמולי_עובד_אחרי_2000: 0,
    תגמולי_עובד_אחרי_2008_לא_משלמת: 0,
    תגמולי_מעביד_עד_2000: 0,
    תגמולי_מעביד_אחרי_2000: 0,
    תגמולי_מעביד_אחרי_2008_לא_משלמת: 0,
    selected: false,
    selected_amounts: {},
  };

  const newAccount = calculateInitialTagmulim(baseAccount);
  const message = `תכנית "${name}" נוספה בהצלחה`;

  return { account: newAccount, message };
}
