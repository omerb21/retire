import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import axios from 'axios';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../utils/dateUtils';

interface Grant {
  id?: number;
  employer_name: string;
  work_start_date: string;
  work_end_date: string;
  grant_type: string;
  grant_date: string;
  amount?: number;       // שדה מהשרת
  grant_amount?: number; // שדה מהקליינט
  reason?: string;
  tax_calculation?: {
    grant_exempt: number;
    grant_taxable: number;
    tax_due: number;
  };
}

const SimpleGrants: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [grants, setGrants] = useState<Grant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [grantDetails, setGrantDetails] = useState<{[key: number]: any}>({});
  const [newGrant, setNewGrant] = useState<Grant>({
    employer_name: '',
    work_start_date: '',
    work_end_date: '',
    grant_type: 'severance',
    grant_date: '',
    grant_amount: 0,
    amount: 0,
    reason: ''
  });

  // Load grants on component mount
  useEffect(() => {
    const fetchGrants = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/v1/clients/${id}/grants`);
        // Ensure we have an array, even if the response is not in the expected format
        let grantsData = [];
        if (Array.isArray(response.data)) {
          grantsData = response.data;
        } else if (response.data && typeof response.data === 'object') {
          // If the response is an object, try to extract an array from it
          const data = response.data;
          if (Array.isArray(data.grants)) {
            grantsData = data.grants;
          } else if (Array.isArray(data.items)) {
            grantsData = data.items;
          } else if (data.data && Array.isArray(data.data)) {
            grantsData = data.data;
          } else {
            // If we can't find an array, log the response for debugging
            console.warn('Unexpected grants API response format:', response.data);
          }
        }
        
        console.log('Grants data loaded:', grantsData);
        setGrants(grantsData);
        
        // Calculate details for each grant
        grantsData.forEach((grant: Grant) => {
          // התאמת שדות - אם יש amount אבל אין grant_amount, העתק את הערך
          if (grant.amount !== undefined && grant.grant_amount === undefined) {
            grant.grant_amount = grant.amount;
          }
          // התאמת שדות - אם יש grant_amount אבל אין amount, העתק את הערך
          if (grant.grant_amount !== undefined && grant.amount === undefined) {
            grant.amount = grant.grant_amount;
          }
          calculateGrantDetails(grant);
        });
      } catch (err) {
        console.error('Error loading grants:', err);
        setError('שגיאה בטעינת המענקים');
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchGrants();
    }
  }, [id]);

  // Calculate service years and tax details
  const calculateGrantDetails = async (grant: Grant) => {
    if (!grant.work_start_date || !grant.work_end_date || !grant.id) return;

    const startDate = new Date(grant.work_start_date);
    const endDate = new Date(grant.work_end_date);
    const serviceYears = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
    
    // וודא שיש ערך לסכום המענק (בין אם בשדה amount או grant_amount)
    const grantAmount = grant.grant_amount || grant.amount || 0;
    
    try {
      // Get official severance exemption from API
      const response = await axios.get('/api/v1/tax-data/severance-exemption', {
        params: { service_years: serviceYears }
      });
      
      const maxExemption = response.data.total_exemption;
      const exemptAmount = Math.min(grantAmount, maxExemption);
      const taxableAmount = Math.max(0, grantAmount - exemptAmount);
      
      // Tax calculation on taxable amount (assuming 10% tax rate for simplicity)
      const taxRate = 0.10;
      const taxOwed = taxableAmount * taxRate;
      
      const details = {
        serviceYears: Math.round(serviceYears * 100) / 100,
        taxExemptAmount: Math.round(exemptAmount),
        taxableAmount: Math.round(taxableAmount),
        taxDue: Math.round(taxOwed)
      };
      
      setGrantDetails(prev => ({ ...prev, [grant.id!]: details }));
    } catch (error) {
      console.error('Error fetching tax data:', error);
      // Fallback to hardcoded values if API fails
      const fallbackCap = 41667;
      // Simple tax calculation fallback
      const grantAmount = grant.grant_amount || grant.amount || 0;
      const exemptAmount = Math.min(grantAmount, fallbackCap * serviceYears);
      const taxableAmount = Math.max(0, grantAmount - exemptAmount);
      
      const taxRate = 0.10;
      const taxOwed = taxableAmount * taxRate;
      
      const details = {
        serviceYears: Math.round(serviceYears * 100) / 100,
        taxExemptAmount: Math.round(exemptAmount),
        taxableAmount: Math.round(taxableAmount),
        taxDue: Math.round(taxOwed)
      };
      
      setGrantDetails(prev => ({ ...prev, [grant.id!]: details }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      setError(null);

      // Validate required fields
      if (!newGrant.employer_name || !newGrant.work_start_date || !newGrant.work_end_date || 
          !newGrant.grant_date || (newGrant.grant_amount || 0) <= 0) {
        throw new Error('יש למלא את כל השדות הנדרשים');
      }

      // Convert dates to ISO format
      const workStartDateISO = convertDDMMYYToISO(newGrant.work_start_date);
      const workEndDateISO = convertDDMMYYToISO(newGrant.work_end_date);
      const grantDateISO = convertDDMMYYToISO(newGrant.grant_date);
      
      if (!workStartDateISO || !workEndDateISO || !grantDateISO) {
        throw new Error('תאריכים לא תקינים - יש להזין בפורמט DD/MM/YYYY');
      }

      await axios.post(`/api/v1/clients/${id}/grants`, {
        ...newGrant,
        work_start_date: workStartDateISO,
        work_end_date: workEndDateISO,
        grant_date: grantDateISO
      });

      // Reset form
      setNewGrant({
        employer_name: '',
        work_start_date: '',
        work_end_date: '',
        grant_type: 'severance',
        grant_date: '',
        grant_amount: 0,
        amount: 0,
        reason: ''
      });

      // Reload grants
      const response = await axios.get(`/api/v1/clients/${id}/grants`);
      setGrants(response.data || []);

      alert('מענק נוסף בהצלחה');
    } catch (err: any) {
      setError('שגיאה בהוספת מענק: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setNewGrant(prev => ({
      ...prev,
      [name]: name === 'grant_amount' || name === 'amount' ? parseFloat(value) || 0 : value
    }));
    
    // אם מעדכנים את שדה grant_amount, עדכן גם את שדה amount
    if (name === 'grant_amount') {
      setNewGrant(prev => ({ ...prev, amount: parseFloat(value) || 0 }));
    }
    // אם מעדכנים את שדה amount, עדכן גם את שדה grant_amount
    if (name === 'amount') {
      setNewGrant(prev => ({ ...prev, grant_amount: parseFloat(value) || 0 }));
    }
  };

  const handleDelete = async (grantId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את המענק?')) return;

    try {
      setLoading(true);
      await axios.delete(`/api/v1/clients/${id}/grants/${grantId}`);
      
      // Reload grants
      const response = await axios.get(`/api/v1/clients/${id}/grants`);
      setGrants(response.data || []);
      
      alert('מענק נמחק בהצלחה');
    } catch (err: any) {
      setError('שגיאה במחיקת מענק: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💰 מענקים ממעסיקים קודמים</h1>
            <p className="card-subtitle">ניהול מענקי פיצויים מכל מעסיקי העבר</p>
          </div>
          <button onClick={() => navigate(`/clients/${id}`)} className="btn btn-secondary">
            ← חזרה
          </button>
        </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {/* Add new grant form */}
      <div style={{ marginTop: '2rem', padding: '1.5rem', backgroundColor: 'var(--gray-50)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--gray-200)' }}>
        <h3 style={{ marginBottom: '1.5rem', color: 'var(--gray-700)', fontSize: '1.25rem' }}>➕ הוספת מענק חדש</h3>
        
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                שם מעסיק:
              </label>
              <input
                type="text"
                name="employer_name"
                value={newGrant.employer_name}
                onChange={handleInputChange}
                required
                className="form-input"
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                סוג מענק:
              </label>
              <select
                name="grant_type"
                value={newGrant.grant_type}
                onChange={handleInputChange}
                className="form-select"
              >
                <option value="severance">פיצויים</option>
                <option value="bonus">בונוס</option>
                <option value="pension">פנסיה</option>
                <option value="other">אחר</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                תאריך התחלת עבודה:
              </label>
              <input
                type="text"
                name="work_start_date"
                placeholder="DD/MM/YYYY"
                value={newGrant.work_start_date || ''}
                onChange={(e) => {
                  const formatted = formatDateInput(e.target.value);
                  setNewGrant({ ...newGrant, work_start_date: formatted });
                }}
                required
                maxLength={10}
                className="form-input"
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                תאריך סיום עבודה:
              </label>
              <input
                type="text"
                name="work_end_date"
                placeholder="DD/MM/YYYY"
                value={newGrant.work_end_date || ''}
                onChange={(e) => {
                  const formatted = formatDateInput(e.target.value);
                  setNewGrant({ ...newGrant, work_end_date: formatted });
                }}
                required
                maxLength={10}
                className="form-input"
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                תאריך קבלת מענק:
              </label>
              <input
                type="text"
                name="grant_date"
                placeholder="DD/MM/YYYY"
                value={newGrant.grant_date || ''}
                onChange={(e) => {
                  const formatted = formatDateInput(e.target.value);
                  setNewGrant({ ...newGrant, grant_date: formatted });
                }}
                required
                maxLength={10}
                className="form-input"
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                סכום מענק (₪):
              </label>
              <input
                type="number"
                name="grant_amount"
                value={newGrant.grant_amount}
                onChange={handleInputChange}
                required
                min="0"
                className="form-input"
              />
            </div>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              הערות (אופציונלי):
            </label>
            <textarea
              name="reason"
              value={newGrant.reason}
              onChange={handleInputChange}
              rows={3}
              className="form-textarea"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-success"
          >
            {loading ? 'מוסיף...' : '➕ הוסף מענק'}
          </button>
        </form>
      </div>

      {/* Grants list */}
      <div>
        <h3>רשימת מענקים</h3>
        
        {grants.length === 0 ? (
          <div style={{ 
            padding: '20px', 
            backgroundColor: '#f8f9fa', 
            borderRadius: '4px',
            textAlign: 'center',
            color: '#666'
          }}>
            אין מענקים רשומים
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '15px' }}>
            {grants.map((grant, index) => {
              const details = grant.id ? grantDetails[grant.id] : null;
              
              return (
                <div 
                  key={grant.id || index}
                  style={{ 
                    padding: '20px', 
                    border: '1px solid #ddd', 
                    borderRadius: '4px',
                    backgroundColor: 'white'
                  }}
                >
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '15px', alignItems: 'start' }}>
                    <div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
                        <div><strong>מעסיק:</strong> {grant.employer_name}</div>
                        <div><strong>תקופת עבודה:</strong> {formatDateToDDMMYY(new Date(grant.work_start_date))} - {formatDateToDDMMYY(new Date(grant.work_end_date))}</div>
                        <div><strong>תאריך מענק:</strong> {formatDateToDDMMYY(new Date(grant.grant_date))}</div>
                      </div>
                      
                      <div style={{ marginBottom: '10px' }}>
                        <div><strong>סכום מענק:</strong> ₪{(grant.grant_amount || grant.amount || 0).toLocaleString()}</div>
                      </div>

                      {details && (
                        <div style={{ 
                          padding: '10px', 
                          backgroundColor: '#f8fff9', 
                          borderRadius: '4px',
                          border: '1px solid #d4edda'
                        }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '14px' }}>
                            <div><strong>שנות שירות:</strong> {details.serviceYears}</div>
                            {details.taxDue > 0 && (
                              <div style={{ color: '#dc3545' }}>
                                <strong>מס משוער:</strong> ₪{details.taxDue.toLocaleString()}
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {grant.reason && (
                        <div style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                          <strong>הערות:</strong> {grant.reason}
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => grant.id && handleDelete(grant.id)}
                      style={{
                        backgroundColor: '#dc3545',
                        color: 'white',
                        border: 'none',
                        padding: '8px 12px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '14px'
                      }}
                    >
                      מחק
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div style={{ 
        marginTop: '30px', 
        padding: '15px', 
        backgroundColor: '#e9ecef', 
        borderRadius: '4px',
        fontSize: '14px'
      }}>
        <strong>הסבר:</strong> המערכת מחשבת את הפטור ממס בהתאם לחוק (עד 375,000 ₪). 
        חשוב לוודא שתאריכי העבודה נכונים לחישוב מדויק של שנות השירות.
        הסכומים הפטורים ממס נלקחים בחשבון בחישוב קיבוע המס הכללי.
      </div>
      </div>
    </div>
  );
};

export default SimpleGrants;
