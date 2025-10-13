import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

type CapitalAsset = {
  id?: number;
  client_id?: number;
  asset_type: string;
  description?: string;
  current_value: number;
  purchase_value?: number;
  purchase_date?: string;
  annual_return?: number;
  annual_return_rate: number;
  payment_frequency: "monthly" | "quarterly" | "annual";
  liquidity?: string;
  risk_level?: string;
  // שדות נוספים לשימוש בפרונטאנד
  asset_name?: string;
  monthly_income?: number;
  start_date?: string;
  end_date?: string;
  indexation_method?: "none" | "fixed" | "cpi";
  fixed_rate?: number;
  tax_treatment?: "exempt" | "taxable" | "fixed_rate" | "capital_gains";
  tax_rate?: number;
};

const ASSET_TYPES = [
  { value: "rental_property", label: "דירה להשכרה" },
  { value: "investment", label: "השקעות" },
  { value: "stocks", label: "מניות" },
  { value: "bonds", label: "אגרות חוב" },
  { value: "mutual_funds", label: "קרנות נאמנות" },
  { value: "real_estate", label: "נדלן" },
  { value: "savings_account", label: "חשבון חיסכון" },
  { value: "deposits", label: "פקדונות" },
  { value: "provident_fund", label: "קופת גמל" },
  { value: "education_fund", label: "קרן השתלמות" },
  { value: "other", label: "אחר" }
];

