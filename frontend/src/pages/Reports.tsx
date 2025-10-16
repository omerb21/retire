import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface Scenario {
  id: number;
  scenario_name: string;
  client_id: number;
  created_at: string;
}

interface ReportRequest {
  scenario_ids: number[];
  report_type: string;
  include_charts: boolean;
  include_cashflow: boolean;
}

const Reports: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarios, setSelectedScenarios] = useState<number[]>([]);
  const [reportType, setReportType] = useState<string>('comprehensive');
  const [includeCharts, setIncludeCharts] = useState<boolean>(true);
  const [includeCashflow, setIncludeCashflow] = useState<boolean>(true);

  // Fetch scenarios for the client
  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/v1/clients/${id}/scenarios`);
        setScenarios(response.data || []);
        setLoading(false);
      } catch (err: any) {
        setError('שגיאה בטעינת תרחישים: ' + err.message);
        setLoading(false);
      }
    };

    if (id) {
      fetchScenarios();
    }
  }, [id]);

  // Handle scenario selection
  const handleScenarioToggle = (scenarioId: number) => {
    setSelectedScenarios(prev => {
      if (prev.includes(scenarioId)) {
        return prev.filter(id => id !== scenarioId);
      } else {
        return [...prev, scenarioId];
      }
    });
  };

  // Generate PDF report
  const handleGenerateReport = async () => {
    if (selectedScenarios.length === 0) {
      setError('יש לבחור לפחות תרחיש אחד');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const reportRequest: ReportRequest = {
        scenario_ids: selectedScenarios,
        report_type: reportType,
        include_charts: includeCharts,
        include_cashflow: includeCashflow
      };

      const response = await axios.post(
        `/api/v1/clients/${id}/reports/generate`,
        reportRequest,
        {
          responseType: 'blob', // Important for PDF download
        }
      );

      // Create blob link to download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Generate filename with timestamp
      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
      link.setAttribute('download', `retirement_report_${id}_${timestamp}.pdf`);
      
      // Append to html link element page
      document.body.appendChild(link);
      
      // Start download
      link.click();
      
      // Clean up and remove the link
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);

      setLoading(false);
      alert('דוח נוצר והורד בהצלחה');

    } catch (err: any) {
      setError('שגיאה ביצירת דוח: ' + err.message);
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>📊 תוצאות</h2>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`}>חזרה לפרטי לקוח</a>
      </div>

      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

      {/* Report Configuration */}
      <div style={{ marginBottom: '40px' }}>
        <h3>הגדרות דוח</h3>
        
        {/* Report Type Selection */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
            סוג דוח:
          </label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
          >
            <option value="comprehensive">דוח מקיף</option>
            <option value="summary">דוח סיכום</option>
            <option value="cashflow">דוח תזרים מזומנים</option>
            <option value="comparison">דוח השוואה</option>
          </select>
        </div>

        {/* Options */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
            אפשרויות נוספות:
          </label>
          
          <div style={{ marginBottom: '10px' }}>
            <label style={{ display: 'flex', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={includeCharts}
                onChange={(e) => setIncludeCharts(e.target.checked)}
                style={{ marginLeft: '8px' }}
              />
              כלול גרפים וטבלאות
            </label>
          </div>
          
          <div style={{ marginBottom: '10px' }}>
            <label style={{ display: 'flex', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={includeCashflow}
                onChange={(e) => setIncludeCashflow(e.target.checked)}
                style={{ marginLeft: '8px' }}
              />
              כלול פירוט תזרים מזומנים
            </label>
          </div>
        </div>
      </div>

      {/* Scenario Selection */}
      <div style={{ marginBottom: '40px' }}>
        <h3>בחירת תרחישים</h3>
        
        {loading ? (
          <p>טוען תרחישים...</p>
        ) : scenarios.length === 0 ? (
          <div style={{ padding: '20px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
            <p>אין תרחישים זמינים לדוח</p>
            <p>יש ליצור תרחיש לפני יצירת דוח</p>
          </div>
        ) : (
          <div>
            <p style={{ marginBottom: '15px', color: '#666' }}>
              בחר את התרחישים שברצונך לכלול בדוח:
            </p>
            
            <div style={{ display: 'grid', gap: '10px' }}>
              {scenarios.map((scenario) => (
                <label
                  key={scenario.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '12px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    backgroundColor: selectedScenarios.includes(scenario.id) ? '#e6f7ff' : 'white',
                    cursor: 'pointer'
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedScenarios.includes(scenario.id)}
                    onChange={() => handleScenarioToggle(scenario.id)}
                    style={{ marginLeft: '8px' }}
                  />
                  <div>
                    <div style={{ fontWeight: 'bold' }}>{scenario.scenario_name}</div>
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      נוצר: {new Date(scenario.created_at).toLocaleDateString('he-IL')}
                    </div>
                  </div>
                </label>
              ))}
            </div>
            
            <div style={{ marginTop: '15px', fontSize: '14px', color: '#666' }}>
              נבחרו {selectedScenarios.length} תרחישים
            </div>
          </div>
        )}
      </div>

      {/* Generate Report Button */}
      <div style={{ marginBottom: '40px' }}>
        <button
          onClick={handleGenerateReport}
          disabled={loading || selectedScenarios.length === 0}
          style={{
            backgroundColor: loading || selectedScenarios.length === 0 ? '#6c757d' : '#007bff',
            color: 'white',
            border: 'none',
            padding: '15px 30px',
            borderRadius: '4px',
            fontSize: '16px',
            cursor: loading || selectedScenarios.length === 0 ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'מייצר דוח...' : 'ייצר דוח PDF'}
        </button>
      </div>

      {/* Report Types Description */}
      <div style={{ marginTop: '40px', padding: '20px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
        <h4>תיאור סוגי הדוחות:</h4>
        <ul style={{ marginTop: '10px', paddingRight: '20px' }}>
          <li><strong>דוח מקיף:</strong> כולל את כל הנתונים, חישובים, גרפים ופירוטים</li>
          <li><strong>דוח סיכום:</strong> סיכום תוצאות עיקריות בלבד</li>
          <li><strong>דוח תזרים מזומנים:</strong> מתמקד בתחזיות תזרים מזומנים</li>
          <li><strong>דוח השוואה:</strong> השוואה בין התרחישים הנבחרים</li>
        </ul>
      </div>
    </div>
  );
};

export default Reports;
