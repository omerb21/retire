import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type FixationResult = {
  summary?: {
    total_pension?: number;
    total_grants?: number;
    net_amount?: number;
  };
  appendices?: Array<{
    name: string;
    data: any;
  }>;
  grants?: Array<{
    type: string;
    amount: number;
    details: any;
  }>;
  calculation_details?: any;
};

export default function Fixation() {
  const { id: clientId } = useParams<{ id: string }>();
  const [result, setResult] = useState<FixationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  async function handleComputeFixation() {
    if (!clientId) return;

    setLoading(true);
    setError("");
    setResult(null);
    
    try {
      // Use the correct fixation endpoint path with proper segment order
      // Backend route is /fixation/{client_id}/compute
      const data = await apiFetch<FixationResult>(`/fixation/${clientId}/compute`, {
        method: "POST",
      });
      console.log("Fixation compute response:", data);
      setResult(data);
    } catch (e: any) {
      setError(`שגיאה בחישוב קיבוע: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to={`/clients/${clientId}`}>← חזרה לפרטי לקוח</Link>
      </div>
      
      <h2>קיבוע מס</h2>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Compute Button */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>חישוב קיבוע</h3>
        <button
          type="button"
          onClick={handleComputeFixation}
          disabled={loading}
          style={{ 
            padding: "12px 20px", 
            backgroundColor: loading ? "#6c757d" : "#dc3545", 
            color: "white", 
            border: "none", 
            borderRadius: 4,
            fontSize: "16px",
            cursor: loading ? "not-allowed" : "pointer"
          }}
        >
          {loading ? "מחשב..." : "חשב קיבוע"}
        </button>
      </section>

      {/* Results Display */}
      {result && (
        <section style={{ marginBottom: 32 }}>
          <h3>תוצאות קיבוע</h3>
          
          {/* Summary */}
          {result.summary && (
            <div style={{ marginBottom: 24, padding: 16, border: "1px solid #ddd", borderRadius: 4, backgroundColor: "#f8f9fa" }}>
              <h4>סיכום</h4>
              <div style={{ display: "grid", gap: 8 }}>
                {result.summary.total_pension && (
                  <div><strong>סך פנסיה:</strong> ₪{result.summary.total_pension.toLocaleString()}</div>
                )}
                {result.summary.total_grants && (
                  <div><strong>סך גרנטים:</strong> ₪{result.summary.total_grants.toLocaleString()}</div>
                )}
                {result.summary.net_amount && (
                  <div style={{ color: "green", fontWeight: "bold", fontSize: "18px" }}>
                    <strong>סכום נטו:</strong> ₪{result.summary.net_amount.toLocaleString()}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Grants */}
          {result.grants && result.grants.length > 0 && (
            <div style={{ marginBottom: 24, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
              <h4>גרנטים</h4>
              <div style={{ display: "grid", gap: 12 }}>
                {result.grants.map((grant, index) => (
                  <div key={index} style={{ padding: 12, border: "1px solid #e9ecef", borderRadius: 4 }}>
                    <div><strong>סוג:</strong> {grant.type}</div>
                    <div><strong>סכום:</strong> ₪{grant.amount.toLocaleString()}</div>
                    {grant.details && (
                      <div style={{ marginTop: 8 }}>
                        <strong>פרטים:</strong>
                        <pre style={{ fontSize: "12px", backgroundColor: "#f8f9fa", padding: 8, borderRadius: 4, overflow: "auto" }}>
                          {JSON.stringify(grant.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Appendices */}
          {result.appendices && result.appendices.length > 0 && (
            <div style={{ marginBottom: 24, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
              <h4>נספחים</h4>
              <div style={{ display: "grid", gap: 12 }}>
                {result.appendices.map((appendix, index) => (
                  <div key={index} style={{ padding: 12, border: "1px solid #e9ecef", borderRadius: 4 }}>
                    <div><strong>שם:</strong> {appendix.name}</div>
                    <div style={{ marginTop: 8 }}>
                      <strong>נתונים:</strong>
                      <pre style={{ fontSize: "12px", backgroundColor: "#f8f9fa", padding: 8, borderRadius: 4, overflow: "auto", maxHeight: 200 }}>
                        {JSON.stringify(appendix.data, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Calculation Details */}
          {result.calculation_details && (
            <div style={{ marginBottom: 24, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
              <h4>פרטי חישוב</h4>
              <pre style={{ fontSize: "12px", backgroundColor: "#f8f9fa", padding: 12, borderRadius: 4, overflow: "auto", maxHeight: 300 }}>
                {JSON.stringify(result.calculation_details, null, 2)}
              </pre>
            </div>
          )}

          {/* Raw Result (fallback) */}
          {!result.summary && !result.grants && !result.appendices && !result.calculation_details && (
            <div style={{ marginBottom: 24, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
              <h4>תוצאה מלאה</h4>
              <pre style={{ fontSize: "12px", backgroundColor: "#f8f9fa", padding: 12, borderRadius: 4, overflow: "auto", maxHeight: 400 }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
