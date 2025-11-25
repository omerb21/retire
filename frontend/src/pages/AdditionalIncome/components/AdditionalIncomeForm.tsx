import React from 'react';
import { formatDateInput } from '../../../utils/dateUtils';
import { AdditionalIncome } from '../hooks/useAdditionalIncome';

const INCOME_TYPE_MAP: Record<string, string> = {
  rental: 'שכירות',
  dividends: 'דיבידנדים',
  interest: 'ריבית',
  business: 'עסק',
  salary: 'שכיר',
  other: 'אחר',
};

const INCOME_TYPES = ['rental', 'dividends', 'interest', 'business', 'salary', 'other'];

interface AdditionalIncomeFormProps {
  form: Partial<AdditionalIncome>;
  setForm: (form: Partial<AdditionalIncome>) => void;
  editingIncomeId: number | null;
  setEditingIncomeId: (id: number | null) => void;
  handleSubmit: (e: React.FormEvent) => void;
}

export const AdditionalIncomeForm: React.FC<AdditionalIncomeFormProps> = ({
  form,
  setForm,
  editingIncomeId,
  setEditingIncomeId,
  handleSubmit,
}) => {
  return (
    <section className="additional-income-form-section">
      <h3>{editingIncomeId ? 'ערוך הכנסה נוספת' : 'הוסף הכנסה נוספת'}</h3>
      <form onSubmit={handleSubmit} className="additional-income-form">
        <div>
          <label>סוג הכנסה:</label>
          <select
            value={form.source_type}
            onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            className="additional-income-select additional-income-select--full"
          >
            {INCOME_TYPES.map((type) => (
              <option key={type} value={type}>
                {INCOME_TYPE_MAP[type]}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label>שם הכנסה:</label>
          <input
            type="text"
            placeholder="שם ההכנסה"
            value={form.description || ''}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="additional-income-input additional-income-input--full"
            required
          />
        </div>

        <input
          type="number"
          placeholder="סכום"
          value={form.amount || ''}
          onChange={(e) => setForm({ ...form, amount: parseFloat(e.target.value) || 0 })}
          className="additional-income-input"
        />

        <div>
          <label>תדירות:</label>
          <select
            value={form.frequency}
            onChange={(e) =>
              setForm({ ...form, frequency: e.target.value as 'monthly' | 'annually' })
            }
            className="additional-income-select additional-income-select--full"
          >
            <option value="monthly">חודשי</option>
            <option value="annually">שנתי</option>
          </select>
        </div>

        <div>
          <label>תאריך התחלה:</label>
          <input
            type="text"
            placeholder="DD/MM/YYYY"
            value={form.start_date || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setForm({ ...form, start_date: formatted });
            }}
            className="additional-income-input additional-income-input--full"
            maxLength={10}
          />
        </div>

        <div>
          <label>תאריך סיום (אופציונלי):</label>
          <input
            type="text"
            placeholder="DD/MM/YYYY"
            value={form.end_date || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setForm({ ...form, end_date: formatted || undefined });
            }}
            className="additional-income-input additional-income-input--full"
            maxLength={10}
          />
        </div>

        <div>
          <label>שיטת הצמדה:</label>
          <select
            value={form.indexation_method}
            onChange={(e) =>
              setForm({ ...form, indexation_method: e.target.value as 'none' | 'fixed' | 'cpi' })
            }
            className="additional-income-select additional-income-select--full"
          >
            <option value="none">ללא הצמדה</option>
            <option value="fixed">הצמדה קבועה</option>
            <option value="cpi">הצמדה למדד</option>
          </select>
        </div>

        {form.indexation_method === 'fixed' && (
          <input
            type="number"
            step="0.01"
            placeholder="שיעור הצמדה קבוע (%)"
            value={form.fixed_rate || ''}
            onChange={(e) =>
              setForm({ ...form, fixed_rate: parseFloat(e.target.value) || 0 })
            }
            className="additional-income-input"
          />
        )}

        <div>
          <label>יחס מס:</label>
          <select
            value={form.tax_treatment}
            onChange={(e) =>
              setForm({
                ...form,
                tax_treatment: e.target.value as 'exempt' | 'taxable' | 'fixed_rate',
              })
            }
            className="additional-income-select additional-income-select--full"
          >
            <option value="exempt">פטור ממס</option>
            <option value="taxable">חייב במס</option>
            <option value="fixed_rate">שיעור מס קבוע</option>
          </select>
        </div>

        {form.tax_treatment === 'fixed_rate' && (
          <input
            type="number"
            step="0.01"
            placeholder="שיעור מס (%)"
            value={form.tax_rate || ''}
            onChange={(e) =>
              setForm({ ...form, tax_rate: parseFloat(e.target.value) || 0 })
            }
            className="additional-income-input"
          />
        )}

        <div className="additional-income-submit-row">
          <button type="submit" className="additional-income-submit-button">
            {editingIncomeId ? 'שמור שינויים' : 'צור הכנסה נוספת'}
          </button>

          {editingIncomeId && (
            <button
              type="button"
              onClick={() => {
                setEditingIncomeId(null);
                setForm({
                  source_type: 'rental',
                  description: '',
                  amount: 0,
                  frequency: 'monthly',
                  start_date: '',
                  indexation_method: 'none',
                  tax_treatment: 'taxable',
                  fixed_rate: 0,
                  tax_rate: 0,
                });
              }}
              className="additional-income-cancel-button"
            >
              בטל עריכה
            </button>
          )}
        </div>
      </form>
    </section>
  );
};
