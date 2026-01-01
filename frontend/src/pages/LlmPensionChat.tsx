import React, { useState, FormEvent, useEffect, useRef } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { apiFetch, llmApi, LlmChatMessageDto, LlmStatusDto, LlmPensionPortfolioAccount, publicChatApi, handleApiError, API_BASE } from "../lib/api";
import { useClientData } from "./ClientDetails/hooks/useClientData";
import { loadLlmChatFromStorage, saveLlmChatToStorage, clearLlmChatFromStorage } from "../services/llmChatStorageService";
import {
  applyConversionUpdatesToPensionPortfolio,
  loadPensionDataFromStorage,
  updatePensionDataInStorage,
} from "./PensionPortfolio/services/pensionPortfolioStorageService";
import "./LlmPensionChat.css";

const PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION = new Set<string>([
  "פיצויים_מעסיק_נוכחי",
  "פיצויים_שלא_עברו_התחשבנות",
  "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
]);

const BALANCE_ZERO_EPSILON = 0.01;

const MODEL_PRESETS: Record<string, { value: string; label: string }[]> = {
  ollama: [
    { value: "", label: "ברירת מחדל (מהשרת)" },
    { value: "gemma3:4b", label: "gemma3:4b" },
    { value: "qwen3:8b", label: "qwen3:8b" },
  ],
  openai: [
    { value: "", label: "ברירת מחדל (gpt-5-mini)" },
    { value: "gpt-5-mini", label: "gpt-5-mini (מומלץ)" },
    { value: "gpt-4o-mini", label: "gpt-4o-mini" },
    { value: "gpt-4o", label: "gpt-4o" },
  ],
  gemini: [
    { value: "", label: "ברירת מחדל (gemini-2.0-flash)" },
    { value: "gemini-2.0-flash", label: "gemini-2.0-flash (מומלץ)" },
    { value: "gemini-1.5-flash", label: "gemini-1.5-flash" },
    { value: "gemini-1.5-pro", label: "gemini-1.5-pro" },
  ],
  anthropic: [
    { value: "", label: "ברירת מחדל (claude-3-haiku-20240307)" },
    { value: "claude-3-haiku-20240307", label: "claude-3-haiku-20240307" },
    { value: "claude-3-5-sonnet-20241022", label: "claude-3-5-sonnet-20241022" },
  ],
};

// יחס המרה משוער מדולר לשקל לצורך הצגת עלות (הערכה בלבד, לא חיוב אמיתי)
const ILS_PER_USD = 3.6;

type UsageInfo = {
  totalTokens: number;
  totalChars: number;
  estimatedCostUsd: number;
  estimatedCostIls: number;
  provider: string;
  modelName: string | null;
};

// טיפוסים לנתונים מחושבים מהמערכת (לא מה-LLM)
type ComputedPensionSource = {
  source_name: string;
  source_type: string; // "pension" or "capital"
  balance: number;
  monthly_pension: number;
  annuity_factor: number;
  tax_treatment: string;
};

type ComputedPensionData = {
  sources: ComputedPensionSource[];
  target_monthly_pension: number;
  accumulated_pension: number;
  remaining_capital: number;
  target_achieved: boolean;
  retirement_age: number;
};

async function persistPortfolioUpdateToDb(
  clientId: string | undefined,
  updater: (accounts: any[]) => any[],
) {
  if (!clientId) return;

  const portfolio = await apiFetch<any[]>(`/clients/${clientId}/pension-portfolio/`);
  const updated = updater(Array.isArray(portfolio) ? portfolio : []);
  await apiFetch(`/clients/${clientId}/pension-portfolio/save`, {
    method: "POST",
    body: JSON.stringify({ accounts: updated }),
  });
}

function estimateTokensForMessages(messages: LlmChatMessageDto[]): { totalTokens: number; totalChars: number } {
  if (!messages || messages.length === 0) {
    return { totalTokens: 0, totalChars: 0 };
  }

  const joined = messages
    .map((m) => `${m.role}: ${m.content ?? ""}`)
    .join("\n");

  const totalChars = joined.length;
  if (!totalChars) {
    return { totalTokens: 0, totalChars };
  }

  // קירוב גס: ~4 תווים לטוקן אחד
  const totalTokens = Math.ceil(totalChars / 4);
  return { totalTokens, totalChars };
}

