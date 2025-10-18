import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch, ClientItem, getClient } from '../lib/api';
import { formatDateToDDMMYY } from '../utils/dateUtils';
import axios from 'axios';
import SystemSnapshot from '../components/SystemSnapshot';

export default function ClientDetails() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<ClientItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [pensionStartDate, setPensionStartDate] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadClient() {
      if (!id) return;
      
      setLoading(true);
      setError(null);
      
      try {
        const clientData = await getClient(parseInt(id));
        setClient(clientData);
        setPensionStartDate(clientData.pension_start_date || '');
      } catch (e: any) {
        setError(`שגיאה בטעינת לקוח: ${e?.message || e}`);
      } finally {
        setLoading(false);
      }
    }
    
    loadClient();
  }, [id]);

  const handleSavePensionDate = async () => {
    if (!id) return;
    
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);
      
      await axios.patch(`/api/v1/clients/${id}/pension-start-date`, {
        pension_start_date: pensionStartDate || null
      });
      
      // עדכון הלקוח המקומי
      if (client) {
        setClient({
          ...client,
          pension_start_date: pensionStartDate || null
        });
      }
      
      setSuccessMessage('תאריך קבלת קצבה עודכן בהצלחה');
      setEditMode(false);
      
      // הסתרת הודעת הצלחה אחרי 3 שניות
      setTimeout(() => setSuccessMessage(null), 3000);
      
    } catch (e: any) {
      setError(`שגיאה בעדכון תאריך קצבה: ${e?.response?.data?.detail || e?.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setPensionStartDate(client?.pension_start_date || '');
    setEditMode(false);
    setError(null);
  };

  if (loading) return <div>טוען...</div>;
  if (error && !client) return <div className="error">{error}</div>;
  if (!client) return <div>לקוח לא נמצא</div>;

  return (
    <div className="client-details">
      <h2>תהליך פרישה - {client.first_name} {client.last_name} (ת"ז: {client.id_number})</h2>
      
      <div className="client-info" style={{ marginBottom: '20px' }}>
        <p><strong>ת"ז:</strong> {client.id_number}</p>
        <p><strong>תאריך לידה:</strong> {client.birth_date}</p>
        <p><strong>מין:</strong> {client.gender === 'male' ? 'זכר' : client.gender === 'female' ? 'נקבה' : 'לא צוין'}</p>
        <p><strong>אימייל:</strong> {client.email || 'לא הוזן'}</p>
        <p><strong>טלפון:</strong> {client.phone || 'לא הוזן'}</p>
        
        {/* תאריך קבלת קצבה ראשונה */}
        <div style={{ marginTop: '15px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '4px', border: '1px solid #dee2e6' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <strong>תאריך קבלת קצבה ראשונה:</strong>
            {!editMode && (
              <button 
                onClick={() => setEditMode(true)}
                style={{
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  padding: '5px 10px',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                ערוך
              </button>
            )}
          </div>
          
          {editMode ? (
            <div>
              <input
                type="date"
                value={pensionStartDate}
                onChange={(e) => setPensionStartDate(e.target.value)}
                style={{
                  padding: '8px',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  marginBottom: '10px',
                  width: '200px'
                }}
              />
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={handleSavePensionDate}
                  disabled={saving}
                  style={{
                    backgroundColor: saving ? '#6c757d' : '#28a745',
                    color: 'white',
                    border: 'none',
                    padding: '8px 15px',
                    borderRadius: '4px',
                    cursor: saving ? 'not-allowed' : 'pointer'
                  }}
                >
                  {saving ? 'שומר...' : 'שמור'}
                </button>
                <button
                  onClick={handleCancelEdit}
                  disabled={saving}
                  style={{
                    backgroundColor: '#6c757d',
                    color: 'white',
                    border: 'none',
                    padding: '8px 15px',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  בטל
                </button>
              </div>
            </div>
          ) : (
            <div style={{ color: client.pension_start_date ? '#28a745' : '#dc3545' }}>
              {client.pension_start_date ? 
                formatDateToDDMMYY(new Date(client.pension_start_date)) : 
                'טרם הוזן תאריך קבלת קצבה'
              }
            </div>
          )}
        </div>
      </div>
      
      {/* הודעות מערכת */}
      {error && (
        <div style={{ 
          color: '#dc3545', 
          backgroundColor: '#f8d7da', 
          padding: '10px', 
          borderRadius: '4px', 
          marginBottom: '15px',
          border: '1px solid #f5c6cb'
        }}>
          {error}
        </div>
      )}
      
      {successMessage && (
        <div style={{ 
          color: '#155724', 
          backgroundColor: '#d4edda', 
          padding: '10px', 
          borderRadius: '4px', 
          marginBottom: '15px',
          border: '1px solid #c3e6cb'
        }}>
          ✓ {successMessage}
        </div>
      )}
      
      <div className="module-links" style={{ 
        display: 'flex', 
        flexDirection: 'row', 
        gap: '10px', 
        flexWrap: 'wrap',
        marginBottom: '20px'
      }}>
        <ModuleLink to={`/clients/${id}/pension-funds`} label="קרנות פנסיה" />
        <ModuleLink to={`/clients/${id}/additional-incomes`} label="הכנסות נוספות" />
        <ModuleLink to={`/clients/${id}/capital-assets`} label="נכסי הון" />
        <ModuleLink to={`/clients/${id}/fixation`} label="קיבוע זכויות" />
        <ModuleLink to={`/clients/${id}/scenarios`} label="תרחישים" />
      </div>
      
      <Link to="/clients" style={{ display: 'inline-block', marginTop: '20px', marginBottom: '20px' }}>
        חזרה לרשימת לקוחות
      </Link>
      
      {/* System Snapshot - שמירה ושחזור מצב */}
      <div style={{ 
        marginTop: '30px',
        marginBottom: '20px', 
        padding: '20px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '8px',
        border: '2px solid #dee2e6'
      }}>
        <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#495057' }}>
          🔄 שמירה ושחזור מצב מערכת
        </h3>
        <SystemSnapshot 
          clientId={parseInt(id!)} 
          onSnapshotRestored={() => window.location.reload()}
        />
      </div>
    </div>
  );
}

function ModuleLink({ to, label }: { to: string, label: string }) {
  return (
    <Link 
      to={to}
      style={{
        padding: '10px 15px',
        backgroundColor: '#f0f0f0',
        borderRadius: '4px',
        textDecoration: 'none',
        color: '#333',
        fontWeight: 'bold',
      }}
    >
      {label}
    </Link>
  );
}
