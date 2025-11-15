/**
 * Employer Details Form Component
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { SimpleEmployer, TerminationDecision } from '../types';
import { formatDateInput } from '../../../utils/dateUtils';
import { clearTerminationState } from '../utils/storageHelpers';
import { formatCurrency } from '../../../lib/validation';

interface EmployerDetailsFormProps {
  clientId: string;
  employer: SimpleEmployer;
  setEmployer: React.Dispatch<React.SetStateAction<SimpleEmployer>>;
  terminationDecision: TerminationDecision;
  setTerminationDecision: React.Dispatch<React.SetStateAction<TerminationDecision>>;
  loading: boolean;
  onSubmit: (e: React.FormEvent) => Promise<void>;
}

export const EmployerDetailsForm: React.FC<EmployerDetailsFormProps> = ({
  clientId,
  employer,
  setEmployer,
  terminationDecision,
  setTerminationDecision,
  loading,
  onSubmit
}) => {
  const navigate = useNavigate();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setEmployer(prev => ({
      ...prev,
      [name]: name.includes('salary') || name.includes('balance') 
        ? parseFloat(value) || 0 : value
    }));
    
    // If user changes data, clear confirmation flag
    clearTerminationState(clientId);
    setTerminationDecision(prev => ({ ...prev, confirmed: false }));
  };

  return (
    <form onSubmit={onSubmit}>
      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          שם מעסיק *
        </label>
        <input
          type="text"
          name="employer_name"
          value={employer.employer_name}
          onChange={handleInputChange}
          required
          style={{
            width: '100%',
            padding: '10px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '16px'
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          תאריך התחלת עבודה *
        </label>
        <input
          type="text"
          name="start_date"
          placeholder="DD/MM/YYYY"
          value={employer.start_date || ''}
          onChange={(e) => {
            const formatted = formatDateInput(e.target.value);
            setEmployer({ ...employer, start_date: formatted });
          }}
          maxLength={10}
          required
          style={{
            width: '100%',
            padding: '10px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '16px'
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          שכר חודשי (₪) *
        </label>
        <input
          type="number"
          name="last_salary"
          value={employer.last_salary}
          onChange={handleInputChange}
          required
          min="0"
          step="0.01"
          style={{
            width: '100%',
            padding: '10px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '16px'
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          תאריך סיום עבודה (אופציונלי)
        </label>
        <input
          type="text"
          name="end_date"
          placeholder="DD/MM/YYYY"
          value={employer.end_date || ''}
          onChange={(e) => {
            const formatted = formatDateInput(e.target.value);
            setEmployer({ ...employer, end_date: formatted });
            
            // Clear confirmation flag when end date changes
            clearTerminationState(clientId);
            setTerminationDecision(prev => ({ ...prev, confirmed: false }));
          }}
          maxLength={10}
          style={{
            width: '100%',
            padding: '10px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '16px'
          }}
        />
        <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
          יש להזין רק אם העבודה כבר הסתיימה. אם השדה ריק, תתבקש להזין תאריך בעת מעבר לעזיבת עבודה.
        </small>
        {terminationDecision.confirmed && (
          <div style={{ 
            marginTop: '10px', 
            padding: '10px', 
            backgroundColor: '#fff3cd', 
            border: '1px solid #ffeaa7', 
            borderRadius: '4px' 
          }}>
            <p style={{ color: '#856404', fontSize: '14px', margin: 0, fontWeight: 'bold' }}>
              ⚠️ קיימת עזיבת עבודה שמורה במערכת מתאריך {employer.end_date}
            </p>
            <p style={{ color: '#856404', fontSize: '12px', margin: '5px 0 0 0' }}>
              לעריכת החלטות חדשות, עבור לטאב "עזיבת עבודה" ומחק את העזיבה הקיימת
            </p>
          </div>
        )}
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          יתרת פיצויים נצברת (₪)
        </label>
        <div style={{ 
          padding: '12px', 
          backgroundColor: '#f8f9fa',
          border: '2px solid #e9ecef',
          borderRadius: '4px',
          fontSize: '18px',
          fontWeight: 'bold',
          color: '#495057'
        }}>
          {formatCurrency(employer.severance_accrued)}
        </div>
        <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
          שדה מחושב: סה"כ יתרות פיצויים מתיק פנסיוני של מעסיק נוכחי
        </small>
      </div>

      <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={() => navigate(`/clients/${clientId}`)}
          disabled={loading}
          style={{
            padding: '10px 20px',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '16px'
          }}
        >
          ביטול
        </button>
        
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '10px 20px',
            backgroundColor: loading ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '16px'
          }}
        >
          {loading ? 'שומר...' : 'שמור'}
        </button>
      </div>
    </form>
  );
};