function getEstimatedPricePer1kTokensUsd(provider: string | null | undefined): number {
  if (!provider) return 0;
  const normalized = provider.toLowerCase();

  // ערכי ברירת מחדל גסים לפי ספק – לשימוש פנימי בלבד
  if (normalized === "openai") return 0.003; // הערכה גסה בלבד
  if (normalized === "gemini") return 0.001; // כ-0.001$ ל-1,000 טוקנים
  if (normalized === "anthropic") return 0.002; // כ-0.002$ ל-1,000 טוקנים

  // Ollama מקומי – ללא עלות כספית
  return 0;
}

function estimateCostForCall(
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

function estimatePreviewCost(
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

  // להערכה גסה של טוקני תשובה – נכפיל את טוקני הקלט
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

/**
 * טוען את נתוני התיק הפנסיוני מה-localStorage ומחזיר אותם בפורמט מתאים ל-LLM
 */
function loadPensionPortfolioForLlm(clientId: string | undefined): LlmPensionPortfolioAccount[] {
  if (!clientId) return [];
  
  try {
    const rawData = loadPensionDataFromStorage(clientId);
    if (!rawData || rawData.length === 0) return [];
    
    // המר את הנתונים לפורמט המתאים ל-API
    return rawData.map((account) => ({
      מספר_חשבון: account.מספר_חשבון,
      שם_תכנית: account.שם_תכנית,
      חברה_מנהלת: account.חברה_מנהלת,
      סוג_מוצר: account.סוג_מוצר,
      יתרה: account.יתרה,
      תאריך_התחלה: account.תאריך_התחלה,
      פיצויים_מעסיק_נוכחי: account.פיצויים_מעסיק_נוכחי,
      פיצויים_ממעסיקים_קודמים_רצף_קצבה: account.פיצויים_ממעסיקים_קודמים_רצף_קצבה,
      תגמולי_עובד_עד_2000: account.תגמולי_עובד_עד_2000,
      תגמולי_עובד_אחרי_2000: account.תגמולי_עובד_אחרי_2000,
      תגמולי_מעביד_עד_2000: account.תגמולי_מעביד_עד_2000,
      תגמולי_מעביד_אחרי_2000: account.תגמולי_מעביד_אחרי_2000,
      תגמולים: account.תגמולים,
      סך_תגמולים: account.סך_תגמולים,
      סך_פיצויים: account.סך_פיצויים,
    }));
  } catch (e) {
    console.warn("Failed to load pension portfolio for LLM:", e);
    return [];
  }
}

const LlmPensionChat: React.FC = () => {
  const { id: clientId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { client } = useClientData(clientId);
  const [messages, setMessages] = useState<LlmChatMessageDto[]>([]);
  const [input, setInput] = useState("");
  const [pendingApprovalRequest, setPendingApprovalRequest] = useState<any | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [llmStatus, setLlmStatus] = useState<LlmStatusDto | null>(null);
  const [providerForm, setProviderForm] = useState<{ provider: string; modelName: string }>(
    { provider: "", modelName: "" },
  );
  const [isSwitchingProvider, setIsSwitchingProvider] = useState(false);
  const [isOpeningPublicChat, setIsOpeningPublicChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [usageByMessageIndex, setUsageByMessageIndex] = useState<Record<number, UsageInfo>>({});
  const [nextMessageUsage, setNextMessageUsage] = useState<UsageInfo | null>(null);
  const [computedData, setComputedData] = useState<ComputedPensionData | null>(null);

  const clientName = client?.full_name || (clientId ? `לקוח ${clientId}` : "");

  const getToolDisplayNameHebrew = (toolName: string): string => {
    const mapping: Record<string, string> = {
      RUN_RETIREMENT_SCENARIOS: 'הרצת תרחישי פרישה',
      EXECUTE_RETIREMENT_SCENARIO: 'החלת תרחיש',
      CHECK_DATA_COMPLETENESS: 'בדיקת שלמות נתונים',
      GET_TAX_PROJECTION: 'הערכת מס',
      SELECT_TARGET_PENSION_SCENARIO: 'בחירת תרחיש ליעד',
      BUILD_TARGET_PENSION_PLAN: 'בניית תכנית קצבה',
      FIND_OPTIMAL_SCENARIO: 'מציאת תרחיש אופטימלי',
      RUN_RETIREMENT_CASHFLOW_ANALYSIS: 'ניתוח פרישה',
      PROCESS_TERMINATION: 'סיום עבודה',
      TRANSFORM_FUNDS_TO_ASSETS: 'המרת תיק לנכסים',
      CALCULATE_CAPITAL_WITHDRAWAL_TAX: 'חישוב מס על משיכת הון',
      CALCULATE_TAX_SPREAD_BENEFIT: 'חישוב הטבת מס בפריסה',
      CALCULATE_TAX_EXEMPT_PENSION: 'חישוב קצבה פטורה (קיבוע זכויות)',
      GENERATE_FULL_REPORT: 'הפקת דוח',
      GENERATE_TAX_DEDUCTION_DOCUMENTS: 'הפקת מסמכי מס',
      GET_ACCOUNT_DETAILS: 'שליפת פרטי חשבון',
    };
    return mapping[toolName] || toolName;
  };

  // Auto-scroll to bottom when streaming
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

    const confirmed = window.confirm(
      "לנקות את השיחה לחלוטין ולהתחיל שיחה חדשה עם הסוכן?"
    );
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
      const updated = await llmApi.updateProvider(
        providerForm.provider,
        providerForm.modelName || undefined,
      );
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
      setError("לא ניתן לפתוח Public Chat: חסרה תעודת זהות ללקוח.");
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
        console.warn("Failed to load pension portfolio from DB for LLM chat, falling back to localStorage:", fetchErr);
      }

      let fullContent = "";
      let extractedComputedData: ComputedPensionData | null = null;
      const pendingUiActions: any[] = [];

      // Use streaming API (portfolio is loaded from DB on the server)
      for await (const chunk of llmApi.chatStream(newMessages, numericClientId, pensionPortfolioForLlm)) {
        fullContent += chunk;

        // חפש וחלץ נתונים מחושבים מהמערכת (לא מה-LLM)
        const computedStartMarker = "###COMPUTED_DATA###";
        const computedEndMarker = "###END_COMPUTED_DATA###";

        
        if (fullContent.includes(computedStartMarker) && fullContent.includes(computedEndMarker)) {
          const startIdx = fullContent.indexOf(computedStartMarker) + computedStartMarker.length;
          const endIdx = fullContent.indexOf(computedEndMarker);
          const jsonStr = fullContent.substring(startIdx, endIdx).trim();
          
          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.type === "computed_data" && parsed.data) {
              extractedComputedData = parsed.data as ComputedPensionData;
              setComputedData(extractedComputedData);
              console.log("Extracted computed pension data from system:", extractedComputedData);
            }
          } catch (parseErr) {
            console.warn("Failed to parse computed data JSON:", parseErr);
          }
          
          // הסר את הסמנים מהתוכן המוצג
          fullContent = fullContent.substring(0, fullContent.indexOf(computedStartMarker)) +
                        fullContent.substring(endIdx + computedEndMarker.length);
        }
        
        // D3.11: חפש וטפל באיפוס פיצויים מהפורטפוליו
        const severanceResetMarker = "###SEVERANCE_RESET###";
        const severanceResetEndMarker = "###END_SEVERANCE_RESET###";
        
        if (fullContent.includes(severanceResetMarker) && fullContent.includes(severanceResetEndMarker)) {
          const resetStartIdx = fullContent.indexOf(severanceResetMarker) + severanceResetMarker.length;
          const resetEndIdx = fullContent.indexOf(severanceResetEndMarker);
          const resetJsonStr = fullContent.substring(resetStartIdx, resetEndIdx).trim();
          
          try {
            const resetInfo = JSON.parse(resetJsonStr);
            if (resetInfo.portfolio_severance_to_reset) {
              console.log("📋 D3.11: Resetting severance in pension portfolio", resetInfo);
              // אפס את פיצויים_מעסיק_נוכחי בכל החשבונות ב-localStorage
              updatePensionDataInStorage(clientId, (accounts) => {
                return accounts.map(acc => ({
                  ...acc,
                  פיצויים_מעסיק_נוכחי: 0
                }));
              });
              await persistPortfolioUpdateToDb(clientId, (accounts) =>
                accounts.map((acc) => ({
                  ...acc,
                  פיצויים_מעסיק_נוכחי: 0,
                })),
              );
              console.log("✅ D3.11: Severance reset in localStorage completed");
            }
          } catch (parseErr) {
            console.warn("Failed to parse severance reset JSON:", parseErr);
          }
          
          // הסר את הסמנים מהתוכן המוצג
          fullContent = fullContent.substring(0, fullContent.indexOf(severanceResetMarker)) +
                        fullContent.substring(resetEndIdx + severanceResetEndMarker.length);
        }

        // D3.12: חפש וטפל בעדכוני המרה לטבלת המוצרים (איפוס רכיבים והפחתת יתרה)
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
                    if (
                      field.startsWith("תגמולי_") ||
                      field.startsWith("פיצויים_") ||
                      field === "קרן_השתלמות"
                    ) {
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
                    (acc: any) => String(acc.מספר_חשבון || "").trim() === accountNumber,
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

                    const eduDelta = Number((specific as any).קרן_השתלמות ?? 0) || 0;
                    if (eduDelta > 0) {
                      Object.keys(account).forEach((field) => {
                        if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
                          return;
                        }
                        if (
                          field.startsWith("תגמולי_") ||
                          field === "תגמולים" ||
                          field === "סך_תגמולים" ||
                          field === "קרן_השתלמות"
                        ) {
                          (account as any)[field] = 0;
                        }
                      });
                      account.יתרה = 0;
                    }
                  }

                  const originalBalance = Number(account.יתרה ?? 0) || 0;
                  const convertedAmount = Number(u.converted_amount ?? 0) || 0;
                  if (hasSpecific) {
                    const remainingFromComponents = computeRemainingBalanceFromComponents(account);
                    if (remainingFromComponents > 0 || convertedAmount > 0) {
                      account.יתרה = remainingFromComponents;
                    }
                  } else {
                    if (convertedAmount > 0) {
                      account.יתרה = Math.max(0, originalBalance - convertedAmount);
                    }
                  }

                  if (Math.abs(Number(account.יתרה ?? 0) || 0) < BALANCE_ZERO_EPSILON) {
                    account.יתרה = 0;
                  }

                  if (!hasSpecific && Number(account.יתרה ?? 0) === 0) {
                    Object.keys(account).forEach((field) => {
                      if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
                        return;
                      }
                      if (
                        field.startsWith("תגמולי_") ||
                        field.startsWith("פיצויים_") ||
                        field === "תגמולים" ||
                        field === "סך_תגמולים" ||
                        field === "סך_פיצויים" ||
                        field === "סך_רכיבים" ||
                        field === "קרן_השתלמות"
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

          // הסר את הסמנים מהתוכן המוצג
          fullContent = fullContent.substring(0, fullContent.indexOf(portfolioUpdateMarker)) +
                        fullContent.substring(updEndIdx + portfolioUpdateEndMarker.length);
        }

        // UI actions from system (open download URL / navigate)
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

          // remove markers from displayed content
          fullContent = fullContent.substring(0, fullContent.indexOf(uiActionMarker)) +
                        fullContent.substring(actionEndIdx + uiActionEndMarker.length);
        }
        
        const visible = (fullContent || "").trim();
        if (!visible && (sawApprovalRequestInStream || pendingApprovalRequest)) {
          setStreamingContent("נדרש אישור לפני הפעלת כלי. אשר/בטל בחלונית האישור.");
        } else {
          setStreamingContent(fullContent);
        }
      }

      // When done, add the complete message (without computed data markers)
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

      pendingUiActions.forEach((action: any) => {
        if (!action || typeof action !== "object") return;

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

        if (action.type === "navigate" && typeof action.path === "string" && action.path.trim()) {
          const url = normalizeUrl(action.path);
          if (!url) return;
          window.open(url, "_blank");
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

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    if (pendingApprovalRequest) {
      const raw = (input || "").trim().toLowerCase();
      const isApprovalText =
        raw === "מאשר" ||
        raw === "אני מאשר" ||
        raw === "מאשרת" ||
        raw === "אני מאשרת" ||
        raw === "כן" ||
        raw === "אשר" ||
        raw === "approve" ||
        raw === "ok";
      const isCancelText = raw === "בטל" || raw === "ביטול" || raw === "לא" || raw === "cancel";

      if (!isApprovalText && !isCancelText) {
        setError("נדרש אישור לפני הפעלת כלי. אנא אשר/בטל (בחלונית או ע" + "י כתיבה 'מאשר'/'בטל').");
        return;
      }

      setError(null);
      setInput("");
      await handleApprovalDecision(isApprovalText);
      return;
    }
    await sendMessage(input);
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

  const statusText = llmStatus
    ? `מודל: ${llmStatus.backend || "לא ידוע"}${
        llmStatus.model_name ? ` (${llmStatus.model_name})` : ""
      }`
    : "";

  // הערכת עלות משוערת לפרומפט הבא על בסיס ההיסטוריה והטקסט הנוכחי
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

  return (
    <div className="llm-chat-page">
      <div className="modern-card llm-chat-card">
        <div className="llm-chat-back-row">
          {clientId && (
            <Link
              to={`/clients/${clientId}`}
              className="llm-chat-back-link"
            >
              חזור לפרטי לקוח
            </Link>
          )}
        </div>
        <div className="card-header">
          <div>
            <h1 className="card-title">
              יועץ פרישה AI : טיפול בלקוח{clientName ? `  ${clientName}` : ""}
            </h1>
            <p className="card-subtitle">
              שיחה חופשית עם יועץ פרישה חכם. אפשר לשאול שאלות, לתאר מצב, ולבקש תרחישי "מה אם".
            </p>
            {statusText && (
              <div className="llm-chat-status">{statusText}</div>
            )}
          </div>

          <div className="llm-chat-header-actions">
            <div className="llm-chat-provider-controls">
              <div className="llm-chat-provider-label">בחירת מודל</div>
              <div className="llm-chat-provider-row">
                <select
                  className="llm-chat-provider-select"
                  value={providerForm.provider}
                  onChange={(e) =>
                    setProviderForm((prev) => ({
                      ...prev,
                      provider: e.target.value,
                    }))
                  }
                  disabled={isSending || isSwitchingProvider}
                >
                  <option value="ollama">Ollama (מקומי)</option>
                  <option value="openai">OpenAI (ChatGPT)</option>
                  <option value="gemini">Gemini (ענן)</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                </select>
                <button
                  type="button"
                  className="llm-chat-public-chat-button"
                  onClick={handleOpenPublicChat}
                  disabled={isSending || isSwitchingProvider || isOpeningPublicChat}
                >
                  {isOpeningPublicChat ? "פותח Public Chat..." : "פתח Public Chat של הלקוח"}
                </button>
                {(() => {
                  const providerKey = providerForm.provider || llmStatus?.provider || "";
                  const presets = MODEL_PRESETS[providerKey] || [];
                  const inPresets = presets.some(
                    (p) => p.value && p.value === (providerForm.modelName || ""),
                  );
                  const selectValue = inPresets
                    ? providerForm.modelName || ""
                    : providerForm.modelName
                    ? "custom"
                    : "";
                  const isCustom = selectValue === "custom";

                  return (
                    <>
                      <select
                        className="llm-chat-provider-input"
                        value={selectValue}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === "custom") {
                            setProviderForm((prev) => ({
                              ...prev,
                              modelName: prev.modelName || "",
                            }));
                          } else {
                            setProviderForm((prev) => ({
                              ...prev,
                              modelName: value,
                            }));
                          }
                        }}
                        disabled={isSending || isSwitchingProvider}
                      >
                        {presets.map((preset) => (
                          <option key={preset.value || "default"} value={preset.value}>
                            {preset.label}
                          </option>
                        ))}
                        <option value="custom">אחר (כתיבה חופשית)</option>
                      </select>
                      {isCustom && (
                        <input
                          className="llm-chat-provider-input"
                          type="text"
                          value={providerForm.modelName || ""}
                          onChange={(e) =>
                            setProviderForm((prev) => ({
                              ...prev,
                              modelName: e.target.value,
                            }))
                          }
                          placeholder="שם מודל אחר"
                          disabled={isSending || isSwitchingProvider}
                        />
                      )}
                    </>
                  );
                })()}
                <button
                  type="button"
                  className="btn llm-chat-provider-apply-button"
                  onClick={handleApplyProvider}
                  disabled={
                    isSending ||
                    isSwitchingProvider ||
                    !providerForm.provider
                  }
                >
                  החל
                </button>
              </div>
            </div>
            <button
              type="button"
              className="btn llm-chat-clear-button"
              onClick={handleClearChat}
              disabled={isSending || isSwitchingProvider}
            >
              🧹 נקה שיחה והתחל מחדש
            </button>
          </div>
        </div>

        {error && (
          <div className="alert alert-error llm-chat-error">{error}</div>
        )}

        {/* טבלת נתונים מחושבים מהמערכת - לא מה-LLM */}
        {computedData && computedData.sources.length > 0 && (
          <div className="llm-computed-data-panel" dir="rtl">
            <div className="llm-computed-data-header">
              <h3>📊 נתונים מחושבים מהמערכת (לא מה-AI)</h3>
              <span className="llm-computed-data-badge">
                {computedData.target_achieved ? "✅ יעד הושג" : "⚠️ יעד לא הושג"}
              </span>
            </div>
            
            <div className="llm-computed-data-summary">
              <div className="llm-computed-data-stat">
                <span className="stat-label">🎯 יעד קצבה:</span>
                <span className="stat-value">{computedData.target_monthly_pension.toLocaleString()} ₪/חודש</span>
              </div>
              <div className="llm-computed-data-stat">
                <span className="stat-label">קצבה מצטברת:</span>
                <span className="stat-value" style={{color: computedData.target_achieved ? '#16a34a' : '#dc2626'}}>
                  {computedData.accumulated_pension.toLocaleString()} ₪/חודש
                </span>
              </div>
              {!computedData.target_achieved && (
                <div className="llm-computed-data-stat">
                  <span className="stat-label">פער מהיעד:</span>
                  <span className="stat-value" style={{color: '#dc2626'}}>
                    {(computedData.target_monthly_pension - computedData.accumulated_pension).toLocaleString()} ₪
                  </span>
                </div>
              )}
              <div className="llm-computed-data-stat">
                <span className="stat-label">הון נותר:</span>
                <span className="stat-value">{computedData.remaining_capital.toLocaleString()} ₪</span>
              </div>
              <div className="llm-computed-data-stat">
                <span className="stat-label">גיל פרישה:</span>
                <span className="stat-value">{computedData.retirement_age}</span>
              </div>
            </div>

            <table className="llm-computed-data-table">
              <thead>
                <tr>
                  <th>מוצר</th>
                  <th>סוג</th>
                  <th>יתרה (₪)</th>
                  <th>קצבה חודשית (₪)</th>
                  <th>מקדם</th>
                  <th>מיסוי</th>
                </tr>
              </thead>
              <tbody>
                {computedData.sources.map((source, idx) => (
                  <tr key={idx} className={source.source_type === "pension" ? "pension-row" : "capital-row"}>
                    <td>{source.source_name}</td>
                    <td>{source.source_type === "pension" ? "קצבה" : "הון"}</td>
                    <td>{source.balance.toLocaleString()}</td>
                    <td className={source.monthly_pension > 0 ? "highlight-pension" : ""}>
                      {source.monthly_pension > 0 ? source.monthly_pension.toLocaleString() : "-"}
                    </td>
                    <td>{source.annuity_factor > 0 ? source.annuity_factor.toFixed(1) : "-"}</td>
                    <td>{source.tax_treatment === "exempt" ? "פטור" : source.tax_treatment === "taxable" ? "חייב" : source.tax_treatment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            <div className="llm-computed-data-note">
              💡 הנתונים למעלה מחושבים ישירות מהמערכת ולא מומצאים על ידי ה-AI
            </div>
          </div>
        )}

        <div className="llm-chat-messages" dir="rtl">
          {messages.length === 0 && (
            <div className="llm-chat-empty">
              התחל בשאלה או תיאור מצב פנסיוני, למשל: "אני בן 40, חוסך 3,000 ש" + "ח בחודש ורוצה להבין מה תהיה הקצבה".
            </div>
          )}

          {messages.map((m, idx) => (
            <div
              key={idx}
              className={
                "llm-chat-message " +
                (m.role === "user"
                  ? "llm-chat-message-user"
                  : m.role === "assistant"
                  ? "llm-chat-message-assistant"
                  : "llm-chat-message-system")
              }
            >
              <div className="llm-chat-message-role">
                {m.role === "user" ? "אתה" : m.role === "assistant" ? "יועץ" : "מערכת"}
              </div>
              <div className="llm-chat-message-content">{m.content}</div>
              {m.role === "assistant" && usageByMessageIndex[idx] && (
                <div className="llm-chat-message-usage">
                  {`צריכת מודל להודעה זו: ${usageByMessageIndex[idx].totalTokens.toLocaleString()} טוקנים`}
                  {usageByMessageIndex[idx].estimatedCostIls > 0 && (
                    <span>
                      {` (~${usageByMessageIndex[idx].estimatedCostIls.toFixed(3)} ₪, הערכה)`}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Show streaming content in real-time */}
          {streamingContent && (
            <div className="llm-chat-message llm-chat-message-assistant llm-chat-message-streaming">
              <div className="llm-chat-message-role">יועץ</div>
              <div className="llm-chat-message-content">{streamingContent}</div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {pendingApprovalRequest && (
          <div className="llm-chat-approval-row" dir="rtl">
            <div className="llm-chat-approval-text">
              {(() => {
                const rawToolName =
                  typeof pendingApprovalRequest?.tool_name === 'string'
                    ? pendingApprovalRequest.tool_name
                    : '';
                const toolLabel = rawToolName ? getToolDisplayNameHebrew(rawToolName) : 'כלי';
                return `נדרש אישור לפני הפעלת כלי: ${toolLabel}. אשר/בטל:`;
              })()}
            </div>
            <div className="llm-chat-approval-actions">
              <button
                type="button"
                className="llm-chat-approval-button llm-chat-approval-approve"
                onClick={() => handleApprovalDecision(true)}
                disabled={isSending}
              >
                אשר
              </button>
              <button
                type="button"
                className="llm-chat-approval-button llm-chat-approval-cancel"
                onClick={() => handleApprovalDecision(false)}
                disabled={isSending}
              >
                בטל
              </button>
            </div>
          </div>
        )}

        <form className="llm-chat-input-row" onSubmit={handleSend}>
          <textarea
            className="llm-chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="כתוב כאן שאלה או בקשה ליועץ הפרישה..."
            rows={3}
          />
          {nextMessageUsage && nextMessageUsage.totalTokens > 0 && (
            <div className="llm-chat-estimated-cost">
              {`עלות משוערת לפרומפט זה: ${nextMessageUsage.totalTokens.toLocaleString()} טוקנים`}
              {nextMessageUsage.estimatedCostIls > 0 && (
                <span>
                  {` (~${nextMessageUsage.estimatedCostIls.toFixed(3)} ₪, הערכה)`}
                </span>
              )}
            </div>
          )}
          <button
            type="submit"
            className="btn btn-primary llm-chat-send-button"
            disabled={isSending || !input.trim()}
          >
            {isSending ? "שולח..." : "שלח"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LlmPensionChat;
