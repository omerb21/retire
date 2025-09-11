import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface ReportData {
  client_info: {
    name: string;
    id_number: string;
  };
  grants_summary: {
    total_grants: number;
    total_exempt: number;
    total_taxable: number;
    estimated_tax: number;
  };
  cashflow_projection: Array<{
    date: string;
    amount: number;
    source: string;
  }>;
  yearly_totals: {
    total_income: number;
    total_tax: number;
    net_income: number;
  };
}

const SimpleReports: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  // Load report data
  useEffect(() => {
    const fetchReportData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get client info
        const clientResponse = await axios.get(`/api/v1/clients/${id}`);
        const client = clientResponse.data;

        // Get grants summary
        const grantsResponse = await axios.get(`/api/v1/clients/${id}/grants`);
        const grants = grantsResponse.data || [];
        
        // Calculate grants summary
        let totalGrants = 0;
        let totalExempt = 0;
        let totalTaxable = 0;
        
        grants.forEach((grant: any) => {
          const maxExemption = 375000;
          const exemptAmount = Math.min(grant.grant_amount, maxExemption);
          const taxableAmount = Math.max(0, grant.grant_amount - exemptAmount);
          
          totalGrants += grant.grant_amount;
          totalExempt += exemptAmount;
          totalTaxable += taxableAmount;
        });

        const estimatedTax = totalTaxable * 0.25;

        // Get scenarios for cashflow
        const scenariosResponse = await axios.get(`/api/v1/clients/${id}/scenarios`);
        const scenarios = scenariosResponse.data || [];
        
        // Mock cashflow data (in real system, this would come from actual calculations)
        const mockCashflow = Array.from({ length: 12 }, (_, i) => ({
          date: new Date(2024, i, 1).toISOString().split('T')[0],
          amount: Math.round((totalGrants / 12) + Math.random() * 10000),
          source: i < 6 ? 'פנסיה' : 'מענקים'
        }));

        const yearlyTotals = {
          total_income: totalGrants,
          total_tax: estimatedTax,
          net_income: totalGrants - estimatedTax
        };

        setReportData({
          client_info: {
            name: client.name || 'לא צוין',
            id_number: client.id_number || 'לא צוין'
          },
          grants_summary: {
            total_grants: totalGrants,
            total_exempt: totalExempt,
            total_taxable: totalTaxable,
            estimated_tax: estimatedTax
          },
          cashflow_projection: mockCashflow,
          yearly_totals: yearlyTotals
        });

        setLoading(false);
      } catch (err: any) {
        setError('שגיאה בטעינת נתוני דוח: ' + err.message);
        setLoading(false);
      }
    };

    if (id) {
      fetchReportData();
    }
  }, [id]);

  const handleGeneratePDF = async () => {
    if (!reportData) return;

    try {
      setLoading(true);
      setError(null);

      // Generate PDF report using the correct API endpoint
      // First create a scenario if none exists
      let scenarioId = 1; // Default scenario ID
      try {
        const scenarioResponse = await axios.get(`/api/v1/clients/${id}/scenarios`);
        const scenarios = Array.isArray(scenarioResponse.data) ? scenarioResponse.data : (scenarioResponse.data?.scenarios || []);
        if (scenarios.length === 0) {
          // Create a default scenario
          const newScenario = await axios.post(`/api/v1/clients/${id}/scenarios`, {
            name: "דוח ברירת מחדל",
            parameters: "{}",
            description: "תרחיש ברירת מחדל ליצירת דוח"
          });
          scenarioId = newScenario.data.id;
        } else {
          scenarioId = scenarios[0].id;
        }
      } catch (e) {
        console.warn('Could not get/create scenario, using default ID');
      }
      
      // Use the correct API endpoint for PDF generation
      const response = await axios.post(`/api/v1/clients/${id}/reports/pdf`, {
        scenario_id: scenarioId,
        report_type: "comprehensive",
        include_charts: true,
        include_cashflow: true
      }, {
        responseType: 'blob'
      });

      // Create blob URL for PDF
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      setPdfUrl(url);

      // Also trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = `retirement_report_${id}_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      alert('דוח PDF נוצר בהצלחה');
    } catch (err: any) {
      setError('שגיאה ביצירת דוח PDF: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateExcel = async () => {
    if (!reportData) return;

    try {
      setLoading(true);
      setError(null);

      // Generate Excel report
      const response = await axios.post(`/api/v1/clients/${id}/reports/excel`, {
        report_data: reportData
      }, {
        responseType: 'blob'
      });

      // Create blob URL for Excel
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const url = window.URL.createObjectURL(blob);

      // Trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = `retirement_report_${id}_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      alert('דוח Excel נוצר בהצלחה');
    } catch (err: any) {
      setError('שגיאה ביצירת דוח Excel: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !reportData) {
    return <div style={{ padding: '20px' }}>טוען נתוני דוח...</div>;
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </a>
      </div>

      <h2>דוחות</h2>

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

      {/* Report Generation Controls */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        border: '1px solid #007bff', 
        borderRadius: '4px',
        backgroundColor: '#f8f9ff'
      }}>
        <h3>יצירת דוחות</h3>
        
        <div style={{ display: 'flex', gap: '15px', marginBottom: '15px' }}>
          <button
            onClick={handleGeneratePDF}
            disabled={loading || !reportData}
            style={{
              backgroundColor: loading ? '#6c757d' : '#dc3545',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {loading ? 'יוצר...' : 'יצירת דוח PDF'}
          </button>

          <button
            onClick={handleGenerateExcel}
            disabled={loading || !reportData}
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
            {loading ? 'יוצר...' : 'יצירת דוח Excel'}
          </button>
        </div>

        {pdfUrl && (
          <div style={{ marginTop: '15px' }}>
            <a 
              href={pdfUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: '#007bff', textDecoration: 'none' }}
            >
              📄 צפה בדוח PDF שנוצר
            </a>
          </div>
        )}
      </div>

      {/* Report Preview */}
      {reportData && (
        <div>
          <h3>תצוגה מקדימה של הדוח</h3>
          
          {/* Client Info */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>פרטי לקוח</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div><strong>שם:</strong> {reportData.client_info.name}</div>
              <div><strong>ת.ז.:</strong> {reportData.client_info.id_number}</div>
            </div>
          </div>

          {/* Grants Summary */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>סיכום מענקים</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div><strong>סך כל מענקים:</strong> ₪{reportData.grants_summary.total_grants.toLocaleString()}</div>
              <div style={{ color: '#28a745' }}><strong>סך פטור ממס:</strong> ₪{reportData.grants_summary.total_exempt.toLocaleString()}</div>
              <div style={{ color: '#dc3545' }}><strong>סך חייב במס:</strong> ₪{reportData.grants_summary.total_taxable.toLocaleString()}</div>
              <div style={{ color: '#dc3545' }}><strong>מס משוער:</strong> ₪{reportData.grants_summary.estimated_tax.toLocaleString()}</div>
            </div>
          </div>

          {/* Yearly Totals */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>סיכום שנתי</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
              <div><strong>סך הכנסות:</strong> ₪{reportData.yearly_totals.total_income.toLocaleString()}</div>
              <div style={{ color: '#dc3545' }}><strong>סך מסים:</strong> ₪{reportData.yearly_totals.total_tax.toLocaleString()}</div>
              <div style={{ color: '#28a745' }}><strong>הכנסה נטו:</strong> ₪{reportData.yearly_totals.net_income.toLocaleString()}</div>
            </div>
          </div>

          {/* Cashflow Preview */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>תחזית תזרים מזומנים (12 חודשים)</h4>
            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#e9ecef' }}>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>תאריך</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>סכום</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>מקור</th>
                  </tr>
                </thead>
                <tbody>
                  {reportData.cashflow_projection.slice(0, 6).map((entry, index) => (
                    <tr key={index}>
                      <td style={{ padding: '8px', border: '1px solid #ddd' }}>
                        {new Date(entry.date).toLocaleDateString('he-IL')}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left' }}>
                        ₪{entry.amount.toLocaleString()}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd' }}>{entry.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {reportData.cashflow_projection.length > 6 && (
                <div style={{ padding: '10px', textAlign: 'center', color: '#666' }}>
                  ועוד {reportData.cashflow_projection.length - 6} חודשים...
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {!reportData && !loading && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fff3cd', 
          borderRadius: '4px',
          textAlign: 'center',
          color: '#856404'
        }}>
          אין מספיק נתונים ליצירת דוח. יש להוסיף מענקים ותרחישים תחילה.
          <div style={{ marginTop: '10px' }}>
            <a href={`/clients/${id}/grants`} style={{ color: '#007bff', textDecoration: 'none', marginRight: '15px' }}>
              הוסף מענקים ←
            </a>
            <a href={`/clients/${id}/scenarios`} style={{ color: '#007bff', textDecoration: 'none' }}>
              הוסף תרחישים ←
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
        <strong>הסבר:</strong> הדוחות מבוססים על כלל הנתונים שהוזנו במערכת - מענקים, תרחישים, וחישובי מס. 
        דוח ה-PDF מכיל את כל הפרטים כולל גרפים וטבלאות מפורטות. 
        דוח ה-Excel מאפשר עיבוד נוסף של הנתונים.
      </div>
    </div>
  );
};

export default SimpleReports;
