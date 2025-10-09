import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

interface TaxBracket {
  id: number;
  minMonthly: number;
  maxMonthly: number;
  minAnnual: number;
  maxAnnual: number;
  rate: number;
}

const SystemSettings: React.FC = () => {
  const [taxBrackets, setTaxBrackets] = useState<TaxBracket[]>([
    { id: 1, minMonthly: 0, maxMonthly: 7010, minAnnual: 0, maxAnnual: 84120, rate: 10 },
    { id: 2, minMonthly: 7011, maxMonthly: 10060, minAnnual: 84121, maxAnnual: 120720, rate: 14 },
    { id: 3, minMonthly: 10061, maxMonthly: 16150, minAnnual: 120721, maxAnnual: 193800, rate: 20 },
    { id: 4, minMonthly: 16151, maxMonthly: 22440, minAnnual: 193801, maxAnnual: 269280, rate: 31 },
    { id: 5, minMonthly: 22441, maxMonthly: 46690, minAnnual: 269281, maxAnnual: 560280, rate: 35 },
    { id: 6, minMonthly: 46691, maxMonthly: 60130, minAnnual: 560281, maxAnnual: 721560, rate: 47 },
    { id: 7, minMonthly: 60131, maxMonthly: Infinity, minAnnual: 721561, maxAnnual: Infinity, rate: 50 }
  ]);

  const [isEditing, setIsEditing] = useState(false);
  const [editedBrackets, setEditedBrackets] = useState<TaxBracket[]>([]);

  useEffect(() => {
    // טעינת מדרגות המס מ-localStorage אם קיימות
    const savedBrackets = localStorage.getItem('taxBrackets');
    if (savedBrackets) {
      setTaxBrackets(JSON.parse(savedBrackets));
    }
  }, []);

  const handleEdit = () => {
    setEditedBrackets([...taxBrackets]);
    setIsEditing(true);
  };

  const handleSave = () => {
    setTaxBrackets([...editedBrackets]);
    localStorage.setItem('taxBrackets', JSON.stringify(editedBrackets));
    setIsEditing(false);
    alert('מדרגות המס נשמרו בהצלחה!');
  };

  const handleCancel = () => {
    setEditedBrackets([]);
    setIsEditing(false);
  };

  const handleBracketChange = (index: number, field: keyof TaxBracket, value: number) => {
    const updated = [...editedBrackets];
    updated[index] = { ...updated[index], [field]: value };
    setEditedBrackets(updated);
  };

  const formatCurrency = (amount: number) => {
    if (amount === Infinity) return 'ומעלה';
    return amount.toLocaleString('he-IL') + ' ₪';
  };

  const currentBrackets = isEditing ? editedBrackets : taxBrackets;

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* כותרת וניווט */}
      <div style={{ marginBottom: '20px' }}>
        <Link to="/" style={{ color: '#007bff', textDecoration: 'none', fontSize: '14px' }}>
          ← חזרה לדף הבית
        </Link>
      </div>

      <div style={{ 
        backgroundColor: 'white', 
        padding: '30px', 
        borderRadius: '8px', 
        boxShadow: '0 2px 10px rgba(0,0,0,0.1)' 
      }}>
        <h1 style={{ 
          color: '#2c3e50', 
          marginBottom: '10px', 
          fontSize: '28px',
          fontWeight: 'bold'
        }}>
          הגדרות מערכת
        </h1>
        
        <p style={{ color: '#666', marginBottom: '30px', fontSize: '16px' }}>
          כאן ניתן לעדכן את הגדרות המערכת, כולל מדרגות המס השנתיות
        </p>

        {/* מדרגות המס */}
        <div style={{ marginBottom: '40px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '20px' 
          }}>
            <h2 style={{ color: '#2c3e50', fontSize: '24px', margin: 0 }}>
              מדרגות מס הכנסה לשנת 2025
            </h2>
            
            {!isEditing ? (
              <button
                onClick={handleEdit}
                style={{
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                ערוך מדרגות מס
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={handleSave}
                  style={{
                    backgroundColor: '#28a745',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  שמור
                </button>
                <button
                  onClick={handleCancel}
                  style={{
                    backgroundColor: '#6c757d',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  ביטול
                </button>
              </div>
            )}
          </div>

          {/* טבלת מדרגות המס */}
          <div style={{ 
            border: '1px solid #dee2e6', 
            borderRadius: '8px', 
            overflow: 'hidden',
            backgroundColor: 'white'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8f9fa' }}>
                  <th style={{ 
                    padding: '15px', 
                    textAlign: 'center', 
                    borderBottom: '2px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#2c3e50'
                  }}>
                    שיעור מס
                  </th>
                  <th style={{ 
                    padding: '15px', 
                    textAlign: 'center', 
                    borderBottom: '2px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#2c3e50'
                  }}>
                    הכנסה חודשית
                  </th>
                  <th style={{ 
                    padding: '15px', 
                    textAlign: 'center', 
                    borderBottom: '2px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#2c3e50'
                  }}>
                    הכנסה שנתית
                  </th>
                </tr>
              </thead>
              <tbody>
                {currentBrackets.map((bracket, index) => (
                  <tr key={bracket.id} style={{ 
                    backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                    borderBottom: '1px solid #dee2e6'
                  }}>
                    <td style={{ 
                      padding: '12px', 
                      textAlign: 'center', 
                      fontWeight: 'bold',
                      color: '#007bff',
                      fontSize: '16px'
                    }}>
                      {isEditing ? (
                        <input
                          type="number"
                          value={bracket.rate}
                          onChange={(e) => handleBracketChange(index, 'rate', parseInt(e.target.value))}
                          style={{
                            width: '60px',
                            padding: '5px',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                            textAlign: 'center'
                          }}
                        />
                      ) : (
                        `${bracket.rate}%`
                      )}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}>
                          <input
                            type="number"
                            value={bracket.minMonthly}
                            onChange={(e) => handleBracketChange(index, 'minMonthly', parseInt(e.target.value))}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                          <span>-</span>
                          {bracket.maxMonthly === Infinity ? (
                            <span>ומעלה</span>
                          ) : (
                            <input
                              type="number"
                              value={bracket.maxMonthly}
                              onChange={(e) => handleBracketChange(index, 'maxMonthly', parseInt(e.target.value))}
                              style={{
                                width: '80px',
                                padding: '5px',
                                border: '1px solid #ccc',
                                borderRadius: '4px',
                                textAlign: 'center'
                              }}
                            />
                          )}
                        </div>
                      ) : (
                        bracket.maxMonthly === Infinity ? 
                          `${formatCurrency(bracket.minMonthly)} ומעלה` :
                          `${formatCurrency(bracket.minMonthly)} - ${formatCurrency(bracket.maxMonthly)}`
                      )}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}>
                          <input
                            type="number"
                            value={bracket.minAnnual}
                            onChange={(e) => handleBracketChange(index, 'minAnnual', parseInt(e.target.value))}
                            style={{
                              width: '100px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                          <span>-</span>
                          {bracket.maxAnnual === Infinity ? (
                            <span>ומעלה</span>
                          ) : (
                            <input
                              type="number"
                              value={bracket.maxAnnual}
                              onChange={(e) => handleBracketChange(index, 'maxAnnual', parseInt(e.target.value))}
                              style={{
                                width: '100px',
                                padding: '5px',
                                border: '1px solid #ccc',
                                borderRadius: '4px',
                                textAlign: 'center'
                              }}
                            />
                          )}
                        </div>
                      ) : (
                        bracket.maxAnnual === Infinity ? 
                          `${formatCurrency(bracket.minAnnual)} ומעלה` :
                          `${formatCurrency(bracket.minAnnual)} - ${formatCurrency(bracket.maxAnnual)}`
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ 
            marginTop: '15px', 
            padding: '15px', 
            backgroundColor: '#e7f3ff', 
            borderRadius: '4px',
            border: '1px solid #b3d9ff'
          }}>
            <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
              <strong>הערה:</strong> מדרגות המס מתעדכנות אוטומטית בכל חישובי המס במערכת. 
              שינויים נשמרים במחשב המקומי ויישמרו עד לעדכון הבא.
            </p>
          </div>
        </div>

        {/* הגדרות נוספות עתידיות */}
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#f8f9fa', 
          borderRadius: '4px',
          border: '1px solid #dee2e6'
        }}>
          <h3 style={{ color: '#6c757d', marginBottom: '10px' }}>הגדרות נוספות</h3>
          <p style={{ color: '#6c757d', margin: 0, fontSize: '14px' }}>
            כאן ניתן יהיה להוסיף הגדרות נוספות בעתיד, כגון:
            <br />• ערך נקודת זיכוי
            <br />• שיעורי ביטוח לאומי ומס בריאות
            <br />• תקרות פטור ממס
          </p>
        </div>
      </div>
    </div>
  );
};

export default SystemSettings;
