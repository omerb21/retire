/**
 * Employer Details Form Component
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { SimpleEmployer, TerminationDecision } from '../types';
import { formatDateInput } from '../../../utils/dateUtils';
import {
  clearTerminationState,
  setEmployerCompletionPreference,
} from '../utils/storageHelpers';
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
      <div className="employer-form-field">
        <label className="employer-form-label">
          שם מעסיק *
        </label>
        <input
          type="text"
          name="employer_name"
          value={employer.employer_name}
          onChange={handleInputChange}
          required
          className="employer-form-input"
        />
      </div>

      <div className="employer-form-field">
        <label className="employer-form-label">
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
          className="employer-form-input"
        />
      </div>

      <div className="employer-form-field">
        <label className="employer-form-label">
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
          className="employer-form-input employer-form-input--number"
        />
      </div>

      <div className="employer-form-field">
        <label className="employer-form-label">
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
          className="employer-form-input"
        />
        <small className="employer-form-helper-text">
          יש להזין רק אם העבודה כבר הסתיימה. אם השדה ריק, תתבקש להזין תאריך בעת מעבר לעזיבת עבודה.
        </small>
        {terminationDecision.confirmed && (
          <div className="termination-warning-box">
            <p className="termination-warning-title">
              ⚠️ קיימת עזיבת עבודה שמורה במערכת מתאריך {employer.end_date}
            </p>
            <p className="termination-warning-text">
              לעריכת החלטות חדשות, עבור לטאב "עזיבת עבודה" ומחק את העזיבה הקיימת
            </p>
          </div>
        )}
      </div>

      <div className="employer-form-field">
        <label className="employer-form-label">
          השלמת מעסיק
        </label>
        <label className="employer-form-checkbox-label">
          <input
            type="checkbox"
            checked={!!terminationDecision.use_employer_completion}
            onChange={(e) => {
              const useCompletion = e.target.checked;
              // עדכון החלטת העזיבה בזיכרון
              setTerminationDecision(prev => ({
                ...prev,
                use_employer_completion: useCompletion,
                confirmed: false,
              }));

              // שמירת העדפה ב-localStorage
              setEmployerCompletionPreference(clientId, useCompletion);

              // שינוי החלטה מחייב ניקוי מצב עזיבה קודם
              clearTerminationState(clientId);
            }}
            disabled={loading}
            className="employer-form-checkbox-input"
          />
          תבוצע השלמת מעסיק (בתהליכי עזיבה ותרחישי פרישה)
        </label>
      </div>

      <div className="employer-form-field">
        <label className="employer-form-label">
          יתרת פיצויים נצברת (₪)
        </label>
        <div className="employer-form-severance-box">
          {formatCurrency(employer.severance_accrued)}
        </div>
        <small className="employer-form-helper-text">
          שדה מחושב: סה"כ יתרות פיצויים מתיק פנסיוני של מעסיק נוכחי
        </small>
      </div>

      <div className="employer-form-actions">
        <button
          type="button"
          onClick={() => navigate(`/clients/${clientId}`)}
          disabled={loading}
          className="employer-form-button-cancel"
        >
          ביטול
        </button>
        
        <button
          type="submit"
          disabled={loading}
          className={`employer-form-button-submit ${loading ? 'employer-form-button-submit--disabled' : ''}`}
        >
          {loading ? 'שומר...' : 'שמור'}
        </button>
      </div>
    </form>
  );
};
