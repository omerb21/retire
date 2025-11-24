/**
 * Saved Data Display Component
 */

import React from 'react';
import { SimpleEmployer } from '../types';
import { formatCurrency } from '../../../lib/validation';

interface SavedDataDisplayProps {
  employer: SimpleEmployer;
}

export const SavedDataDisplay: React.FC<SavedDataDisplayProps> = ({ employer }) => {
  if (!employer.id) {
    return (
      <div className="saved-data-container saved-data-container--empty">
        <p className="saved-data-empty-text">לא נמצאו נתונים שמורים. אנא מלא את הפרטים למטה.</p>
      </div>
    );
  }

  return (
    <div className="saved-data-container saved-data-container--filled">
      <h3 className="saved-data-title">נתונים שמורים</h3>
      {(() => {
        console.log('📊 TABLE DATA:', {
          employer_name: employer.employer_name,
          start_date: employer.start_date,
          end_date: employer.end_date,
          last_salary: employer.last_salary,
          severance_accrued: employer.severance_accrued,
          id: employer.id
        });
        return null;
      })()}
      <div className="saved-data-grid">
        <div><strong>שם מעסיק:</strong> {employer.employer_name}</div>
        <div><strong>תאריך התחלה:</strong> {employer.start_date}</div>
        <div><strong>תאריך סיום:</strong> {employer.end_date || 'לא הוזן'}</div>
        <div><strong>שכר חודשי:</strong> {(() => {
          console.log('💰 TABLE SALARY:', employer.last_salary);
          return formatCurrency(employer.last_salary);
        })()}</div>
        <div><strong>יתרת פיצויים:</strong> {formatCurrency(employer.severance_accrued)}</div>
        {employer.employer_completion !== undefined && (
          <div className="saved-data-employer-completion">
            <strong>השלמת המעסיק:</strong> {formatCurrency(employer.employer_completion)}
          </div>
        )}
      </div>
    </div>
  );
};
