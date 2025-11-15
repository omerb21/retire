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
      <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
        אין היוונים
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {commutations.map((commutation) => {
        const relatedFund = funds.find(f => f.id === commutation.pension_fund_id);
        return (
          <div key={commutation.id} style={{ padding: 12, border: "1px solid #ddd", borderRadius: 4 }}>
            <div><strong>קצבה:</strong> {relatedFund?.fund_name || "לא נמצא"}</div>
            <div><strong>סכום היוון:</strong> {formatCurrency(commutation.exempt_amount || 0)}</div>
            <div><strong>תאריך:</strong> {commutation.commutation_date}</div>
            <div><strong>יחס מס:</strong> {commutation.commutation_type === "exempt" ? "פטור ממס" : "חייב במס"}</div>
            <button
              type="button"
              onClick={() => onDelete(commutation.id!)}
              style={{ padding: "4px 8px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: 4, marginTop: 8 }}
            >
              מחק
            </button>
          </div>
        );
      })}
    </div>
  );
};
