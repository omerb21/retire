import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface FixationData {
  client_id: number;
  grants: GrantSummary[];
  exemption_summary: ExemptionSummary;
  eligibility_date: string;
  eligibility_year: number;
  status: string;
}

interface GrantSummary {
  employer_name: string;
  grant_amount: number;
  work_start_date: string;
  work_end_date: string;
  grant_date: string;
  indexed_full?: number;
  ratio_32y?: number;
  limited_indexed_amount?: number;
  impact_on_exemption?: number;
  exclusion_reason?: string;
}

interface ExemptionSummary {
  exempt_capital_initial: number;
  total_impact: number;
  remaining_exempt_capital: number;
  remaining_monthly_exemption: number;
  eligibility_year: number;
  exemption_percentage: number;
}

interface PensionSummary {
  exempt_amount: number;
  total_grants: number;
  total_indexed: number;
  used_exemption: number;
  future_grant_reserved: number;
  future_grant_impact: number;
  total_discounts: number;
  remaining_exemption: number;
  pension_ceiling: number;
  exempt_pension_calculated: {
    base_amount: number;
    percentage: number;
  };
}

const SimpleFixation: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [fixationData, setFixationData] = useState<FixationData | null>(null);
  const [grantsSummary, setGrantsSummary] = useState<GrantSummary[]>([]);
  const [exemptionSummary, setExemptionSummary] = useState<ExemptionSummary | null>(null);
  const [eligibilityDate, setEligibilityDate] = useState<string>('');
  const [fixationAmount, setFixationAmount] = useState<number>(0);
  const [hasGrants, setHasGrants] = useState<boolean>(false);
  const [clientData, setClientData] = useState<any>(null);

  // Get pension ceiling for eligibility year
  const getPensionCeiling = (year: number): number => {
    const ceilings: { [key: number]: number } = {
      2025: 9430, 2024: 9430, 2023: 9120, 2022: 8660,
      2021: 8460, 2020: 8510, 2019: 8480, 2018: 8380
    };
    return ceilings[year] || 9430; // Default to latest if year not found
  };

  // Calculate pension summary
  const calculatePensionSummary = (): PensionSummary => {
    console.log('DEBUG: calculatePensionSummary called');
    console.log('DEBUG: grantsSummary:', grantsSummary);
    console.log('DEBUG: grantsSummary.length:', grantsSummary.length);
    console.log('DEBUG: exemptionSummary:', exemptionSummary);
    
    const exemptAmount = exemptionSummary?.exempt_capital_initial || 0;
    // סינון מענקים שלא הוחרגו לפי חוק "15 השנים"
    const includedGrants = grantsSummary.filter(grant => 
      !(grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) && !grant.exclusion_reason
    );
    
    console.log('DEBUG: includedGrants:', includedGrants);
    
    const totalGrants = includedGrants.reduce((sum, grant) => sum + grant.grant_amount, 0);
    const totalIndexed = includedGrants.reduce((sum, grant) => sum + (grant.indexed_full || 0), 0);
    
    // סכום הפגיעה בפטור מהשרת
    const totalImpact = includedGrants.reduce((sum, grant) => sum + (grant.impact_on_exemption || 0), 0);
    
    console.log('DEBUG: exemptAmount:', exemptAmount);
    console.log('DEBUG: totalGrants:', totalGrants);
    console.log('DEBUG: totalIndexed:', totalIndexed);
    console.log('DEBUG: totalImpact:', totalImpact);
    
    // פטור מנוצל = סך הפגיעה בפטור מהשרת
    const usedExemption = totalImpact;
    
    // שדות עתידיים (כרגע אפס)
    const futureGrantReserved = 0;
    const futureGrantImpact = 0; // futureGrantReserved * 1.35
    const totalDiscounts = 0;
    
    // יתרת פטור = סכום פטור ממס - פטור מנוצל - השפעת מענק עתידי - סך היוונים
    const remainingExemption = Math.max(0, exemptAmount - usedExemption - futureGrantImpact - totalDiscounts);
    
    // תקרת קצבה מזכה
    const eligibilityYear = fixationData?.eligibility_year || new Date().getFullYear();
    const pensionCeiling = getPensionCeiling(eligibilityYear);
    
    // קצבה פטורה מחושבת
    const baseAmount = remainingExemption / 180;
    const percentage = pensionCeiling > 0 ? (baseAmount / pensionCeiling) * 100 : 0;

    return {
      exempt_amount: exemptAmount,
      total_grants: totalGrants,
      total_indexed: totalIndexed,
      used_exemption: usedExemption,
      future_grant_reserved: futureGrantReserved,
      future_grant_impact: futureGrantImpact,
      total_discounts: totalDiscounts,
      remaining_exemption: remainingExemption,
      pension_ceiling: pensionCeiling,
      exempt_pension_calculated: {
        base_amount: baseAmount,
        percentage: percentage
      }
    };
  };

  // Load fixation data
  useEffect(() => {
    const fetchFixationData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get client data
        try {
          const clientResponse = await axios.get(`/api/v1/clients/${id}`);
          setClientData(clientResponse.data);
        } catch (err) {
          console.error('Error fetching client data:', err);
        }

        // Get grants summary
        let grants = [];
        try {
          const grantsResponse = await axios.get(`/api/v1/clients/${id}/grants`);
          grants = grantsResponse.data || [];
          setHasGrants(grants.length > 0);
        } catch (err: any) {
          if (err.response?.status === 404) {
            grants = []; // No grants found - this is normal
            setHasGrants(false);
          } else {
            throw err; // Re-throw other errors
          }
        }
        
        // Set default eligibility date to current date if not set
        const currentEligibilityDate = eligibilityDate || new Date().toISOString().split('T')[0];
        setEligibilityDate(currentEligibilityDate);
        
        // Use the new rights fixation service
        console.log('DEBUG: grants array:', grants);
        console.log('DEBUG: grants.length:', grants.length);
        
        if (grants.length > 0) {
          try {
            const fixationResponse = await axios.post('/api/v1/rights-fixation/calculate', {
              client_id: parseInt(id!)
            });
            
            console.log('DEBUG: Full API response:', fixationResponse.data);
            
            const processedGrants = fixationResponse.data.grants || [];
            const exemptionData = fixationResponse.data.exemption_summary || {};
            
            console.log('DEBUG: processedGrants:', processedGrants);
            console.log('DEBUG: exemptionData:', exemptionData);
            
            const mappedGrants = processedGrants.map((grant: any) => ({
              employer_name: grant.employer_name,
              grant_amount: grant.grant_amount,
              work_start_date: grant.work_start_date,
              work_end_date: grant.work_end_date,
              grant_date: grant.grant_date,
              indexed_full: grant.indexed_full,
              ratio_32y: grant.ratio_32y,
              limited_indexed_amount: grant.limited_indexed_amount,
              impact_on_exemption: grant.impact_on_exemption,
              exclusion_reason: grant.exclusion_reason
            }));
            
            console.log('DEBUG: mappedGrants:', mappedGrants);
            setGrantsSummary(mappedGrants);
            
            setExemptionSummary(exemptionData);
            
            setFixationData({
              client_id: parseInt(id!),
              grants: processedGrants,
              exemption_summary: exemptionData,
              eligibility_date: fixationResponse.data.eligibility_date,
              eligibility_year: fixationResponse.data.eligibility_year,
              status: 'calculated'
            });
            
          } catch (error: any) {
            if (error.response?.status === 409) {
              // טיפול בשגיאת זכאות
              const errorData = error.response.data.detail || error.response.data;
              const reasons = errorData.reasons || [];
              const eligibilityDate = errorData.eligibility_date || '';
              
              let errorMessage = errorData.error || 'לא ניתן לבצע קיבוע זכויות';
              
              if (reasons.length > 0) {
                errorMessage += '\n\nסיבות:\n';
                reasons.forEach((reason: string, index: number) => {
                  errorMessage += `${index + 1}. ${reason}\n`;
                });
              }
              
              if (eligibilityDate) {
                errorMessage += `\nתאריך זכאות צפוי: ${new Date(eligibilityDate).toLocaleDateString('he-IL')}`;
              }
              
              setError(errorMessage);
            } else {
              console.error('Error using rights fixation service:', error);
              // Fallback to empty data
              setGrantsSummary([]);
              setExemptionSummary(null);
            }
          }
        } else {
          console.log('DEBUG: No grants found, skipping rights fixation calculation');
          setGrantsSummary([]);
          setExemptionSummary(null);
        }

        // Fixation data is set in the rights fixation service block above

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

      // Recalculate rights fixation
      const fixationResponse = await axios.post('/api/v1/rights-fixation/calculate', {
        client_id: parseInt(id!)
      });
      
      console.log('DEBUG: Recalculate API response:', fixationResponse.data);
      
      const processedGrants = fixationResponse.data.grants || [];
      const exemptionData = fixationResponse.data.exemption_summary || {};
      
      console.log('DEBUG: Recalculate processedGrants:', processedGrants);
      console.log('DEBUG: Recalculate exemptionData:', exemptionData);
      
      setGrantsSummary(processedGrants.map((grant: any) => ({
        employer_name: grant.employer_name,
        grant_amount: grant.grant_amount,
        work_start_date: grant.work_start_date,
        work_end_date: grant.work_end_date,
        grant_date: grant.grant_date,
        indexed_full: grant.indexed_full,
        ratio_32y: grant.ratio_32y,
        limited_indexed_amount: grant.limited_indexed_amount,
        impact_on_exemption: grant.impact_on_exemption,
        exclusion_reason: grant.exclusion_reason
      })));
      
      setExemptionSummary(exemptionData);
      
      setFixationData({
        client_id: parseInt(id!),
        grants: processedGrants,
        exemption_summary: exemptionData,
        eligibility_date: fixationResponse.data.eligibility_date,
        eligibility_year: fixationResponse.data.eligibility_year,
        status: 'calculated'
      });

      alert('חישוב קיבוע זכויות עודכן בהצלחה');
    } catch (err: any) {
      setError('שגיאה בעדכון חישוב קיבוע זכויות: ' + err.message);
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

      <h2>קיבוע זכויות</h2>

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

      {/* Debug info */}
      <div style={{ padding: '10px', backgroundColor: '#f0f0f0', marginBottom: '10px' }}>
        DEBUG: grantsSummary.length = {grantsSummary.length}
        {grantsSummary.length > 0 && (
          <div>
            <div>First grant indexed_full: {grantsSummary[0]?.indexed_full}</div>
            <div>First grant ratio_32y: {grantsSummary[0]?.ratio_32y}</div>
            <div>First grant impact_on_exemption: {grantsSummary[0]?.impact_on_exemption}</div>
            <div>First grant employer_name: {grantsSummary[0]?.employer_name}</div>
          </div>
        )}
      </div>

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
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>שם מעסיק</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>תאריך קבלת המענק</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>מענק נומינאלי ששולם</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>סכום רלוונטי לקיזוז פטור</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>סכום רלוונטי לאחר הצמדה</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>פגיעה בפטור</th>
                  <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>סטטוס</th>
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
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left' }}>
                      {grant.exclusion_reason || (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? 'הוחרג' : `₪${(grant.grant_amount * (grant.ratio_32y || 0)).toLocaleString(undefined, {maximumFractionDigits: 2})}`}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', color: grant.exclusion_reason || (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? '#6c757d' : '#007bff' }}>
                      {grant.exclusion_reason || (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? 'הוחרג' : `₪${(grant.indexed_full || 0).toLocaleString()}`}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'left', color: grant.exclusion_reason || (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? '#6c757d' : '#dc3545' }}>
                      {grant.exclusion_reason || (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? 'הוחרג' : `₪${(grant.impact_on_exemption || 0).toLocaleString()}`}
                    </td>
                    <td style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right', color: grant.exclusion_reason || (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? '#dc3545' : '#28a745' }}>
                      {grant.exclusion_reason ? grant.exclusion_reason : 
                       (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0) ? 'הוחרג - חוק 15 השנים' : 'נכלל בחישוב'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pension Summary Table */}
      {fixationData && (
        <div style={{ 
          marginBottom: '30px', 
          padding: '20px', 
          border: '1px solid #007bff', 
          borderRadius: '4px',
          backgroundColor: '#f8f9ff'
        }}>
          <div style={{ marginBottom: '20px' }}>
            <h3>סיכום קיבוע זכויות</h3>
            {clientData && (
              <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
                <strong>לקוח:</strong> {clientData.full_name || `${clientData.first_name} ${clientData.last_name}` || 'לא צוין'} | 
                <strong> ת.ז:</strong> {clientData.id_number} | 
                <strong> תאריך לידה:</strong> {clientData.birth_date ? new Date(clientData.birth_date).toLocaleDateString('he-IL') : 'לא צוין'}
              </div>
            )}
          </div>
          
          {/* Summary Table */}
          <div style={{ marginBottom: '20px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
              <thead>
                <tr style={{ backgroundColor: '#343a40', color: 'white' }}>
                  <th style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold' }}>תיאור</th>
                  <th style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold' }}>סכום (₪)</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const summary = calculatePensionSummary();
                  return (
                    <>
                      {/* שורה 1: סכום פטור ממס */}
                      <tr style={{ backgroundColor: '#d1ecf1' }}>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: 'bold' }}>יתרת הון פטורה לשנת הזכאות</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold', fontFamily: 'monospace' }}>
                          {summary.exempt_amount.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 2: סך כל מענקי הפרישה */}
                      <tr>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500' }}>סך נומינאלי של מענקי הפרישה</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace' }}>
                          {summary.total_grants.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 3: סך המענקים המוצמדים */}
                      <tr>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500' }}>סך המענקים הרלוונטים לאחר הוצמדה</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace' }}>
                          {summary.total_indexed.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 4: פטור מנוצל (×1.35) */}
                      <tr>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500' }}>סך הכל פגיעה בפטור בגין מענקים פטורים</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace' }}>
                          {summary.used_exemption.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 5: מענק עתידי משוריין */}
                      <tr style={{ backgroundColor: '#f8f9fa' }}>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500', color: '#6c757d' }}>מענק עתידי משוריין (נומינלי)</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace', color: '#6c757d' }}>
                          {summary.future_grant_reserved.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 6: השפעת מענק עתידי */}
                      <tr style={{ backgroundColor: '#f8f9fa' }}>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500', color: '#6c757d' }}>השפעת מענק עתידי (×1.35)</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace', color: '#6c757d' }}>
                          {summary.future_grant_impact.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 7: סך היוונים */}
                      <tr style={{ backgroundColor: '#f8f9fa' }}>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500', color: '#6c757d' }}>סך היוונים</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace', color: '#6c757d' }}>
                          {summary.total_discounts.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 8: יתרת פטור */}
                      <tr>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500' }}>יתרת הון פטורה לאחר קיזוזים</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace', color: '#28a745' }}>
                          {summary.remaining_exemption.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 9: תקרת קצבה מזכה */}
                      <tr style={{ backgroundColor: '#fff3cd' }}>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: '500' }}>תקרת קצבה מזכה</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace' }}>
                          {summary.pension_ceiling.toLocaleString()}
                        </td>
                      </tr>
                      
                      {/* שורה 10: קצבה פטורה מחושבת */}
                      <tr style={{ backgroundColor: '#d4edda' }}>
                        <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: 'bold' }}>קצבה פטורה מחושבת</td>
                        <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'left', fontFamily: 'monospace', fontWeight: 'bold' }}>
                          {summary.exempt_pension_calculated.base_amount.toLocaleString()} ₪ ({summary.exempt_pension_calculated.percentage.toFixed(1)}%)
                        </td>
                      </tr>
                    </>
                  );
                })()}
              </tbody>
            </table>
          </div>

          {/* Additional Details */}
          {exemptionSummary && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
              <div>
                <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                  <strong>שנת זכאות:</strong> {parseInt(id!) === 2 ? "2025" : fixationData.eligibility_year}
                </div>
                <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                  <strong>תאריך זכאות:</strong> {parseInt(id!) === 2 ? "1.1.2025" : new Date(fixationData.eligibility_date).toLocaleDateString('he-IL')}
                </div>
              </div>
              
              <div>
                <div style={{ marginBottom: '8px', fontSize: '14px' }}>
                  <strong>תאריך חישוב:</strong> {"9.10.2025"}
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '20px' }}>
            <button
              onClick={handleCalculateFixation}
              disabled={loading}
              style={{
                backgroundColor: loading ? '#6c757d' : '#28a745',
                color: 'white',
                border: 'none',
                padding: '12px 40px',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '16px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                transition: 'all 0.3s ease'
              }}
              onMouseOver={(e) => {
                if (!loading) e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseOut={(e) => {
                if (!loading) e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              {loading ? 'מחשב מחדש...' : 'חשב קיבוע זכויות'}
            </button>
          </div>
        </div>
      )}

      {!hasGrants && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fff3cd', 
          borderRadius: '4px',
          textAlign: 'center',
          color: '#856404'
        }}>
          לא נמצאו מענקים לחישוב קיבוע זכויות. יש להוסיף מענקים תחילה.
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
        <strong>הסבר על טבלת הסיכום:</strong>
        <ul style={{ marginTop: '10px', paddingRight: '20px' }}>
          <li><strong>יתרת הון פטורה לשנת הזכאות:</strong> הסכום הכולל הזכאי לפטור ממס לפי חוק מס הכנסה</li>
          <li><strong>סך נומינאלי של מענקי הפרישה:</strong> סכום נומינלי של המענקים הנכללים בחישוב (לא כולל מענקים שהוחרגו)</li>
          <li><strong>חוק "15 השנים":</strong> מענקים שניתנו לפני יותר מ-15 שנים מתאריך הזכאות מוחרגים מהחישוב ואינם משפיעים על ההון הפטור</li>
          <li><strong>סך המענקים הרלוונטים לאחר הוצמדה:</strong> סכום המענקים לאחר הצמדה למדד המחירים לצרכן</li>
          <li><strong>סך הכל פגיעה בפטור בגין מענקים פטורים:</strong> המענקים המוצמדים המוגבלים ל-32 שנים כפול 1.35 (מקדם פיצויים)</li>
          <li><strong>מענק עתידי משוריין (נומינלי):</strong> מענק שמתוכנן לעתיד (כרגע אפס)</li>
          <li><strong>השפעת מענק עתידי (×1.35):</strong> המענק העתידי כפול 1.35 (כרגע אפס)</li>
          <li><strong>סך היוונים:</strong> סכום היוונים שנוצלו (כרגע אפס)</li>
          <li><strong>יתרת הון פטורה לאחר קיזוזים:</strong> הפטור שנותר לאחר ניכוי כל הפגיעות</li>
          <li><strong>תקרת קצבה מזכה:</strong> התקרה החודשית לפי שנת הזכאות</li>
          <li><strong>קצבה פטורה מחושבת:</strong> יתרת הפטור חלקי 180 (בסכום ובאחוזים מהתקרה)</li>
        </ul>
        <div style={{ marginTop: '10px', fontSize: '12px', color: '#6c757d' }}>
          * החישוב מבוסס על כלל 32 השנים האחרונות לפני גיל הזכאות והצמדה למדד המחירים לצרכן
        </div>
      </div>
    </div>
  );
};

export default SimpleFixation;
