import { } from "react";

export interface ExecutionAction {
  type: string;
  details: string;
  from: string;
  to: string;
  amount: number;
}

export interface ScenarioResult {
  scenario_name: string;
  total_pension_monthly: number;
  total_capital: number;
  total_additional_income_monthly: number;
  estimated_npv: number;
  pension_funds_count: number;
  capital_assets_count: number;
  additional_incomes_count: number;
  execution_plan?: ExecutionAction[];
  scenario_id?: number;
}

export interface ScenariosResponse {
  success: boolean;
  client_id: number;
  retirement_age: number;
  scenarios: {
    scenario_1_max_pension: ScenarioResult;
    scenario_2_max_capital: ScenarioResult;
    scenario_3_max_npv: ScenarioResult;
  };
}
