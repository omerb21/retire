export interface Scenario {
  id: number;
  scenario_name: string;
  apply_tax_planning: boolean;
  apply_capitalization: boolean;
  apply_exemption_shield: boolean;
  created_at: string;
}

export interface ScenarioResult {
  id: number;
  scenario_name: string;
  client_id: number;
  apply_tax_planning: boolean;
  apply_capitalization: boolean;
  apply_exemption_shield: boolean;
  seniority_years: number;
  grant_gross: number;
  grant_exempt: number;
  grant_tax: number;
  grant_net: number;
  pension_monthly: number;
  indexation_factor: number;
  cashflow: Array<{
    date: string;
    inflow: number;
    outflow: number;
    net: number;
  }>;
  created_at: string;
}

export interface ScenariosProps {
  clientId: number;
}

export interface ScenarioFormData {
  scenario_name: string;
  planned_termination_date: string;
  monthly_expenses: string;
  apply_tax_planning: boolean;
  apply_capitalization: boolean;
  apply_exemption_shield: boolean;
  other_parameters: Record<string, any>;
}

export const INITIAL_FORM_STATE: ScenarioFormData = {
  scenario_name: '',
  planned_termination_date: '',
  monthly_expenses: '',
  apply_tax_planning: false,
  apply_capitalization: false,
  apply_exemption_shield: false,
  other_parameters: {}
};
