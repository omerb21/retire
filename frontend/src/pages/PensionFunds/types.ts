export type PensionFund = {
  id?: number;
  fund_name?: string;
  fund_number?: string;
  fund_type?: string;
  calculation_mode?: "calculated" | "manual"; // לתאימות לאחור
  input_mode?: "calculated" | "manual";
  current_balance?: number;
  balance?: number;
  commutable_balance?: number; // יתרה להיוון - השדה החשוב!
  annuity_factor?: number;
  monthly_amount?: number;
  monthly?: number; // שדה נוסף מהשרת
  pension_amount?: number;
  computed_monthly_amount?: number;
  pension_start_date?: string;
  start_date?: string; // לתאימות לאחור
  end_date?: string;
  indexation_method?: "none" | "fixed" | "cpi";
  indexation_rate?: number;
  fixed_index_rate?: number;
  employer_contributions?: number;
  employee_contributions?: number;
  annual_return_rate?: number;
  deduction_file?: string; // תיק ניכויים
  tax_treatment?: "taxable" | "exempt" | "capital_gains"; // יחס למס
};

export type Commutation = {
  id?: number;
  pension_fund_id?: number;
  exempt_amount?: number;
  commutation_date?: string;
  commutation_type?: "exempt" | "taxable"; // פטור ממס או חייב במס
  original_pension?: PensionFund; // צילום של הקצבה המקורית לצורך שחזור מדויק
};
