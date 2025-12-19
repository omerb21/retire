/**
 * System Health Monitor - מוניטור תקינות המערכת
 * מציג את סטטוס כל הטבלאות הקריטיות ומאפשר תיקון אוטומטי
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './SystemHealthMonitor.css';
import { API_BASE } from '../../lib/api';

const SYSTEM_ACCESS_STORAGE_KEY = 'systemAccessPassword';

function getSystemAccessPassword(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return window.localStorage.getItem(SYSTEM_ACCESS_STORAGE_KEY);
  } catch {
    return null;
  }
}

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
      const systemPassword = getSystemAccessPassword();
      const response = await axios.get<SystemHealthResponse>(`${API_BASE}/system/health`, {
        headers: systemPassword
          ? { 'X-System-Password': systemPassword }
          : undefined,
      });
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
      const systemPassword = getSystemAccessPassword();
      const response = await axios.post<AutoFixResponse>(`${API_BASE}/system/health/fix`, undefined, {
        headers: systemPassword
          ? { 'X-System-Password': systemPassword }
          : undefined,
      });
      
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
      <div className="system-health-loading">
        <div className="system-health-loading-icon">⏳</div>
        <div>בודק תקינות מערכת...</div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="system-health-error">
        <div className="system-health-error-icon">❌</div>
        <div>שגיאה בבדיקת תקינות המערכת</div>
        <button
          onClick={checkHealth}
          className="system-health-try-again-button"
        >
          נסה שוב
        </button>
      </div>
    );
  }

  const isHealthy = health.status === 'healthy';

  return (
    <div className="system-health-container">
      <div className="system-health-header">
        <h2 className="system-health-title">
          🏥 מוניטור תקינות מערכת
        </h2>
        <div className="system-health-actions">
          <button
            onClick={checkHealth}
            disabled={loading}
            className={`system-health-refresh-button${loading ? ' system-health-refresh-button--loading' : ''}`}
          >
            {loading ? '⏳ בודק...' : '🔄 רענן'}
          </button>
          {!isHealthy && (
            <button
              onClick={autoFix}
              disabled={fixing}
              className={`system-health-fix-button${fixing ? ' system-health-fix-button--fixing' : ''}`}
            >
              {fixing ? '⏳ מתקן...' : '🔧 תקן אוטומטית'}
            </button>
          )}
        </div>
      </div>

      {/* סטטוס כללי */}
      <div className={`system-health-status-card ${isHealthy ? 'system-health-status-card--healthy' : 'system-health-status-card--unhealthy'}`}>
        <div className="system-health-status-row">
          <div className="system-health-status-icon">
            {isHealthy ? '✅' : '⚠️'}
          </div>
          <div>
            <h3
              className={`system-health-status-title ${isHealthy ? 'system-health-status-title--healthy' : 'system-health-status-title--unhealthy'}`}
            >
              {isHealthy ? 'המערכת תקינה' : 'המערכת דורשת תשומת לב'}
            </h3>
            <div className="system-health-status-subtitle">
              בדיקה אחרונה: {lastCheck?.toLocaleTimeString('he-IL')}
            </div>
          </div>
        </div>

        <div className="system-health-summary-grid">
          <div className="system-health-summary-card">
            <div className="system-health-summary-label">סה"כ טבלאות</div>
            <div className="system-health-summary-value system-health-summary-value--total">
              {health.summary.total_tables}
            </div>
          </div>
          <div className="system-health-summary-card">
            <div className="system-health-summary-label">תקינות</div>
            <div className="system-health-summary-value system-health-summary-value--valid">
              {health.summary.valid_tables}
            </div>
          </div>
          <div className="system-health-summary-card">
            <div className="system-health-summary-label">דורשות תיקון</div>
            <div className="system-health-summary-value system-health-summary-value--invalid">
              {health.summary.invalid_tables}
            </div>
          </div>
        </div>
      </div>

      {/* רשימת טבלאות */}
      <div className="system-health-tables-card">
        <h3 className="system-health-tables-title">📋 סטטוס טבלאות</h3>
        
        <div className="system-health-tables-list">
          {Object.entries(health.tables).map(([tableName, validation]) => (
            <div
              key={tableName}
              className={`system-health-table-item ${validation.valid ? 'system-health-table-item--valid' : 'system-health-table-item--invalid'}`}
            >
              <div className="system-health-table-icon">
                {validation.valid ? '✅' : '⚠️'}
              </div>
              <div className="system-health-table-content">
                <div className="system-health-table-description">
                  {validation.description}
                </div>
                <div className="system-health-table-name">
                  {tableName}
                </div>
                {!validation.valid && validation.error && (
                  <div className="system-health-table-error">
                    <strong>שגיאה:</strong> {validation.error}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* הסבר */}
      <div className="system-health-info-card">
        <strong>💡 מה זה אומר?</strong>
        <ul className="system-health-info-list">
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
