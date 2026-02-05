import { LlmChatMessageDto } from "../../lib/api";

export type UsageInfo = {
  totalTokens: number;
  totalChars: number;
  estimatedCostUsd: number;
  estimatedCostIls: number;
  provider: string;
  modelName: string | null;
};

export type ComputedPensionSource = {
  source_name: string;
  source_type: string;
  balance: number;
  monthly_pension: number;
  annuity_factor: number;
  tax_treatment: string;
};

export type ComputedPensionData = {
  sources: ComputedPensionSource[];
  target_monthly_pension: number;
  accumulated_pension: number;
  remaining_capital: number;
  target_achieved: boolean;
  retirement_age: number;
};

export type MonthlyPensionItem = {
  id: number;
  amount: number;
  start_date: string | null;
  tax_treatment: string;
};

export type MonthlyPensionSplit = {
  count: number;
  sum: number;
  items: MonthlyPensionItem[];
};

export type MonthlyPensionCurrent = MonthlyPensionSplit & {
  taxable: {
    count: number;
    sum: number;
  };
  exempt: {
    count: number;
    sum: number;
  };
};

export type MonthlyPensionComputedData = {
  client_id: number;
  today: string;
  monthly_pension: {
    current: MonthlyPensionCurrent;
    future: MonthlyPensionSplit;
    total: {
      count: number;
      sum: number;
    };
  };
};

export type ComputedDataPayload = ComputedPensionData | MonthlyPensionComputedData;

export type TokenEstimate = { totalTokens: number; totalChars: number };

export type EstimateTokensFn = (messages: LlmChatMessageDto[]) => TokenEstimate;
