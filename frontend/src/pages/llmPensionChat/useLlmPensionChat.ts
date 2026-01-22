import { FormEvent, useEffect, useRef, useState } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { useNavigate } from "react-router-dom";

import { applyUiNavigateIfPresent } from "./uiActions";

import {
  apiFetch,
  llmApi,
  LlmChatMessageDto,
  LlmStatusDto,
  publicChatApi,
  handleApiError,
  API_BASE,
} from "../../lib/api";
import { loadLlmChatFromStorage, saveLlmChatToStorage, clearLlmChatFromStorage } from "../../services/llmChatStorageService";
import { applyConversionUpdatesToPensionPortfolio } from "../PensionPortfolio/services/pensionPortfolioStorageService";

import { BALANCE_ZERO_EPSILON, PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION } from "./constants";
import { estimateCostForCall, estimatePreviewCost } from "./costEstimation";
import { loadPensionPortfolioForLlm, persistPortfolioUpdateToDb, resetSeveranceInPortfolio } from "./portfolio";
import { ComputedPensionData, UsageInfo } from "./types";

export type ProviderFormState = { provider: string; modelName: string };

type Params = {
  clientId: string | undefined;
  client: any;
};

type Return = {
  messages: LlmChatMessageDto[];
  setMessages: Dispatch<SetStateAction<LlmChatMessageDto[]>>;
  input: string;
  setInput: Dispatch<SetStateAction<string>>;
  pendingApprovalRequest: any | null;
  isSending: boolean;
  error: string | null;
  streamingContent: string;
  llmStatus: LlmStatusDto | null;
  providerForm: ProviderFormState;
  setProviderForm: Dispatch<SetStateAction<ProviderFormState>>;
  isSwitchingProvider: boolean;
  isOpeningPublicChat: boolean;
  messagesEndRef: RefObject<HTMLDivElement>;
  usageByMessageIndex: Record<number, UsageInfo>;
  nextMessageUsage: UsageInfo | null;
  computedData: ComputedPensionData | null;
  handleClearChat: () => void;
  handleApplyProvider: () => Promise<void>;
  handleOpenPublicChat: () => Promise<void>;
  handleSend: (e: FormEvent) => Promise<void>;
  handleApprovalDecision: (approved: boolean) => Promise<void>;
  statusText: string;
};

