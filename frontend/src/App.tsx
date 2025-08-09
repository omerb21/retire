import React, { useState } from "react";

const API_BASE: string =
  (import.meta as any).env?.VITE_API_BASE || "http://127.0.0.1:8000";

export default function App() {
  const [clientId, setClientId] = useState<string>("1");
  const [scenarioIds, setScenarioIds] = useState<string>("2");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>("");

  const exportPdf = async () => {
    setBusy(true);
    setMsg("");
    try {
      const ids = scenarioIds
        .split(",")
        .map(s => s.trim())
        .filter(Boolean)
        .map(Number);

      const r = await fetch(`${API_BASE}/api/v1/reports/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: Number(clientId), scenario_ids: ids }),
      });

      if (!r.ok) {
        const err = await r.text();
        throw new Error(`HTTP ${r.status}: ${err.slice(0, 200)}`);
      }

      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${clientId}_${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setMsg("✅ PDF הורד בהצלחה");
    } catch (e: any) {
      setMsg("❌ כשל ביצוא: " + (e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ fontFamily: "system-ui, Arial", margin: 24, direction: "rtl" }}>
      <h2>Retirement Planning – בדיקת פרונט</h2>
      <p>API: <code>{API_BASE}</code></p>

      <div style={{ display: "grid", gap: 12, maxWidth: 420 }}>
        <label>
          מזהה לקוח:
          <input
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            style={{ width: "100%", padding: 8 }}
            />
        </label>
        <label>
          מזהי תרחישים (מופרדים בפסיק):
          <input
            value={scenarioIds}
            onChange={(e) => setScenarioIds(e.target.value)}
            style={{ width: "100%", padding: 8 }}
            />
        </label>
        <button onClick={exportPdf} disabled={busy} style={{ padding: "10px 14px" }}>
          {busy ? "מייצא..." : "ייצוא PDF"}
        </button>
        {msg && <div>{msg}</div>}
        <hr />
        <small>
          טיפ: אם הרצת את <code>tools/report_smoke.py</code> הוא יוצר בד"כ Client=1 ו-Scenario=2.
        </small>
      </div>
    </div>
  );
}
