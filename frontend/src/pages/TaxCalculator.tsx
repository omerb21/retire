import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

interface PersonalDetails {
  birth_date?: string;
  marital_status: string;
  num_children: number;
  is_new_immigrant: boolean;
  is_veteran: boolean;
  is_disabled: boolean;
  disability_percentage?: number;
  is_student: boolean;
  reserve_duty_days: number;
}

interface TaxCalculationInput {
  tax_year: number;
  personal_details: PersonalDetails;
  salary_income: number;
  pension_income: number;
  rental_income: number;
  capital_gains: number;
  business_income: number;
  interest_income: number;
  dividend_income: number;
  other_income: number;
  pension_contributions: number;
  study_fund_contributions: number;
  insurance_premiums: number;
  charitable_donations: number;
}

interface TaxCalculationResult {
  total_income: number;
  taxable_income: number;
  exempt_income: number;
  income_tax: number;
  national_insurance: number;
  health_tax: number;
  total_tax: number;
  tax_credits_amount: number;
  net_tax: number;
  net_income: number;
  effective_tax_rate: number;
  marginal_tax_rate: number;
  applied_credits: Array<{
    code: string;
    amount: number;
    description: string;
  }>;
  tax_breakdown: Array<{
    bracket_min: number;
    bracket_max?: number;
    rate: number;
    taxable_amount: number;
    tax_amount: number;
  }>;
}

