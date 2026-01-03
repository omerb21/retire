import React from "react";
import { useParams } from "react-router-dom";

import { useClientData } from "../ClientDetails/hooks/useClientData";

import ApprovalRow from "./components/ApprovalRow";
import ComputedDataPanel from "./components/ComputedDataPanel";
import HeaderControls from "./components/HeaderControls";
import MessagesPanel from "./components/MessagesPanel";
import { useLlmPensionChat } from "./useLlmPensionChat";

const LlmPensionChat: React.FC = () => {
  const { id: clientId } = useParams<{ id: string }>();
  const { client } = useClientData(clientId);

  const {
    messages,
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
  } = useLlmPensionChat({ clientId, client });

  const clientName = client?.full_name || (clientId ? `לקוח ${clientId}` : "");

  return (
    <div className="llm-chat-page">
      <div className="modern-card llm-chat-card">
        <HeaderControls
          clientId={clientId}
          clientName={clientName}
          statusText={statusText}
          providerForm={providerForm}
          setProviderForm={setProviderForm}
          llmStatus={llmStatus}
          isSending={isSending}
          isSwitchingProvider={isSwitchingProvider}
          isOpeningPublicChat={isOpeningPublicChat}
          onApplyProvider={handleApplyProvider}
          onOpenPublicChat={handleOpenPublicChat}
          onClearChat={handleClearChat}
        />

        {error && <div className="alert alert-error llm-chat-error">{error}</div>}

        {computedData && <ComputedDataPanel computedData={computedData} />}

        <MessagesPanel
          messages={messages}
          streamingContent={streamingContent}
          usageByMessageIndex={usageByMessageIndex}
          messagesEndRef={messagesEndRef}
        />

        <ApprovalRow
          pendingApprovalRequest={pendingApprovalRequest}
          isSending={isSending}
          onApprove={() => handleApprovalDecision(true)}
          onCancel={() => handleApprovalDecision(false)}
        />

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
                <span>{` (~${nextMessageUsage.estimatedCostIls.toFixed(3)} ₪, הערכה)`}</span>
              )}
            </div>
          )}
          <button type="submit" className="btn btn-primary llm-chat-send-button" disabled={isSending || !input.trim()}>
            {isSending ? "שולח..." : "שלח"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LlmPensionChat;
