import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface SimpleEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  monthly_salary: number;
  severance_balance: number;
}

const SimpleCurrentEmployer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [employer, setEmployer] = useState<SimpleEmployer>({
    employer_name: '',
    start_date: '',
    monthly_salary: 0,
    severance_balance: 0
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
              monthly_salary: Number(response.data.monthly_salary || response.data.last_salary || response.data.average_salary || 0),
              severance_balance: Number(response.data.severance_balance || response.data.severance_accrued || 0)
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

  // Calculate grant details when employer data changes
  useEffect(() => {
    const calculateGrantDetails = async () => {
      if (employer.start_date && employer.monthly_salary > 0) {
        const startDate = new Date(employer.start_date);
        const currentDate = new Date();
        const serviceYears = (currentDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
        
        // Basic severance calculation (1 month salary per year)
        const expectedGrant = employer.monthly_salary * serviceYears;
        
        try {
          // Get real-time severance cap and exemption from API
          const [capResponse, exemptionResponse] = await Promise.all([
            axios.get('/api/v1/tax-data/severance-cap'),
            axios.get('/api/v1/tax-data/severance-exemption', {
              params: { service_years: serviceYears }
            })
          ]);
          
          const realMonthlyCap = capResponse.data.monthly_cap;
          const taxExemptAmount = Math.min(expectedGrant, exemptionResponse.data.total_exemption);
          const taxableAmount = Math.max(0, expectedGrant - taxExemptAmount);

          setGrantDetails({
            serviceYears: Math.round(serviceYears * 100) / 100,
            expectedGrant: Math.round(expectedGrant),
            taxExemptAmount: Math.round(taxExemptAmount),
            taxableAmount: Math.round(taxableAmount),
            severanceCap: realMonthlyCap
          });
        } catch (error) {
          console.error('Error fetching real-time tax data:', error);
          // Fallback calculation with current known cap
          const fallbackCap = 41667; // תקרה חודשית נוכחית
          const taxExemptAmount = Math.min(expectedGrant, fallbackCap * serviceYears);
          const taxableAmount = Math.max(0, expectedGrant - taxExemptAmount);

          setGrantDetails({
            serviceYears: Math.round(serviceYears * 100) / 100,
            expectedGrant: Math.round(expectedGrant),
            taxExemptAmount: Math.round(taxExemptAmount),
            taxableAmount: Math.round(taxableAmount),
            severanceCap: fallbackCap
          });
        }
      }
    };
    
    calculateGrantDetails();
  }, [employer.start_date, employer.monthly_salary]);

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
            <div><strong>שכר חודשי:</strong> ₪{employer.monthly_salary.toLocaleString()}</div>
            <div><strong>יתרת פיצויים:</strong> ₪{employer.severance_balance.toLocaleString()}</div>
          </div>
          
          {grantDetails.serviceYears > 0 && (
            <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#e7f3ff', borderRadius: '4px' }}>
              <h4>חישוב מענק פיצויים צפוי (תקרה חודשית: ₪{grantDetails.severanceCap.toLocaleString()})</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '14px' }}>
                <div><strong>שנות שירות:</strong> {grantDetails.serviceYears}</div>
                <div><strong>מענק צפוי:</strong> ₪{grantDetails.expectedGrant.toLocaleString()}</div>
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
            name="monthly_salary"
            value={employer.monthly_salary}
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
            name="severance_balance"
            value={employer.severance_balance}
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

        {/* Display calculated grant details */}
        {grantDetails.serviceYears > 0 && (
          <div style={{
            marginBottom: '20px',
            padding: '15px',
            backgroundColor: '#f0f8ff',
            border: '1px solid #007bff',
            borderRadius: '4px'
          }}>
            <h3 style={{ marginTop: 0, color: '#007bff' }}>חישוב מענק פיצויים צפוי</h3>
            <div style={{ marginBottom: '10px', fontSize: '14px', color: '#666' }}>
              תקרה חודשית נוכחית: ₪{grantDetails.severanceCap.toLocaleString()} (מתעדכנת דרך API)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <strong>שנות שירות:</strong> {grantDetails.serviceYears}
              </div>
              <div>
                <strong>מענק צפוי:</strong> ₪{grantDetails.expectedGrant.toLocaleString()}
              </div>
              <div style={{ color: '#28a745' }}>
                <strong>פטור ממס:</strong> ₪{grantDetails.taxExemptAmount.toLocaleString()}
              </div>
              <div style={{ color: '#dc3545' }}>
                <strong>חייב במס:</strong> ₪{grantDetails.taxableAmount.toLocaleString()}
              </div>
            </div>
          </div>
        )}

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
