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
      <div style={{
        marginBottom: '20px',
        padding: '15px',
        border: '1px solid #ffc107',
        borderRadius: '4px',
        backgroundColor: '#fff3cd'
      }}>
        <p style={{ margin: 0, color: '#856404' }}>לא נמצאו נתונים שמורים. אנא מלא את הפרטים למטה.</p>
      </div>
    );
  }

  return (
    <div style={{ 
      marginBottom: '20px', 
      padding: '15px', 
      border: '1px solid #28a745', 
      borderRadius: '4px',
      backgroundColor: '#f8fff9'
    }}>
      <h3 style={{ color: '#28a745', marginBottom: '15px' }}>נתונים שמורים</h3>
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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
        <div><strong>שם מעסיק:</strong> {employer.employer_name}</div>
        <div><strong>תאריך התחלה:</strong> {employer.start_date}</div>
        <div><strong>תאריך סיום:</strong> {employer.end_date || 'לא הוזן'}</div>
        <div><strong>שכר חודשי:</strong> {(() => {
          console.log('💰 TABLE SALARY:', employer.last_salary);
          return formatCurrency(employer.last_salary);
        })()}</div>
        <div><strong>יתרת פיצויים:</strong> {formatCurrency(employer.severance_accrued)}</div>
        {employer.employer_completion !== undefined && (
          <div style={{ color: '#0066cc', fontWeight: 'bold', gridColumn: '1 / -1' }}>
            <strong>השלמת המעסיק:</strong> {formatCurrency(employer.employer_completion)}
          </div>
        )}
      </div>
    </div>
  );
};