export default function CapitalAssets() {
  const { id: clientId } = useParams<{ id: string }>();
  const [assets, setAssets] = useState<CapitalAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [editingAssetId, setEditingAssetId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<CapitalAsset>>({
    asset_name: "",
    asset_type: "rental_property",
    current_value: 0,
    monthly_income: 0,
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
      console.log("SERVER RESPONSE - Capital Assets:", JSON.stringify(data, null, 2));
      
      // בדיקה מפורטת של כל נכס
      if (data && data.length > 0) {
        data.forEach((asset, index) => {
          console.log(`ASSET ${index + 1} DETAILS:`);
          console.log(`  ID: ${asset.id}`);
          console.log(`  Name: ${asset.asset_name || asset.description || 'No name'}`);
          console.log(`  Type: ${asset.asset_type}`);
          console.log(`  Monthly Income: ${asset.monthly_income || 0}`);
          console.log(`  Current Value: ${asset.current_value || 0}`);
          console.log(`  Start Date: ${asset.start_date || 'Not set'}`);
          console.log(`  End Date: ${asset.end_date || 'Not set'}`);
          console.log(`  conversion_source: ${(asset as any).conversion_source || 'NOT SET'}`);
          console.log(`  All Properties:`, asset);
        });
      } else {
        console.log("No assets returned from server");
      }
      
      setAssets(data || []);
    } catch (e: any) {
      console.error("Error loading assets:", e);
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
      if (!form.asset_name || form.asset_name.trim() === "") {
        throw new Error("חובה למלא שם הנכס");
      }
      if (!form.asset_type) {
        throw new Error("חובה לבחור סוג נכס");
      }
      if (!form.monthly_income || form.monthly_income <= 0) {
        throw new Error("חובה למלא תשלום חודשי חיובי");
      }
      if (!form.start_date) {
        throw new Error("חובה למלא תאריך התחלה");
      }
      
      // Validation for capital gains tax
      if (form.tax_treatment === "capital_gains" && (form.annual_return_rate === undefined || form.annual_return_rate < 2)) {
        throw new Error("עבור מס רווח הון, חובה למלא שיעור תשואה שנתי של לפחות 2%");
      }

      if (form.indexation_method === "fixed" && (!form.fixed_rate || form.fixed_rate < 0)) {
        throw new Error("חובה למלא שיעור הצמדה קבוע");
      }

      if (form.tax_treatment === "fixed_rate" && (!form.tax_rate || form.tax_rate < 0 || form.tax_rate > 100)) {
        throw new Error("חובה למלא שיעור מס בין 0-100");
      }

      // Convert dates to ISO format
      const startDateISO = convertDDMMYYToISO(form.start_date);
      if (!startDateISO) {
        throw new Error("תאריך התחלה לא תקין - יש להזין בפורמט DD/MM/YYYY");
      }
      
      const endDateISO = form.end_date ? convertDDMMYYToISO(form.end_date) : null;
      
      // בדיקה מה השדות שהשרת מצפה לקבל
      console.log("FORM DATA BEFORE SUBMIT:", form);
      
      const payload = {
        asset_type: form.asset_type,
        description: form.asset_name?.trim() || "נכס הון",
        current_value: Number(form.current_value) || 0,
        purchase_value: 0, // ערך ברירת מחדל
        purchase_date: startDateISO,
        annual_return: 0, // ערך ברירת מחדל
        annual_return_rate: Number(form.annual_return_rate) / 100 || 0, // המרה לעשרוני
        payment_frequency: form.payment_frequency,
        liquidity: "medium", // ערך ברירת מחדל
        risk_level: "medium", // ערך ברירת מחדל
        
        // השדות הנדרשים לתצוגה
        monthly_income: Number(form.monthly_income) || 0,
        start_date: startDateISO,
        end_date: endDateISO,
        indexation_method: form.indexation_method || "none",
        fixed_rate: form.fixed_rate !== undefined ? Number(form.fixed_rate) : 0,
        tax_treatment: form.tax_treatment || "undefined",
        tax_rate: form.tax_rate !== undefined ? Number(form.tax_rate) : 0
      };

      console.log("SENDING PAYLOAD TO SERVER:", JSON.stringify(payload, null, 2));
      
      // בדיקה אם אנחנו במצב עריכה או יצירה חדשה
      if (editingAssetId) {
        // עדכון נכס קיים
        console.log(`מעדכן נכס קיים עם מזהה: ${editingAssetId}`);
        const response = await apiFetch(`/clients/${clientId}/capital-assets/${editingAssetId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        console.log("SERVER RESPONSE AFTER UPDATE:", JSON.stringify(response, null, 2));
      } else {
        // יצירת נכס חדש
        const response = await apiFetch(`/clients/${clientId}/capital-assets/`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        console.log("SERVER RESPONSE AFTER CREATE:", JSON.stringify(response, null, 2));
      }

      // איפוס הטופס ומצב העריכה
      setForm({
        asset_name: "",
        asset_type: "rental_property",
        current_value: 0,
        monthly_income: 0,
        annual_return_rate: 0,
        payment_frequency: "monthly",
        start_date: "",
        indexation_method: "none",
        tax_treatment: "taxable",
        fixed_rate: 0,
        tax_rate: 0,
      });
      
      // איפוס מצב העריכה
      setEditingAssetId(null);

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
      // קבלת פרטי הנכס לפני המחיקה
      const asset = assets.find(a => a.id === assetId);
      
      // בדיקה אם יש מידע על מקור המרה
      if (asset && (asset as any).conversion_source) {
        try {
          const conversionSource = JSON.parse((asset as any).conversion_source);
          
          // אם זו המרה מתיק פנסיוני - נחזיר את הסכומים למקור
          if (conversionSource.type === 'pension_portfolio') {
            console.log('Restoring amounts to pension portfolio:', conversionSource);
            
            // קריאה ל-API להחזרת הסכומים
            await apiFetch(`/clients/${clientId}/pension-portfolio/restore`, {
              method: 'POST',
              body: JSON.stringify({
                account_name: conversionSource.account_name,
                company: conversionSource.company,
                account_number: conversionSource.account_number,
                product_type: conversionSource.product_type,
                amount: conversionSource.amount,
                specific_amounts: conversionSource.specific_amounts
              })
            });
            
            // עדכון localStorage - החזרת הסכומים לטבלה
            const storageKey = `pensionData_${clientId}`;
            const storedData = localStorage.getItem(storageKey);
            
            if (storedData) {
              try {
                const pensionData = JSON.parse(storedData);
                
                // חיפוש החשבון המתאים
                const accountIndex = pensionData.findIndex((acc: any) => 
                  acc.שם_תכנית === conversionSource.account_name &&
                  acc.חברה_מנהלת === conversionSource.company &&
                  acc.מספר_תכנית === conversionSource.account_number
                );
                
                if (accountIndex !== -1) {
                  // החזרת הסכומים לשדות הספציפיים
                  if (conversionSource.specific_amounts && Object.keys(conversionSource.specific_amounts).length > 0) {
                    Object.entries(conversionSource.specific_amounts).forEach(([key, value]) => {
                      pensionData[accountIndex][key] = (pensionData[accountIndex][key] || 0) + parseFloat(value as string);
                    });
                  }
                  
                  // החזרת הסכום ליתרה הכללית
                  pensionData[accountIndex].יתרה = (pensionData[accountIndex].יתרה || 0) + conversionSource.amount;
                  
                  // שמירה חזרה ל-localStorage
                  localStorage.setItem(storageKey, JSON.stringify(pensionData));
                  console.log('Successfully restored amounts to pension portfolio in localStorage');
                } else {
                  console.warn('Account not found in localStorage, amounts not restored to table');
                }
              } catch (storageError) {
                console.error('Error updating localStorage:', storageError);
              }
            }
            
            console.log('Successfully restored amounts to pension portfolio');
          }
        } catch (parseError) {
          console.warn('Could not parse conversion_source:', parseError);
          // ממשיכים עם המחיקה גם אם יש שגיאה בפרסור
        }
      }
      
      // מחיקת הנכס
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
    // שמירת מזהה הנכס שעורכים
    setEditingAssetId(asset.id || null);
    
    // Populate form with asset data for editing
    setForm({
      asset_name: asset.asset_name || "",
      asset_type: asset.asset_type,
      current_value: asset.current_value || 0,
      monthly_income: asset.monthly_income || 0,
      annual_return_rate: asset.annual_return_rate || 0,
      payment_frequency: asset.payment_frequency,
      start_date: asset.start_date ? convertISOToDDMMYY(asset.start_date) : "",
      end_date: asset.end_date ? convertISOToDDMMYY(asset.end_date) : "",
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
        <h3>{editingAssetId ? 'ערוך נכס הון' : 'הוסף נכס הון'}</h3>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12, maxWidth: 500 }}>
          <input
            type="text"
            placeholder="שם הנכס"
            value={form.asset_name || ""}
            onChange={(e) => setForm({ ...form, asset_name: e.target.value })}
            style={{ padding: 8 }}
            required
          />

          <div>
            <label>סוג נכס:</label>
            <select
              value={form.asset_type}
              onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
              style={{ padding: 8, width: "100%" }}
            >
              {ASSET_TYPES.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>

          <input
            type="number"
            placeholder="תשלום חודשי (₪)"
            value={form.monthly_income || ""}
            onChange={(e) => setForm({ ...form, monthly_income: parseFloat(e.target.value) || 0 })}
            style={{ padding: 8 }}
            required
          />

          <input
            type="number"
            placeholder="ערך נוכחי (₪) - אופציונלי"
            value={form.current_value || ""}
            onChange={(e) => setForm({ ...form, current_value: parseFloat(e.target.value) || 0 })}
            style={{ padding: 8 }}
          />

          <input
            type="number"
            step="0.01"
            placeholder="שיעור תשואה שנתי (%) - לחישוב מס רווח הון"
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
            type="text"
            placeholder="DD/MM/YYYY"
            value={form.start_date || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setForm({ ...form, start_date: formatted });
            }}
            style={{ padding: 8 }}
            maxLength={10}
          />

          <input
            type="text"
            placeholder="DD/MM/YYYY (אופציונלי)"
            value={form.end_date || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setForm({ ...form, end_date: formatted || undefined });
            }}
            style={{ padding: 8 }}
            maxLength={10}
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
              onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "exempt" | "taxable" | "fixed_rate" | "capital_gains" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="exempt">פטור ממס</option>
              <option value="taxable">חייב במס רגיל</option>
              <option value="capital_gains">מס רווח הון (25% מהרווח הריאלי)</option>
              <option value="fixed_rate">שיעור מס קבוע</option>
            </select>
          </div>

          {form.tax_treatment === "capital_gains" && (
            <div style={{ padding: 8, backgroundColor: "#e7f3ff", borderRadius: 4, fontSize: "14px" }}>
              <strong>מס רווח הון:</strong> יחושב כ-25% מהרווח הריאלי (שיעור התשואה פחות 2% מדד)
            </div>
          )}

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

          <div style={{ display: "flex", gap: 10 }}>
            <button 
              type="submit" 
              style={{ 
                padding: "10px 16px", 
                backgroundColor: "#007bff", 
                color: "white", 
                border: "none", 
                borderRadius: 4,
                flex: 1
              }}
            >
              {editingAssetId ? 'שמור שינויים' : 'צור נכס הון'}
            </button>
            
            {editingAssetId && (
              <button 
                type="button" 
                onClick={() => {
                  setEditingAssetId(null);
                  setForm({
                    asset_name: "",
                    asset_type: "rental_property",
                    current_value: 0,
                    monthly_income: 0,
                    annual_return_rate: 0,
                    payment_frequency: "monthly",
                    start_date: "",
                    indexation_method: "none",
                    tax_treatment: "taxable",
                    fixed_rate: 0,
                    tax_rate: 0,
                  });
                }}
                style={{ 
                  padding: "10px 16px", 
                  backgroundColor: "#6c757d", 
                  color: "white", 
                  border: "none", 
                  borderRadius: 4 
                }}
              >
                בטל עריכה
              </button>
            )}
          </div>
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
              <div key={asset.id || index} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4, backgroundColor: "#f9f9f9" }}>
                <div style={{ display: "grid", gap: 8 }}>
                  <div style={{ fontSize: "18px", fontWeight: "bold", color: "#0056b3", marginBottom: "8px" }}>
                    {asset.asset_name || asset.description || "נכס ללא שם"}
                  </div>
                  
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    <div style={{ backgroundColor: "#fff", padding: "8px", borderRadius: "4px", border: "1px solid #eee" }}>
                      <div style={{ fontWeight: "bold", marginBottom: "4px" }}>פרטי נכס</div>
                      <div><strong>סוג נכס:</strong> {ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type}</div>
                      <div><strong>תשלום חודשי:</strong> ₪{(asset.monthly_income || 0).toLocaleString()}</div>
                      <div><strong>ערך נוכחי:</strong> ₪{asset.current_value?.toLocaleString() || 0}</div>
                      <div><strong>תשואה שנתית:</strong> {
                        asset.annual_return_rate > 1 ? asset.annual_return_rate : 
                        asset.annual_return_rate ? (asset.annual_return_rate * 100) : 
                        asset.annual_return || 0
                      }%</div>
                    </div>
                    
                    <div style={{ backgroundColor: "#fff", padding: "8px", borderRadius: "4px", border: "1px solid #eee" }}>
                      <div style={{ fontWeight: "bold", marginBottom: "4px" }}>תאריכים והצמדה</div>
                      <div><strong>תאריך התחלה:</strong> {asset.start_date ? formatDateToDDMMYY(new Date(asset.start_date)) : "לא צוין"}</div>
                      <div><strong>תאריך סיום:</strong> {asset.end_date ? formatDateToDDMMYY(new Date(asset.end_date)) : "ללא הגבלה"}</div>
                      <div><strong>תדירות תשלום:</strong> {
                        asset.payment_frequency === "monthly" ? "חודשי" :
                        asset.payment_frequency === "quarterly" ? "רבעוני" : "שנתי"
                      }</div>
                      <div><strong>הצמדה:</strong> {
                        asset.indexation_method === "none" ? "ללא" :
                        asset.indexation_method === "fixed" ? `קבועה ${asset.fixed_rate}%` :
                        "למדד"
                      }</div>
                    </div>
                  </div>
                  
                  <div style={{ backgroundColor: "#f0f8ff", padding: "8px", borderRadius: "4px", border: "1px solid #d1e7ff" }}>
                    <div style={{ fontWeight: "bold", marginBottom: "4px" }}>מיסוי</div>
                    <div><strong>יחס מס:</strong> {
                      asset.tax_treatment === "exempt" ? "פטור ממס" :
                      asset.tax_treatment === "taxable" ? "חייב במס רגיל" :
                      asset.tax_treatment === "capital_gains" ? "מס רווח הון (25%)" :
                      `שיעור קבוע ${asset.tax_rate}%`
                    }</div>
                  </div>
                  
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
