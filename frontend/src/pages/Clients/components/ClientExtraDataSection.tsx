import React from 'react';
import { NewClientForm } from '../types';

interface ClientExtraDataSectionProps {
  form: NewClientForm;
  setForm: React.Dispatch<React.SetStateAction<NewClientForm>>;
}

export const ClientExtraDataSection: React.FC<ClientExtraDataSectionProps> = ({ form, setForm }) => {
  return (
    <section>
      <h3 style={{ marginBottom: '1rem', color: 'var(--gray-700)', fontSize: '1.25rem' }}>נתונים נוספים</h3>
      <div className="grid" style={{ gap: '1rem' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">מצב משפחתי:</label>
          <select
            value={form.marital_status}
            onChange={(e) => setForm({ ...form, marital_status: e.target.value })}
            className="form-select"
          >
            <option value="">בחר מצב משפחתי</option>
            <option value="single">רווק/ה</option>
            <option value="married">נשוי/ה</option>
            <option value="divorced">גרוש/ה</option>
            <option value="widowed">אלמן/ה</option>
          </select>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">נקודות זיכוי:</label>
          <input
            type="number"
            placeholder="נקודות זיכוי"
            value={form.tax_credit_points}
            onChange={(e) => setForm({ ...form, tax_credit_points: parseFloat(e.target.value) || 0 })}
            min="0"
            step="0.01"
            className="form-input"
          />
        </div>
      </div>
    </section>
  );
};
