import React from 'react';
import { Commutation, PensionFund } from '../types';
import { formatCurrency } from '../../../lib/validation';

interface CommutationListProps {
  commutations: Commutation[];
  funds: PensionFund[];
  onDelete: (commutationId: number) => void;
}

export const CommutationList: React.FC<CommutationListProps> = ({
  commutations,
  funds,
  onDelete
}) => {
  if (commutations.length === 0) {
    return (
      <div className="pension-funds-empty-card">
        אין היוונים
      </div>
    );
  }

  return (
    <div className="pension-funds-commutation-list-grid">
      {commutations.map((commutation) => {
        const relatedFund = funds.find(f => f.id === commutation.pension_fund_id);
        return (
          <div key={commutation.id} className="pension-funds-commutation-card">
            <div><strong>קצבה:</strong> {relatedFund?.fund_name || "לא נמצא"}</div>
            <div><strong>סכום היוון:</strong> {formatCurrency(commutation.exempt_amount || 0)}</div>
            <div><strong>תאריך:</strong> {commutation.commutation_date}</div>
            <div><strong>יחס מס:</strong> {commutation.commutation_type === "exempt" ? "פטור ממס" : "חייב במס"}</div>
            <button
              type="button"
              onClick={() => onDelete(commutation.id!)}
              className="pension-funds-commutation-delete-button"
            >
              מחק
            </button>
          </div>
        );
      })}
    </div>
  );
};
