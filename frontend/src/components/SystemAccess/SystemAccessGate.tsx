import React, { useState, useEffect } from "react";
import { API_BASE } from "../../lib/api";
import "./SystemAccessGate.css";

interface SystemAccessGateProps {
  onAccessGranted: () => void;
}

const STORAGE_KEY = "systemAccessPassword";

const SystemAccessGate: React.FC<SystemAccessGateProps> = ({ onAccessGranted }) => {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) {
      onAccessGranted();
    }
  }, [onAccessGranted]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmed = password.trim();
    if (!trimmed) {
      setError("יש להזין סיסמה");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/health`, {
        method: "GET",
        headers: {
          "X-System-Password": trimmed,
        },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setError("סיסמת מערכת שגויה");
        } else {
          setError("שגיאה באימות מול השרת");
        }
        return;
      }

      window.localStorage.setItem(STORAGE_KEY, trimmed);
      onAccessGranted();
    } catch (err) {
      console.error("System access check failed", err);
      setError("שגיאת חיבור לשרת");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="system-access-gate">
      <div className="system-access-card">
        <h2 className="system-access-title">כניסה למערכת תכנון פרישה</h2>
        <p className="system-access-subtitle">
          הזן סיסמת מערכת לקבלת גישה מלאה
        </p>
        <form onSubmit={handleSubmit} className="system-access-form">
          <label className="system-access-label">
            סיסמת מערכת
            <input
              type="password"
              className="system-access-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
            />
          </label>
          {error && <div className="system-access-error">{error}</div>}
          <button
            type="submit"
            className="system-access-button"
            disabled={loading}
          >
            {loading ? "בודק..." : "כניסה"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default SystemAccessGate;
