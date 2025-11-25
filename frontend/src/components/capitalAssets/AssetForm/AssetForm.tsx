/**
 * AssetForm Component
 * ===================
 * Form component for creating and editing capital assets
 */

import React from 'react';
import { CapitalAsset, ASSET_TYPES } from '../../../types/capitalAsset';
import { formatDateInput } from '../../../utils/dateUtils';
import { formatCurrency } from '../../../lib/validation';
import './AssetForm.css';

interface AssetFormProps {
  form: Partial<CapitalAsset>;
  setForm: React.Dispatch<React.SetStateAction<Partial<CapitalAsset>>>;
  editingAssetId: number | null;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
}

export function AssetForm({ form, setForm, editingAssetId, onSubmit, onCancel }: AssetFormProps) {
  return (
    <section className="asset-form-section">
      <h3>{editingAssetId ? 'ערוך נכס הון' : 'הוסף נכס הון'}</h3>
      
      {/* הסבר על לוגיקת נכסי הון */}
      <div className="asset-form-info">
        <strong>💡 איך נכסי הון מוצגים במערכת:</strong>
        <ul className="asset-form-info-list">
          <li><strong>תשלום חד פעמי:</strong> אם שדה "ערך נוכחי" {'>'} 0, הנכס יוצג בתזרים בתאריך התשלום החד פעמי</li>
          <li><strong>הכנסה חודשית:</strong> אם שדה "תשלום" {'>'} 0, הנכס יוצג כהכנסה חודשית קבועה</li>
          <li><strong>פריסת מס:</strong> עבור תשלום חד-פעמי עם פריסה, המס יחושב על פי הפריסה אך ישולם בחד-פעמיות בתאריך התשלום</li>
        </ul>
      </div>
      
      <form onSubmit={onSubmit} className="asset-form">
        <input
          type="text"
          placeholder="שם הנכס"
          value={form.asset_name || ""}
          onChange={(e) => setForm({ ...form, asset_name: e.target.value })}
          className="asset-form-input"
          required
        />

        <div>
          <label>סוג נכס:</label>
          <select
            value={form.asset_type}
            onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
            className="asset-form-input asset-form-input-full"
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
            className="asset-form-input asset-form-input-full"
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
            className="asset-form-input asset-form-input-full"
            min="0"
          />
        </div>

        <input
          type="number"
          step="0.01"
          placeholder="שיעור תשואה שנתי (%) - לחישוב מס רווח הון"
          value={form.annual_return_rate || ""}
          onChange={(e) => setForm({ ...form, annual_return_rate: parseFloat(e.target.value) || 0 })}
          className="asset-form-input"
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
            className="asset-form-input asset-form-input-full"
            maxLength={10}
            required
          />
        </div>

        <div>
          <label>שיטת הצמדה:</label>
          <select
            value={form.indexation_method}
            onChange={(e) => setForm({ ...form, indexation_method: e.target.value as "none" | "fixed" | "cpi" })}
            className="asset-form-input asset-form-input-full"
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
            className="asset-form-input"
          />
        )}

        <div>
          <label>יחס מס:</label>
          <select
            value={form.tax_treatment}
            onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "exempt" | "taxable" | "capital_gains" | "tax_spread" })}
            className="asset-form-input asset-form-input-full"
          >
            <option value="exempt">פטור ממס</option>
            <option value="taxable">חייב במס רגיל</option>
            <option value="capital_gains">מס רווח הון (25% מהרווח הריאלי)</option>
            <option value="tax_spread">פריסת מס</option>
          </select>
        </div>

        {form.tax_treatment === "capital_gains" && (
          <div className="asset-form-capital-gains-box">
            <strong>💰 מס רווח הון (25%)</strong>
            <p className="asset-form-help-text">
              <strong>איך עובד חישוב מס רווח הון:</strong><br/>
              • המס מחושב על הרווח בלבד (תשלום - הפקדה נומינלית)<br/>
              • שיעור המס: 25% מהרווח<br/>
              • התשלום המעודכן: תשלום - 0.25 × (תשלום - הפקדה נומינלית)<br/>
              • הנכס יישמר כ"פטור ממס" עם התשלום המעודכן
            </p>
            <div className="asset-form-field-group">
              <label>סכום ההפקדה הנומינאלי (₪):</label>
              <input
                type="number"
                min="0"
                placeholder="סכום ההפקדה הנומינאלי"
                value={form.nominal_principal !== undefined && form.nominal_principal > 0 ? form.nominal_principal : (form.monthly_income || 0)}
                onChange={(e) => setForm({ ...form, nominal_principal: parseFloat(e.target.value) || 0 })}
                className="asset-form-input asset-form-input-full asset-form-input-with-margin"
                required
              />
              <div className="asset-form-default-text">
                ברירת מחדל: {formatCurrency(form.monthly_income || 0)} (סכום התשלום)
              </div>
              {form.monthly_income && form.monthly_income > 0 && (
                <div className="asset-form-calculation-box">
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
          <div className="asset-form-tax-spread-box">
            <strong>📋 פריסת מס על מספר שנים</strong>
            <p className="asset-form-tax-spread-text">
              <strong>איך עובדת פריסת מס:</strong><br/>
              • הסכום מתחלק שווה על מספר השנים<br/>
              • לכל שנה מחושב המס לפי מדרגות (הכנסה רגילה + חלק שנתי מהמענק)<br/>
              • <strong>בשנה הראשונה משולם כל המס המצטבר</strong><br/>
              • בשנים הבאות - המס מוצג רק ויזואלית, לא בפועל
            </p>
            <div className="asset-form-field-group">
              <label>מספר שנות פריסה (בד"כ 1-6 לפי וותק):</label>
              <input
                type="number"
                min="1"
                max="10"
                placeholder="מספר שנות פריסה"
                value={form.spread_years || ""}
                onChange={(e) => setForm({ ...form, spread_years: parseInt(e.target.value) || 0 })}
                className="asset-form-tax-spread-years-input"
                required
              />
            </div>
          </div>
        )}

        <div className="asset-form-actions">
          <button 
            type="submit" 
            className="asset-form-submit-btn"
          >
            {editingAssetId ? 'שמור שינויים' : 'צור נכס הון'}
          </button>
          
          {editingAssetId && (
            <button 
              type="button" 
              onClick={onCancel}
              className="asset-form-cancel-btn"
            >
              בטל עריכה
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
