import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type CapitalAsset = {
  id?: number;
  asset_type: string;
  current_value: number;
  annual_return_rate: number;
  payment_frequency: "monthly" | "quarterly" | "annual";
  start_date: string;
  end_date?: string;
  indexation_method: "none" | "fixed" | "cpi";
  fixed_rate?: number;
  tax_treatment: "exempt" | "taxable" | "fixed_rate";
  tax_rate?: number;
  computed_monthly_amount?: number;
};

const ASSET_TYPES = [
  "stocks", "bonds", "mutual_funds", "real_estate", "savings_account", "deposits", "other"
];

export default function CapitalAssets() {
  const { id: clientId } = useParams<{ id: string }>();
  const [assets, setAssets] = useState<CapitalAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [form, setForm] = useState<Partial<CapitalAsset>>({
    asset_type: "stocks",
    current_value: 0,
    annual_return_rate: 0,
    payment_frequency: "monthly",
    start_date: "",
    indexation_method: "none",
    tax_treatment: "taxable",
    fixed_rate: 0,
    tax_rate: 0,
  });

  async function loadAssets() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const data = await apiFetch<CapitalAsset[]>(`/clients/${clientId}/capital-assets/`);
      setAssets(data || []);
    } catch (e: any) {
      setError(`שגיאה בטעינת נכסי הון: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAssets();
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      // Basic validation
      if (!form.asset_type) {
        throw new Error("חובה לבחור סוג נכס");
      }
      if (!form.current_value || form.current_value <= 0) {
        throw new Error("חובה למלא ערך נוכחי חיובי");
      }
      if (form.annual_return_rate === undefined || form.annual_return_rate < 0) {
        throw new Error("חובה למלא שיעור תשואה שנתי");
      }
      if (!form.start_date) {
        throw new Error("חובה למלא תאריך התחלה");
      }

      if (form.indexation_method === "fixed" && (!form.fixed_rate || form.fixed_rate < 0)) {
        throw new Error("חובה למלא שיעור הצמדה קבוע");
      }

      if (form.tax_treatment === "fixed_rate" && (!form.tax_rate || form.tax_rate < 0 || form.tax_rate > 100)) {
        throw new Error("חובה למלא שיעור מס בין 0-100");
      }

      // Align date to first of month
      const alignedStartDate = new Date(form.start_date);
      alignedStartDate.setDate(1);
      
      let alignedEndDate;
      if (form.end_date) {
        alignedEndDate = new Date(form.end_date);
        alignedEndDate.setDate(1);
      }
      
      const payload = {
        ...form,
        current_value: Number(form.current_value),
        annual_return_rate: Number(form.annual_return_rate),
        fixed_rate: form.fixed_rate !== undefined ? Number(form.fixed_rate) : undefined,
        tax_rate: form.tax_rate !== undefined ? Number(form.tax_rate) : undefined,
        start_date: alignedStartDate.toISOString().split('T')[0],
        end_date: alignedEndDate?.toISOString().split('T')[0] || null,
      };

      await apiFetch(`/clients/${clientId}/capital-assets/`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // Reset form
      setForm({
        asset_type: "stocks",
        current_value: 0,
        annual_return_rate: 0,
        payment_frequency: "monthly",
        start_date: "",
        indexation_method: "none",
        tax_treatment: "taxable",
        fixed_rate: 0,
        tax_rate: 0,
      });

      // Reload assets
      await loadAssets();
    } catch (e: any) {
      setError(`שגיאה ביצירת נכס הון: ${e?.message || e}`);
    }
  }

  async function handleDelete(assetId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את נכס ההון?")) {
      return;
    }

    try {
      await apiFetch(`/clients/${clientId}/capital-assets/${assetId}`, {
        method: "DELETE",
      });
      
      // Reload assets after deletion
      await loadAssets();
    } catch (e: any) {
      setError(`שגיאה במחיקת נכס הון: ${e?.message || e}`);
    }
  }

  function handleEdit(asset: any) {
    // Populate form with asset data for editing
    setForm({
      asset_type: asset.asset_type,
      current_value: asset.current_value || 0,
      annual_return_rate: asset.annual_return_rate || 0,
      payment_frequency: asset.payment_frequency,
      start_date: asset.start_date,
      end_date: asset.end_date || "",
      indexation_method: asset.indexation_method,
      tax_treatment: asset.tax_treatment,
      fixed_rate: asset.fixed_rate || 0,
      tax_rate: asset.tax_rate || 0,
    });
    
    // Scroll to form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (loading) return <div>טוען נכסי הון...</div>;

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to={`/clients/${clientId}`}>← חזרה לפרטי לקוח</Link>
      </div>
      
      <h2>נכסי הון</h2>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Create Form */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>הוסף נכס הון</h3>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 500 }}>
          <div>
            <label>סוג נכס:</label>
            <select
              value={form.asset_type}
              onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
              style={{ padding: 8, width: "100%" }}
            >
              {ASSET_TYPES.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <input
            type="number"
            placeholder="ערך נוכחי"
            value={form.current_value || ""}
            onChange={(e) => setForm({ ...form, current_value: parseFloat(e.target.value) || 0 })}
            style={{ padding: 8 }}
          />

          <input
            type="number"
            step="0.01"
            placeholder="שיעור תשואה שנתי (%)"
            value={form.annual_return_rate || ""}
            onChange={(e) => setForm({ ...form, annual_return_rate: parseFloat(e.target.value) || 0 })}
            style={{ padding: 8 }}
          />

          <div>
            <label>תדירות תשלום:</label>
            <select
              value={form.payment_frequency}
              onChange={(e) => setForm({ ...form, payment_frequency: e.target.value as "monthly" | "quarterly" | "annual" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="monthly">חודשי</option>
              <option value="quarterly">רבעוני</option>
              <option value="annual">שנתי</option>
            </select>
          </div>

          <input
            type="date"
            placeholder="תאריך התחלה"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            style={{ padding: 8 }}
          />

          <input
            type="date"
            placeholder="תאריך סיום (אופציונלי)"
            value={form.end_date || ""}
            onChange={(e) => setForm({ ...form, end_date: e.target.value || undefined })}
            style={{ padding: 8 }}
          />

          <div>
            <label>שיטת הצמדה:</label>
            <select
              value={form.indexation_method}
              onChange={(e) => setForm({ ...form, indexation_method: e.target.value as "none" | "fixed" | "cpi" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="none">ללא הצמדה</option>
              <option value="fixed">הצמדה קבועה</option>
              <option value="cpi">הצמדה למדד</option>
            </select>
          </div>

          {form.indexation_method === "fixed" && (
            <input
              type="number"
              step="0.01"
              placeholder="שיעור הצמדה קבוע (%)"
              value={form.fixed_rate || ""}
              onChange={(e) => setForm({ ...form, fixed_rate: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
            />
          )}

          <div>
            <label>יחס מס:</label>
            <select
              value={form.tax_treatment}
              onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "exempt" | "taxable" | "fixed_rate" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="exempt">פטור ממס</option>
              <option value="taxable">חייב במס</option>
              <option value="fixed_rate">שיעור מס קבוע</option>
            </select>
          </div>

          {form.tax_treatment === "fixed_rate" && (
            <input
              type="number"
              step="0.01"
              placeholder="שיעור מס (%)"
              value={form.tax_rate || ""}
              onChange={(e) => setForm({ ...form, tax_rate: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8 }}
            />
          )}

          <button type="submit" style={{ padding: "10px 16px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}>
            צור נכס הון
          </button>
        </form>
      </section>

      {/* Assets List */}
      <section>
        <h3>רשימת נכסי הון</h3>
        {assets.length === 0 ? (
          <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
            אין נכסי הון
          </div>
        ) : (
          <div style={{ display: "grid", gap: 16 }}>
            {assets.map((asset, index) => (
              <div key={asset.id || index} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
                <div style={{ display: "grid", gap: 8 }}>
                  <div><strong>סוג נכס:</strong> {asset.asset_type}</div>
                  <div><strong>ערך נוכחי:</strong> ₪{asset.current_value?.toLocaleString()}</div>
                  <div><strong>תשואה שנתית:</strong> {asset.annual_return_rate}%</div>
                  <div><strong>תדירות תשלום:</strong> {
                    asset.payment_frequency === "monthly" ? "חודשי" :
                    asset.payment_frequency === "quarterly" ? "רבעוני" : "שנתי"
                  }</div>
                  <div><strong>תאריך התחלה:</strong> {asset.start_date}</div>
                  {asset.end_date && <div><strong>תאריך סיום:</strong> {asset.end_date}</div>}
                  <div><strong>הצמדה:</strong> {
                    asset.indexation_method === "none" ? "ללא" :
                    asset.indexation_method === "fixed" ? `קבועה ${asset.fixed_rate}%` :
                    "למדד"
                  }</div>
                  <div><strong>יחס מס:</strong> {
                    asset.tax_treatment === "exempt" ? "פטור ממס" :
                    asset.tax_treatment === "taxable" ? "חייב במס" :
                    `שיעור קבוע ${asset.tax_rate}%`
                  }</div>
                  
                  {asset.computed_monthly_amount && (
                    <div style={{ color: "green", fontWeight: "bold" }}>
                      <strong>תשלום חודשי מחושב:</strong> ₪{asset.computed_monthly_amount.toLocaleString()}
                    </div>
                  )}
                  
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    {asset.id && (
                      <button
                        type="button"
                        onClick={() => handleEdit(asset)}
                        style={{ padding: "8px 12px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}
                      >
                        ערוך
                      </button>
                    )}
                    
                    {asset.id && (
                      <button
                        type="button"
                        onClick={() => handleDelete(asset.id!)}
                        style={{ padding: "8px 12px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: 4 }}
                      >
                        מחק
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
