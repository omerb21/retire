import React, { useState, FormEvent, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { llmApi, LlmChatMessageDto, LlmStatusDto, LlmPensionPortfolioAccount, handleApiError } from "../lib/api";
import { useClientData } from "./ClientDetails/hooks/useClientData";
import { loadLlmChatFromStorage, saveLlmChatToStorage, clearLlmChatFromStorage } from "../services/llmChatStorageService";
import { loadPensionDataFromStorage } from "./PensionPortfolio/services/pensionPortfolioStorageService";
import "./LlmPensionChat.css";

const MODEL_PRESETS: Record<string, { value: string; label: string }[]> = {
  ollama: [
    { value: "", label: "ברירת מחדל (מהשרת)" },
    { value: "gemma3:4b", label: "gemma3:4b" },
    { value: "qwen3:8b", label: "qwen3:8b" },
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
  const { client } = useClientData(clientId);
  const [messages, setMessages] = useState<LlmChatMessageDto[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [llmStatus, setLlmStatus] = useState<LlmStatusDto | null>(null);
  const [providerForm, setProviderForm] = useState<{ provider: string; modelName: string }>(
    { provider: "", modelName: "" },
  );
  const [isSwitchingProvider, setIsSwitchingProvider] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [usageByMessageIndex, setUsageByMessageIndex] = useState<Record<number, UsageInfo>>({});
  const [nextMessageUsage, setNextMessageUsage] = useState<UsageInfo | null>(null);
  const [computedData, setComputedData] = useState<ComputedPensionData | null>(null);

  const clientName = client?.full_name || (clientId ? `לקוח ${clientId}` : "");

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

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
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
      
      // טען את נתוני התיק הפנסיוני מה-localStorage
      const pensionPortfolio = loadPensionPortfolioForLlm(clientId);
      if (pensionPortfolio.length > 0) {
        console.log(`Sending ${pensionPortfolio.length} pension accounts to LLM`);
      }
      
      let fullContent = "";
      let extractedComputedData: ComputedPensionData | null = null;

      // Use streaming API with pension portfolio
      for await (const chunk of llmApi.chatStream(newMessages, numericClientId, pensionPortfolio)) {
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
        
        // הצג רק את התוכן ללא סמני הנתונים המחושבים
        setStreamingContent(fullContent);
      }

      // When done, add the complete message (without computed data markers)
      const assistantMessage: LlmChatMessageDto = {
        role: "assistant",
        content: fullContent.trim(),
      };
      const finalMessages = [...newMessages, assistantMessage];
      setMessages(finalMessages);
      setStreamingContent("");

      // הערכת צריכת טוקנים ועלות להודעת היועץ
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
                  <option value="gemini">Gemini (ענן)</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                </select>
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
              התחל בשאלה או תיאור מצב פנסיוני, למשל: "אני בן 40, חוסך 3,000 ש"ח בחודש ורוצה להבין מה תהיה הקצבה".
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
