/**
 * GrantForm Component - Form for adding new grants
 * רכיב טופס להוספת מענקים חדשים
 */

import React, { useState } from 'react';
import { GrantFormData, GRANT_TYPE_LABELS } from '../../types/grant.types';
import { formatDateInput } from '../../utils/dateUtils';

interface GrantFormProps {
  onSubmit: (grantData: GrantFormData) => Promise<boolean>;
  loading: boolean;
}

const initialFormState: GrantFormData = {
  employer_name: '',
  work_start_date: '',
  work_end_date: '',
  grant_type: 'severance',
  grant_date: '',
  grant_amount: 0,
  amount: 0,
  reason: ''
};

export const GrantForm: React.FC<GrantFormProps> = ({ onSubmit, loading }) => {
  const [formData, setFormData] = useState<GrantFormData>(initialFormState);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    
    setFormData(prev => ({
      ...prev,
      [name]: name === 'grant_amount' || name === 'amount' ? parseFloat(value) || 0 : value
    }));
    
    // סנכרון בין grant_amount ו-amount
    if (name === 'grant_amount') {
      setFormData(prev => ({ ...prev, amount: parseFloat(value) || 0 }));
    }
    if (name === 'amount') {
      setFormData(prev => ({ ...prev, grant_amount: parseFloat(value) || 0 }));
    }
  };

  const handleDateChange = (field: 'work_start_date' | 'work_end_date' | 'grant_date', value: string) => {
    const formatted = formatDateInput(value);
    setFormData(prev => ({ ...prev, [field]: formatted }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const success = await onSubmit(formData);
    
    if (success) {
      // Reset form on success
      setFormData(initialFormState);
      alert('מענק נוסף בהצלחה');
    }
  };

  return (
    <div style={{ 
      marginTop: '2rem', 
      padding: '1.5rem', 
      backgroundColor: 'var(--gray-50)', 
      borderRadius: 'var(--radius-lg)', 
      border: '1px solid var(--gray-200)' 
    }}>
      <h3 style={{ marginBottom: '1.5rem', color: 'var(--gray-700)', fontSize: '1.25rem' }}>
        ➕ הוספת מענק חדש
      </h3>
      
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              שם מעסיק:
            </label>
            <input
              type="text"
              name="employer_name"
              value={formData.employer_name}
              onChange={handleInputChange}
              required
              className="form-input"
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              סוג מענק:
            </label>
            <select
              name="grant_type"
              value={formData.grant_type}
              onChange={handleInputChange}
              className="form-select"
            >
              {Object.entries(GRANT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              תאריך התחלת עבודה:
            </label>
            <input
              type="text"
              name="work_start_date"
              placeholder="DD/MM/YYYY"
              value={formData.work_start_date}
              onChange={(e) => handleDateChange('work_start_date', e.target.value)}
              required
              maxLength={10}
              className="form-input"
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              תאריך סיום עבודה:
            </label>
            <input
              type="text"
              name="work_end_date"
              placeholder="DD/MM/YYYY"
              value={formData.work_end_date}
              onChange={(e) => handleDateChange('work_end_date', e.target.value)}
              required
              maxLength={10}
              className="form-input"
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              תאריך קבלת מענק:
            </label>
            <input
              type="text"
              name="grant_date"
              placeholder="DD/MM/YYYY"
              value={formData.grant_date}
              onChange={(e) => handleDateChange('grant_date', e.target.value)}
              required
              maxLength={10}
              className="form-input"
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              סכום מענק (₪):
            </label>
            <input
              type="number"
              name="grant_amount"
              value={formData.grant_amount}
              onChange={handleInputChange}
              required
              min="0"
              className="form-input"
            />
          </div>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            הערות (אופציונלי):
          </label>
          <textarea
            name="reason"
            value={formData.reason}
            onChange={handleInputChange}
            rows={3}
            className="form-textarea"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn btn-success"
        >
          {loading ? 'מוסיף...' : '➕ הוסף מענק'}
        </button>
      </form>
    </div>
  );
};
