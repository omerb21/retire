/**
 * AssetForm Component
 * ===================
 * Form component for creating and editing capital assets
 */

import React from 'react';
import { CapitalAsset, ASSET_TYPES } from '../../../types/capitalAsset';
import { formatDateInput } from '../../../utils/dateUtils';
import { formatCurrency } from '../../../lib/validation';

interface AssetFormProps {
  form: Partial<CapitalAsset>;
  setForm: React.Dispatch<React.SetStateAction<Partial<CapitalAsset>>>;
  editingAssetId: number | null;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
}

export function AssetForm({ form, setForm, editingAssetId, onSubmit, onCancel }: AssetFormProps) {
  return (
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
      
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, maxWidth: 500 }}>
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
          <div style={{ padding: 15, backgroundColor: "#e7f3ff", borderRadius: 4, border: "1px solid #007bff" }}>
            <strong>💰 מס רווח הון (25%)</strong>
            <p style={{ fontSize: "14px", marginTop: "8px", color: "#666", lineHeight: "1.6" }}>
              <strong>איך עובד חישוב מס רווח הון:</strong><br/>
              • המס מחושב על הרווח בלבד (תשלום - הפקדה נומינלית)<br/>
              • שיעור המס: 25% מהרווח<br/>
              • התשלום המעודכן: תשלום - 0.25 × (תשלום - הפקדה נומינלית)<br/>
              • הנכס יישמר כ"פטור ממס" עם התשלום המעודכן
            </p>
            <div style={{ marginTop: "10px" }}>
              <label>סכום ההפקדה הנומינאלי (₪):</label>
              <input
                type="number"
                min="0"
                placeholder="סכום ההפקדה הנומינאלי"
                value={form.nominal_principal !== undefined && form.nominal_principal > 0 ? form.nominal_principal : (form.monthly_income || 0)}
                onChange={(e) => setForm({ ...form, nominal_principal: parseFloat(e.target.value) || 0 })}
                style={{ padding: 8, width: "100%", marginTop: "5px" }}
                required
              />
              <div style={{ fontSize: "12px", color: "#666", marginTop: "5px" }}>
                ברירת מחדל: {formatCurrency(form.monthly_income || 0)} (סכום התשלום)
              </div>
              {form.monthly_income && form.monthly_income > 0 && (
                <div style={{ marginTop: "10px", padding: "8px", backgroundColor: "#fff", borderRadius: "4px", border: "1px solid #ddd" }}>
                  <strong>חישוב:</strong><br/>
                  רווח: {formatCurrency((form.monthly_income || 0) - (form.nominal_principal && form.nominal_principal > 0 ? form.nominal_principal : form.monthly_income || 0))}<br/>
                  מס (25%): {formatCurrency(((form.monthly_income || 0) - (form.nominal_principal && form.nominal_principal > 0 ? form.nominal_principal : form.monthly_income || 0)) * 0.25)}<br/>
                  <strong>תשלום מעודכן: {formatCurrency((form.monthly_income || 0) - 0.25 * ((form.monthly_income || 0) - (form.nominal_principal && form.nominal_principal > 0 ? form.nominal_principal : form.monthly_income || 0)))}</strong>
                </div>
              )}
            </div>
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
              onClick={onCancel}
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
  );
}
