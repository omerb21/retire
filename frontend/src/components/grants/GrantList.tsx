/**
 * GrantList Component - Display list of grants
 * רכיב רשימת מענקים
 */

import React from 'react';
import { Grant, GrantDetails } from '../../types/grant.types';
import { formatDateToDDMMYY } from '../../utils/dateUtils';
import { getGrantAmount } from '../../utils/grantCalculations';
import { formatCurrency } from '../../lib/validation';
import './GrantList.css';

interface GrantListProps {
  grants: Grant[];
  grantDetails: { [key: number]: GrantDetails };
  onDelete: (grantId: number) => Promise<boolean>;
}

export const GrantList: React.FC<GrantListProps> = ({ grants, grantDetails, onDelete }) => {
  if (grants.length === 0) {
    return (
      <div className="grant-list-empty">
        אין מענקים רשומים
      </div>
    );
  }

  return (
    <div className="grant-list-grid">
      {grants.map((grant, index) => {
        const details = grant.id ? grantDetails[grant.id] : null;
        const amount = getGrantAmount(grant);
        
        return (
          <div 
            key={grant.id || index}
            className="grant-list-item"
          >
            <div className="grant-list-item-inner">
              <div>
                <div className="grant-list-item-meta-grid">
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
                
                <div className="grant-list-amount-section">
                  <div>
                    <strong>סכום מענק:</strong> {formatCurrency(amount)}
                  </div>
                </div>

                {details && (
                  <div className="grant-list-details">
                    <div className="grant-list-details-grid">
                      <div>
                        <strong>תקופת עבודה:</strong> {details.serviceYears} שנים
                      </div>
                      {details.taxDue > 0 && (
                        <div className="grant-list-tax-warning">
                          <strong>מס משוער:</strong> {formatCurrency(details.taxDue)}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {grant.reason && (
                  <div className="grant-list-notes">
                    <strong>הערות:</strong> {grant.reason}
                  </div>
                )}
              </div>

              <button
                onClick={() => grant.id && onDelete(grant.id)}
                className="grant-list-delete-button"
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
