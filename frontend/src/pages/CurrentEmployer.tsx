import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface CurrentEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  monthly_salary: number;
  severance_balance: number;
  service_years?: number;
  expected_grant_amount?: number;
  tax_exempt_amount?: number;
  taxable_amount?: number;
  reserved_exemption?: number;
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
  const [employer, setEmployer] = useState<CurrentEmployer>({
    employer_name: '',
    start_date: '',
    monthly_salary: 0,
    severance_balance: 0,
    expected_grant_amount: 0,
    tax_exempt_amount: 0,
    taxable_amount: 0,
    reserved_exemption: 0
  });
  const [grants, setGrants] = useState<EmployerGrant[]>([]);
  const [newEmployer, setNewEmployer] = useState<CurrentEmployer>({
    employer_name: '',
    start_date: '',
    monthly_salary: 0,
    severance_balance: 0,
  });
  const [newGrant, setNewGrant] = useState<EmployerGrant>({
    grant_type: 'severance',
    grant_date: '',
    amount: 0,
    reason: '',
  });

  // Calculate service years and grant amounts
  const calculateGrantDetails = () => {
    if (!employer.start_date) return;

    const startDate = new Date(employer.start_date);
    const currentDate = new Date();
    const serviceYears = (currentDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
    
    // Basic severance calculation (1 month salary per year)
    const expectedGrant = employer.monthly_salary * serviceYears;
    
    // Tax exemption calculation (up to 375,000 NIS or 9 months salary, whichever is lower)
    const maxExemption = Math.min(375000, employer.monthly_salary * 9);
    const taxExemptAmount = Math.min(expectedGrant, maxExemption - (employer.reserved_exemption || 0));
    const taxableAmount = expectedGrant - taxExemptAmount;

    setEmployer(prev => ({
      ...prev,
      service_years: Math.round(serviceYears * 100) / 100,
      expected_grant_amount: Math.round(expectedGrant),
      tax_exempt_amount: Math.max(0, Math.round(taxExemptAmount)),
      taxable_amount: Math.max(0, Math.round(taxableAmount))
    }));
  };

  // Load existing employer data
  useEffect(() => {
    const fetchEmployer = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/v1/clients/${id}/current-employer`);
        if (response.data && response.data.length > 0) {
          setEmployer(response.data[0]);
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

  // Recalculate when relevant fields change
  useEffect(() => {
    if (employer.start_date && employer.monthly_salary > 0) {
      calculateGrantDetails();
    }
  }, [employer.start_date, employer.monthly_salary, employer.reserved_exemption]);

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

  return (
    <div>
      <h2>מעסיק נוכחי</h2>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`}>חזרה לפרטי לקוח</a>
      </div>

      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

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
            <input
              type="number"
              name="severance_balance"
              value={employer.severance_balance}
              onChange={handleInputChange}
              required
              style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            />
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
            <h4>הוספת מענק חדש</h4>
            <form onSubmit={handleGrantSubmit}>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px' }}>סוג מענק:</label>
                <select
                  value={newGrant.grant_type}
                  onChange={(e) => setNewGrant({ ...newGrant, grant_type: e.target.value })}
                  style={{ width: '100%', padding: '8px' }}
                  required
                >
                  <option value="severance">פיצויים</option>
                  <option value="bonus">בונוס</option>
                  <option value="adjustment">התאמת שכר</option>
                  <option value="other">אחר</option>
                </select>
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px' }}>תאריך מענק:</label>
                <input
                  type="date"
                  value={newGrant.grant_date}
                  onChange={(e) => setNewGrant({ ...newGrant, grant_date: e.target.value })}
                  style={{ width: '100%', padding: '8px' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px' }}>סכום:</label>
                <input
                  type="number"
                  value={newGrant.amount}
                  onChange={(e) => setNewGrant({ ...newGrant, amount: Number(e.target.value) })}
                  style={{ width: '100%', padding: '8px' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px' }}>סיבה:</label>
                <input
                  type="text"
                  value={newGrant.reason}
                  onChange={(e) => setNewGrant({ ...newGrant, reason: e.target.value })}
                  style={{ width: '100%', padding: '8px' }}
                  required
                />
              </div>

              <button
                type="submit"
                style={{
                  backgroundColor: '#28a745',
                  color: 'white',
                  border: 'none',
                  padding: '10px 15px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                הוסף מענק
              </button>
            </form>
          </div>

          {/* Grants List */}
          <div>
            <h4>רשימת מענקים</h4>
            {grants.length === 0 ? (
              <p>אין מענקים רשומים</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>סוג</th>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>תאריך</th>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>סכום</th>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>סיבה</th>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>פטור ממס</th>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>חייב במס</th>
                    <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>מס לתשלום</th>
                  </tr>
                </thead>
                <tbody>
                  {grants.map((grant) => (
                    <tr key={grant.id}>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.grant_type}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.grant_date}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.amount.toLocaleString()}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.reason}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                        {grant.calculation?.grant_exempt.toLocaleString()}
                      </td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                        {grant.calculation?.grant_taxable.toLocaleString()}
                      </td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                        {grant.calculation?.tax_due.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CurrentEmployer;
