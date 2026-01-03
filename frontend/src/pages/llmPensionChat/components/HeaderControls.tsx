import React from "react";
import { Link } from "react-router-dom";

import { LlmStatusDto } from "../../../lib/api";

import { MODEL_PRESETS } from "../constants";

type ProviderForm = { provider: string; modelName: string };

type Props = {
  clientId: string | undefined;
  clientName: string;
  statusText: string;
  providerForm: ProviderForm;
  setProviderForm: React.Dispatch<React.SetStateAction<ProviderForm>>;
  llmStatus: LlmStatusDto | null;
  isSending: boolean;
  isSwitchingProvider: boolean;
  isOpeningPublicChat: boolean;
  onApplyProvider: () => void;
  onOpenPublicChat: () => void;
  onClearChat: () => void;
};

export default function HeaderControls({
  clientId,
  clientName,
  statusText,
  providerForm,
  setProviderForm,
  llmStatus,
  isSending,
  isSwitchingProvider,
  isOpeningPublicChat,
  onApplyProvider,
  onOpenPublicChat,
  onClearChat,
}: Props) {
  return (
    <>
      <div className="llm-chat-back-row">
        {clientId && (
          <Link to={`/clients/${clientId}`} className="llm-chat-back-link">
            חזור לפרטי לקוח
          </Link>
        )}
      </div>
      <div className="card-header">
        <div>
          <h1 className="card-title">יועץ פרישה AI : טיפול בלקוח{clientName ? `  ${clientName}` : ""}</h1>
          <p className="card-subtitle">
            שיחה חופשית עם יועץ פרישה חכם. אפשר לשאול שאלות, לתאר מצב, ולבקש תרחישי "מה אם".
          </p>
          {statusText && <div className="llm-chat-status">{statusText}</div>}
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
                onClick={onOpenPublicChat}
                disabled={isSending || isSwitchingProvider || isOpeningPublicChat}
              >
                {isOpeningPublicChat ? "פותח Public Chat..." : "פתח Public Chat של הלקוח"}
              </button>
              {(() => {
                const providerKey = providerForm.provider || llmStatus?.provider || "";
                const presets = MODEL_PRESETS[providerKey] || [];
                const inPresets = presets.some((p) => p.value && p.value === (providerForm.modelName || ""));
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
                onClick={onApplyProvider}
                disabled={isSending || isSwitchingProvider || !providerForm.provider}
              >
                החל
              </button>
            </div>
          </div>
          <button
            type="button"
            className="btn llm-chat-clear-button"
            onClick={onClearChat}
            disabled={isSending || isSwitchingProvider}
          >
            🧹 נקה שיחה והתחל מחדש
          </button>
        </div>
      </div>
    </>
  );
}
