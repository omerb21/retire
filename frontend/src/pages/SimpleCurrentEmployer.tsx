import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import axios from 'axios';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

interface SimpleEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  end_date?: string;
  last_salary: number;
  severance_accrued: number;
  employer_completion?: number;
  service_years?: number;
  expected_grant_amount?: number;
  tax_exempt_amount?: number;
  taxable_amount?: number;
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

const SimpleCurrentEmployer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'details' | 'termination'>('details');
  const [employer, setEmployer] = useState<SimpleEmployer>({
    employer_name: '',
    start_date: '',
    last_salary: 0,
    severance_accrued: 0
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

  // Calculate grant details
  const [grantDetails, setGrantDetails] = useState({
    serviceYears: 0,
    expectedGrant: 0,
    taxExemptAmount: 0,
    taxableAmount: 0,
    severanceCap: 0
  });

  // Load existing employer data
  useEffect(() => {
    const fetchEmployer = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/v1/clients/${id}/current-employer`);
        
        // Load severance balance from pension portfolio (localStorage)
        let severanceFromPension = 0;
        const pensionStorageKey = `pensionData_${id}`;
        const storedPensionData = localStorage.getItem(pensionStorageKey);
        
        if (storedPensionData) {
          try {
            const pensionData = JSON.parse(storedPensionData);
            // Sum all severance amounts from "פיצויים מעסיק נוכחי" column
            severanceFromPension = pensionData.reduce((sum: number, account: any) => {
              const currentEmployerSeverance = Number(account['פיצויים_מעסיק_נוכחי'] || account.פיצויים_מעסיק_נוכחי || 0);
              return sum + currentEmployerSeverance;
            }, 0);
            console.log('יתרת פיצויים מתיק פנסיוני:', severanceFromPension);
            console.log('מספר חשבונות:', pensionData.length);
            pensionData.forEach((acc: any, idx: number) => {
              console.log(`חשבון ${idx + 1}: פיצויים מעסיק נוכחי = ${acc.פיצויים_מעסיק_נוכחי || 0}`);
            });
          } catch (e) {
            console.error('שגיאה בטעינת נתוני תיק פנסיוני:', e);
          }
        } else {
          console.log('לא נמצא תיק פנסיוני ב-localStorage עבור לקוח:', id);
        }
        
        if (response.data) {
          // Handle both array and single object responses
          if (Array.isArray(response.data) && response.data.length > 0) {
            setEmployer({
              ...response.data[0],
              severance_accrued: severanceFromPension
            });
          } else if (typeof response.data === 'object' && response.data.employer_name) {
            // Single employer object - map fields correctly
            setEmployer({
              id: response.data.id,
              employer_name: response.data.employer_name || '',
              start_date: response.data.start_date || '',
              last_salary: Number(response.data.monthly_salary || response.data.last_salary || response.data.average_salary || 0),
              severance_accrued: severanceFromPension
            });
          }
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

  // Calculate grant details when employer data changes with debouncing
  useEffect(() => {
    const calculateGrantDetails = async () => {
      if (employer.start_date && employer.last_salary > 0) {
        const startDate = new Date(employer.start_date);
        const currentDate = new Date();
        
        // Calculate service years
        const serviceYears = (currentDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
        
        // Basic severance calculation (1 month salary per year)
        const expectedGrant = employer.last_salary * serviceYears;
        
        try {
          // Call the new severance calculation API
          const response = await axios.post(`${API_BASE}/current-employer/calculate-severance`, {
            start_date: employer.start_date,
            last_salary: employer.last_salary
          });

          const calculation = response.data;
          
          // חישוב השלמת המעסיק = סכום המענק הצפוי פחות יתרת פיצויים נצברת
          const employerCompletion = Math.max(0, calculation.severance_amount - employer.severance_accrued);
          
          // עדכון השלמת המעסיק באובייקט המעסיק
          setEmployer(prev => ({
            ...prev,
            employer_completion: employerCompletion
          }));
          
          setGrantDetails({
            serviceYears: calculation.service_years,
            expectedGrant: calculation.severance_amount,
            taxExemptAmount: calculation.exempt_amount,
            taxableAmount: calculation.taxable_amount,
            severanceCap: calculation.annual_exemption_cap
          });
        } catch (error) {
          console.error('Error calculating severance:', error);
          // Fallback calculation with correct formula
          const currentYearCap = 13750; // תקרת פטור למענקי פרישה 2025
          const severanceExemption = currentYearCap * serviceYears;
          const taxExemptAmount = Math.min(expectedGrant, severanceExemption);
          const taxableAmount = Math.max(0, expectedGrant - taxExemptAmount);

          // חישוב השלמת המעסיק = סכום המענק הצפוי פחות יתרת פיצויים נצברת
          const employerCompletion = Math.max(0, Math.round(expectedGrant) - employer.severance_accrued);
          
          // עדכון השלמת המעסיק באובייקט המעסיק
          setEmployer(prev => ({
            ...prev,
            employer_completion: employerCompletion
          }));
          
          setGrantDetails({
            serviceYears: Math.round(serviceYears * 100) / 100,
            expectedGrant: Math.round(expectedGrant),
            taxExemptAmount: Math.round(taxExemptAmount),
            taxableAmount: Math.round(taxableAmount),
            severanceCap: currentYearCap
          });
        }
      }
    };
    
    // Add debouncing to prevent excessive API calls
    const timeoutId = setTimeout(() => {
      calculateGrantDetails();
    }, 500);
    
    return () => clearTimeout(timeoutId);
  }, [employer.start_date, employer.last_salary, employer.severance_accrued, id]);

  // Calculate termination details when termination date is set
  useEffect(() => {
    const calculateTermination = async () => {
      // Validate that date is complete (DD/MM/YYYY = 10 characters)
      if (!terminationDecision.termination_date || 
          terminationDecision.termination_date.length < 10 ||
          !employer.start_date || 
          !employer.last_salary) {
        return;
      }
      
      if (terminationDecision.termination_date && employer.start_date && employer.last_salary) {
        // Parse dates properly - handle both DD/MM/YYYY and ISO formats
        let startDateISO = employer.start_date;
        if (employer.start_date.includes('/')) {
          startDateISO = convertDDMMYYToISO(employer.start_date) || employer.start_date;
        }
        
        let endDateISO = terminationDecision.termination_date;
        if (terminationDecision.termination_date.includes('/')) {
          endDateISO = convertDDMMYYToISO(terminationDecision.termination_date) || terminationDecision.termination_date;
        }
        
        const startDate = new Date(startDateISO);
        const endDate = new Date(endDateISO);
        
        console.log('Date parsing debug:', {
          original_termination: terminationDecision.termination_date,
          endDateISO,
          endDate: endDate.toString(),
          terminationYear: endDate.getFullYear()
        });
        
        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
          console.error('Invalid dates:', { startDate: startDateISO, endDate: endDateISO });
          return;
        }
        
        const serviceYears = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
        // מענק פיצויים צפוי = שכר אחרון × וותק
        const expectedGrant = employer.last_salary * serviceYears;
        
        const maxSpreadYears = Math.floor(serviceYears / 4);
        
        // אם הצבורים גבוהים יותר, משתמשים בהם לחישוב
        const severanceAmount = Math.max(expectedGrant, employer.severance_accrued);
        
        // Get severance cap for termination year from API
        const terminationYear = endDate.getFullYear();
        console.log('Fetching cap for year:', terminationYear);
        let monthlyCap = 13750; // Default for 2024-2025
        
        try {
          const response = await axios.get(`/api/v1/tax-data/severance-cap?year=${terminationYear}`);
          if (response.data && response.data.monthly_cap) {
            monthlyCap = response.data.monthly_cap;
          }
        } catch (err) {
          console.warn('Failed to fetch severance cap, using default:', err);
        }
        
        // תקרת פטור = תקרה שנתית × וותק
        // התקרה החודשית שמוחזרת מה-API היא למעשה תקרה שנתית!
        const exemptCap = monthlyCap * serviceYears;
        const exemptAmount = Math.min(severanceAmount, exemptCap);
        const taxableAmount = Math.max(0, severanceAmount - exemptAmount);
        
        console.log('Exemption calculation:', {
          terminationYear,
          monthlyCap,
          serviceYears,
          exemptCap,
          severanceAmount,
          exemptAmount,
          taxableAmount
        });
        
        setTerminationDecision(prev => ({
          ...prev,
          severance_amount: Math.round(severanceAmount),
          exempt_amount: Math.round(exemptAmount),
          taxable_amount: Math.round(taxableAmount),
          max_spread_years: maxSpreadYears
        }));
      }
    };
    
    // Add debouncing to avoid excessive API calls while user is typing
    const timeoutId = setTimeout(() => {
      calculateTermination();
    }, 500);
    
    return () => clearTimeout(timeoutId);
  }, [terminationDecision.termination_date, terminationDecision.use_employer_completion, employer.start_date, employer.last_salary, employer.severance_accrued]);

  const handleTerminationSubmit = async () => {
    try {
      setLoading(true);
      setError(null);

      const terminationDateISO = convertDDMMYYToISO(terminationDecision.termination_date) || terminationDecision.termination_date;
      
      await axios.post(`/api/v1/clients/${id}/current-employer/termination`, {
        ...terminationDecision,
        termination_date: terminationDateISO
      });

      alert('החלטות עזיבה נשמרו בהצלחה');
      navigate(`/clients/${id}`);
    } catch (err: any) {
      setError('שגיאה בשמירת החלטות עזיבה: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      setError(null);

      // Convert start_date to ISO format
      const startDateISO = convertDDMMYYToISO(employer.start_date);
      if (!startDateISO) {
        throw new Error('תאריך התחלת עבודה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }

      const employerData = {
        ...employer,
        start_date: startDateISO
      };

      if (employer.id) {
        const response = await axios.put(`/api/v1/clients/${id}/current-employer/${employer.id}`, employerData);
        setEmployer({ ...response.data, start_date: convertISOToDDMMYY(response.data.start_date) });
      } else {
        const response = await axios.post(`/api/v1/clients/${id}/current-employer`, employerData);
        setEmployer({ ...response.data, start_date: convertISOToDDMMYY(response.data.start_date) });
      }

      alert('נתוני מעסיק נשמרו בהצלחה');
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
      [name]: name.includes('salary') || name.includes('balance') 
        ? parseFloat(value) || 0 : value
    }));
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </a>
      </div>

      <h2>מעסיק נוכחי</h2>

      {error && (
        <div style={{ color: 'red', marginBottom: '20px', padding: '10px', backgroundColor: '#fee', borderRadius: '4px' }}>
          {error}
        </div>
      )}

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
      <div>

      {/* Display existing employer data if loaded */}
      {employer.id && (
        <div style={{ 
          marginBottom: '20px', 
          padding: '15px', 
          border: '1px solid #28a745', 
          borderRadius: '4px',
          backgroundColor: '#f8fff9'
        }}>
          <h3 style={{ color: '#28a745', marginBottom: '15px' }}>נתונים שמורים</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
            <div><strong>שם מעסיק:</strong> {employer.employer_name}</div>
            <div><strong>תאריך התחלה:</strong> {employer.start_date}</div>
            <div><strong>שכר חודשי:</strong> ₪{employer.last_salary.toLocaleString()}</div>
            <div><strong>יתרת פיצויים:</strong> ₪{employer.severance_accrued.toLocaleString()}</div>
            {employer.employer_completion !== undefined && (
              <div style={{ color: '#0066cc', fontWeight: 'bold', gridColumn: '1 / -1' }}>
                <strong>השלמת המעסיק:</strong> ₪{employer.employer_completion.toLocaleString()}
              </div>
            )}
          </div>
          
          {grantDetails.serviceYears > 0 && (
            <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#e7f3ff', borderRadius: '4px' }}>
              <h4>חישוב מענק פיצויים צפוי (תקרה שנתית: ₪{grantDetails.severanceCap.toLocaleString()})</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '14px' }}>
                <div><strong>שנות שירות:</strong> {grantDetails.serviceYears}</div>
                <div><strong>מענק צפוי:</strong> ₪{grantDetails.expectedGrant.toLocaleString()}</div>
                <div><strong>יתרת פיצויים:</strong> ₪{employer.severance_accrued.toLocaleString()}</div>
                <div style={{ color: '#0066cc', fontWeight: 'bold' }}><strong>השלמת המעסיק:</strong> ₪{employer.employer_completion?.toLocaleString() || '0'}</div>
                <div style={{ color: '#28a745' }}><strong>פטור ממס:</strong> ₪{grantDetails.taxExemptAmount.toLocaleString()}</div>
                <div style={{ color: '#dc3545' }}><strong>חייב במס:</strong> ₪{grantDetails.taxableAmount.toLocaleString()}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {!employer.id && (
        <div style={{
          marginBottom: '20px',
          padding: '15px',
          border: '1px solid #ffc107',
          borderRadius: '4px',
          backgroundColor: '#fff3cd'
        }}>
          <p style={{ margin: 0, color: '#856404' }}>לא נמצאו נתונים שמורים. אנא מלא את הפרטים למטה.</p>
        </div>
      )}

      {error && (
        <div style={{ 
          color: 'red', 
          marginBottom: '20px', 
          padding: '10px', 
          backgroundColor: '#fee', 
          borderRadius: '4px' 
        }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            שם מעסיק *
          </label>
          <input
            type="text"
            name="employer_name"
            value={employer.employer_name}
            onChange={handleInputChange}
            required
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '16px'
            }}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            תאריך התחלת עבודה *
          </label>
          <input
            type="text"
            name="start_date"
            placeholder="DD/MM/YYYY"
            value={employer.start_date || ''}
            onChange={(e) => {
              const formatted = formatDateInput(e.target.value);
              setEmployer({ ...employer, start_date: formatted });
            }}
            maxLength={10}
            required
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '16px'
            }}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            שכר חודשי (₪) *
          </label>
          <input
            type="number"
            name="last_salary"
            value={employer.last_salary}
            onChange={handleInputChange}
            required
            min="0"
            step="0.01"
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '16px'
            }}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            יתרת פיצויים נצברת (₪)
          </label>
          <div style={{ 
            padding: '12px', 
            backgroundColor: '#f8f9fa',
            border: '2px solid #e9ecef',
            borderRadius: '4px',
            fontSize: '18px',
            fontWeight: 'bold',
            color: '#495057'
          }}>
            ₪{employer.severance_accrued.toLocaleString()}
          </div>
          <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
            שדה מחושב: סה"כ יתרות פיצויים מתיק פנסיוני של מעסיק נוכחי
          </small>
        </div>


        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={() => navigate(`/clients/${id}`)}
            disabled={loading}
            style={{
              padding: '10px 20px',
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            ביטול
          </button>
          
          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '10px 20px',
              backgroundColor: loading ? '#ccc' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {loading ? 'שומר...' : 'שמור'}
          </button>
        </div>
      </form>
      </div>
      )}

      {/* Termination Tab */}
      {activeTab === 'termination' && (
        <div>
          <h3>מסך עזיבת עבודה</h3>
          
          <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '4px' }}>
            <h4>שלב 1: קביעת תאריך סיום עבודה</h4>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>תאריך סיום עבודה:</label>
              <input
                type="text"
                placeholder="DD/MM/YYYY"
                value={terminationDecision.termination_date}
                onChange={(e) => {
                  const formatted = formatDateInput(e.target.value);
                  setTerminationDecision(prev => ({ ...prev, termination_date: formatted }));
                }}
                maxLength={10}
                style={{ width: '100%', padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
              />
            </div>
          </div>

          {terminationDecision.termination_date && employer.start_date && (
            <>
              <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
                <h4>שלב 2: סיכום זכויות</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div><strong>שנות וותק:</strong> {(() => {
                    let startISO = employer.start_date.includes('/') ? convertDDMMYYToISO(employer.start_date) : employer.start_date;
                    let endISO = terminationDecision.termination_date.includes('/') ? convertDDMMYYToISO(terminationDecision.termination_date) : terminationDecision.termination_date;
                    const years = (new Date(endISO || '').getTime() - new Date(startISO || '').getTime()) / (1000 * 60 * 60 * 24 * 365.25);
                    return isNaN(years) ? '0' : years.toFixed(2);
                  })()} שנים</div>
                  <div><strong>פיצויים צבורים:</strong> ₪{employer.severance_accrued.toLocaleString()}</div>
                  <div><strong>פיצויים צפויים:</strong> ₪{(() => {
                    let startISO = employer.start_date.includes('/') ? convertDDMMYYToISO(employer.start_date) : employer.start_date;
                    let endISO = terminationDecision.termination_date.includes('/') ? convertDDMMYYToISO(terminationDecision.termination_date) : terminationDecision.termination_date;
                    const years = (new Date(endISO || '').getTime() - new Date(startISO || '').getTime()) / (1000 * 60 * 60 * 24 * 365.25);
                    if (isNaN(years)) return '0';
                    const expectedFromSalary = Math.round(employer.last_salary * years);
                    const accrued = employer.severance_accrued || 0;
                    // לתצוגה: אם צבורים גבוהים יותר, הראה אותם
                    return Math.max(expectedFromSalary, accrued).toLocaleString();
                  })()}</div>
                </div>
              </div>

              <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ffc107', borderRadius: '4px', backgroundColor: '#fffdf5' }}>
                <h4>שלב 3: השלמת מעסיק</h4>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={terminationDecision.use_employer_completion}
                    onChange={(e) => setTerminationDecision(prev => ({ ...prev, use_employer_completion: e.target.checked }))}
                    style={{ marginLeft: '10px', width: '20px', height: '20px' }}
                  />
                  תבוצע השלמת מעסיק
                </label>
                {terminationDecision.use_employer_completion && (
                  <div style={{ padding: '10px', backgroundColor: '#e8f4f8', borderRadius: '4px', marginTop: '10px' }}>
                    <p><strong>גובה השלמת המעסיק:</strong> ₪{(() => {
                      let startISO = employer.start_date.includes('/') ? convertDDMMYYToISO(employer.start_date) : employer.start_date;
                      let endISO = terminationDecision.termination_date.includes('/') ? convertDDMMYYToISO(terminationDecision.termination_date) : terminationDecision.termination_date;
                      const years = (new Date(endISO || '').getTime() - new Date(startISO || '').getTime()) / (1000 * 60 * 60 * 24 * 365.25);
                      const expectedGrant = Math.round(employer.last_salary * years);
                      const completion = Math.max(0, expectedGrant - employer.severance_accrued);
                      return isNaN(completion) ? '0' : completion.toLocaleString();
                    })()}</p>
                    <small>ההפרש בין המענק הצפוי ליתרת הפיצויים הנצברת</small>
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #17a2b8', borderRadius: '4px', backgroundColor: '#f0f9fc' }}>
                <h4>שלב 4: חלוקה לפטור/חייב במס</h4>
                
                {/* Debug info */}
                <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#fff3cd', borderRadius: '4px', fontSize: '12px', border: '1px solid #ffc107' }}>
                  <strong>🔍 פרטי חישוב:</strong>
                  <div>תאריך עזיבה מקורי: <strong>{terminationDecision.termination_date}</strong></div>
                  <div>שנת עזיבה מחושבת: <strong>{(() => {
                    let endISO = terminationDecision.termination_date.includes('/') ? convertDDMMYYToISO(terminationDecision.termination_date) : terminationDecision.termination_date;
                    return new Date(endISO).getFullYear();
                  })()}</strong></div>
                  <div>סכום פיצויים: <strong>₪{terminationDecision.severance_amount.toLocaleString()}</strong></div>
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div style={{ padding: '15px', backgroundColor: '#d4edda', borderRadius: '4px' }}>
                    <strong style={{ color: '#155724' }}>חלק פטור ממס:</strong>
                    <p style={{ fontSize: '20px', fontWeight: 'bold', margin: '10px 0' }}>₪{terminationDecision.exempt_amount.toLocaleString()}</p>
                  </div>
                  <div style={{ padding: '15px', backgroundColor: '#f8d7da', borderRadius: '4px' }}>
                    <strong style={{ color: '#721c24' }}>חלק חייב במס:</strong>
                    <p style={{ fontSize: '20px', fontWeight: 'bold', margin: '10px 0' }}>₪{terminationDecision.taxable_amount.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              {terminationDecision.exempt_amount > 0 && (
                <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
                  <h4>שלב 5א: בחירת אפשרות לחלק הפטור ממס</h4>
                  {['redeem_with_exemption', 'redeem_no_exemption', 'annuity'].map(choice => (
                    <label key={choice} style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        value={choice}
                        checked={terminationDecision.exempt_choice === choice}
                        onChange={(e) => setTerminationDecision(prev => ({ ...prev, exempt_choice: e.target.value as any }))}
                        style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                      />
                      {choice === 'redeem_with_exemption' ? 'פדיון הסכום עם שימוש בפטור' :
                       choice === 'redeem_no_exemption' ? 'פדיון הסכום ללא שימוש בפטור' : 'סימון כקצבה'}
                    </label>
                  ))}
                </div>
              )}

              {terminationDecision.taxable_amount > 0 && (
                <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #dc3545', borderRadius: '4px', backgroundColor: '#fff5f5' }}>
                  <h4>שלב 5ב: בחירת אפשרות לחלק החייב במס</h4>
                  {['redeem_no_exemption', 'annuity', 'tax_spread'].map(choice => (
                    <label key={choice} style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        value={choice}
                        checked={terminationDecision.taxable_choice === choice}
                        onChange={(e) => setTerminationDecision(prev => ({ ...prev, taxable_choice: e.target.value as any }))}
                        style={{ marginLeft: '10px', width: '18px', height: '18px' }}
                      />
                      {choice === 'redeem_no_exemption' ? 'פדיון הסכום ללא שימוש בפטור' :
                       choice === 'annuity' ? 'סימון כקצבה' : 'פריסת מס'}
                    </label>
                  ))}

                  {terminationDecision.taxable_choice === 'tax_spread' && terminationDecision.max_spread_years !== undefined && (
                    <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fff3cd', borderRadius: '4px', border: '1px solid #ffc107' }}>
                      <h5>זכאות לפריסת פיצויים</h5>
                      
                      <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#e7f3ff', borderRadius: '4px', fontSize: '14px' }}>
                        <strong>📘 מה זה פריסת פיצויים?</strong>
                        <p style={{ margin: '8px 0 0 0' }}>
                          פריסת פיצויים מאפשרת לפרוס את החלק החייב במס של המענק על פני מספר שנות מס.
                          הזכאות נקבעת לפי <strong>שנת פריסה אחת לכל 4 שנות וותק מלאות</strong>.
                          פריסה עשויה להקטין את המס הכולל על המענק בזכות מדרגות המס השנתיות.
                        </p>
                        <p style={{ margin: '8px 0 0 0', fontSize: '13px', color: '#555' }}>
                          <strong>תשלום המס:</strong> בשנה הראשונה משולם כל סכום המענק, אך המס מחושב בהתחשב 
                          בפריסה על פני כל השנים. בשאר השנים, המס מוצג רק ויזואלית ולא משולם בפועל.
                        </p>
                      </div>
                      
                      <p><strong>זכאות מקסימלית:</strong> {terminationDecision.max_spread_years} שנים<br/>
                      <small style={{ color: '#666' }}>(שנת פריסה אחת לכל 4 שנות וותק מלאות)</small></p>
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
                              tax_spread_years: Math.min(parseInt(e.target.value) || 0, terminationDecision.max_spread_years || 0)
                            }))}
                            style={{ width: '100%', padding: '8px', marginTop: '5px', border: '1px solid #ddd', borderRadius: '4px' }}
                          />
                          <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
                            המערכת ממליצה על פריסה מלאה של {terminationDecision.max_spread_years} שנים לחיסכון מרבי במס
                          </small>
                        </div>
                      ) : (
                        <div style={{ padding: '10px', backgroundColor: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
                          <strong>אין זכאות לפריסה</strong>
                          <p style={{ marginTop: '5px', fontSize: '14px' }}>נדרשות לפחות 4 שנות וותק מלאות לזכאות לפריסת מס</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

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
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default SimpleCurrentEmployer;
