/**
 * Grant Types and Interfaces
 * טיפוסים וממשקים למענקים
 */

export interface Grant {
  id?: number;
  employer_name: string;
  work_start_date: string;
  work_end_date: string;
  grant_type: string;
  grant_date: string;
  amount?: number;       // שדה מהשרת
  grant_amount?: number; // שדה מהקליינט
  reason?: string;
  tax_calculation?: TaxCalculation;
}

export interface TaxCalculation {
  grant_exempt: number;
  grant_taxable: number;
  tax_due: number;
}

export interface GrantDetails {
  serviceYears: number;
  taxExemptAmount: number;
  taxableAmount: number;
  taxDue: number;
}

export interface GrantFormData {
  employer_name: string;
  work_start_date: string;
  work_end_date: string;
  grant_type: string;
  grant_date: string;
  grant_amount: number;
  amount: number;
  reason: string;
}

export type GrantType = 'severance' | 'bonus' | 'pension' | 'other';

export const GRANT_TYPE_LABELS: Record<GrantType, string> = {
  severance: 'פיצויים',
  bonus: 'בונוס',
  pension: 'פנסיה',
  other: 'אחר'
};
