import React from "react";

import { getToolDisplayNameHebrew } from "../toolDisplayName.ts";

type Props = {
  pendingApprovalRequest: any | null;
  isSending: boolean;
  onApprove: () => void;
  onCancel: () => void;
};

export default function ApprovalRow({ pendingApprovalRequest, isSending, onApprove, onCancel }: Props) {
  if (!pendingApprovalRequest) {
    return null;
  }

  return (
    <div className="llm-chat-approval-row" dir="rtl">
      <div className="llm-chat-approval-text">
        {(() => {
          const rawToolName =
            typeof pendingApprovalRequest?.tool_name === "string" ? pendingApprovalRequest.tool_name : "";
          const toolLabel = rawToolName ? getToolDisplayNameHebrew(rawToolName) : "כלי";
          return `נדרש אישור לפני הפעלת כלי: ${toolLabel}. אשר/בטל:`;
        })()}
      </div>
      <div className="llm-chat-approval-actions">
        <button
          type="button"
          className="llm-chat-approval-button llm-chat-approval-approve"
          onClick={onApprove}
          disabled={isSending}
        >
          אשר
        </button>
        <button
          type="button"
          className="llm-chat-approval-button llm-chat-approval-cancel"
          onClick={onCancel}
          disabled={isSending}
        >
          בטל
        </button>
      </div>
    </div>
  );
}
