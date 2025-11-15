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
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.5)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000
      }}
    >
      <div
        style={{
          backgroundColor: 'white',
          padding: '20px',
          borderRadius: '8px',
          minWidth: '400px',
          maxWidth: '500px',
          direction: 'rtl'
        }}
      >
        <h3>עריכת פרטי לקוח</h3>
        <div style={{ display: 'grid', gap: '12px' }}>
          <input
            placeholder={"ת\"ז"}
            value={editForm.id_number}
            onChange={(e) => setEditForm({ ...editForm, id_number: e.target.value })}
            style={{ padding: 8 }}
          />
          <input
            placeholder="שם פרטי"
            value={editForm.first_name}
            onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
            style={{ padding: 8 }}
          />
          <input
            placeholder="שם משפחה"
            value={editForm.last_name}
            onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
            style={{ padding: 8 }}
          />
          <input
            type="text"
            placeholder="DD/MM/YYYY"
            value={editForm.birth_date}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setEditForm({ ...editForm, birth_date: formatted });
            }}
            style={{ padding: 8 }}
            maxLength={10}
          />
          <select
            value={editForm.gender}
            onChange={(e) => setEditForm({ ...editForm, gender: e.target.value })}
            style={{ padding: 8 }}
          >
            <option value="male">זכר</option>
            <option value="female">נקבה</option>
          </select>
          <input
            placeholder="Email (אופציונלי)"
            value={editForm.email}
            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            style={{ padding: 8 }}
          />
          <input
            placeholder="טלפון (אופציונלי)"
            value={editForm.phone}
            onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
            style={{ padding: 8 }}
          />
          <h4 style={{ marginTop: 16, marginBottom: 8 }}>כתובת</h4>
          <input
            placeholder="רחוב (אופציונלי)"
            value={editForm.address_street}
            onChange={(e) => setEditForm({ ...editForm, address_street: e.target.value })}
            style={{ padding: 8 }}
          />
          <input
            placeholder="עיר (אופציונלי)"
            value={editForm.address_city}
            onChange={(e) => setEditForm({ ...editForm, address_city: e.target.value })}
            style={{ padding: 8 }}
          />
          <input
            placeholder="מיקוד (אופציונלי)"
            value={editForm.address_postal_code}
            onChange={(e) => setEditForm({ ...editForm, address_postal_code: e.target.value })}
            style={{ padding: 8 }}
          />

          <h4 style={{ marginTop: 16, marginBottom: 8 }}>נתונים נוספים</h4>

          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ marginLeft: 8, minWidth: 100 }}>מצב משפחתי:</label>
            <select
              value={editForm.marital_status}
              onChange={(e) => setEditForm({ ...editForm, marital_status: e.target.value })}
              style={{ padding: 8, flexGrow: 1 }}
            >
              <option value="">בחר מצב משפחתי</option>
              <option value="single">רווק/ה</option>
              <option value="married">נשוי/ה</option>
              <option value="divorced">גרוש/ה</option>
              <option value="widowed">אלמן/ה</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ marginLeft: 8 }}>נקודות זיכוי:</label>
            <input
              type="number"
              placeholder="נקודות זיכוי"
              value={editForm.tax_credit_points}
              onChange={(e) =>
                setEditForm({ ...editForm, tax_credit_points: parseFloat(e.target.value) || 0 })
              }
              min="0"
              step="0.01"
              style={{ padding: 8, flexGrow: 1 }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: 16 }}>
            <button
              onClick={onCancel}
              style={{
                padding: '8px 16px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              ביטול
            </button>
            <button
              onClick={onSave}
              style={{
                padding: '8px 16px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              שמור
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
