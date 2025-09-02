import React, { useState } from "react";

export default function Tools() {
  const [clientId, setClientId] = useState<string>("1");
  const [scenarioIds, setScenarioIds] = useState<string>("2");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>("");
  
  // API base path using environment variable or default relative path
  const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

  const exportPdf = async () => {
    setBusy(true);
    setMsg("");
    try {
      // PDF report endpoint is not currently available
      // Commenting out the fetch call to avoid 404 errors
      /*
      const ids = scenarioIds.split(",").map(s => s.trim()).filter(Boolean).map(Number);
      
      // Using fetch with credentials:omit to avoid CORS issues
      const response = await fetch(`${API_BASE}/reports/pdf/`, {
        method: "POST",
        credentials: "omit",  // Critical change to avoid CORS issues
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: Number(clientId), scenario_ids: ids }),
      });
      
      if (!response.ok) {
        // Use simplified error handling with clone
        let errorMsg = `HTTP ${response.status}`;
        try {
          const contentType = response.headers.get("content-type") ?? "";
          if (contentType.includes("application/json")) {
            const jsonError = await response.clone().json();
            errorMsg = jsonError?.detail || JSON.stringify(jsonError);
          } else {
            errorMsg = await response.clone().text() || errorMsg;
          }
        } catch {}
        throw new Error(errorMsg);
      }
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${clientId}_${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      */
      
      // Display message about endpoint not being available
      setMsg("⚠️ PDF export is temporarily unavailable - backend endpoint not implemented yet");
    } catch (e: any) {
      setMsg("❌ כשל ביצוא: " + (e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 420, direction: "rtl" }}>
      <h2>כלי בדיקה</h2>
      <p>API: <code>{API_BASE}</code></p>
      <label>
        מזהה לקוח:
        <input value={clientId} onChange={(e) => setClientId(e.target.value)} style={{ width: "100%", padding: 8 }} />
      </label>
      <label>
        מזהי תרחישים (פסיקים):
        <input value={scenarioIds} onChange={(e) => setScenarioIds(e.target.value)} style={{ width: "100%", padding: 8 }} />
      </label>
      <button onClick={exportPdf} disabled={busy} style={{ padding: "10px 14px" }}>
        {busy ? "מייצא..." : "ייצוא PDF"}
      </button>
      {msg && <div>{msg}</div>}
    </div>
  );
}
