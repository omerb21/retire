import React from 'react';
import { PensionFund } from '../types';
import { formatDateInput } from '../../../utils/dateUtils';

interface PensionFundFormProps {
  form: Partial<PensionFund>;
  setForm: (form: Partial<PensionFund>) => void;
  onSubmit: (e: React.FormEvent) => void;
  editingFundId: number | null;
  onCancelEdit: () => void;
  clientData: any;
}

export const PensionFundForm: React.FC<PensionFundFormProps> = ({
  form,
  setForm,
  onSubmit,
  editingFundId,
  onCancelEdit,
  clientData
}) => {
  return (
    <section className="pension-funds-section-card">
      <h3>{editingFundId ? 'ערוך קצבה' : 'הוסף קצבה'}</h3>
    
      {clientData && clientData.birth_date && (
        <div className="pension-funds-form-info">
          <strong>מידע:</strong> אם לא תזין תאריך התחלת קצבה, המערכת תשתמש בתאריך הקצבה המוקדמת ביותר או בגיל פרישה {clientData.gender?.toLowerCase() === "female" ? "62" : "67"}.
        </div>
      )}
      
      <form onSubmit={onSubmit} className="pension-funds-form-grid">
        <input
          type="text"
          placeholder="שם המשלם"
          value={form.fund_name || ""}
          onChange={(e) => setForm({ ...form, fund_name: e.target.value })}
          className="pension-funds-input"
          required
        />
        
        <div>
          <label>מצב חישוב:</label>
          <select
            value={form.calculation_mode}
            onChange={(e) => setForm({ ...form, calculation_mode: e.target.value as "calculated" | "manual" })}
            className="pension-funds-select"
          >
            <option value="calculated">מחושב</option>
            <option value="manual">ידני</option>
          </select>
        </div>

        {form.calculation_mode === "calculated" && (
          <>
            <input
              type="number"
              placeholder="יתרה"
              value={form.balance || ""}
              onChange={(e) => setForm({ ...form, balance: parseFloat(e.target.value) || 0 })}
              className="pension-funds-input"
            />
            <input
              type="number"
              step="0.01"
              placeholder="מקדם קצבה"
              value={form.annuity_factor || ""}
              onChange={(e) => setForm({ ...form, annuity_factor: parseFloat(e.target.value) || 0 })}
              className="pension-funds-input"
            />
          </>
        )}

        {form.calculation_mode === "manual" && (
          <input
            type="number"
            placeholder="סכום חודשי"
            value={form.monthly_amount || ""}
            onChange={(e) => setForm({ ...form, monthly_amount: parseFloat(e.target.value) || 0 })}
            className="pension-funds-input"
          />
        )}

        <input
          type="text"
          placeholder="תיק ניכויים"
          value={form.deduction_file || ""}
          onChange={(e) => setForm({ ...form, deduction_file: e.target.value })}
          className="pension-funds-input"
        />

        <input
          type="text"
          placeholder="DD/MM/YYYY"
          value={form.pension_start_date || ""}
          onChange={(e) => {
            const formatted = formatDateInput(e.target.value);
            setForm({ ...form, pension_start_date: formatted });
          }}
          className="pension-funds-input"
          maxLength={10}
        />

        <div>
          <label>שיטת הצמדה:</label>
          <select
            value={form.indexation_method}
            onChange={(e) => setForm({ ...form, indexation_method: e.target.value as "none" | "fixed" | "cpi" })}
            className="pension-funds-select"
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
            value={form.indexation_rate || ""}
            onChange={(e) => setForm({ ...form, indexation_rate: parseFloat(e.target.value) || 0 })}
            className="pension-funds-input"
          />
        )}

        <div>
          <label>יחס למס:</label>
          <select
            value={form.tax_treatment || "taxable"}
            onChange={(e) => setForm({ ...form, tax_treatment: e.target.value as "taxable" | "exempt" })}
            className="pension-funds-select"
          >
            <option value="taxable">חייב במס</option>
            <option value="exempt">פטור ממס</option>
          </select>
        </div>

        <div className="pension-funds-form-actions">
          <button 
            type="submit" 
            className="pension-funds-form-submit"
          >
            {editingFundId ? 'שמור שינויים' : 'צור קצבה'}
          </button>
          
          {editingFundId && (
            <button 
              type="button" 
              onClick={onCancelEdit}
              className="pension-funds-form-cancel"
            >
              בטל עריכה
            </button>
          )}
        </div>
      </form>
    </section>
  );
};
