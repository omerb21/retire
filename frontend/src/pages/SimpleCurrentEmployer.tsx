import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

interface SimpleEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  last_salary: number;
  severance_accrued: number;
  employer_completion?: number; // השלמת המעסיק
}

const SimpleCurrentEmployer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [employer, setEmployer] = useState<SimpleEmployer>({
    employer_name: '',
    start_date: '',
    last_salary: 0,
    severance_accrued: 0
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
        if (response.data) {
          // Handle both array and single object responses
          if (Array.isArray(response.data) && response.data.length > 0) {
            setEmployer(response.data[0]);
          } else if (typeof response.data === 'object' && response.data.employer_name) {
            // Single employer object - map fields correctly
            setEmployer({
              id: response.data.id,
              employer_name: response.data.employer_name || '',
              start_date: response.data.start_date || '',
              last_salary: Number(response.data.monthly_salary || response.data.last_salary || response.data.average_salary || 0),
              severance_accrued: Number(response.data.severance_balance || response.data.severance_accrued || 0)
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
  }, [employer.start_date, employer.last_salary, id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      setError(null);

      if (employer.id) {
        const response = await axios.put(`/api/v1/clients/${id}/current-employer/${employer.id}`, employer);
        setEmployer(response.data);
      } else {
        const response = await axios.post(`/api/v1/clients/${id}/current-employer`, employer);
        setEmployer(response.data);
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
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </a>
      </div>

      <h2>מעסיק נוכחי</h2>

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
            type="date"
            name="start_date"
            value={employer.start_date}
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
          <input
            type="number"
            name="severance_accrued"
            value={employer.severance_accrued}
            onChange={handleInputChange}
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
  );
};

export default SimpleCurrentEmployer;
