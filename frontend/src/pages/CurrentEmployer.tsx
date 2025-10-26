import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface CurrentEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  end_date?: string;
  monthly_salary: number;
  severance_balance: number;
  service_years?: number;
  expected_grant_amount?: number;
  employer_completion?: number; // השלמת המעסיק
  tax_exempt_amount?: number;
  taxable_amount?: number;
  reserved_exemption?: number;
}

interface TerminationDecision {
  termination_date: string;
  use_employer_completion: boolean;
  severance_amount: number;
  exempt_amount: number;
  taxable_amount: number;
  exempt_choice: 'redeem_with_exemption' | 'redeem_no_exemption' | 'annuity';
  taxable_choice: 'redeem_no_exemption' | 'annuity' | 'tax_spread';
  tax_spread_years?: number;
  max_spread_years?: number;
}

interface EmployerGrant {
  id?: number;
  current_employer_id?: number;
  grant_type: string;
  grant_date: string;
  amount: number;
  reason: string;
  calculation?: {
    grant_exempt: number;
    grant_taxable: number;
    tax_due: number;
  };
}

const CurrentEmployer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'details' | 'termination'>('details');
  const [employer, setEmployer] = useState<CurrentEmployer>({
    employer_name: '',
    start_date: '',
    monthly_salary: 0,
    severance_balance: 0,
    expected_grant_amount: 0,
    employer_completion: 0,
    tax_exempt_amount: 0,
    taxable_amount: 0,
    reserved_exemption: 0
  });
  const [terminationDecision, setTerminationDecision] = useState<TerminationDecision>({
    termination_date: '',
    use_employer_completion: false,
    severance_amount: 0,
    exempt_amount: 0,
    taxable_amount: 0,
    exempt_choice: 'redeem_with_exemption',
    taxable_choice: 'redeem_no_exemption',
    tax_spread_years: 0,
    max_spread_years: 0
  });
  const [grants, setGrants] = useState<EmployerGrant[]>([]);

  // Calculate service years and grant amounts using server API
  const calculateGrantDetails = async () => {
    if (!employer.start_date || !employer.monthly_salary) return;

    try {
      const expectedGrant = employer.monthly_salary * ((new Date().getTime() - new Date(employer.start_date).getTime()) / (1000 * 60 * 60 * 24 * 365.25));
      
      const response = await axios.post(`/api/v1/clients/${id}/current-employer/calculate`, {
        start_date: employer.start_date,
        monthly_salary: employer.monthly_salary,
        severance_amount: Math.round(expectedGrant)
      });

      const calculation = response.data;
      
      // תיקון לוגיקה: כאשר יתרת הפיצויים גבוהה מהמענק הצפוי, המענק הצפוי מקבל את הערך של יתרת הפיצויים
      const actualExpectedGrant = Math.max(calculation.severance_amount, employer.severance_balance);
      
      // חישוב השלמת המעסיק = סכום המענק הצפוי פחות יתרת פיצויים נצברת
      const employerCompletion = Math.max(0, actualExpectedGrant - employer.severance_balance);
      
      console.log('חישוב השלמת מעסיק:', {
        'סכום מענק צפוי מחושב': calculation.severance_amount,
        'יתרת פיצויים נצברת': employer.severance_balance,
        'מענק צפוי בפועל': actualExpectedGrant,
        'השלמת מעסיק מחושבת': employerCompletion
      });
      
      setEmployer(prev => ({
        ...prev,
        service_years: calculation.service_years,
        expected_grant_amount: actualExpectedGrant,
        employer_completion: employerCompletion,
        tax_exempt_amount: calculation.final_exemption,
        taxable_amount: calculation.taxable_amount
      }));
    } catch (error) {
      console.error('שגיאה בחישוב פטור ממס:', error);
      // Fallback to basic calculation
      const startDate = new Date(employer.start_date);
      const currentDate = new Date();
      const serviceYears = (currentDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
      const expectedGrant = employer.monthly_salary * serviceYears;
      
      // תיקון לוגיקה: כאשר יתרת הפיצויים גבוהה מהמענק הצפוי, המענק הצפוי מקבל את הערך של יתרת הפיצויים
      const actualExpectedGrant = Math.max(Math.round(expectedGrant), employer.severance_balance);
      
      const maxExemption = Math.min(375000, employer.monthly_salary * 9);
      const taxExemptAmount = Math.min(actualExpectedGrant, maxExemption - (employer.reserved_exemption || 0));
      const taxableAmount = actualExpectedGrant - taxExemptAmount;
      
      // חישוב השלמת המעסיק = סכום המענק הצפוי פחות יתרת פיצויים נצברת
      const employerCompletion = Math.max(0, actualExpectedGrant - employer.severance_balance);

      setEmployer(prev => ({
        ...prev,
        service_years: Math.round(serviceYears * 100) / 100,
        expected_grant_amount: actualExpectedGrant,
        employer_completion: employerCompletion,
        tax_exempt_amount: Math.max(0, Math.round(taxExemptAmount)),
        taxable_amount: Math.max(0, Math.round(taxableAmount))
      }));
    }
  };

  // Load existing employer data
  useEffect(() => {
    const fetchEmployer = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/v1/clients/${id}/current-employer`);
        if (response.data && response.data.length > 0) {
          const employerData = response.data[0];
          
          // תיקון לוגיקה: אם יתרת הפיצויים גבוהה מהמענק הצפוי, תקן את המענק הצפוי
          const severanceBalance = Number(employerData.severance_balance) || 0;
          const expectedGrant = Number(employerData.expected_grant_amount) || 0;
          
          console.log('🔍 Checking severance vs expected grant:', {
            severance_balance: severanceBalance,
            expected_grant_amount: expectedGrant,
            severance_balance_type: typeof employerData.severance_balance,
            expected_grant_type: typeof employerData.expected_grant_amount,
            should_fix: severanceBalance > expectedGrant
          });
          
          if (severanceBalance > expectedGrant) {
            console.log('🔧 Fixing expected_grant_amount:', {
              old: expectedGrant,
              new: severanceBalance
            });
            employerData.expected_grant_amount = severanceBalance;
            employerData.employer_completion = 0; // אין השלמה כי היתרה כבר מכסה הכל
          }
          
          setEmployer(employerData);
        }
        setLoading(false);
      } catch (err: any) {
        if (err.response?.status !== 404) {
          setError('שגיאה בטעינת נתוני מעסיק: ' + err.message);
        }
        setLoading(false);
      }
    };

    if (id) {
      fetchEmployer();
    }
  }, [id]);

  // Recalculate when relevant fields change with debouncing
  useEffect(() => {
    if (employer.start_date && employer.monthly_salary > 0) {
      const timeoutId = setTimeout(() => {
        calculateGrantDetails();
      }, 500); // Debounce for 500ms
      
      return () => clearTimeout(timeoutId);
    }
  }, [employer.start_date, employer.monthly_salary, employer.reserved_exemption, employer.severance_balance]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      setError(null);

      if (employer.id) {
        // Update existing employer
        await axios.put(`/api/v1/clients/${id}/current-employer/${employer.id}`, employer);
      } else {
        // Create new employer
        await axios.post(`/api/v1/clients/${id}/current-employer`, employer);
      }

      alert('נתוני מעסיק נשמרו בהצלחה');
      navigate(`/clients/${id}`);
    } catch (err: any) {
      setError('שגיאה בשמירת נתוני מעסיק: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setEmployer(prev => ({
      ...prev,
      [name]: name.includes('salary') || name.includes('balance') || name.includes('amount') || name.includes('exemption') 
        ? parseFloat(value) || 0 : value
    }));
  };

  // Calculate termination details when termination date is set
  useEffect(() => {
    if (terminationDecision.termination_date && employer.start_date && employer.monthly_salary) {
      const startDate = new Date(employer.start_date);
      const endDate = new Date(terminationDecision.termination_date);
      const serviceYears = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
      const expectedGrant = employer.monthly_salary * serviceYears;
      
      // חישוב שנות פריסה לפי הכללים:
      // עד 2 שנים: 0 שנות פריסה
      // 2+ שנים: 1 שנת פריסה
      // 6+ שנים: 2 שנות פריסה
      // 10+ שנים: 3 שנות פריסה
      // 14+ שנים: 4 שנות פריסה
      // 18+ שנים: 5 שנות פריסה
      // 22+ שנים: 6 שנות פריסה (מקסימום)
      let maxSpreadYears = 0;
      if (serviceYears >= 22) {
        maxSpreadYears = 6;
      } else if (serviceYears >= 18) {
        maxSpreadYears = 5;
      } else if (serviceYears >= 14) {
        maxSpreadYears = 4;
      } else if (serviceYears >= 10) {
        maxSpreadYears = 3;
      } else if (serviceYears >= 6) {
        maxSpreadYears = 2;
      } else if (serviceYears >= 2) {
        maxSpreadYears = 1;
      }
      
      // Calculate severance amount based on employer completion choice
      const severanceAmount = terminationDecision.use_employer_completion 
        ? expectedGrant 
        : employer.severance_balance;
      
      // Calculate exempt cap (simplified - actual calculation needs tax year data)
      const exemptCap = Math.min(375000, employer.monthly_salary * 9 * serviceYears);
      const exemptAmount = Math.min(severanceAmount, exemptCap);
      const taxableAmount = Math.max(0, severanceAmount - exemptAmount);
      
      setTerminationDecision(prev => ({
        ...prev,
        severance_amount: severanceAmount,
        exempt_amount: exemptAmount,
        taxable_amount: taxableAmount,
        max_spread_years: maxSpreadYears
      }));
    }
  }, [terminationDecision.termination_date, terminationDecision.use_employer_completion, employer.start_date, employer.monthly_salary, employer.severance_balance]);

  const handleTerminationSubmit = async () => {
    try {
      setLoading(true);
      setError(null);

      // Save termination decision
      await axios.post(`/api/v1/clients/${id}/current-employer/termination`, terminationDecision);

      alert('החלטות עזיבה נשמרו בהצלחה');
      navigate(`/clients/${id}`);
    } catch (err: any) {
      setError('שגיאה בשמירת החלטות עזיבה: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>מעסיק נוכחי</h2>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`}>חזרה לפרטי לקוח</a>
      </div>

      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

      {/* Tabs */}
      <div style={{ marginBottom: '20px', borderBottom: '2px solid #ddd' }}>
        <button
          onClick={() => setActiveTab('details')}
          style={{
            padding: '10px 20px',
            marginLeft: '5px',
            border: 'none',
            borderBottom: activeTab === 'details' ? '3px solid #007bff' : 'none',
            backgroundColor: activeTab === 'details' ? '#f8f9fa' : 'transparent',
            cursor: 'pointer',
            fontWeight: activeTab === 'details' ? 'bold' : 'normal'
          }}
        >
          פרטי מעסיק
        </button>
        <button
          onClick={() => setActiveTab('termination')}
          style={{
            padding: '10px 20px',
            border: 'none',
            borderBottom: activeTab === 'termination' ? '3px solid #007bff' : 'none',
            backgroundColor: activeTab === 'termination' ? '#f8f9fa' : 'transparent',
            cursor: 'pointer',
            fontWeight: activeTab === 'termination' ? 'bold' : 'normal'
          }}
        >
          עזיבת עבודה
        </button>
      </div>

      {/* Employer Details Tab */}
      {activeTab === 'details' && (
      <form onSubmit={handleSubmit}>
        {/* Basic employer info */}
        <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '4px' }}>
          <h3>פרטי מעסיק</h3>
          
          <div style={{ marginBottom: '15px' }}>
            <label>שם מעסיק:</label>
            <input
              type="text"
              name="employer_name"
              value={employer.employer_name}
              onChange={handleInputChange}
              required
              style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            />
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>תאריך התחלת עבודה:</label>
            <input
              type="date"
              name="start_date"
              value={employer.start_date}
              onChange={handleInputChange}
              required
              style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            />
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>שכר חודשי (₪):</label>
            <input
              type="number"
              name="monthly_salary"
              value={employer.monthly_salary}
              onChange={handleInputChange}
              required
              style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            />
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>יתרת פיצויים נצברת (₪):</label>
            <div style={{ 
              padding: '12px', 
              marginTop: '5px',
              backgroundColor: '#f8f9fa',
              border: '2px solid #e9ecef',
              borderRadius: '4px',
              fontSize: '16px',
              fontWeight: 'bold',
              color: '#495057'
            }}>
              ₪{employer.severance_balance?.toLocaleString()}
            </div>
            <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
              שדה מחושב: סה"כ יתרות פיצויים מתיק פנסיוני של מעסיק נוכחי
            </small>
          </div>
        </div>

        {/* Grant calculation results */}
        {employer.service_years && (
          <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
            <h3>חישוב מענק פיצויים</h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <strong>שנות שירות:</strong> {employer.service_years} שנים
              </div>
              <div>
                <strong>סכום מענק צפוי:</strong> ₪{employer.expected_grant_amount?.toLocaleString()}
              </div>
              <div>
                <strong>יתרת פיצויים נצברת:</strong> ₪{employer.severance_balance?.toLocaleString()}
              </div>
              <div style={{ color: '#0066cc', fontWeight: 'bold' }}>
                <strong>השלמת המעסיק:</strong> ₪{employer.employer_completion?.toLocaleString()}
              </div>
              <div style={{ color: '#28a745' }}>
                <strong>סכום פטור ממס:</strong> ₪{employer.tax_exempt_amount?.toLocaleString()}
              </div>
              <div style={{ color: '#dc3545' }}>
                <strong>סכום חייב במס:</strong> ₪{employer.taxable_amount?.toLocaleString()}
              </div>
            </div>
          </div>
        )}

        {/* Tax exemption management */}
        <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ffc107', borderRadius: '4px', backgroundColor: '#fffdf5' }}>
          <h3>ניהול פטור ממס</h3>
          
          <div style={{ marginBottom: '15px' }}>
            <label>פטור שמור לעתיד (₪):</label>
            <input
              type="number"
              name="reserved_exemption"
              value={employer.reserved_exemption || 0}
              onChange={handleInputChange}
              style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            />
            <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
              סכום פטור ממס שברצונך לשמור למענקים עתידיים
            </small>
          </div>

          <div style={{ fontSize: '14px', color: '#666' }}>
            <p><strong>הסבר:</strong> הפטור המקסימלי ממס על פיצויים הוא עד 375,000 ₪ או 9 חודשי שכר (הנמוך מביניהם).</p>
            <p>ניתן לשמור חלק מהפטור למענקים עתידיים או לפיצויים ממעסיקים אחרים.</p>
          </div>
        </div>

        <div style={{ marginTop: '20px' }}>
          <button
            type="submit"
            disabled={loading}
            style={{
              backgroundColor: loading ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '4px',
              marginLeft: '10px',
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? 'שומר...' : 'שמור'}
          </button>
          
          <button
            type="button"
            onClick={() => navigate(`/clients/${id}`)}
            style={{
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            ביטול
          </button>
        </div>
      </form>
      )}

      {/* Termination Tab */}
      {activeTab === 'termination' && (
        <div>
          <h3>מסך עזיבת עבודה</h3>
          
          {/* Step 1: Termination Date */}
          <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '4px' }}>
            <h4>שלב 1: קביעת תאריך סיום עבודה</h4>
            <div style={{ marginBottom: '15px' }}>
              <label>תאריך סיום עבודה:</label>
              <input
                type="date"
                value={terminationDecision.termination_date}
                onChange={(e) => setTerminationDecision(prev => ({ ...prev, termination_date: e.target.value }))}
                style={{ width: '100%', padding: '8px', marginTop: '5px' }}
              />
            </div>
          </div>

          {/* Step 2: Rights Summary (shown after termination date is set) */}
          {terminationDecision.termination_date && (
            <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
              <h4>שלב 2: סיכום זכויות</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                <div>
                  <strong>שנות וותק:</strong> {(
                    (new Date(terminationDecision.termination_date).getTime() - new Date(employer.start_date).getTime()) / 
                    (1000 * 60 * 60 * 24 * 365.25)
                  ).toFixed(2)} שנים
                </div>
                <div>
                  <strong>פיצויים צבורים:</strong> ₪{employer.severance_balance?.toLocaleString()}
                </div>
                <div>
                  <strong>פיצויים צפויים:</strong> ₪{
                    Math.round(
                      employer.monthly_salary * 
                      ((new Date(terminationDecision.termination_date).getTime() - new Date(employer.start_date).getTime()) / 
                      (1000 * 60 * 60 * 24 * 365.25))
                    ).toLocaleString()
                  }
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Employer Completion */}
          {terminationDecision.termination_date && (
            <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ffc107', borderRadius: '4px', backgroundColor: '#fffdf5' }}>
              <h4>שלב 3: השלמת מעסיק</h4>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={terminationDecision.use_employer_completion}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      use_employer_completion: e.target.checked 
                    }))}
                    style={{ marginLeft: '10px', width: '20px', height: '20px' }}
                  />
                  תבוצע השלמת מעסיק
                </label>
              </div>
              
              {terminationDecision.use_employer_completion && (
                <div style={{ padding: '10px', backgroundColor: '#e8f4f8', borderRadius: '4px', marginTop: '10px' }}>
                  <p><strong>גובה השלמת המעסיק:</strong> ₪{
                    Math.max(0, 
                      Math.round(employer.monthly_salary * 
                        ((new Date(terminationDecision.termination_date).getTime() - new Date(employer.start_date).getTime()) / 
                        (1000 * 60 * 60 * 24 * 365.25))
                      ) - employer.severance_balance
                    ).toLocaleString()
                  }</p>
                  <small>ההפרש בין המענק הצפוי ליתרת הפיצויים הנצברת</small>
                </div>
              )}
            </div>
          )}

          {/* Step 4: Tax Breakdown */}
          {terminationDecision.termination_date && (
            <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #17a2b8', borderRadius: '4px', backgroundColor: '#f0f9fc' }}>
              <h4>שלב 4: חלוקה לפטור/חייב במס</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                <div style={{ padding: '15px', backgroundColor: '#d4edda', borderRadius: '4px' }}>
                  <strong style={{ color: '#155724' }}>חלק פטור ממס:</strong>
                  <p style={{ fontSize: '20px', fontWeight: 'bold', margin: '10px 0' }}>
                    ₪{terminationDecision.exempt_amount?.toLocaleString()}
                  </p>
                </div>
                <div style={{ padding: '15px', backgroundColor: '#f8d7da', borderRadius: '4px' }}>
                  <strong style={{ color: '#721c24' }}>חלק חייב במס:</strong>
                  <p style={{ fontSize: '20px', fontWeight: 'bold', margin: '10px 0' }}>
                    ₪{terminationDecision.taxable_amount?.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 5: Grant Choices */}
          {terminationDecision.termination_date && terminationDecision.exempt_amount > 0 && (
            <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
              <h4>שלב 5א: בחירת אפשרות לחלק הפטור ממס</h4>
              <div style={{ marginBottom: '10px' }}>
                <label style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    value="redeem_with_exemption"
                    checked={terminationDecision.exempt_choice === 'redeem_with_exemption'}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      exempt_choice: e.target.value as any 
                    }))}
                    style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                  />
                  פדיון הסכום עם שימוש בפטור
                </label>
                <label style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    value="redeem_no_exemption"
                    checked={terminationDecision.exempt_choice === 'redeem_no_exemption'}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      exempt_choice: e.target.value as any 
                    }))}
                    style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                  />
                  פדיון הסכום ללא שימוש בפטור
                </label>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    value="annuity"
                    checked={terminationDecision.exempt_choice === 'annuity'}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      exempt_choice: e.target.value as any 
                    }))}
                    style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                  />
                  סימון כקצבה
                </label>
              </div>
            </div>
          )}

          {terminationDecision.termination_date && terminationDecision.taxable_amount > 0 && (
            <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #dc3545', borderRadius: '4px', backgroundColor: '#fff5f5' }}>
              <h4>שלב 5ב: בחירת אפשרות לחלק החייב במס</h4>
              <div style={{ marginBottom: '10px' }}>
                <label style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    value="redeem_no_exemption"
                    checked={terminationDecision.taxable_choice === 'redeem_no_exemption'}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      taxable_choice: e.target.value as any 
                    }))}
                    style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                  />
                  פדיון הסכום ללא שימוש בפטור
                </label>
                <label style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    value="annuity"
                    checked={terminationDecision.taxable_choice === 'annuity'}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      taxable_choice: e.target.value as any 
                    }))}
                    style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                  />
                  סימון כקצבה
                </label>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    value="tax_spread"
                    checked={terminationDecision.taxable_choice === 'tax_spread'}
                    onChange={(e) => setTerminationDecision(prev => ({ 
                      ...prev, 
                      taxable_choice: e.target.value as any 
                    }))}
                    style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                  />
                  פריסת מס
                </label>
              </div>

              {/* Tax Spread Details */}
              {terminationDecision.taxable_choice === 'tax_spread' && terminationDecision.max_spread_years !== undefined && (
                <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fff3cd', borderRadius: '4px', border: '1px solid #ffc107' }}>
                  <h5>זכאות לפריסת פיצויים</h5>
                  <p style={{ marginBottom: '10px' }}>
                    <strong>זכאות מקסימלית:</strong> {terminationDecision.max_spread_years} שנים
                    <br/>
                    <small style={{ color: '#666' }}>
                      (שנת פריסה אחת לכל 4 שנות וותק מלאות)
                    </small>
                  </p>
                  
                  {terminationDecision.max_spread_years > 0 ? (
                    <div>
                      <label>בחר מספר שנות פריסה:</label>
                      <input
                        type="number"
                        min="1"
                        max={terminationDecision.max_spread_years}
                        value={terminationDecision.tax_spread_years || terminationDecision.max_spread_years}
                        onChange={(e) => setTerminationDecision(prev => ({
                          ...prev,
                          tax_spread_years: Math.min(
                            parseInt(e.target.value) || 0,
                            terminationDecision.max_spread_years || 0
                          )
                        }))}
                        style={{ width: '100%', padding: '8px', marginTop: '5px' }}
                      />
                      <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
                        המערכת ממליצה על פריסה מלאה של {terminationDecision.max_spread_years} שנים לחיסכון מרבי במס
                      </small>
                    </div>
                  ) : (
                    <div style={{ padding: '10px', backgroundColor: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
                      <strong>אין זכאות לפריסה</strong>
                      <p style={{ marginTop: '5px', fontSize: '14px' }}>
                        נדרשות לפחות 4 שנות וותק מלאות לזכאות לפריסת מס
                      </p>
                    </div>
                  )}

                  {terminationDecision.max_spread_years > 0 && (
                    <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#d1ecf1', borderRadius: '4px', border: '1px solid #bee5eb' }}>
                      <h6 style={{ marginTop: 0 }}>מה זה פריסת פיצויים?</h6>
                      <p style={{ fontSize: '14px', margin: '5px 0' }}>
                        פריסת החלק החייב עשויה להקטין את המס הכולל על המענק. 
                        המערכת תחשב עבורך את ההשפעה ותציג השוואה ברורה בין פריסה לתשלום חד-פעמי.
                      </p>
                      <p style={{ fontSize: '13px', color: '#666', marginBottom: 0 }}>
                        <strong>חשוב:</strong> הפריסה כפופה להסכמות מעסיק/חוק – יש לאשר במערכת הניהול/בחוזה.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Submit Button */}
          {terminationDecision.termination_date && (
            <div style={{ marginTop: '30px', textAlign: 'center' }}>
              <button
                type="button"
                onClick={handleTerminationSubmit}
                disabled={loading}
                style={{
                  backgroundColor: loading ? '#6c757d' : '#28a745',
                  color: 'white',
                  border: 'none',
                  padding: '15px 40px',
                  borderRadius: '4px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  marginLeft: '10px'
                }}
              >
                {loading ? 'שומר...' : 'שמור החלטות ועדכן מערכת'}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('details')}
                style={{
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  padding: '15px 40px',
                  borderRadius: '4px',
                  fontSize: '16px',
                  cursor: 'pointer'
                }}
              >
                ביטול
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CurrentEmployer;
