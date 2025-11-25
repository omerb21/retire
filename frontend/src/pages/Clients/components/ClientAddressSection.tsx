import React from 'react';
import { NewClientForm } from '../types';

interface ClientAddressSectionProps {
  form: NewClientForm;
  setForm: React.Dispatch<React.SetStateAction<NewClientForm>>;
}

export const ClientAddressSection: React.FC<ClientAddressSectionProps> = ({ form, setForm }) => {
  return (
    <section>
      <h3 className="clients-section-title">כתובת</h3>
      <div className="grid clients-grid">
        <input
          placeholder="רחוב (אופציונלי)"
          value={form.address_street}
          onChange={(e) => setForm({ ...form, address_street: e.target.value })}
          className="form-input"
        />
        <input
          placeholder="עיר (אופציונלי)"
          value={form.address_city}
          onChange={(e) => setForm({ ...form, address_city: e.target.value })}
          className="form-input"
        />
        <input
          placeholder="מיקוד (אופציונלי)"
          value={form.address_postal_code}
          onChange={(e) => setForm({ ...form, address_postal_code: e.target.value })}
          className="form-input"
        />
      </div>
    </section>
  );
};
