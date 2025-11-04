/**
 * Types for SimpleCurrentEmployer module
 */

export interface SimpleEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  end_date?: string;
  last_salary: number;
  severance_accrued: number;
  employer_completion?: number;
  service_years?: number;
  expected_grant_amount?: number;
  tax_exempt_amount?: number;
  taxable_amount?: number;
}

export interface TerminationDecision {
  termination_date: string;
  use_employer_completion: boolean;
  severance_amount: number;
  exempt_amount: number;
  taxable_amount: number;
  exempt_choice: 'redeem_with_exemption' | 'redeem_no_exemption' | 'annuity';
  taxable_choice: 'redeem_no_exemption' | 'annuity';
  tax_spread_years?: number;
  max_spread_years?: number;
  confirmed?: boolean; // האם העזיבה אושרה והנתונים הוקפאו
}

export interface GrantDetails {
  serviceYears: number;
  expectedGrant: number;
  taxExemptAmount: number;
  taxableAmount: number;
  severanceCap: number;
}

export interface PlanDetail {
  plan_name: string;
  plan_start_date: string | null;
  product_type: string;
  amount: number;
}

export interface TerminationPayload {
  termination_date: string;
  use_employer_completion: boolean;
  severance_amount: number;
  exempt_amount: number;
  taxable_amount: number;
  exempt_choice: 'redeem_with_exemption' | 'redeem_no_exemption' | 'annuity';
  taxable_choice: 'redeem_no_exemption' | 'annuity';
  tax_spread_years?: number;
  max_spread_years?: number;
  confirmed: boolean;
  source_accounts: string | null;
  plan_details: string | null;
}
