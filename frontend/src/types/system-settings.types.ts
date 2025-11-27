// Types for System Settings

export interface TaxBracket {
  id: number;
  minMonthly: number;
  maxMonthly: number;
  minAnnual: number;
  maxAnnual: number;
  rate: number;
}

export interface SeveranceCap {
  year: number;
  monthly_cap: number;
  annual_cap: number;
  description: string;
}

export interface PensionCeiling {
  year: number;
  monthly_ceiling: number;
  description: string;
}

export interface ExemptCapitalPercentage {
  year: number;
  percentage: number;
  description: string;
}

export interface IdfPromoterRow {
  gender: 'male' | 'female';
  age_at_commutation: number;
  promoter_age_years: number;
  promoter_age_months: number;
  description?: string;
}

export type TabType = 
  | 'tax' 
  | 'severance' 
  | 'conversion' 
  | 'fixation' 
  | 'scenarios' 
  | 'retirement' 
  | 'termination' 
  | 'annuity' 
  | 'tax_calculation'
  | 'health';