const TaxCalculator: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TaxCalculationResult | null>(null);
  
  const [formData, setFormData] = useState<TaxCalculationInput>({
    tax_year: new Date().getFullYear(),
    personal_details: {
      birth_date: '',
      marital_status: 'single',
      num_children: 0,
      is_new_immigrant: false,
      is_veteran: false,
      is_disabled: false,
      disability_percentage: undefined,
      is_student: false,
      reserve_duty_days: 0
    },
    salary_income: 0,
    pension_income: 0,
    rental_income: 0,
    capital_gains: 0,
    business_income: 0,
    interest_income: 0,
    dividend_income: 0,
    other_income: 0,
    pension_contributions: 0,
    study_fund_contributions: 0,
    insurance_premiums: 0,
    charitable_donations: 0
  });

  // טעינת נתוני לקוח קיימים
  useEffect(() => {
    if (id) {
      loadClientData();
    }
  }, [id]);

  const loadClientData = async () => {
    try {
      const response = await axios.get(`/api/v1/clients/${id}`);
      const client = response.data;
      
      setFormData(prev => ({
        ...prev,
        personal_details: {
          ...prev.personal_details,
          birth_date: client.birth_date || '',
          marital_status: client.marital_status || 'single',
          num_children: client.num_children || 0,
          is_new_immigrant: client.is_new_immigrant || false,
          is_veteran: client.is_veteran || false,
          is_disabled: client.is_disabled || false,
          disability_percentage: client.disability_percentage,
          is_student: client.is_student || false,
          reserve_duty_days: client.reserve_duty_days || 0
        },
        salary_income: client.annual_salary || 0,
        pension_contributions: client.pension_contributions || 0,
        study_fund_contributions: client.study_fund_contributions || 0,
        insurance_premiums: client.insurance_premiums || 0,
        charitable_donations: client.charitable_donations || 0
      }));
    } catch (err) {
      console.error('שגיאה בטעינת נתוני לקוח:', err);
    }
  };

  const handleInputChange = (field: string, value: any, isPersonal = false) => {
    if (isPersonal) {
      setFormData(prev => ({
        ...prev,
        personal_details: {
          ...prev.personal_details,
          [field]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const calculateTax = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.post('/api/v1/tax/calculate', formData);
      setResult(response.data);
      
    } catch (err: any) {
      setError('שגיאה בחישוב מס: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const saveClientTaxData = async () => {
    if (!id) return;
    
    try {
      await axios.put(`/api/v1/clients/${id}`, {
        num_children: formData.personal_details.num_children,
        is_new_immigrant: formData.personal_details.is_new_immigrant,
        is_veteran: formData.personal_details.is_veteran,
        is_disabled: formData.personal_details.is_disabled,
        disability_percentage: formData.personal_details.disability_percentage,
        is_student: formData.personal_details.is_student,
        reserve_duty_days: formData.personal_details.reserve_duty_days,
        annual_salary: formData.salary_income,
        pension_contributions: formData.pension_contributions,
        study_fund_contributions: formData.study_fund_contributions,
        insurance_premiums: formData.insurance_premiums,
        charitable_donations: formData.charitable_donations
      });
      
      alert('נתוני המס נשמרו בהצלחה');
    } catch (err) {
      alert('שגיאה בשמירת נתונים');
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>מחשבון מס הכנסה</h1>
      
      {error && (
        <div style={{ 
          backgroundColor: '#f8d7da', 
          color: '#721c24', 
          padding: '10px', 
          borderRadius: '4px', 
          marginBottom: '20px' 
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '30px' }}>
        {/* עמודה שמאלית - קלט */}
        <div>
          <h2>פרטים אישיים</h2>
          <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '4px' }}>
            
            <div style={{ marginBottom: '10px' }}>
              <label>תאריך לידה:</label>
              <input
                type="date"
                value={formData.personal_details.birth_date}
                onChange={(e) => handleInputChange('birth_date', e.target.value, true)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>מצב משפחתי:</label>
              <select
                value={formData.personal_details.marital_status}
                onChange={(e) => handleInputChange('marital_status', e.target.value, true)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              >
                <option value="single">רווק/ה</option>
                <option value="married">נשוי/ה</option>
                <option value="divorced">גרוש/ה</option>
                <option value="widowed">אלמן/ה</option>
              </select>
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>מספר ילדים:</label>
              <input
                type="number"
                min="0"
                value={formData.personal_details.num_children}
                onChange={(e) => handleInputChange('num_children', parseInt(e.target.value) || 0, true)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>
                <input
                  type="checkbox"
                  checked={formData.personal_details.is_new_immigrant}
                  onChange={(e) => handleInputChange('is_new_immigrant', e.target.checked, true)}
                />
                עולה חדש
              </label>
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>
                <input
                  type="checkbox"
                  checked={formData.personal_details.is_veteran}
                  onChange={(e) => handleInputChange('is_veteran', e.target.checked, true)}
                />
                חייל משוחרר
              </label>
            </div>

            <div style={{ marginBottom: '10px' }}>
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
              <div style={{ marginBottom: '10px' }}>
                <label>אחוז נכות:</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={formData.personal_details.disability_percentage || ''}
                  onChange={(e) => handleInputChange('disability_percentage', parseInt(e.target.value) || undefined, true)}
                  style={{ width: '100%', padding: '8px', marginTop: '5px' }}
                />
              </div>
            )}

            <div style={{ marginBottom: '10px' }}>
              <label>
                <input
                  type="checkbox"
                  checked={formData.personal_details.is_student}
                  onChange={(e) => handleInputChange('is_student', e.target.checked, true)}
                />
                סטודנט
              </label>
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>ימי מילואים בשנה:</label>
              <input
                type="number"
                min="0"
                value={formData.personal_details.reserve_duty_days}
                onChange={(e) => handleInputChange('reserve_duty_days', parseInt(e.target.value) || 0, true)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>
          </div>

          <h2>הכנסות</h2>
          <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '4px' }}>
            
            <div style={{ marginBottom: '10px' }}>
              <label>שכר עבודה (שנתי):</label>
              <input
                type="number"
                min="0"
                value={formData.salary_income}
                onChange={(e) => handleInputChange('salary_income', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>פנסיה (שנתי):</label>
              <input
                type="number"
                min="0"
                value={formData.pension_income}
                onChange={(e) => handleInputChange('pension_income', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>הכנסה משכירות (שנתי):</label>
              <input
                type="number"
                min="0"
                value={formData.rental_income}
                onChange={(e) => handleInputChange('rental_income', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>רווח הון (שנתי):</label>
              <input
                type="number"
                min="0"
                value={formData.capital_gains}
                onChange={(e) => handleInputChange('capital_gains', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>הכנסה עצמאית (שנתי):</label>
              <input
                type="number"
                min="0"
                value={formData.business_income}
                onChange={(e) => handleInputChange('business_income', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>
          </div>

          <h2>ניכויים</h2>
          <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '4px' }}>
            
            <div style={{ marginBottom: '10px' }}>
              <label>הפרשות לפנסיה:</label>
              <input
                type="number"
                min="0"
                value={formData.pension_contributions}
                onChange={(e) => handleInputChange('pension_contributions', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>קרן השתלמות:</label>
              <input
                type="number"
                min="0"
                value={formData.study_fund_contributions}
                onChange={(e) => handleInputChange('study_fund_contributions', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>דמי ביטוח:</label>
              <input
                type="number"
                min="0"
                value={formData.insurance_premiums}
                onChange={(e) => handleInputChange('insurance_premiums', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label>תרומות:</label>
              <input
                type="number"
                min="0"
                value={formData.charitable_donations}
                onChange={(e) => handleInputChange('charitable_donations', parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={calculateTax}
              disabled={loading}
              style={{
                backgroundColor: loading ? '#6c757d' : '#007bff',
                color: 'white',
                border: 'none',
                padding: '12px 24px',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '16px'
              }}
            >
              {loading ? 'מחשב...' : 'חישוב מס'}
            </button>

            {id && (
              <button
                onClick={saveClientTaxData}
                style={{
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  padding: '12px 24px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '16px'
                }}
              >
                שמירת נתונים
              </button>
            )}
          </div>
        </div>

        {/* עמודה ימנית - תוצאות */}
        <div>
          {result && (
            <>
              <h2>תוצאות חישוב המס</h2>
              
              {/* סיכום כללי */}
              <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
                <h3>סיכום כללי</h3>
                <div><strong>סך הכנסה:</strong> ₪{result.total_income.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div><strong>הכנסה חייבת:</strong> ₪{result.taxable_income.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div><strong>הכנסה פטורה:</strong> ₪{result.exempt_income.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div style={{ color: '#dc3545' }}><strong>מס נטו לתשלום:</strong> ₪{result.net_tax.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div style={{ color: '#28a745' }}><strong>הכנסה נטו:</strong> ₪{result.net_income.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div><strong>שיעור מס אפקטיבי:</strong> {result.effective_tax_rate.toFixed(2)}%</div>
              </div>

              {/* פירוט מסים */}
              <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '4px' }}>
                <h3>פירוט מסים</h3>
                <div><strong>מס הכנסה:</strong> ₪{result.income_tax.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div><strong>ביטוח לאומי:</strong> ₪{result.national_insurance.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div><strong>מס בריאות:</strong> ₪{result.health_tax.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div><strong>סך מסים:</strong> ₪{result.total_tax.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                <div style={{ color: '#28a745' }}><strong>זיכויים:</strong> ₪{result.tax_credits_amount.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              </div>

              {/* נקודות זיכוי */}
              {result.applied_credits.length > 0 && (
                <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #17a2b8', borderRadius: '4px', backgroundColor: '#f0f9ff' }}>
                  <h3>נקודות זיכוי</h3>
                  {result.applied_credits.map((credit, index) => (
                    <div key={index}>
                      <strong>{credit.description}:</strong> ₪{credit.amount.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                  ))}
                </div>
              )}

              {/* מדרגות מס */}
              {result.tax_breakdown.length > 0 && (
                <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <h3>מדרגות מס</h3>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f8f9fa' }}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>מדרגה</th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>שיעור</th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>סכום חייב</th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>מס</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.tax_breakdown.map((bracket, index) => (
                        <tr key={index}>
                          <td style={{ padding: '8px', border: '1px solid #ddd' }}>
                            ₪{bracket.bracket_min.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} - {bracket.bracket_max ? `₪${bracket.bracket_max.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'ומעלה'}
                          </td>
                          <td style={{ padding: '8px', border: '1px solid #ddd' }}>
                            {(bracket.rate * 100).toFixed(1)}%
                          </td>
                          <td style={{ padding: '8px', border: '1px solid #ddd' }}>
                            ₪{bracket.taxable_amount.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: '8px', border: '1px solid #ddd' }}>
                            ₪{bracket.tax_amount.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TaxCalculator;
