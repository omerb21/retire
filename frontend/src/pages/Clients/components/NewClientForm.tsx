import React from 'react';
import type { NewClientForm as NewClientFormState } from '../types';
import { formatDateInput } from '../../../utils/dateUtils';

interface NewClientFormProps {
  form: NewClientFormState;
  setForm: React.Dispatch<React.SetStateAction<NewClientFormState>>;
  onSubmit: (e: React.FormEvent) => void;
}

export const NewClientForm: React.FC<NewClientFormProps> = ({ form, setForm, onSubmit }) => {
  return (
    <section>
      <h3 className="clients-section-title">פתיחת לקוח חדש</h3>
      <form onSubmit={onSubmit} className="grid clients-grid">
        <input
          placeholder={"ת\"ז (למשל 123456782)"}
          value={form.id_number}
          onChange={(e) => setForm({ ...form, id_number: e.target.value })}
          className="form-input"
        />
        <input
          placeholder={"שם פרטי"}
          value={form.first_name}
          onChange={(e) => setForm({ ...form, first_name: e.target.value })}
          className="form-input"
        />
        <input
          placeholder="שם משפחה"
          value={form.last_name}
          onChange={(e) => setForm({ ...form, last_name: e.target.value })}
          className="form-input"
        />
        <input
          type="text"
          placeholder="תאריך לידה (DD/MM/YYYY)"
          value={form.birth_date}
          onChange={(e) => {
            const formatted = formatDateInput(e.target.value);
            setForm({ ...form, birth_date: formatted });
          }}
          className="form-input"
          maxLength={10}
        />
        <select
          value={form.gender}
          onChange={(e) => setForm({ ...form, gender: e.target.value })}
          className="form-select"
        >
          <option value="male">זכר</option>
          <option value="female">נקבה</option>
        </select>
        <input
          placeholder="Email (אופציונלי)"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          className="form-input"
        />
        <input
          placeholder="טלפון (אופציונלי)"
          value={form.phone}
          onChange={(e) => setForm({ ...form, phone: e.target.value })}
          className="form-input"
        />

        <button type="submit" className="btn btn-success clients-new-client-submit">
          שמור לקוח
        </button>
      </form>
    </section>
  );
};
