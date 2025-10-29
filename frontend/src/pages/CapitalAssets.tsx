import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

type CapitalAsset = {
  id?: number;
  client_id?: number;
  asset_type: string;
  description?: string;
  remarks?: string;  // הערות - משמש לקישור להיוון
  conversion_source?: string;  // מקור המרה (JSON)
  current_value: number;
  purchase_value?: number;
  purchase_date?: string;
  annual_return?: number;
  annual_return_rate: number;
  payment_frequency: "monthly" | "annually";
  liquidity?: string;
  risk_level?: string;
  // שדות נוספים לשימוש בפרונטאנד
  asset_name?: string;
  monthly_income?: number;
  start_date?: string;  // תאריך תשלום חד פעמי
  indexation_method?: "none" | "fixed" | "cpi";
  fixed_rate?: number;
  tax_treatment?: "exempt" | "taxable" | "fixed_rate" | "capital_gains" | "tax_spread";
  tax_rate?: number;
  spread_years?: number;
};

const ASSET_TYPES = [
  { value: "rental_property", label: "דירה להשכרה" },
  { value: "investment", label: "השקעות" },
  { value: "stocks", label: "מניות" },
  { value: "bonds", label: "אגרות חוב" },
  { value: "mutual_funds", label: "קרנות נאמנות" },
  { value: "real_estate", label: "נדלן" },
  { value: "savings_account", label: "חשבון חיסכון" },
  { value: "deposits", label: "היוון" },
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
    spread_years: 0,
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
          console.log(`  Payment Date: ${asset.start_date || 'Not set'}`);
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
      // תשלום אינו חובה - יכול להיות 0
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
      
      // end_date הוסר - תשלום חד פעמי
      
      // בדיקה מה השדות שהשרת מצפה לקבל
      console.log("FORM DATA BEFORE SUBMIT:", form);
      
      // Validation - ערך נוכחי יכול להיות 0 (למשל להיוונים)
      if (form.current_value === undefined || form.current_value === null) {
        throw new Error("יש להזין ערך נכס");
      }
      if (Number(form.current_value) < 0) {
        throw new Error("ערך נכס לא יכול להיות שלילי");
      }
      
      const payload = {
        asset_type: form.asset_type,
        description: form.asset_name?.trim() || "נכס הון",
        current_value: Number(form.current_value),
        purchase_value: Number(form.current_value), // ערך רכישה = ערך נוכחי כברירת מחדל
        purchase_date: startDateISO,
        annual_return: 0, // ערך ברירת מחדל
        annual_return_rate: Number(form.annual_return_rate) / 100 || 0, // המרה לעשרוני
        payment_frequency: "annually", // תמיד שנתי - תשלום חד פעמי
        liquidity: "medium", // ערך ברירת מחדל
        risk_level: "medium", // ערך ברירת מחדל
        
        // השדות הנדרשים לתצוגה
        monthly_income: Number(form.monthly_income) || 0,
        start_date: startDateISO,
        end_date: null,  // תמיד null - תשלום חד פעמי
        indexation_method: form.indexation_method || "none",
        fixed_rate: form.fixed_rate !== undefined ? Number(form.fixed_rate) : 0,
        tax_treatment: form.tax_treatment || "taxable",
        tax_rate: form.tax_rate !== undefined ? Number(form.tax_rate) : 0,
        spread_years: form.spread_years && form.spread_years > 0 ? Number(form.spread_years) : null
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
        spread_years: 0,
      });
      
      // איפוס מצב העריכה
      setEditingAssetId(null);

      // Reload assets
      await loadAssets();
    } catch (e: any) {
      setError(`שגיאה ביצירת נכס הון: ${e?.message || e}`);
    }
  }

  async function handleDeleteAll() {
    if (!clientId) return;
    
    if (assets.length === 0) {
      alert("אין נכסי הון למחיקה");
      return;
    }
    
    if (!confirm(`האם אתה בטוח שברצונך למחוק את כל ${assets.length} נכסי ההון? פעולה זו בלתי הפיכה!`)) {
      return;
    }

    try {
      setError("");
      
      // מחיקת כל הנכסים אחד אחד
      for (const asset of assets) {
        if (asset.id) {
          await apiFetch(`/clients/${clientId}/capital-assets/${asset.id}`, {
            method: 'DELETE'
          });
        }
      }
      
      // רענון הרשימה
      await loadAssets();
      alert(`נמחקו ${assets.length} נכסי הון בהצלחה`);
    } catch (e: any) {
      setError(`שגיאה במחיקת נכסי הון: ${e?.message || e}`);
    }
  }

  async function handleDelete(assetId: number) {
    console.log('🔴 handleDelete called with assetId:', assetId);
    if (!clientId) {
      console.log('❌ No clientId, returning');
      return;
    }
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את נכס ההון?")) {
      console.log('❌ User cancelled deletion');
      return;
    }

    console.log('✅ Starting deletion process...');
    try {
      // קבלת פרטי הנכס מהרשימה המקומית
      const asset = assets.find(a => a.id === assetId);
      
      // מחיקת הנכס והחזרת מידע על שחזור
      const deleteResponse = await apiFetch(`/clients/${clientId}/capital-assets/${assetId}`, {
        method: 'DELETE'
      }) as any;
      
      console.log('🗑️ Delete response:', JSON.stringify(deleteResponse, null, 2));
      console.log('🔍 Restoration object:', deleteResponse?.restoration);
      console.log('🔍 Restoration reason:', deleteResponse?.restoration?.reason);
      
      // בדיקה אם צריך לשחזר יתרה לתיק פנסיוני
      if (deleteResponse?.restoration && deleteResponse.restoration.reason === 'pension_portfolio') {
        const accountNumber = deleteResponse.restoration.account_number;
        const balanceToRestore = deleteResponse.restoration.balance_to_restore;
        
        console.log(`📋 ✅ RESTORING ₪${balanceToRestore} to account ${accountNumber}`);
        
        // עדכון localStorage - החזרת היתרה לטבלה
        const storageKey = `pensionData_${clientId}`;
        const storedData = localStorage.getItem(storageKey);
        
        console.log(`🔍 Storage key: ${storageKey}`);
        console.log(`🔍 Stored data exists: ${!!storedData}`);
        
        if (storedData && asset) {
          try {
            const pensionData = JSON.parse(storedData);
            console.log(`🔍 Parsed pension data (${pensionData.length} accounts):`, pensionData);
            
            // חיפוש החשבון לפי מספר חשבון
            const accountIndex = pensionData.findIndex((acc: any) => 
              acc.מספר_חשבון === accountNumber
            );
            
            console.log(`🔍 Looking for account: ${accountNumber}`);
            console.log(`🔍 Account found at index: ${accountIndex}`);
            
            if (accountIndex !== -1) {
              // החזרת היתרה לשדות הספציפיים שהומרו
              const account = pensionData[accountIndex];
              
              console.log(`🔍 Account before restore:`, account);
              console.log(`🔍 Specific amounts to restore:`, deleteResponse.restoration.specific_amounts);
              
              // אם יש specific_amounts, נחזיר לשדות הספציפיים
              if (deleteResponse.restoration.specific_amounts && 
                  Object.keys(deleteResponse.restoration.specific_amounts).length > 0) {
                Object.entries(deleteResponse.restoration.specific_amounts).forEach(([field, amount]: [string, any]) => {
                  if (account.hasOwnProperty(field)) {
                    account[field] = (parseFloat(account[field]) || 0) + parseFloat(amount);
                    console.log(`✅ Restored ₪${amount} to ${field}`);
                  }
                });
              } else {
                // אם אין specific_amounts, נחזיר לתגמולים (ברירת מחדל)
                account.תגמולים = (parseFloat(account.תגמולים) || 0) + balanceToRestore;
                console.log(`✅ Restored ₪${balanceToRestore} to תגמולים (default)`);
              }
              
              console.log(`🔍 Account after restore:`, account);
              localStorage.setItem(storageKey, JSON.stringify(pensionData));
              console.log('✅ Updated pension portfolio in localStorage');
              
              // הפעלת אירוע כדי לעדכן את הטבלה
              window.dispatchEvent(new Event('storage'));
              console.log('✅ Dispatched storage event to refresh table');
            } else {
              console.warn(`⚠️ Account ${accountNumber} not found in pension portfolio`);
              console.warn(`🔍 Available accounts:`, pensionData.map((acc: any) => acc.מספר_חשבון));
            }
          } catch (e) {
            console.error('❌ Error restoring balance to localStorage:', e);
          }
        } else {
          console.warn(`⚠️ No stored data or asset info. storedData=${!!storedData}, asset=${!!asset}`);
        }
      }
      
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
      indexation_method: asset.indexation_method,
      tax_treatment: asset.tax_treatment,
      fixed_rate: asset.fixed_rate || 0,
      tax_rate: asset.tax_rate || 0,
      spread_years: asset.spread_years || 0,
    });
    
    // Scroll to form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (loading) return <div>טוען נכסי הון...</div>;

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">🏠 נכסי הון</h1>
            <p className="card-subtitle">ניהול נכסים - תשלום חד פעמי או חישוב NPV</p>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={handleDeleteAll}
              className="btn"
              style={{ 
                backgroundColor: '#dc3545', 
                color: 'white',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
              disabled={assets.length === 0}
            >
              🗑️ מחק הכל
            </button>
            <Link to={`/clients/${clientId}`} className="btn btn-secondary">
              ← חזרה
            </Link>
          </div>
        </div>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {/* Create Form */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>{editingAssetId ? 'ערוך נכס הון' : 'הוסף נכס הון'}</h3>
        
        {/* הסבר על לוגיקת נכסי הון */}
        <div style={{ 
          marginBottom: 16, 
          padding: 12, 
          backgroundColor: '#e7f3ff', 
          borderRadius: 4,
          border: '1px solid #b3d9ff',
          fontSize: '14px'
        }}>
          <strong>💡 איך נכסי הון מוצגים במערכת:</strong>
          <ul style={{ marginTop: 8, marginBottom: 0, paddingRight: 20 }}>
            <li><strong>תשלום חד פעמי:</strong> אם שדה "ערך נוכחי" {'>'} 0, הנכס יוצג בתזרים בתאריך התשלום החד פעמי</li>
            <li><strong>הכנסה חודשית:</strong> אם שדה "תשלום" {'>'} 0, הנכס יוצג כהכנסה חודשית קבועה</li>
            <li><strong>פריסת מס:</strong> עבור תשלום חד-פעמי עם פריסה, המס יחושב על פי הפריסה אך ישולם בחד-פעמיות בתאריך התשלום</li>
          </ul>
        </div>
        
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

          <div>
            <label>תשלום (₪) - אופציונלי:</label>
            <input
              type="number"
              placeholder="0"
              value={form.monthly_income !== undefined && form.monthly_income !== null ? form.monthly_income : ""}
              onChange={(e) => {
                const value = e.target.value;
                setForm({ ...form, monthly_income: value === "" ? 0 : parseFloat(value) });
              }}
              style={{ padding: 8, width: "100%" }}
              min="0"
            />
          </div>

          <div>
            <label>ערך נוכחי (₪) - אופציונלי:</label>
            <input
              type="number"
              placeholder="0"
              value={form.current_value || ""}
              onChange={(e) => setForm({ ...form, current_value: parseFloat(e.target.value) || 0 })}
              style={{ padding: 8, width: "100%" }}
              min="0"
            />
          </div>

          <input
            type="number"
            step="0.01"
            placeholder="שיעור תשואה שנתי (%) - לחישוב מס רווח הון"
            value={form.annual_return_rate || ""}
            onChange={(e) => setForm({ ...form, annual_return_rate: parseFloat(e.target.value) || 0 })}
            style={{ padding: 8 }}
          />

          <div>
            <label>תאריך תשלום חד פעמי:</label>
            <input
              type="text"
              placeholder="DD/MM/YYYY"
              value={form.start_date || ''}
              onChange={(e) => {
                const formatted = formatDateInput(e.target.value);
                setForm({ ...form, start_date: formatted });
              }}
              style={{ padding: 8, width: "100%" }}
              maxLength={10}
              required
            />
          </div>

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
              onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "exempt" | "taxable" | "capital_gains" | "tax_spread" })}
              style={{ padding: 8, width: "100%" }}
            >
              <option value="exempt">פטור ממס</option>
              <option value="taxable">חייב במס רגיל</option>
              <option value="capital_gains">מס רווח הון (25% מהרווח הריאלי)</option>
              <option value="tax_spread">פריסת מס</option>
            </select>
          </div>

          {form.tax_treatment === "capital_gains" && (
            <div style={{ padding: 8, backgroundColor: "#e7f3ff", borderRadius: 4, fontSize: "14px" }}>
              <strong>מס רווח הון:</strong> יחושב כ-25% מהרווח הריאלי (שיעור התשואה פחות 2% מדד)
            </div>
          )}

          {form.tax_treatment === "tax_spread" && (
            <div style={{ padding: 15, backgroundColor: "#fff3cd", borderRadius: 4, border: "1px solid #ffc107" }}>
              <strong>📋 פריסת מס על מספר שנים</strong>
              <p style={{ fontSize: "14px", marginTop: "8px", color: "#666", lineHeight: "1.6" }}>
                <strong>איך עובדת פריסת מס:</strong><br/>
                • הסכום מתחלק שווה על מספר השנים<br/>
                • לכל שנה מחושב המס לפי מדרגות (הכנסה רגילה + חלק שנתי מהמענק)<br/>
                • <strong>בשנה הראשונה משולם כל המס המצטבר</strong><br/>
                • בשנים הבאות - המס מוצג רק ויזואלית, לא בפועל
              </p>
              <div style={{ marginTop: "10px" }}>
                <label>מספר שנות פריסה (בד"כ 1-6 לפי וותק):</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  placeholder="מספר שנות פריסה"
                  value={form.spread_years || ""}
                  onChange={(e) => setForm({ ...form, spread_years: parseInt(e.target.value) || 0 })}
                  style={{ padding: 8, width: "100%", marginTop: "5px" }}
                  required
                />
              </div>
            </div>
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
                    spread_years: 0,
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
                      <div><strong>תשלום:</strong> ₪{(asset.monthly_income || 0).toLocaleString()}</div>
                      <div><strong>ערך נוכחי:</strong> ₪{asset.current_value?.toLocaleString() || 0}</div>
                      <div><strong>תשואה שנתית:</strong> {
                        asset.annual_return_rate > 1 ? asset.annual_return_rate : 
                        asset.annual_return_rate ? (asset.annual_return_rate * 100) : 
                        asset.annual_return || 0
                      }%</div>
                    </div>
                    
                    <div style={{ backgroundColor: "#fff", padding: "8px", borderRadius: "4px", border: "1px solid #eee" }}>
                      <div style={{ fontWeight: "bold", marginBottom: "4px" }}>תאריך ומס</div>
                      <div><strong>תאריך תשלום:</strong> {asset.start_date ? formatDateToDDMMYY(new Date(asset.start_date)) : "לא צוין"}</div>
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
                      asset.tax_treatment === "tax_spread" ? `פריסת מס (${asset.spread_years || 0} שנים)` :
                      asset.tax_treatment === "fixed_rate" ? `שיעור קבוע ${asset.tax_rate}%` :
                      "לא מוגדר"
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
    </div>
  );
}
