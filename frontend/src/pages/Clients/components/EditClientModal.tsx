import React from 'react';
import { EditClientForm } from '../types';
import { formatDateInput } from '../../../utils/dateUtils';

interface EditClientModalProps {
  editingClient: any | null;
  editForm: EditClientForm;
  setEditForm: React.Dispatch<React.SetStateAction<EditClientForm>>;
  onSave: () => void | Promise<void>;
  onCancel: () => void;
}

export const EditClientModal: React.FC<EditClientModalProps> = ({
  editingClient,
  editForm,
  setEditForm,
  onSave,
  onCancel
}) => {
  if (!editingClient) {
    return null;
  }

  return (
    <div className="clients-edit-modal-overlay">
      <div className="clients-edit-modal">
        <h3>עריכת פרטי לקוח</h3>
        <div className="clients-edit-modal-grid">
          <input
            placeholder={'ת"ז'}
            value={editForm.id_number}
            onChange={(e) => setEditForm({ ...editForm, id_number: e.target.value })}
            className="clients-edit-input"
          />
          <input
            placeholder="שם פרטי"
            value={editForm.first_name}
            onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
            className="clients-edit-input"
          />
          <input
            placeholder="שם משפחה"
            value={editForm.last_name}
            onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
            className="clients-edit-input"
          />
          <input
            type="text"
            placeholder="DD/MM/YYYY"
            value={editForm.birth_date}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setEditForm({ ...editForm, birth_date: formatted });
            }}
            className="clients-edit-input"
            maxLength={10}
          />
          <select
            value={editForm.gender}
            onChange={(e) => setEditForm({ ...editForm, gender: e.target.value })}
            className="clients-edit-select"
          >
            <option value="male">זכר</option>
            <option value="female">נקבה</option>
          </select>
          <input
            placeholder="Email (אופציונלי)"
            value={editForm.email}
            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            className="clients-edit-input"
          />
          <input
            placeholder="טלפון (אופציונלי)"
            value={editForm.phone}
            onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
            className="clients-edit-input"
          />
          <h4 className="clients-edit-section-title">כתובת</h4>
          <input
            placeholder="רחוב (אופציונלי)"
            value={editForm.address_street}
            onChange={(e) => setEditForm({ ...editForm, address_street: e.target.value })}
            className="clients-edit-input"
          />
          <input
            placeholder="עיר (אופציונלי)"
            value={editForm.address_city}
            onChange={(e) => setEditForm({ ...editForm, address_city: e.target.value })}
            className="clients-edit-input"
          />
          <input
            placeholder="מיקוד (אופציונלי)"
            value={editForm.address_postal_code}
            onChange={(e) => setEditForm({ ...editForm, address_postal_code: e.target.value })}
            className="clients-edit-input"
          />

          <h4 className="clients-edit-section-title">נתונים נוספים</h4>

          <div className="clients-edit-row">
            <label className="clients-edit-label-inline clients-edit-label-inline--wide">מצב משפחתי:</label>
            <select
              value={editForm.marital_status}
              onChange={(e) => setEditForm({ ...editForm, marital_status: e.target.value })}
              className="clients-edit-select clients-edit-input--grow"
            >
              <option value="">בחר מצב משפחתי</option>
              <option value="single">רווק/ה</option>
              <option value="married">נשוי/ה</option>
              <option value="divorced">גרוש/ה</option>
              <option value="widowed">אלמן/ה</option>
            </select>
          </div>

          <div className="clients-edit-row">
            <label className="clients-edit-label-inline">נקודות זיכוי:</label>
            <input
              type="number"
              placeholder="נקודות זיכוי"
              value={editForm.tax_credit_points}
              onChange={(e) =>
                setEditForm({ ...editForm, tax_credit_points: parseFloat(e.target.value) || 0 })
              }
              min="0"
              step="0.01"
              className="clients-edit-input clients-edit-input--grow"
            />
          </div>

          <div className="clients-edit-actions">
            <button
              onClick={onCancel}
              className="clients-edit-button clients-edit-button--cancel"
            >
              ביטול
            </button>
            <button
              onClick={onSave}
              className="clients-edit-button clients-edit-button--save"
            >
              שמור
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
