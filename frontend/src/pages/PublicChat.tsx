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

function estimateTokens(text: string): number {
  const trimmed = (text || "").trim();
  if (!trimmed) return 0;
  return Math.ceil(trimmed.length / 4);
}

function parsePositiveInt(input: string): number {
  const cleaned = (input || "").replace(/[\s,]/g, "");
  const value = Number.parseInt(cleaned, 10);
  if (!Number.isFinite(value) || Number.isNaN(value) || value <= 0) {
    return 0;
  }
  return value;
}

function PublicChatStartPage() {
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
  const [notice, setNotice] = useState<string | null>(null);
  const [topUpValue, setTopUpValue] = useState("1000");
  const [canTopUp, setCanTopUp] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

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

    setCanTopUp(Boolean(window.localStorage.getItem("systemAccessPassword")));

    let active = true;
    (async () => {
      try {
        const [s, h] = await Promise.all([
          publicChatApi.status(sessionKey),
          publicChatApi.history(sessionKey),
        ]);

        if (!active) return;

        setStatus(s);
        setMessages(h.messages || []);
      } catch (err) {
        if (!active) return;
        setError(handleApiError(err));
      }
    })();

    return () => {
      active = false;
    };
  }, [sessionKey]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!sessionKey) return;

    const trimmed = input.trim();
    if (!trimmed) return;

    setError(null);
    setNotice(null);
    setIsSending(true);

    try {
      setMessages((prev) => [...prev, { role: "user", content: trimmed, estimated_tokens: estimateTokens(trimmed) }]);
      setInput("");

      const res = await publicChatApi.sendMessage(sessionKey, trimmed);

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
      setError(handleApiError(err));
      const s = await publicChatApi.status(sessionKey).catch(() => null);
      if (s) {
        setStatus(s);
      }
    } finally {
      setIsSending(false);
    }
  }

  async function handleTopUp() {
    const key = sessionKey;
    if (!key) return;

    setError(null);
    setNotice(null);

    if (!canTopUp) {
      setError("טעינת טוקנים זמינה רק למנהל מערכת");
      return;
    }

    const tokens = parsePositiveInt(topUpValue);

    if (!tokens || tokens <= 0) {
      setError("יש להזין מספר טוקנים חיובי");
      return;
    }

    try {
      const before = status?.token_balance ?? null;
      const res = await publicChatApi.topUp(key, tokens);
      setStatus((prev) =>
        prev
          ? {
              ...prev,
              token_balance: res.token_balance,
              tokens_spent: res.tokens_spent,
            }
          : prev,
      );

      const refreshed = await publicChatApi.status(key).catch(() => null);
      if (refreshed) {
        setStatus(refreshed);
      }

      const after = refreshed?.token_balance ?? res.token_balance;
      if (before != null && after === before) {
        setError("בקשת טעינה נשלחה אבל היתרה לא השתנתה. זה בדרך כלל אומר שהבקשה לא אומתה מול השרת או שנשלחה למושב אחר.");
      } else {
        setNotice(`נטענו ${tokens} טוקנים. יתרה חדשה: ${after}`);
      }
    } catch (err) {
      const msg = handleApiError(err);
      if ((msg || "").toLowerCase().includes("unauthorized")) {
        setError("טעינת טוקנים דורשת סיסמת מערכת");
        return;
      }
      setError(msg);
    }
  }

  const depleted = (status?.token_balance ?? 0) <= 0;

  const modelLabel = useMemo(() => {
    if (!status) return null;
    const backend = status.llm_backend || status.llm_provider;
    const model = status.llm_model_name;
    if (!backend && !model) return null;
    return `${backend || "LLM"}${model ? `: ${model}` : ""}`;
  }, [status]);

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
            <Link to="/public-chat" className="public-chat-link">חדש</Link>
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

        {notice && <div className="public-chat-notice banner">{notice}</div>}
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

        <div className="public-chat-topup">
          <div className="public-chat-topup-row">
            <input
              className="public-chat-input"
              value={topUpValue}
              onChange={(e) => setTopUpValue(e.target.value)}
              inputMode="numeric"
              placeholder="לדוגמה: 1000"
            />
            <button
              className="public-chat-secondary"
              type="button"
              onClick={handleTopUp}
              disabled={!canTopUp}
            >
              טעינת טוקנים
            </button>
          </div>
          {canTopUp && (
            <div className="public-chat-topup-quick">
              <button type="button" className="public-chat-quick" onClick={() => setTopUpValue("500")}>
                +500
              </button>
              <button type="button" className="public-chat-quick" onClick={() => setTopUpValue("1000")}>
                +1000
              </button>
              <button type="button" className="public-chat-quick" onClick={() => setTopUpValue("5000")}>
                +5000
              </button>
            </div>
          )}
          {!canTopUp && (
            <div className="public-chat-hint">טעינת טוקנים זמינה רק למנהל מערכת</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PublicChat() {
  const { sessionKey } = useParams<{ sessionKey?: string }>();

  if (sessionKey) {
    return <PublicChatSessionPage />;
  }

  return <PublicChatStartPage />;
}
