import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { publicChatApi, handleApiError } from "../lib/api";
import "./PublicChat.css";

type ChatMessage = { role: string; content: string; estimated_tokens?: number; tokens_used?: number };

type Status = {
  session_key: string;
  client_id: number;
  client_name: string | null;
  token_balance: number;
  tokens_spent: number;
  is_active: boolean;
  llm_provider?: string | null;
  llm_backend?: string | null;
  llm_model_name?: string | null;
};

const PUBLIC_CHAT_PASSWORD_STORAGE_PREFIX = "publicChatPassword:";

function getStoredPublicChatPassword(sessionKey: string): string | null {
  try {
    return window.sessionStorage.getItem(`${PUBLIC_CHAT_PASSWORD_STORAGE_PREFIX}${sessionKey}`);
  } catch {
    return null;
  }
}

function setStoredPublicChatPassword(sessionKey: string, password: string): void {
  try {
    window.sessionStorage.setItem(`${PUBLIC_CHAT_PASSWORD_STORAGE_PREFIX}${sessionKey}`, password);
  } catch {
    // ignore
  }
}

function clearStoredPublicChatPassword(sessionKey: string): void {
  try {
    window.sessionStorage.removeItem(`${PUBLIC_CHAT_PASSWORD_STORAGE_PREFIX}${sessionKey}`);
  } catch {
    // ignore
  }
}

function estimateTokens(text: string): number {
  const trimmed = (text || "").trim();
  if (!trimmed) return 0;
  return Math.ceil(trimmed.length / 4);
}

