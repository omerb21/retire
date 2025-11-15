import React from 'react';
import { Commutation, PensionFund } from '../types';
import { calculateOriginalBalance } from '../utils';
import { formatCurrency } from '../../../lib/validation';

interface CommutationFormProps {
  commutationForm: Commutation;
  setCommutationForm: (form: Commutation) => void;
  onSubmit: (e: React.FormEvent) => void;
  funds: PensionFund[];
}

export const CommutationForm: React.FC<CommutationFormProps> = ({
  commutationForm,
  setCommutationForm,
  onSubmit,
  funds
}) => {
  return (
    <section style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
      <h3>הוסף היוון</h3>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
        <div>
          <label>קצבה:</label>
          <select
            value={commutationForm.pension_fund_id || ""}
            onChange={(e) => setCommutationForm({ ...commutationForm, pension_fund_id: parseInt(e.target.value) })}
            style={{ padding: 8, width: "100%" }}
            required
          >
            <option value="">בחר קצבה</option>
            {funds.map((fund) => (
              <option key={fund.id} value={fund.id}>
                {fund.fund_name} - יתרה מקורית: {formatCurrency(calculateOriginalBalance(fund))}
              </option>
            ))}
          </select>
        </div>
        
        <input
          type="number"
          placeholder="סכום היוון"
          value={commutationForm.exempt_amount || ""}
          onChange={(e) => setCommutationForm({ ...commutationForm, exempt_amount: parseFloat(e.target.value) || 0 })}
          style={{ padding: 8 }}
          required
        />
        
        <input
          type="date"
          placeholder="תאריך היוון"
          value={commutationForm.commutation_date || ""}
          onChange={(e) => setCommutationForm({ ...commutationForm, commutation_date: e.target.value })}
          style={{ padding: 8 }}
          required
        />
        
        <div>
          <label>יחס מס:</label>
          {(() => {
            const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
            const isExemptPension = selectedFund?.tax_treatment === "exempt";
            
            return (
              <>
                <select
                  value={commutationForm.commutation_type}
                  onChange={(e) => setCommutationForm({ ...commutationForm, commutation_type: e.target.value as "exempt" | "taxable" })}
                  style={{ 
                    padding: 8, 
                    width: "100%",
                    backgroundColor: isExemptPension ? "#f0f0f0" : "white",
                    cursor: isExemptPension ? "not-allowed" : "pointer"
                  }}
                  disabled={isExemptPension}
                >
                  <option value="taxable">חייב במס</option>
                  <option value="exempt">פטור ממס</option>
                </select>
                {isExemptPension && (
                  <div style={{ fontSize: "12px", color: "#856404", marginTop: "4px", fontStyle: "italic" }}>
                    קצבה פטורה ממס - ההיוון חייב להיות פטור ממס
                  </div>
                )}
              </>
            );
          })()}
        </div>
        
        <button type="submit" style={{ padding: "8px 12px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: 4 }}>
          הוסף היוון
        </button>
      </form>
    </section>
  );
};
