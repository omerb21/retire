import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface Grant {
  id?: number;
  employer_name: string;
  work_start_date: string;
  work_end_date: string;
  grant_type: string;
  grant_date: string;
  amount: number;
  service_years?: number;
  reason?: string;
  tax_calculation?: {
    grant_exempt: number;
    grant_taxable: number;
    tax_due: number;
  };
}

interface NewGrant {
  employer_name: string;
  grant_type: string;
  grant_date: string;
  amount: number;
  service_years?: number;
  reason?: string;
  work_start_date?: string;
  work_end_date?: string;
}

const Grants: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [newGrant, setNewGrant] = useState<NewGrant>({
    employer_name: '',
    grant_type: 'severance',
    grant_date: '',
    amount: 0,
    service_years: 0,
    reason: '',
    work_start_date: '',
    work_end_date: ''
  });

  // Fetch grants data on component mount
  useEffect(() => {
    fetchGrants();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch grants data function (extracted for reuse)
  const fetchGrants = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/v1/clients/${id}/grants`);
      setGrants(response.data);
      setLoading(false);
    } catch (err: any) {
      setError('שגיאה בטעינת נתוני מענקים: ' + err.message);
      setLoading(false);
    }
  };

  // Handle grant form submission
  const handleGrantSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const response = await axios.post(`/api/v1/clients/${id}/grants`, newGrant);
      
      // איפוס טופס המענק החדש
      setNewGrant({
        employer_name: '',
        grant_type: 'severance',
        grant_date: '',
        amount: 0,
        service_years: 0,
        reason: '',
        work_start_date: '',
        work_end_date: ''
      });
      
      setLoading(false);
      alert('מענק נוסף בהצלחה');
      
      // רענון הנתונים מהשרת לאחר הוספת מענק
      fetchGrants();
    } catch (err: any) {
      setError('שגיאה בהוספת מענק: ' + err.message);
      setLoading(false);
    }
  };

  // Handle grant deletion
  const handleDeleteGrant = async (grantId: number) => {
    if (!window.confirm('האם אתה בטוח שברצונך למחוק מענק זה?')) {
      return;
    }

    try {
      await axios.delete(`/api/v1/clients/${id}/grants/${grantId}`);
      setGrants(grants.filter(grant => grant.id !== grantId));
      alert('מענק נמחק בהצלחה');
    } catch (err: any) {
      setError('שגיאה במחיקת מענק: ' + err.message);
    }
  };

  return (
    <div>
      <h2>מענקים פטורים שהתקבלו</h2>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`}>חזרה לפרטי לקוח</a>
      </div>

      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

      {/* Add New Grant Form */}
      <div style={{ marginBottom: '40px' }}>
        <h3>הוספת מענק חדש</h3>
        <form onSubmit={handleGrantSubmit}>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>שם מעסיק:</label>
            <input
              type="text"
              value={newGrant.employer_name}
              onChange={(e) => setNewGrant({ ...newGrant, employer_name: e.target.value })}
              style={{ width: '100%', padding: '8px' }}
              required
            />
          </div>

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
            <label style={{ display: 'block', marginBottom: '5px' }}>שנות שירות:</label>
            <input
              type="number"
              value={newGrant.service_years}
              onChange={(e) => setNewGrant({ ...newGrant, service_years: Number(e.target.value) })}
              style={{ width: '100%', padding: '8px' }}
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
        <h3>רשימת מענקים</h3>
        {loading ? (
          <p>טוען נתונים...</p>
        ) : grants.length === 0 ? (
          <p>אין מענקים רשומים</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>מעסיק</th>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>תאריך</th>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>סכום</th>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>שנות שירות</th>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>סיבה</th>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>מס לתשלום</th>
                <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'right' }}>פעולות</th>
              </tr>
            </thead>
            <tbody>
              {grants.map((grant) => (
                <tr key={grant.id}>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.employer_name}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.grant_date}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.amount.toLocaleString()}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.service_years}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{grant.reason}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                    {grant.tax_calculation?.tax_due.toLocaleString() || '-'}
                  </td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                    <button
                      onClick={() => handleDeleteGrant(grant.id!)}
                      style={{
                        backgroundColor: '#dc3545',
                        color: 'white',
                        border: 'none',
                        padding: '5px 10px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                    >
                      מחק
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default Grants;