export function PublicChatStartPage() {
  const navigate = useNavigate();
  const [idNumber, setIdNumber] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = idNumber.trim();
    if (!trimmed) {
      setError("יש להזין תעודת זהות");
      return;
    }

    setIsLoading(true);
    try {
      const started = await publicChatApi.start(trimmed);
      setStoredPublicChatPassword(started.session_key, trimmed);
      navigate(`/public-chat/${started.session_key}`);
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="public-chat-page">
      <div className="public-chat-shell">
        <div className="public-chat-topbar">
          <div className="public-chat-brand">צ'אט פרישה</div>
        </div>

        <div className="public-chat-card">
          <h2 className="public-chat-title">התחלת שיחה</h2>
          <p className="public-chat-subtitle">הזן תעודת זהות כדי לפתוח שיחה אישית.</p>

          <form onSubmit={handleStart} className="public-chat-form">
            <label className="public-chat-label">
              תעודת זהות
              <input
                className="public-chat-input"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value)}
                disabled={isLoading}
                inputMode="numeric"
              />
            </label>

            {error && <div className="public-chat-error">{error}</div>}

            <button className="public-chat-primary" type="submit" disabled={isLoading}>
              {isLoading ? "פותח..." : "המשך"}
            </button>
          </form>

          <div className="public-chat-hint">
            <Link to="/" className="public-chat-link">חזרה</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function PublicChatSessionPage() {
  const { sessionKey } = useParams<{ sessionKey: string }>();
  const [status, setStatus] = useState<Status | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publicChatPassword, setPublicChatPassword] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sessionKey) return;
    const existing = getStoredPublicChatPassword(sessionKey);
    if (existing) {
      setPublicChatPassword(existing);
    }
  }, [sessionKey]);

  const displayName = useMemo(() => {
    if (!status) return "";
    return status.client_name || `לקוח ${status.client_id}`;
  }, [status]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  useEffect(() => {
    if (!sessionKey) {
      return;
    }

    const trimmedPassword = (publicChatPassword || "").trim();
    if (!trimmedPassword) {
      return;
    }

    let active = true;
    (async () => {
      try {
        const [s, h] = await Promise.all([
          publicChatApi.status(sessionKey, trimmedPassword),
          publicChatApi.history(sessionKey, trimmedPassword),
        ]);

        if (!active) return;

        setStatus(s);
        setMessages(h.messages || []);
      } catch (err) {
        if (!active) return;
        const msg = handleApiError(err);
        setError(msg);
        if (msg.toLowerCase().includes("password")) {
          clearStoredPublicChatPassword(sessionKey);
          setPublicChatPassword("");
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [sessionKey, publicChatPassword]);

  async function handleUnlock(e: React.FormEvent) {
    e.preventDefault();
    if (!sessionKey) return;
    setError(null);

    const trimmed = (publicChatPassword || "").trim();
    if (!trimmed) {
      setError("יש להזין תעודת זהות");
      return;
    }

    try {
      await publicChatApi.status(sessionKey, trimmed);
      setStoredPublicChatPassword(sessionKey, trimmed);
      setPublicChatPassword(trimmed);
    } catch (err) {
      setError(handleApiError(err));
      clearStoredPublicChatPassword(sessionKey);
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!sessionKey) return;

    const trimmedPassword = (publicChatPassword || "").trim();
    if (!trimmedPassword) return;

    const trimmed = input.trim();
    if (!trimmed) return;

    setError(null);
    setIsSending(true);

    try {
      setMessages((prev) => [...prev, { role: "user", content: trimmed, estimated_tokens: estimateTokens(trimmed) }]);
      setInput("");

      const res = await publicChatApi.sendMessage(sessionKey, trimmed, trimmedPassword);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          estimated_tokens: estimateTokens(res.reply),
          tokens_used: res.tokens_used,
        },
      ]);
      setStatus((prev) =>
        prev
          ? {
              ...prev,
              token_balance: res.token_balance,
              tokens_spent: res.tokens_spent,
            }
          : prev,
      );
    } catch (err) {
      const msg = handleApiError(err);
      setError(msg);
      if (msg.toLowerCase().includes("password")) {
        clearStoredPublicChatPassword(sessionKey);
        setPublicChatPassword("");
        setStatus(null);
        setMessages([]);
        return;
      }

      const s = await publicChatApi.status(sessionKey, trimmedPassword).catch(() => null);
      if (s) {
        setStatus(s);
      }
    } finally {
      setIsSending(false);
    }
  }

  if (sessionKey && !(publicChatPassword || "").trim()) {
    return (
      <div className="public-chat-page">
        <div className="public-chat-shell">
          <div className="public-chat-topbar">
            <div className="public-chat-brand">צ'אט פרישה</div>
          </div>

          <div className="public-chat-card">
            <h2 className="public-chat-title">פתיחת שיחה</h2>
            <p className="public-chat-subtitle">כדי לפתוח את השיחה יש להזין תעודת זהות של הלקוח.</p>

            <form onSubmit={handleUnlock} className="public-chat-form">
              <label className="public-chat-label">
                תעודת זהות
                <input
                  className="public-chat-input"
                  value={publicChatPassword}
                  onChange={(e) => setPublicChatPassword(e.target.value)}
                  inputMode="numeric"
                />
              </label>

              {error && <div className="public-chat-error">{error}</div>}

              <button className="public-chat-primary" type="submit">
                המשך
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  const depleted = (status?.token_balance ?? 0) <= 0;

  const modelLabel = useMemo(() => {
    if (!status) return null;
    const backend = status.llm_backend || status.llm_provider;
    const model = status.llm_model_name;
    if (!backend && !model) return null;
    return `${backend || "LLM"}${model ? `: ${model}` : ""}`;
  }, [status]);

  function handleClearChat() {
    const ok = window.confirm("לנקות את השיחה מהמסך? פעולה זו לא מוחקת את ההיסטוריה מהשרת.");
    if (!ok) return;
    setMessages([]);
    setError(null);
    setInput("");
  }

  return (
    <div className="public-chat-page">
      <div className="public-chat-shell">
        <div className="public-chat-topbar">
          <div className="public-chat-brand">{displayName}</div>
          <div className="public-chat-meta">
            <span className={depleted ? "public-chat-pill danger" : "public-chat-pill"}>
              יתרה: {status?.token_balance ?? "-"}
            </span>
            {modelLabel && <span className="public-chat-pill">{modelLabel}</span>}
            <button type="button" className="public-chat-secondary" onClick={handleClearChat}>
              נקה שיחה
            </button>
          </div>
        </div>

        <div className="public-chat-thread">
          {messages.map((m, idx) => (
            <div
              key={`${m.role}-${idx}`}
              className={m.role === "user" ? "public-chat-bubble user" : "public-chat-bubble assistant"}
            >
              {m.content}
              <div className="public-chat-bubble-meta">
                {typeof m.estimated_tokens === "number" ? `~${m.estimated_tokens} טוקנים` : ""}
                {typeof m.tokens_used === "number" ? ` | צריכת שיחה: ${m.tokens_used}` : ""}
              </div>
            </div>
          ))}
          {isSending && <div className="public-chat-bubble assistant">...</div>}
          <div ref={bottomRef} />
        </div>

        {error && <div className="public-chat-error banner">{error}</div>}

        <form onSubmit={handleSend} className="public-chat-composer">
          <input
            className="public-chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isSending || depleted}
            placeholder={depleted ? "אין יתרה, יש לבצע טעינה" : "כתוב הודעה..."}
          />
          <button className="public-chat-primary" type="submit" disabled={isSending || depleted}>
            שלח
          </button>
        </form>
      </div>
    </div>
  );
}

export default function PublicChat() {
  const { sessionKey } = useParams<{ sessionKey?: string }>();

  if (sessionKey) {
    return <PublicChatSessionPage />;
  }

  const hasSystemAccess = Boolean(window.localStorage.getItem("systemAccessPassword"));
  if (!hasSystemAccess) {
    return (
      <div className="public-chat-page">
        <div className="public-chat-shell">
          <div className="public-chat-topbar">
            <div className="public-chat-brand">צ'אט פרישה</div>
          </div>
          <div className="public-chat-card">
            <h2 className="public-chat-title">קישור לא תקין</h2>
            <p className="public-chat-subtitle">
              פתיחת שיחה חדשה זמינה רק דרך מנהל המערכת. נא להשתמש בקישור שקיבלת.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <PublicChatStartPage />;
}
