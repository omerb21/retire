/**
 * System Health Monitor - מוניטור תקינות המערכת
 * מציג את סטטוס כל הטבלאות הקריטיות ומאפשר תיקון אוטומטי
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface TableValidation {
  valid: boolean;
  error: string;
  description: string;
}

interface SystemHealthResponse {
  status: 'healthy' | 'unhealthy';
  tables: Record<string, TableValidation>;
  summary: {
    total_tables: number;
    valid_tables: number;
    invalid_tables: number;
  };
  errors: string[];
}

interface AutoFixResponse {
  success: boolean;
  fixed_tables: string[];
  failed_tables: string[];
  message: string;
  remaining_errors?: string[];
}

const SystemHealthMonitor: React.FC = () => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fixing, setFixing] = useState(false);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const response = await axios.get<SystemHealthResponse>('http://localhost:8005/api/v1/system/health');
      setHealth(response.data);
      setLastCheck(new Date());
    } catch (error) {
      console.error('Error checking system health:', error);
    } finally {
      setLoading(false);
    }
  };

  const autoFix = async () => {
    setFixing(true);
    try {
      const response = await axios.post<AutoFixResponse>('http://localhost:8005/api/v1/system/health/fix');
      
      if (response.data.success) {
        alert(`✅ ${response.data.message}\n\nטבלאות שתוקנו: ${response.data.fixed_tables.join(', ') || 'אין'}`);
      } else {
        alert(`⚠️ ${response.data.message}\n\nטבלאות שנכשלו: ${response.data.failed_tables.join(', ')}`);
      }
      
      // רענן את הבדיקה
      await checkHealth();
    } catch (error) {
      console.error('Error auto-fixing system:', error);
      alert('❌ שגיאה בניסיון לתקן את המערכת');
    } finally {
      setFixing(false);
    }
  };

  useEffect(() => {
    checkHealth();
    
    // בדוק כל 5 דקות
    const interval = setInterval(checkHealth, 5 * 60 * 1000);
    
    return () => clearInterval(interval);
  }, []);

  if (loading && !health) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <div style={{ fontSize: '24px', marginBottom: '10px' }}>⏳</div>
        <div>בודק תקינות מערכת...</div>
      </div>
    );
  }

  if (!health) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#dc3545' }}>
        <div style={{ fontSize: '24px', marginBottom: '10px' }}>❌</div>
        <div>שגיאה בבדיקת תקינות המערכת</div>
        <button
          onClick={checkHealth}
          style={{
            marginTop: '15px',
            padding: '10px 20px',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          נסה שוב
        </button>
      </div>
    );
  }

  const isHealthy = health.status === 'healthy';

  return (
    <div style={{ marginBottom: '40px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px'
      }}>
        <h2 style={{ color: '#2c3e50', fontSize: '24px', margin: 0 }}>
          🏥 מוניטור תקינות מערכת
        </h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={checkHealth}
            disabled={loading}
            style={{
              padding: '8px 16px',
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? '⏳ בודק...' : '🔄 רענן'}
          </button>
          {!isHealthy && (
            <button
              onClick={autoFix}
              disabled={fixing}
              style={{
                padding: '8px 16px',
                backgroundColor: '#ffc107',
                color: '#000',
                border: 'none',
                borderRadius: '4px',
                cursor: fixing ? 'not-allowed' : 'pointer',
                opacity: fixing ? 0.6 : 1,
                fontWeight: 'bold'
              }}
            >
              {fixing ? '⏳ מתקן...' : '🔧 תקן אוטומטית'}
            </button>
          )}
        </div>
      </div>

      {/* סטטוס כללי */}
      <div style={{
        padding: '20px',
        backgroundColor: isHealthy ? '#d4edda' : '#f8d7da',
        borderRadius: '8px',
        border: `2px solid ${isHealthy ? '#28a745' : '#dc3545'}`,
        marginBottom: '20px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '15px',
          marginBottom: '15px'
        }}>
          <div style={{ fontSize: '48px' }}>
            {isHealthy ? '✅' : '⚠️'}
          </div>
          <div>
            <h3 style={{
              margin: 0,
              color: isHealthy ? '#155724' : '#721c24',
              fontSize: '20px'
            }}>
              {isHealthy ? 'המערכת תקינה' : 'המערכת דורשת תשומת לב'}
            </h3>
            <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
              בדיקה אחרונה: {lastCheck?.toLocaleTimeString('he-IL')}
            </div>
          </div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '15px',
          fontSize: '14px'
        }}>
          <div style={{
            padding: '10px',
            backgroundColor: 'white',
            borderRadius: '4px',
            textAlign: 'center'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>סה"כ טבלאות</div>
            <div style={{ fontSize: '24px', color: '#007bff' }}>
              {health.summary.total_tables}
            </div>
          </div>
          <div style={{
            padding: '10px',
            backgroundColor: 'white',
            borderRadius: '4px',
            textAlign: 'center'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>תקינות</div>
            <div style={{ fontSize: '24px', color: '#28a745' }}>
              {health.summary.valid_tables}
            </div>
          </div>
          <div style={{
            padding: '10px',
            backgroundColor: 'white',
            borderRadius: '4px',
            textAlign: 'center'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>דורשות תיקון</div>
            <div style={{ fontSize: '24px', color: '#dc3545' }}>
              {health.summary.invalid_tables}
            </div>
          </div>
        </div>
      </div>

      {/* רשימת טבלאות */}
      <div style={{
        padding: '20px',
        backgroundColor: '#fff',
        borderRadius: '8px',
        border: '1px solid #dee2e6'
      }}>
        <h3 style={{ marginTop: 0, marginBottom: '20px' }}>📋 סטטוס טבלאות</h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {Object.entries(health.tables).map(([tableName, validation]) => (
            <div
              key={tableName}
              style={{
                padding: '15px',
                backgroundColor: validation.valid ? '#f8f9fa' : '#fff3cd',
                borderRadius: '4px',
                border: `1px solid ${validation.valid ? '#dee2e6' : '#ffc107'}`,
                display: 'flex',
                alignItems: 'center',
                gap: '15px'
              }}
            >
              <div style={{ fontSize: '24px' }}>
                {validation.valid ? '✅' : '⚠️'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
                  {validation.description}
                </div>
                <div style={{ fontSize: '13px', color: '#666', fontFamily: 'monospace' }}>
                  {tableName}
                </div>
                {!validation.valid && validation.error && (
                  <div style={{
                    marginTop: '8px',
                    padding: '8px',
                    backgroundColor: '#fff',
                    borderRadius: '4px',
                    fontSize: '13px',
                    color: '#856404'
                  }}>
                    <strong>שגיאה:</strong> {validation.error}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* הסבר */}
      <div style={{
        marginTop: '20px',
        padding: '15px',
        backgroundColor: '#e7f3ff',
        borderRadius: '8px',
        border: '1px solid #007bff',
        fontSize: '14px',
        lineHeight: '1.6'
      }}>
        <strong>💡 מה זה אומר?</strong>
        <ul style={{ marginTop: '10px', marginBottom: 0, paddingRight: '20px' }}>
          <li>טבלאות תקינות (✅) - מכילות נתונים ופועלות כראוי</li>
          <li>טבלאות בעייתיות (⚠️) - חסרות נתונים או ריקות</li>
          <li>לחץ על "תקן אוטומטית" כדי לנסות לטעון נתונים מקבצי CSV</li>
          <li>המערכת בודקת אוטומטית כל 5 דקות</li>
        </ul>
      </div>
    </div>
  );
};

export default SystemHealthMonitor;
