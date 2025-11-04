import { PensionAccount } from '../types';

/**
 * פונקציה זו כבר לא מחשבת תגמולים - התגמולים מיובאים ישירות מהתגית YITRAT-KASPEY-TAGMULIM
 * הפונקציה נשארת לצורך תאימות לאחור אך פשוט מחזירה את החשבון כמו שהוא
 */
export function calculateInitialTagmulim(account: PensionAccount): PensionAccount {
  // אין יותר חישוב - התגמולים מיובאים ישירות מה-XML
  return account;
}

/**
 * מחשב יתרה כללית מחדש (סכום כל הטורים כולל תגמולים)
 */
export function calculateTotalBalance(account: PensionAccount): number {
  const allFields = [
    'פיצויים_מעסיק_נוכחי',
    'פיצויים_לאחר_התחשבנות',
    'פיצויים_שלא_עברו_התחשבנות',
    'פיצויים_ממעסיקים_קודמים_רצף_זכויות',
    'פיצויים_ממעסיקים_קודמים_רצף_קצבה',
    'תגמולי_עובד_עד_2000',
    'תגמולי_עובד_אחרי_2000',
    'תגמולי_עובד_אחרי_2008_לא_משלמת',
    'תגמולי_מעביד_עד_2000',
    'תגמולי_מעביד_אחרי_2000',
    'תגמולי_מעביד_אחרי_2008_לא_משלמת',
    'תגמולים'
  ];

  return allFields.reduce((sum, field) => {
    const value = (account as any)[field];
    return sum + (typeof value === 'number' ? value : 0);
  }, 0);
}
