/**
 * Capital Asset Types and Constants
 * ==================================
 * Type definitions and constants for capital assets management
 */

export type CapitalAsset = {
  id?: number;
  client_id?: number;
  asset_type: string;
  description?: string;
  remarks?: string;  // הערות - משמש לקישור להיוון
  conversion_source?: string;  // מקור המרה (JSON)
  current_value: number;
  purchase_value?: number;
  purchase_date?: string;
  annual_return?: number;
  annual_return_rate: number;
  payment_frequency: "monthly" | "annually";
  liquidity?: string;
  risk_level?: string;
  // שדות נוספים לשימוש בפרונטאנד
  asset_name?: string;
  monthly_income?: number;
  start_date?: string;  // תאריך תשלום חד פעמי
  indexation_method?: "none" | "fixed" | "cpi";
  fixed_rate?: number;
  tax_treatment?: "exempt" | "taxable" | "fixed_rate" | "capital_gains" | "tax_spread";
  tax_rate?: number;
  spread_years?: number;
  nominal_principal?: number;  // סכום ההפקדה הנומינאלי למס רווח הון
};

export const ASSET_TYPES = [
  { value: "rental_property", label: "דירה להשכרה" },
  { value: "investment", label: "השקעות" },
  { value: "stocks", label: "מניות" },
  { value: "bonds", label: "אגרות חוב" },
  { value: "mutual_funds", label: "קרנות נאמנות" },
  { value: "real_estate", label: "נדלן" },
  { value: "savings_account", label: "חשבון חיסכון" },
  { value: "deposits", label: "היוון" },
  { value: "provident_fund", label: "קופת גמל" },
  { value: "education_fund", label: "קרן השתלמות" },
  { value: "other", label: "אחר" }
];

export const INITIAL_FORM_STATE: Partial<CapitalAsset> = {
  asset_name: "",
  asset_type: "rental_property",
  current_value: 0,
  monthly_income: 0,
  annual_return_rate: 0,
  payment_frequency: "monthly",
  start_date: "",
  indexation_method: "none",
  tax_treatment: "taxable",
  fixed_rate: 0,
  tax_rate: 0,
  spread_years: 0,
  nominal_principal: 0,
};
