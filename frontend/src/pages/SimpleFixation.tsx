import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface FixationData {
  client_id: number;
  total_grants: number;
  total_exempt: number;
  total_taxable: number;
  estimated_tax: number;
  fixation_amount: number;
  status: string;
}

interface GrantSummary {
  employer_name: string;
  grant_amount: number;
  exempt_amount: number;
  taxable_amount: number;
  grant_date: string;
}

const SimpleFixation: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [fixationData, setFixationData] = useState<FixationData | null>(null);
  const [grantsSummary, setGrantsSummary] = useState<GrantSummary[]>([]);
  const [fixationAmount, setFixationAmount] = useState<number>(0);

  // Load fixation data
  useEffect(() => {
    const fetchFixationData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get grants summary
        let grants = [];
        try {
          const grantsResponse = await axios.get(`/api/v1/clients/${id}/grants`);
          grants = grantsResponse.data || [];
        } catch (err: any) {
          if (err.response?.status === 404) {
            grants = []; // No grants found - this is normal
          } else {
            throw err; // Re-throw other errors
          }
        }
        
        // Calculate totals
        let totalGrants = 0;
        let totalExempt = 0;
        let totalTaxable = 0;
        
        const summary: GrantSummary[] = await Promise.all(grants.map(async (grant: any) => {
          let exemptAmount = 0;
          let taxableAmount = grant.grant_amount;
          let indexedAmount = grant.grant_amount;
          
          if (grant.work_start_date && grant.work_end_date) {
            const startDate = new Date(grant.work_start_date);
            const endDate = new Date(grant.work_end_date);
            const serviceYears = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
            
            try {
              // Get exact grant calculation with indexation
              const exactCalcResponse = await axios.post('/api/v1/indexation/calculate-exact', {
                grant_amount: grant.grant_amount,
                work_start_date: grant.work_start_date,
                work_end_date: grant.work_end_date,
                eligibility_date: null // Will use current date
              });
              
              if (exactCalcResponse.data && !exactCalcResponse.data.error) {
                indexedAmount = exactCalcResponse.data.indexed_amount;
                
                // Get official severance exemption from API
                const exemptionResponse = await axios.get('/api/v1/tax-data/severance-exemption', {
                  params: { service_years: serviceYears }
                });
                
                const maxExemption = exemptionResponse.data.total_exemption;
                exemptAmount = Math.min(indexedAmount, maxExemption);
                taxableAmount = Math.max(0, indexedAmount - exemptAmount);
              } else {
                // Fallback to simple calculation
                const exemptionResponse = await axios.get('/api/v1/tax-data/severance-exemption', {
                  params: { service_years: serviceYears }
                });
                
                const maxExemption = exemptionResponse.data.total_exemption;
                exemptAmount = Math.min(grant.grant_amount, maxExemption);
                taxableAmount = Math.max(0, grant.grant_amount - exemptAmount);
              }
            } catch (error) {
              console.error('Error fetching advanced tax calculation:', error);
              // Fallback to hardcoded values
              const fallbackCap = 41667;
              const maxExemption = fallbackCap * serviceYears;
              exemptAmount = Math.min(grant.grant_amount, maxExemption);
              taxableAmount = Math.max(0, grant.grant_amount - exemptAmount);
            }
          }
          
          totalGrants += indexedAmount; // Use indexed amount for totals
          totalExempt += exemptAmount;
          totalTaxable += taxableAmount;
          
          return {
            employer_name: grant.employer_name,
            grant_amount: indexedAmount, // Show indexed amount
            exempt_amount: exemptAmount,
            taxable_amount: taxableAmount,
            grant_date: grant.grant_date
          };
        }));

        setGrantsSummary(summary);
        
        // Calculate estimated tax (25% on taxable amount)
        const estimatedTax = totalTaxable * 0.25;
        
        setFixationData({
          client_id: parseInt(id!),
          total_grants: totalGrants,
          total_exempt: totalExempt,
          total_taxable: totalTaxable,
          estimated_tax: estimatedTax,
          fixation_amount: 0,
          status: 'pending'
        });

        setLoading(false);
      } catch (err: any) {
        setError('שגיאה בטעינת נתוני קיבוע: ' + err.message);
        setLoading(false);
      }
    };

    if (id) {
      fetchFixationData();
    }
  }, [id]);

  const handleCalculateFixation = async () => {
    if (!fixationData) return;

    try {
      setLoading(true);
      setError(null);

      // Calculate fixation based on total taxable amount
      const calculatedFixation = Math.max(0, fixationData.estimated_tax - fixationAmount);
      
      const fixationRequest = {
        client_id: parseInt(id!),
        total_grants: fixationData.total_grants,
        total_exempt: fixationData.total_exempt,
        total_taxable: fixationData.total_taxable,
        estimated_tax: fixationData.estimated_tax,
        fixation_amount: calculatedFixation,
        status: 'calculated'
      };

      // Save fixation calculation using the correct API endpoint
      await axios.post(`/api/v1/fixation/${id}/compute`, fixationRequest);
      
      setFixationData({
        ...fixationData,
        fixation_amount: calculatedFixation,
        status: 'calculated'
      });

      alert('חישוב קיבוע מס הושלם בהצלחה');
    } catch (err: any) {
      setError('שגיאה בחישוב קיבוע מס: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitFixation = async () => {
    if (!fixationData) return;

    try {
      setLoading(true);
      setError(null);

      const submissionData = {
        ...fixationData,
        status: 'submitted',
        submission_date: new Date().toISOString().split('T')[0]
      };

      // Submit fixation using the package endpoint
      await axios.post(`/api/v1/fixation/${id}/package`, submissionData);
      
      setFixationData({
        ...fixationData,
        status: 'submitted'
      });

      alert('קיבוע מס הוגש בהצלחה');
    } catch (err: any) {
      setError('שגיאה בהגשת קיבוע מס: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !fixationData) {
    return <div style={{ padding: '20px' }}>טוען נתוני קיבוע מס...</div>;
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </a>
      </div>

      <h2>קיבוע מס</h2>

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

      {/* Grants Summary */}
      {grantsSummary.length > 0 && (
        <div style={{ 
          marginBottom: '30px', 
          padding: '20px', 
          border: '1px solid #ddd', 
          borderRadius: '4px',
          backgroundColor: '#f9f9f9'
        }}>
          <h3>סיכום מענקים</h3>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '15px' }}>
              <thead>
                <tr style={{ backgroundColor: '#e9ecef' }}>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>מעסיק</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>תאריך</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>סכום כולל</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>פטור ממס</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>חייב במס</th>
                </tr>
              </thead>
              <tbody>
                {grantsSummary.map((grant, index) => (
                  <tr key={index}>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>{grant.employer_name}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd' }}>{grant.grant_date}</td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left' }}>
                      ₪{grant.grant_amount.toLocaleString()}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', color: '#28a745' }}>
                      ₪{grant.exempt_amount.toLocaleString()}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', color: '#dc3545' }}>
                      ₪{grant.taxable_amount.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Fixation Calculation */}
      {fixationData && (
        <div style={{ 
          marginBottom: '30px', 
          padding: '20px', 
          border: '1px solid #007bff', 
          borderRadius: '4px',
          backgroundColor: '#f8f9ff'
        }}>
          <h3>חישוב קיבוע מס</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
            <div>
              <div style={{ marginBottom: '10px' }}>
                <strong>סך כל מענקים:</strong> ₪{fixationData.total_grants.toLocaleString()}
              </div>
              <div style={{ marginBottom: '10px', color: '#28a745' }}>
                <strong>סך פטור ממס:</strong> ₪{fixationData.total_exempt.toLocaleString()}
              </div>
              <div style={{ marginBottom: '10px', color: '#dc3545' }}>
                <strong>סך חייב במס:</strong> ₪{fixationData.total_taxable.toLocaleString()}
              </div>
            </div>
            
            <div>
              <div style={{ marginBottom: '10px', color: '#dc3545' }}>
                <strong>מס משוער (25%):</strong> ₪{fixationData.estimated_tax.toLocaleString()}
              </div>
              <div style={{ marginBottom: '10px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  מס ששולם במקור (₪):
                </label>
                <input
                  type="number"
                  value={fixationAmount}
                  onChange={(e) => setFixationAmount(parseFloat(e.target.value) || 0)}
                  style={{ 
                    width: '100%', 
                    padding: '8px', 
                    border: '1px solid #ccc',
                    borderRadius: '4px'
                  }}
                />
              </div>
              <div style={{ marginBottom: '10px', color: '#6f42c1' }}>
                <strong>יתרת מס לתשלום:</strong> ₪{Math.max(0, fixationData.estimated_tax - fixationAmount).toLocaleString()}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={handleCalculateFixation}
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
              {loading ? 'מחשב...' : 'חשב קיבוע'}
            </button>

            {fixationData.status === 'calculated' && (
              <button
                onClick={handleSubmitFixation}
                disabled={loading}
                style={{
                  backgroundColor: loading ? '#6c757d' : '#28a745',
                  color: 'white',
                  border: 'none',
                  padding: '12px 24px',
                  borderRadius: '4px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '16px'
                }}
              >
                {loading ? 'מגיש...' : 'הגש קיבוע'}
              </button>
            )}
          </div>

          {fixationData.status === 'submitted' && (
            <div style={{ 
              marginTop: '15px', 
              padding: '10px', 
              backgroundColor: '#d4edda', 
              borderRadius: '4px',
              color: '#155724'
            }}>
              ✓ קיבוע מס הוגש בהצלחה
            </div>
          )}
        </div>
      )}

      {grantsSummary.length === 0 && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fff3cd', 
          borderRadius: '4px',
          textAlign: 'center',
          color: '#856404'
        }}>
          לא נמצאו מענקים לחישוב קיבוע מס. יש להוסיף מענקים תחילה.
          <div style={{ marginTop: '10px' }}>
            <a href={`/clients/${id}/grants`} style={{ color: '#007bff', textDecoration: 'none' }}>
              הוסף מענקים ←
            </a>
          </div>
        </div>
      )}

      <div style={{ 
        marginTop: '30px', 
        padding: '15px', 
        backgroundColor: '#e9ecef', 
        borderRadius: '4px',
        fontSize: '14px'
      }}>
        <strong>הסבר:</strong> חישוב קיבוע המס מבוסס על כלל המענקים שהוזנו במערכת. 
        הפטור ממס מחושב בהתאם לחוק (עד 375,000 ₪ למענק). 
        שיעור המס על הסכום החייב הוא 25%. יש להזין את סכום המס ששולם במקור כדי לחשב את יתרת המס לתשלום.
      </div>
    </div>
  );
};

export default SimpleFixation;