export function useLlmPensionChat({ clientId, client }: Params): Return {
  const routerNavigate = useNavigate();
  const [messages, setMessages] = useState<LlmChatMessageDto[]>([]);
  const [input, setInput] = useState("");
  const [pendingApprovalRequest, setPendingApprovalRequest] = useState<any | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [llmStatus, setLlmStatus] = useState<LlmStatusDto | null>(null);
  const [providerForm, setProviderForm] = useState<ProviderFormState>({ provider: "", modelName: "" });
  const [isSwitchingProvider, setIsSwitchingProvider] = useState(false);
  const [isOpeningPublicChat, setIsOpeningPublicChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [usageByMessageIndex, setUsageByMessageIndex] = useState<Record<number, UsageInfo>>({});
  const [nextMessageUsage, setNextMessageUsage] = useState<UsageInfo | null>(null);
  const [computedData, setComputedData] = useState<ComputedPensionData | null>(null);

  useEffect(() => {
    if (streamingContent) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [streamingContent]);

  useEffect(() => {
    if (!clientId) {
      return;
    }
    const stored = loadLlmChatFromStorage(clientId);
    if (stored && stored.length > 0) {
      setMessages(stored);
    }
  }, [clientId]);

  useEffect(() => {
    if (!clientId) {
      return;
    }
    saveLlmChatToStorage(clientId, messages);
  }, [clientId, messages]);

  useEffect(() => {
    let isMounted = true;
    llmApi
      .status()
      .then((status) => {
        if (isMounted) {
          setLlmStatus(status);
          setProviderForm({
            provider: status.provider || "",
            modelName: status.model_name || "",
          });
        }
      })
      .catch((e) => {
        console.warn("Failed to fetch LLM status", e);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  function handleClearChat() {
    if (!clientId) {
      return;
    }

    const confirmed = window.confirm("×œ× ×§×•×ª ××ª ×”×©×™×—×” ×œ×—×œ×•×˜×™×Ÿ ×•×œ×”×ª×—×™×œ ×©×™×—×” ×—×“×©×” ×¢× ×”×¡×•×›×Ÿ?");
    if (!confirmed) {
      return;
    }

    try {
      clearLlmChatFromStorage(clientId);
    } catch (e) {
      console.warn("Failed to clear LLM chat from storage:", e);
    }

    setMessages([]);
    setInput("");
    setError(null);
    setStreamingContent("");
    setUsageByMessageIndex({});
    setNextMessageUsage(null);
    setComputedData(null);
  }

  async function handleApplyProvider() {
    if (!providerForm.provider) {
      return;
    }

    setIsSwitchingProvider(true);
    setError(null);

    try {
      const updated = await llmApi.updateProvider(providerForm.provider, providerForm.modelName || undefined);
      setLlmStatus(updated);
      setProviderForm({
        provider: updated.provider || "",
        modelName: updated.model_name || "",
      });
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsSwitchingProvider(false);
    }
  }

  async function handleOpenPublicChat() {
    if (!client?.id_number) {
      setError("×œ× × ×™×ª×Ÿ ×œ×¤×ª×•×— Public Chat: ×—×¡×¨×” ×ª×¢×•×“×ª ×–×”×•×ª ×œ×œ×§×•×—.");
      return;
    }

    setIsOpeningPublicChat(true);
    setError(null);

    try {
      const started = await publicChatApi.start(client.id_number);
      const base = `${window.location.origin}${window.location.pathname}`;
      const url = `${base}#/public-chat/${started.session_key}`;
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsOpeningPublicChat(false);
    }
  }

  async function sendMessage(text: string) {
    const trimmed = (text || "").trim();
    if (!trimmed || isSending) {
      return;
    }

    const userMessage: LlmChatMessageDto = {
      role: "user",
      content: trimmed,
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsSending(true);
    setError(null);
    setStreamingContent("");
    setNextMessageUsage(null);

    try {
      const numericClientId = clientId ? Number(clientId) : undefined;
      let pensionPortfolioForLlm = loadPensionPortfolioForLlm(clientId);
      try {
        if (clientId) {
          const dbPortfolio = await apiFetch<any[]>(`/clients/${clientId}/pension-portfolio/`);
          if (Array.isArray(dbPortfolio) && dbPortfolio.length > 0) {
            pensionPortfolioForLlm = dbPortfolio as any;
          }
        }
      } catch (fetchErr) {
        console.warn(
          "Failed to load pension portfolio from DB for LLM chat, falling back to localStorage:",
          fetchErr,
        );
      }

      let fullContent = "";
      const pendingUiActions: any[] = [];

      for await (const chunk of llmApi.chatStream(newMessages, numericClientId, pensionPortfolioForLlm)) {
        fullContent += chunk;

        const computedStartMarker = "###COMPUTED_DATA###";
        const computedEndMarker = "###END_COMPUTED_DATA###";

        if (fullContent.includes(computedStartMarker) && fullContent.includes(computedEndMarker)) {
          const startIdx = fullContent.indexOf(computedStartMarker) + computedStartMarker.length;
          const endIdx = fullContent.indexOf(computedEndMarker);
          const jsonStr = fullContent.substring(startIdx, endIdx).trim();

          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.type === "computed_data" && parsed.data) {
              const data = parsed.data as ComputedPensionData;
              setComputedData(data);
              console.log("Extracted computed pension data from system:", data);
            }
          } catch (parseErr) {
            console.warn("Failed to parse computed data JSON:", parseErr);
          }

          fullContent =
            fullContent.substring(0, fullContent.indexOf(computedStartMarker)) +
            fullContent.substring(endIdx + computedEndMarker.length);
        }

        const severanceResetMarker = "###SEVERANCE_RESET###";
        const severanceResetEndMarker = "###END_SEVERANCE_RESET###";

        if (fullContent.includes(severanceResetMarker) && fullContent.includes(severanceResetEndMarker)) {
          const resetStartIdx = fullContent.indexOf(severanceResetMarker) + severanceResetMarker.length;
          const resetEndIdx = fullContent.indexOf(severanceResetEndMarker);
          const resetJsonStr = fullContent.substring(resetStartIdx, resetEndIdx).trim();

          try {
            const resetInfo = JSON.parse(resetJsonStr);
            if (resetInfo.portfolio_severance_to_reset) {
              console.log("ðŸ“‹ D3.11: Resetting severance in pension portfolio", resetInfo);
              resetSeveranceInPortfolio(clientId);
              await persistPortfolioUpdateToDb(clientId, (accounts) =>
                accounts.map((acc) => ({
                  ...acc,
                  ×¤×™×¦×•×™×™×_×ž×¢×¡×™×§_× ×•×›×—×™: 0,
                })),
              );
              console.log("âœ… D3.11: Severance reset in localStorage completed");
            }
          } catch (parseErr) {
            console.warn("Failed to parse severance reset JSON:", parseErr);
          }

          fullContent =
            fullContent.substring(0, fullContent.indexOf(severanceResetMarker)) +
            fullContent.substring(resetEndIdx + severanceResetEndMarker.length);
        }

        const portfolioUpdateMarker = "###PENSION_PORTFOLIO_UPDATE###";
        const portfolioUpdateEndMarker = "###END_PENSION_PORTFOLIO_UPDATE###";

        if (fullContent.includes(portfolioUpdateMarker) && fullContent.includes(portfolioUpdateEndMarker)) {
          const updStartIdx = fullContent.indexOf(portfolioUpdateMarker) + portfolioUpdateMarker.length;
          const updEndIdx = fullContent.indexOf(portfolioUpdateEndMarker);
          const updJsonStr = fullContent.substring(updStartIdx, updEndIdx).trim();

          try {
            const parsed = JSON.parse(updJsonStr);
            if (parsed?.type === "pension_portfolio_updates" && Array.isArray(parsed.updates)) {
              applyConversionUpdatesToPensionPortfolio(clientId, parsed.updates);

              await persistPortfolioUpdateToDb(clientId, (accounts) => {
                const updatedAccounts = [...accounts];

                const computeRemainingBalanceFromComponents = (account: any): number => {
                  if (!account || typeof account !== "object") {
                    return 0;
                  }
                  let sum = 0;
                  let sawComponent = false;
                  Object.keys(account).forEach((field) => {
                    if (field.startsWith("×ª×’×ž×•×œ×™_") || field.startsWith("×¤×™×¦×•×™×™×_") || field === "×§×¨×Ÿ_×”×©×ª×œ×ž×•×ª") {
                      sawComponent = true;
                      const v = Number((account as any)[field] ?? 0) || 0;
                      if (v > 0) {
                        sum += v;
                      }
                    }
                  });
                  if (!sawComponent) {
                    return 0;
                  }
                  return sum;
                };

                parsed.updates.forEach((u: any) => {
                  const accountNumber = String(u.account_number || "").trim();
                  if (!accountNumber) return;

                  const idx = updatedAccounts.findIndex(
                    (acc: any) => String(acc.×ž×¡×¤×¨_×—×©×‘×•×Ÿ || "").trim() === accountNumber,
                  );
                  if (idx === -1) return;

                  const account = { ...updatedAccounts[idx] } as any;
                  const specific = u.specific_amounts && typeof u.specific_amounts === "object" ? u.specific_amounts : null;

                  const hasSpecific = !!(specific && Object.keys(specific).length > 0);

                  if (hasSpecific) {
                    Object.keys(specific).forEach((field) => {
                      if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
                        return;
                      }
                      const rawDelta = (specific as any)[field];
                      const delta = Number(rawDelta ?? 0) || 0;
                      if (delta <= 0) {
                        return;
                      }
                      const currentVal = Number((account as any)[field] ?? 0) || 0;
                      const remaining = Math.max(0, currentVal - delta);
                      (account as any)[field] = Math.abs(remaining) < BALANCE_ZERO_EPSILON ? 0 : remaining;
                    });

                    const eduDelta = Number((specific as any).×§×¨×Ÿ_×”×©×ª×œ×ž×•×ª ?? 0) || 0;
                    if (eduDelta > 0) {
                      Object.keys(account).forEach((field) => {
                        if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
                          return;
                        }
                        if (
                          field.startsWith("×ª×’×ž×•×œ×™_") ||
                          field === "×ª×’×ž×•×œ×™×" ||
                          field === "×¡×š_×ª×’×ž×•×œ×™×" ||
                          field === "×§×¨×Ÿ_×”×©×ª×œ×ž×•×ª"
                        ) {
                          (account as any)[field] = 0;
                        }
                      });
                      account.×™×ª×¨×” = 0;
                    }
                  }

                  const originalBalance = Number(account.×™×ª×¨×” ?? 0) || 0;
                  const convertedAmount = Number(u.converted_amount ?? 0) || 0;
                  if (hasSpecific) {
                    const remainingFromComponents = computeRemainingBalanceFromComponents(account);
                    if (remainingFromComponents > 0 || convertedAmount > 0) {
                      account.×™×ª×¨×” = remainingFromComponents;
                    }
                  } else {
                    if (convertedAmount > 0) {
                      account.×™×ª×¨×” = Math.max(0, originalBalance - convertedAmount);
                    }
                  }

                  if (Math.abs(Number(account.×™×ª×¨×” ?? 0) || 0) < BALANCE_ZERO_EPSILON) {
                    account.×™×ª×¨×” = 0;
                  }

                  if (!hasSpecific && Number(account.×™×ª×¨×” ?? 0) === 0) {
                    Object.keys(account).forEach((field) => {
                      if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
                        return;
                      }
                      if (
                        field.startsWith("×ª×’×ž×•×œ×™_") ||
                        field.startsWith("×¤×™×¦×•×™×™×_") ||
                        field === "×ª×’×ž×•×œ×™×" ||
                        field === "×¡×š_×ª×’×ž×•×œ×™×" ||
                        field === "×¡×š_×¤×™×¦×•×™×™×" ||
                        field === "×¡×š_×¨×›×™×‘×™×" ||
                        field === "×§×¨×Ÿ_×”×©×ª×œ×ž×•×ª"
                      ) {
                        (account as any)[field] = 0;
                      }
                    });
                  }

                  updatedAccounts[idx] = account;
                });

                return updatedAccounts;
              });
            }
          } catch (parseErr) {
            console.warn("Failed to parse pension portfolio update JSON:", parseErr);
          }

          fullContent =
            fullContent.substring(0, fullContent.indexOf(portfolioUpdateMarker)) +
            fullContent.substring(updEndIdx + portfolioUpdateEndMarker.length);
        }

        const uiActionMarker = "###UI_ACTION###";
        const uiActionEndMarker = "###END_UI_ACTION###";

        let sawApprovalRequestInStream = false;

        if (fullContent.includes(uiActionMarker) && fullContent.includes(uiActionEndMarker)) {
          const actionStartIdx = fullContent.indexOf(uiActionMarker) + uiActionMarker.length;
          const actionEndIdx = fullContent.indexOf(uiActionEndMarker);
          const actionJsonStr = fullContent.substring(actionStartIdx, actionEndIdx).trim();

          try {
            const parsed = JSON.parse(actionJsonStr);
            if (parsed?.type === "ui_actions" && Array.isArray(parsed.actions)) {
              pendingUiActions.push(...parsed.actions);

              const approvalAction = parsed.actions.find(
                (a: any) => a && typeof a === "object" && a.type === "approval_request",
              );
              if (approvalAction) {
                setPendingApprovalRequest(approvalAction);
                sawApprovalRequestInStream = true;
              }
            }
          } catch (parseErr) {
            console.warn("Failed to parse UI_ACTION JSON:", parseErr);
          }

          fullContent =
            fullContent.substring(0, fullContent.indexOf(uiActionMarker)) +
            fullContent.substring(actionEndIdx + uiActionEndMarker.length);
        }

        const visible = (fullContent || "").trim();
        if (!visible && (sawApprovalRequestInStream || pendingApprovalRequest)) {
          setStreamingContent("× ×“×¨×© ××™×©×•×¨ ×œ×¤× ×™ ×”×¤×¢×œ×ª ×›×œ×™. ××©×¨/×‘×˜×œ ×‘×—×œ×•× ×™×ª ×”××™×©×•×¨.");
        } else {
          setStreamingContent(fullContent);
        }
      }

      const assistantMessage: LlmChatMessageDto = {
        role: "assistant",
        content: fullContent.trim(),
      };
      const finalMessages = [...newMessages, assistantMessage];
      setMessages(finalMessages);
      setStreamingContent("");

      if (clientId) {
        try {
          saveLlmChatToStorage(clientId, finalMessages);
        } catch (e) {
          console.warn("Failed to persist LLM chat before UI actions:", e);
        }
      }

      const normalizeUrl = (raw: string): string => {
        const trimmed = (raw || "").trim();
        if (!trimmed) return "";
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
          return trimmed;
        }
        if (trimmed.startsWith("/api/v1/")) {
          return `${API_BASE}${trimmed.slice("/api/v1".length)}`;
        }
        if (trimmed === "/api/v1") {
          return API_BASE;
        }
        return `${window.location.origin}${trimmed.startsWith("/") ? "" : "/"}${trimmed}`;
      };

      const didNavigate = applyUiNavigateIfPresent({ type: "ui_actions", actions: pendingUiActions }, (path) => {
        routerNavigate(path);
      });

      pendingUiActions.forEach((action: any) => {
        if (!action || typeof action !== "object") return;

        if (didNavigate && action.type === "navigate") {
          return;
        }

        if (action.type === "open_url" && typeof action.url === "string" && action.url.trim()) {
          const url = normalizeUrl(action.url);
          if (!url) return;
          try {
            const link = document.createElement("a");
            link.href = url;
            link.download = "";
            link.rel = "noopener";
            document.body.appendChild(link);
            link.click();
            link.remove();
          } catch {
            window.open(url, "_blank");
          }
          return;
        }
      });

      const effectiveProvider = llmStatus?.provider || "ollama";
      const effectiveModel = llmStatus?.model_name || null;
      const usage = estimateCostForCall(finalMessages, effectiveProvider, effectiveModel);
      if (usage) {
        const assistantIndex = finalMessages.length - 1;
        setUsageByMessageIndex((prev) => ({
          ...prev,
          [assistantIndex]: usage,
        }));
      }
    } catch (err) {
      setError(handleApiError(err));
      setStreamingContent("");
    } finally {
      setIsSending(false);
    }
  }

  async function handleApprovalDecision(approved: boolean) {
    const req = pendingApprovalRequest;
    setPendingApprovalRequest(null);

    if (!req) {
      return;
    }

    const toolName = typeof req.tool_name === "string" ? req.tool_name : "";
    const toolArgs = req.arguments && typeof req.arguments === "object" ? req.arguments : {};
    if (!toolName) {
      return;
    }

    const payload = {
      tool_name: toolName,
      arguments: toolArgs,
    };

    if (approved) {
      await sendMessage(`###USER_APPROVED### ${JSON.stringify(payload)}`);
      return;
    }

    await sendMessage(`###USER_CANCELLED### ${JSON.stringify(payload)}`);
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    if (pendingApprovalRequest) {
      const raw = (input || "").trim().toLowerCase();
      const isApprovalText =
        raw === "×ž××©×¨" ||
        raw === "×× ×™ ×ž××©×¨" ||
        raw === "×ž××©×¨×ª" ||
        raw === "×× ×™ ×ž××©×¨×ª" ||
        raw === "×›×Ÿ" ||
        raw === "××©×¨" ||
        raw === "approve" ||
        raw === "ok";
      const isCancelText = raw === "×‘×˜×œ" || raw === "×‘×™×˜×•×œ" || raw === "×œ×" || raw === "cancel";

      if (!isApprovalText && !isCancelText) {
        setError("× ×“×¨×© ××™×©×•×¨ ×œ×¤× ×™ ×”×¤×¢×œ×ª ×›×œ×™. ×× × ××©×¨/×‘×˜×œ (×‘×—×œ×•× ×™×ª ××• ×¢" + "×™ ×›×ª×™×‘×” '×ž××©×¨'/'×‘×˜×œ').");
        return;
      }

      setError(null);
      setInput("");
      await handleApprovalDecision(isApprovalText);
      return;
    }
    await sendMessage(input);
  }

  const statusText = llmStatus
    ? `×ž×•×“×œ: ${llmStatus.backend || "×œ× ×™×“×•×¢"}${llmStatus.model_name ? ` (${llmStatus.model_name})` : ""}`
    : "";

  useEffect(() => {
    if (!llmStatus) {
      setNextMessageUsage(null);
      return;
    }

    const trimmed = input.trim();
    if (!trimmed || isSending) {
      setNextMessageUsage(null);
      return;
    }

    const effectiveProvider = llmStatus.provider || "ollama";
    const effectiveModel = llmStatus.model_name || null;
    const preview = estimatePreviewCost(messages, trimmed, effectiveProvider, effectiveModel);
    setNextMessageUsage(preview);
  }, [input, messages, llmStatus, isSending]);

  return {
    messages,
    setMessages,
    input,
    setInput,
    pendingApprovalRequest,
    isSending,
    error,
    streamingContent,
    llmStatus,
    providerForm,
    setProviderForm,
    isSwitchingProvider,
    isOpeningPublicChat,
    messagesEndRef,
    usageByMessageIndex,
    nextMessageUsage,
    computedData,
    handleClearChat,
    handleApplyProvider,
    handleOpenPublicChat,
    handleSend,
    handleApprovalDecision,
    statusText,
  };
}
