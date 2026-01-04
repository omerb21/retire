import React from "react";

import { LlmChatMessageDto } from "../../../lib/api";
import { UsageInfo } from "../types";

type Props = {
  messages: LlmChatMessageDto[];
  streamingContent: string;
  usageByMessageIndex: Record<number, UsageInfo>;
  messagesEndRef: React.RefObject<HTMLDivElement>;
};

export default function MessagesPanel({
  messages,
  streamingContent,
  usageByMessageIndex,
  messagesEndRef,
}: Props) {
  void usageByMessageIndex;
  return (
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
        </div>
      ))}

      {streamingContent && (
        <div className="llm-chat-message llm-chat-message-assistant llm-chat-message-streaming">
          <div className="llm-chat-message-role">יועץ</div>
          <div className="llm-chat-message-content">{streamingContent}</div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}
