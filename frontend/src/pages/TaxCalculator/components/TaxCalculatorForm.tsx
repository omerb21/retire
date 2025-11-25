import React from 'react';
import { TaxCalculationInput } from '../hooks/useTaxCalculator';

interface TaxCalculatorFormProps {
  clientId?: string;
  formData: TaxCalculationInput;
  loading: boolean;
  handleInputChange: (field: string, value: any, isPersonal?: boolean) => void;
  calculateTax: () => void | Promise<void>;
  saveClientTaxData: () => void | Promise<void>;
}

export const TaxCalculatorForm: React.FC<TaxCalculatorFormProps> = ({
  clientId,
  formData,
  loading,
  handleInputChange,
  calculateTax,
  saveClientTaxData,
}) => {
  return (
    <div>
      <h2>פרטים אישיים</h2>
      <div className="tax-calculator-panel">
        <div className="tax-calculator-field">
          <label>תאריך לידה:</label>
          <input
            type="date"
            value={formData.personal_details.birth_date}
            onChange={(e) => handleInputChange('birth_date', e.target.value, true)}
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>מצב משפחתי:</label>
          <select
            value={formData.personal_details.marital_status}
            onChange={(e) => handleInputChange('marital_status', e.target.value, true)}
            className="tax-calculator-select"
          >
            <option value="single">רווק/ה</option>
            <option value="married">נשוי/ה</option>
            <option value="divorced">גרוש/ה</option>
            <option value="widowed">אלמן/ה</option>
          </select>
        </div>

        <div className="tax-calculator-field">
          <label>מספר ילדים:</label>
          <input
            type="number"
            min="0"
            value={formData.personal_details.num_children}
            onChange={(e) =>
              handleInputChange('num_children', parseInt(e.target.value) || 0, true)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>
            <input
              type="checkbox"
              checked={formData.personal_details.is_new_immigrant}
              onChange={(e) => handleInputChange('is_new_immigrant', e.target.checked, true)}
            />
            עולה חדש
          </label>
        </div>

        <div className="tax-calculator-field">
          <label>
            <input
              type="checkbox"
              checked={formData.personal_details.is_veteran}
              onChange={(e) => handleInputChange('is_veteran', e.target.checked, true)}
            />
            חייל משוחרר
          </label>
        </div>

        <div className="tax-calculator-field">
          <label>
            <input
              type="checkbox"
              checked={formData.personal_details.is_disabled}
              onChange={(e) => handleInputChange('is_disabled', e.target.checked, true)}
            />
            נכה
          </label>
        </div>

        {formData.personal_details.is_disabled && (
          <div className="tax-calculator-field">
            <label>אחוז נכות:</label>
            <input
              type="number"
              min="0"
              max="100"
              value={formData.personal_details.disability_percentage || ''}
              onChange={(e) =>
                handleInputChange(
                  'disability_percentage',
                  parseInt(e.target.value) || undefined,
                  true
                )
              }
              className="tax-calculator-input"
            />
          </div>
        )}

        <div className="tax-calculator-field">
          <label>
            <input
              type="checkbox"
              checked={formData.personal_details.is_student}
              onChange={(e) => handleInputChange('is_student', e.target.checked, true)}
            />
            סטודנט
          </label>
        </div>

        <div className="tax-calculator-field">
          <label>ימי מילואים בשנה:</label>
          <input
            type="number"
            min="0"
            value={formData.personal_details.reserve_duty_days}
            onChange={(e) =>
              handleInputChange('reserve_duty_days', parseInt(e.target.value) || 0, true)
            }
            className="tax-calculator-input"
          />
        </div>
      </div>

      <h2>הכנסות</h2>
      <div className="tax-calculator-panel">
        <div className="tax-calculator-field">
          <label>שכר עבודה (שנתי):</label>
          <input
            type="number"
            min="0"
            value={formData.salary_income}
            onChange={(e) =>
              handleInputChange('salary_income', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>פנסיה (שנתי):</label>
          <input
            type="number"
            min="0"
            value={formData.pension_income}
            onChange={(e) =>
              handleInputChange('pension_income', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>הכנסה משכירות (שנתי):</label>
          <input
            type="number"
            min="0"
            value={formData.rental_income}
            onChange={(e) =>
              handleInputChange('rental_income', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>רווח הון (שנתי):</label>
          <input
            type="number"
            min="0"
            value={formData.capital_gains}
            onChange={(e) =>
              handleInputChange('capital_gains', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>הכנסה עצמאית (שנתי):</label>
          <input
            type="number"
            min="0"
            value={formData.business_income}
            onChange={(e) =>
              handleInputChange('business_income', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>
      </div>

      <h2>ניכויים</h2>
      <div className="tax-calculator-panel">
        <div className="tax-calculator-field">
          <label>הפרשות לפנסיה:</label>
          <input
            type="number"
            min="0"
            value={formData.pension_contributions}
            onChange={(e) =>
              handleInputChange('pension_contributions', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>קרן השתלמות:</label>
          <input
            type="number"
            min="0"
            value={formData.study_fund_contributions}
            onChange={(e) =>
              handleInputChange(
                'study_fund_contributions',
                parseFloat(e.target.value) || 0
              )
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>דמי ביטוח:</label>
          <input
            type="number"
            min="0"
            value={formData.insurance_premiums}
            onChange={(e) =>
              handleInputChange('insurance_premiums', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>

        <div className="tax-calculator-field">
          <label>תרומות:</label>
          <input
            type="number"
            min="0"
            value={formData.charitable_donations}
            onChange={(e) =>
              handleInputChange('charitable_donations', parseFloat(e.target.value) || 0)
            }
            className="tax-calculator-input"
          />
        </div>
      </div>

      <div className="tax-calculator-actions">
        <button
          onClick={calculateTax}
          disabled={loading}
          className="tax-calculator-button tax-calculator-button--primary"
        >
          {loading ? 'מחשב...' : 'חישוב מס'}
        </button>

        {clientId && (
          <button
            onClick={saveClientTaxData}
            className="tax-calculator-button tax-calculator-button--save"
          >
            שמירת נתונים
          </button>
        )}
      </div>
    </div>
  );
};
