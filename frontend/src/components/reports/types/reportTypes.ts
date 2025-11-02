/**
 * טיפוסים משותפים לדוחות
 */

export interface YearlyProjection {
  year: number;
  clientAge: number;
  totalMonthlyIncome: number;
  totalMonthlyTax: number;
  netMonthlyIncome: number;
  incomeBreakdown: number[];
  taxBreakdown: number[];
  exemptPension?: number;
}

export interface ReportData {
  totalWealth: number;
  totalMonthlyIncome: number;
  estimatedTax: number;
  cashflow: any[];
}

export const ASSET_TYPES = [
  { value: "rental_property", label: "דירה להשכרה" },
  { value: "investment", label: "השקעות" },
  { value: "stocks", label: "מניות" },
  { value: "bonds", label: "אגרות חוב" },
  { value: "mutual_funds", label: "קרנות נאמנות" },
  { value: "real_estate", label: "נדלן" },
  { value: "savings_account", label: "חשבון חיסכון" },
  { value: "other", label: "אחר" }
];
