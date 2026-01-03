import { LlmChatMessageDto } from "../../lib/api";

import { ILS_PER_USD } from "./constants";
import { UsageInfo } from "./types";

export function estimateTokensForMessages(messages: LlmChatMessageDto[]): {
  totalTokens: number;
  totalChars: number;
} {
  if (!messages || messages.length === 0) {
    return { totalTokens: 0, totalChars: 0 };
  }

  const joined = messages.map((m) => `${m.role}: ${m.content ?? ""}`).join("\n");

  const totalChars = joined.length;
  if (!totalChars) {
    return { totalTokens: 0, totalChars };
  }

  const totalTokens = Math.ceil(totalChars / 4);
  return { totalTokens, totalChars };
}

export function getEstimatedPricePer1kTokensUsd(provider: string | null | undefined): number {
  if (!provider) return 0;
  const normalized = provider.toLowerCase();

  if (normalized === "openai") return 0.003;
  if (normalized === "gemini") return 0.001;
  if (normalized === "anthropic") return 0.002;

  return 0;
}

export function estimateCostForCall(
  messages: LlmChatMessageDto[],
  provider: string | null | undefined,
  modelName: string | null | undefined,
): UsageInfo | null {
  const { totalTokens, totalChars } = estimateTokensForMessages(messages);
  if (!totalTokens) {
    return null;
  }

  const pricePer1k = getEstimatedPricePer1kTokensUsd(provider);
  const estimatedCostUsd = (totalTokens / 1000) * pricePer1k;
  const estimatedCostIls = estimatedCostUsd * ILS_PER_USD;

  return {
    totalTokens,
    totalChars,
    estimatedCostUsd,
    estimatedCostIls,
    provider: provider || "",
    modelName: modelName || null,
  };
}

export function estimatePreviewCost(
  existingMessages: LlmChatMessageDto[],
  nextUserMessage: string,
  provider: string | null | undefined,
  modelName: string | null | undefined,
): UsageInfo | null {
  const previewMessages: LlmChatMessageDto[] = [
    ...existingMessages,
    { role: "user", content: nextUserMessage },
  ];

  const { totalTokens, totalChars } = estimateTokensForMessages(previewMessages);
  if (!totalTokens) {
    return null;
  }

  const approxTotalTokens = totalTokens * 2;
  const pricePer1k = getEstimatedPricePer1kTokensUsd(provider);
  const estimatedCostUsd = (approxTotalTokens / 1000) * pricePer1k;
  const estimatedCostIls = estimatedCostUsd * ILS_PER_USD;

  return {
    totalTokens: approxTotalTokens,
    totalChars,
    estimatedCostUsd,
    estimatedCostIls,
    provider: provider || "",
    modelName: modelName || null,
  };
}
