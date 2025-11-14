/**
 * טיפוסים עבור מודול תיק פנסיוני
 */

export type PensionAccount = {
  id?: number;
  מספר_חשבון: string;
  שם_תכנית: string;
  חברה_מנהלת: string;
  קוד_חברה_מנהלת?: string;
  יתרה: number; // יתרה מקורית - לא מוצגת, רק לחישובים
  תאריך_נכונות_יתרה: string;
  תאריך_התחלה?: string;
  סוג_מוצר: string;
  מעסיקים_היסטוריים?: string;
  פיצויים_מעסיק_נוכחי?: number;
  פיצויים_לאחר_התחשבנות?: number;
  פיצויים_שלא_עברו_התחשבנות?: number;
  פיצויים_ממעסיקים_קודמים_רצף_זכויות?: number;
  פיצויים_ממעסיקים_קודמים_רצף_קצבה?: number;
  תגמולי_עובד_עד_2000?: number;
  תגמולי_עובד_אחרי_2000?: number;
  תגמולי_עובד_אחרי_2008_לא_משלמת?: number;
  תגמולי_מעביד_עד_2000?: number;
  תגמולי_מעביד_אחרי_2000?: number;
  תגמולי_מעביד_אחרי_2008_לא_משלמת?: number;
  תגמולים?: number; // ערך מיובא מתגית YITRAT-KASPEY-TAGMULIM
  סך_תגמולים?: number;
  סך_פיצויים?: number;
  סך_רכיבים?: number;
  פער_יתרה_מול_רכיבים?: number;
  תגמולים_לפי_תקופה?: Record<string, number>;
  רכיבי_פיצויים?: Record<string, number>;
  שדות_פיצויים_תגמולים?: Record<string, string>;
  קובץ_מקור?: string;
  processed_at?: string;
  selected?: boolean;
  conversion_type?: 'pension' | 'capital_asset';
  selected_amounts?: {[key: string]: boolean}; // לסימון סכומים ספציפיים
  saved_fund_id?: number; // ID של התכנית השמורה במסד הנתונים
  debug_plan_name?: string; // לצורך debug
};

export type ProcessedFile = {
  file: string;
  accounts: PensionAccount[];
  processed_at: string;
};

export type ConversionSourceData = {
  type: 'pension_portfolio';
  account_name: string;
  company: string;
  account_number: string;
  product_type: string;
  amount: number;
  specific_amounts: Record<string, number>;
  conversion_date: string;
  tax_treatment: string;
};

export type EditingCell = {
  row: number;
  field: string;
};
