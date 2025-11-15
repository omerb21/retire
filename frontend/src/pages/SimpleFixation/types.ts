export interface GrantSummary {
  employer_name: string;
  grant_amount: number;
  work_start_date: string;
  work_end_date: string;
  grant_date: string;
  indexed_full?: number;
  ratio_32y?: number;
  limited_indexed_amount?: number;
  impact_on_exemption?: number;
  exclusion_reason?: string;
}

export interface ExemptionSummary {
  exempt_capital_initial: number;
  total_impact: number;
  remaining_exempt_capital: number;
  remaining_monthly_exemption: number;
  eligibility_year: number;
  exemption_percentage: number;
}

export interface PensionSummary {
  exempt_amount: number;
  total_grants: number;
  total_indexed: number;
  used_exemption: number;
  future_grant_reserved: number;
  future_grant_impact: number;
  total_discounts: number;
  remaining_exemption: number;
  pension_ceiling: number;
  exempt_pension_calculated: {
    base_amount: number;
    percentage: number;
  };
}

export interface Commutation {
  id: number;
  pension_fund_id?: number;
  fund_name?: string;
  deduction_file?: string;
  exempt_amount: number;
  commutation_date: string;
  commutation_type: string;
}

export interface FixationData {
  client_id: number;
  grants: GrantSummary[];
  exemption_summary: ExemptionSummary;
  eligibility_date: string;
  eligibility_year: number;
  status: string;
}
