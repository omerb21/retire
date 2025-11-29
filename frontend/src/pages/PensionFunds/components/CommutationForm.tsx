import React from 'react';
import { Commutation, PensionFund } from '../types';
import { calculateOriginalBalance } from '../utils';
import { formatCurrency } from '../../../lib/validation';
import DateField from '../../../components/forms/DateField';

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
    <section className="pension-funds-section-card">
      <h3>הוסף היוון</h3>
      <form onSubmit={onSubmit} className="pension-funds-commutation-form-grid">
        <div>
          <label>קצבה:</label>
          <select
            value={commutationForm.pension_fund_id || ""}
            onChange={(e) => setCommutationForm({ ...commutationForm, pension_fund_id: parseInt(e.target.value) })}
            className="pension-funds-select"
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
          onChange={(e) =>
            setCommutationForm({
              ...commutationForm,
              exempt_amount: parseFloat(e.target.value) || 0,
            })
          }
          className="pension-funds-input"
          required
        />

        <DateField
          label="תאריך היוון"
          value={commutationForm.commutation_date || null}
          onChange={(newValue) =>
            setCommutationForm({
              ...commutationForm,
              commutation_date: newValue || '',
            })
          }
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
                  className={`pension-funds-select ${isExemptPension ? 'pension-funds-select--disabled' : ''}`}
                  disabled={isExemptPension}
                >
                  <option value="taxable">חייב במס</option>
                  <option value="exempt">פטור ממס</option>
                </select>
                {isExemptPension && (
                  <div className="pension-funds-commutation-warning">
                    קצבה פטורה ממס - ההיוון חייב להיות פטור ממס
                  </div>
                )}
              </>
            );
          })()}
        </div>
        
        <button type="submit" className="pension-funds-commutation-submit">
          הוסף היוון
        </button>
      </form>
    </section>
  );
};
