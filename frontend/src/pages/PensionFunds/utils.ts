import { PensionFund } from './types';

/**
 * פונקציה מרכזית לחישוב היתרה המקורית של קצבה
 */
export function calculateOriginalBalance(fund: PensionFund): number {
  // אם יש שדה commutable_balance (יתרה להיוון) - זה השדה המדויק!
  if (fund.commutable_balance && fund.commutable_balance > 0) {
    return fund.commutable_balance;
  }
  
  // אם יש יתרה בפועל - השתמש בה
  let balance = fund.balance || fund.current_balance || 0;
  
  if (balance > 0) {
    return balance;
  }
  
  // אם אין שום יתרה - החזר 0
  return 0;
}
