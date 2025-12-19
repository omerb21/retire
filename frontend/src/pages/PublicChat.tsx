import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { publicChatApi, handleApiError } from "../lib/api";
import "./PublicChat.css";

type ChatMessage = { role: string; content: string };

type Status = {
  session_key: string;
  client_id: number;
  client_name: string | null;
  token_balance: number;
  tokens_spent: number;
  is_active: boolean;
};

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
    setIsSending(true);

    try {
      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setInput("");

      const res = await publicChatApi.sendMessage(sessionKey, trimmed);

      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
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

    if (!canTopUp) {
      setError("טעינת טוקנים זמינה רק למנהל מערכת");
      return;
    }

    let tokens = 0;
    try {
      tokens = parseInt(topUpValue, 10);
    } catch {
      tokens = 0;
    }

    if (!tokens || tokens <= 0) {
      setError("יש להזין מספר טוקנים חיובי");
      return;
    }

    try {
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

  return (
    <div className="public-chat-page">
      <div className="public-chat-shell">
        <div className="public-chat-topbar">
          <div className="public-chat-brand">{displayName}</div>
          <div className="public-chat-meta">
            <span className={depleted ? "public-chat-pill danger" : "public-chat-pill"}>
              יתרה: {status?.token_balance ?? "-"}
            </span>
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

        <div className="public-chat-topup">
          <div className="public-chat-topup-row">
            <input
              className="public-chat-input"
              value={topUpValue}
              onChange={(e) => setTopUpValue(e.target.value)}
              inputMode="numeric"
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
