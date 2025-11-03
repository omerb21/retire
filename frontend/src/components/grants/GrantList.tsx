/**
 * GrantList Component - Display list of grants
 * רכיב רשימת מענקים
 */

import React from 'react';
import { Grant, GrantDetails } from '../../types/grant.types';
import { formatDateToDDMMYY } from '../../utils/dateUtils';
import { getGrantAmount } from '../../utils/grantCalculations';

interface GrantListProps {
  grants: Grant[];
  grantDetails: { [key: number]: GrantDetails };
  onDelete: (grantId: number) => Promise<boolean>;
}

export const GrantList: React.FC<GrantListProps> = ({ grants, grantDetails, onDelete }) => {
  if (grants.length === 0) {
    return (
      <div style={{ 
        padding: '20px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '4px',
        textAlign: 'center',
        color: '#666'
      }}>
        אין מענקים רשומים
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: '15px' }}>
      {grants.map((grant, index) => {
        const details = grant.id ? grantDetails[grant.id] : null;
        const amount = getGrantAmount(grant);
        
        return (
          <div 
            key={grant.id || index}
            style={{ 
              padding: '20px', 
              border: '1px solid #ddd', 
              borderRadius: '4px',
              backgroundColor: 'white'
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '15px', alignItems: 'start' }}>
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
                  <div>
                    <strong>מעסיק:</strong> {grant.employer_name}
                  </div>
                  <div>
                    <strong>תקופת עבודה:</strong> {formatDateToDDMMYY(new Date(grant.work_start_date))} - {formatDateToDDMMYY(new Date(grant.work_end_date))}
                  </div>
                  <div>
                    <strong>תאריך מענק:</strong> {formatDateToDDMMYY(new Date(grant.grant_date))}
                  </div>
                </div>
                
                <div style={{ marginBottom: '10px' }}>
                  <div>
                    <strong>סכום מענק:</strong> ₪{amount.toLocaleString()}
                  </div>
                </div>

                {details && (
                  <div style={{ 
                    padding: '10px', 
                    backgroundColor: '#f8fff9', 
                    borderRadius: '4px',
                    border: '1px solid #d4edda'
                  }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '14px' }}>
                      <div>
                        <strong>תקופת עבודה:</strong> {details.serviceYears} שנים
                      </div>
                      {details.taxDue > 0 && (
                        <div style={{ color: '#dc3545' }}>
                          <strong>מס משוער:</strong> ₪{details.taxDue.toLocaleString()}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {grant.reason && (
                  <div style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                    <strong>הערות:</strong> {grant.reason}
                  </div>
                )}
              </div>

              <button
                onClick={() => grant.id && onDelete(grant.id)}
                style={{
                  backgroundColor: '#dc3545',
                  color: 'white',
                  border: 'none',
                  padding: '8px 12px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                מחק
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
