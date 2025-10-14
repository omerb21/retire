import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

interface Pension {
  id: number;
  client_id: number;
  payer_name: string;
  start_date: string;
  commutations: any[];
}

const Pensions: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [pensions, setPensions] = useState<Pension[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPensions();
  }, [id]);

  const fetchPensions = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/v1/clients/${id}/pensions`);
      setPensions(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching pensions:', err);
      setError('שגיאה בטעינת קצבאות');
    } finally {
      setLoading(false);
    }
  };

  const deletePension = async (pensionId: number) => {
    if (!window.confirm('האם אתה בטוח שברצונך למחוק קצבה זו?')) {
      return;
    }

    try {
      await axios.delete(`/api/v1/clients/${id}/pensions/${pensionId}`);
      await fetchPensions();
    } catch (err: any) {
      console.error('Error deleting pension:', err);
      alert('שגיאה במחיקת קצבה');
    }
  };

  if (loading) {
    return <div className="container" style={{ padding: '20px' }}>טוען קצבאות...</div>;
  }

  if (error) {
    return <div className="container" style={{ padding: '20px', color: 'red' }}>{error}</div>;
  }

  return (
    <div className="container" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px' }}>קצבאות</h1>
      
      {pensions.length === 0 ? (
        <div style={{ 
          padding: '40px', 
          textAlign: 'center', 
          backgroundColor: '#f5f5f5', 
          borderRadius: '8px' 
        }}>
          <p style={{ fontSize: '18px', color: '#666' }}>אין קצבאות רשומות</p>
          <p style={{ fontSize: '14px', color: '#999' }}>
            קצבאות נוצרות אוטומטית כאשר בוחרים "סימון כקצבה" בתהליך עזיבת עבודה
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {pensions.map((pension) => (
            <div
              key={pension.id}
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '20px',
                backgroundColor: 'white',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: '0 0 12px 0', color: '#1976d2' }}>
                    {pension.payer_name}
                  </h3>
                  
                  <div style={{ display: 'grid', gap: '8px', fontSize: '14px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <strong style={{ minWidth: '120px' }}>מספר קצבה:</strong>
                      <span>{pension.id}</span>
                    </div>
                    
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <strong style={{ minWidth: '120px' }}>תאריך התחלה:</strong>
                      <span>{new Date(pension.start_date).toLocaleDateString('he-IL')}</span>
                    </div>
                    
                    {pension.commutations && pension.commutations.length > 0 && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <strong style={{ minWidth: '120px' }}>קומוטציות:</strong>
                        <span>{pension.commutations.length}</span>
                      </div>
                    )}
                  </div>
                </div>
                
                <button
                  onClick={() => deletePension(pension.id)}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#d32f2f',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#b71c1c'}
                  onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#d32f2f'}
                >
                  מחק
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div style={{ 
        marginTop: '30px', 
        padding: '16px', 
        backgroundColor: '#e3f2fd', 
        borderRadius: '8px',
        border: '1px solid #90caf9'
      }}>
        <h4 style={{ margin: '0 0 8px 0', color: '#1976d2' }}>💡 מידע</h4>
        <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.6' }}>
          קצבאות נוצרות אוטומטית כאשר בוחרים באופציה "סימון כקצבה" במסך עזיבת עבודה.
          <br />
          הסכומים והאינדקסציה של הקצבאות מטופלים על ידי מנוע החישוב.
        </p>
      </div>
    </div>
  );
};

export default Pensions;
