import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from "../lib/api";

interface TaxBracket {
  id: number;
  minMonthly: number;
  maxMonthly: number;
  minAnnual: number;
  maxAnnual: number;
  rate: number;
}

interface SeveranceCap {
  year: number;
  monthly_cap: number;
  annual_cap: number;
  description: string;
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
  
  // תקרות פיצויים
  const [severanceCaps, setSeveranceCaps] = useState<SeveranceCap[]>([]);
  const [isEditingCaps, setIsEditingCaps] = useState(false);
  const [editedCaps, setEditedCaps] = useState<SeveranceCap[]>([]);
  const [capsLoading, setCapsLoading] = useState(false);
  const [capsError, setCapsError] = useState<string>("");

  useEffect(() => {
    // טעינת מדרגות המס מ-localStorage אם קיימות
    const savedBrackets = localStorage.getItem('taxBrackets');
    if (savedBrackets) {
      setTaxBrackets(JSON.parse(savedBrackets));
    }
    
    // טעינת תקרות פיצויים
    loadSeveranceCaps();
  }, []);
  
  // פונקציה לטעינת תקרות פיצויים מהשרת
  const loadSeveranceCaps = async () => {
    setCapsLoading(true);
    setCapsError("");
    
    try {
      // ניסיון לטעון מהשרת
      try {
        const response = await apiFetch<{caps: SeveranceCap[]}>('/api/v1/tax-data/severance-caps');
        
        if (response && response.caps) {
          setSeveranceCaps(response.caps);
          
          // שמירה גם ב-localStorage לגיבוי
          localStorage.setItem('severanceCaps', JSON.stringify(response.caps));
          return;
        }
      } catch (apiError) {
        console.log("API error, falling back to local data:", apiError);
        // המשך לשימוש בנתונים מקומיים
      }
      
      // אם אין תגובה מהשרת, נסה לטעון מ-localStorage
      const savedCaps = localStorage.getItem('severanceCaps');
      if (savedCaps) {
        setSeveranceCaps(JSON.parse(savedCaps));
      } else {
        // אם אין גם ב-localStorage, השתמש בערכי ברירת מחדל המעודכנים
        const defaultCaps = [
          {year: 2025, monthly_cap: 13750, annual_cap: 13750 * 12, description: 'תקרה חודשית לשנת 2025'},
          {year: 2024, monthly_cap: 13750, annual_cap: 13750 * 12, description: 'תקרה חודשית לשנת 2024'},
          {year: 2023, monthly_cap: 13310, annual_cap: 13310 * 12, description: 'תקרה חודשית לשנת 2023'},
          {year: 2022, monthly_cap: 12640, annual_cap: 12640 * 12, description: 'תקרה חודשית לשנת 2022'},
          {year: 2021, monthly_cap: 12340, annual_cap: 12340 * 12, description: 'תקרה חודשית לשנת 2021'},
          {year: 2020, monthly_cap: 12420, annual_cap: 12420 * 12, description: 'תקרה חודשית לשנת 2020'},
          {year: 2019, monthly_cap: 12380, annual_cap: 12380 * 12, description: 'תקרה חודשית לשנת 2019'},
          {year: 2018, monthly_cap: 12230, annual_cap: 12230 * 12, description: 'תקרה חודשית לשנת 2018'},
          {year: 2017, monthly_cap: 12200, annual_cap: 12200 * 12, description: 'תקרה חודשית לשנת 2017'},
          {year: 2016, monthly_cap: 12230, annual_cap: 12230 * 12, description: 'תקרה חודשית לשנת 2016'},
          {year: 2015, monthly_cap: 12340, annual_cap: 12340 * 12, description: 'תקרה חודשית לשנת 2015'},
          {year: 2014, monthly_cap: 12360, annual_cap: 12360 * 12, description: 'תקרה חודשית לשנת 2014'},
          {year: 2013, monthly_cap: 12120, annual_cap: 12120 * 12, description: 'תקרה חודשית לשנת 2013'},
          {year: 2012, monthly_cap: 11950, annual_cap: 11950 * 12, description: 'תקרה חודשית לשנת 2012'},
          {year: 2011, monthly_cap: 11650, annual_cap: 11650 * 12, description: 'תקרה חודשית לשנת 2011'},
          {year: 2010, monthly_cap: 11390, annual_cap: 11390 * 12, description: 'תקרה חודשית לשנת 2010'},
        ];
        
        setSeveranceCaps(defaultCaps);
        
        // שמירה ב-localStorage לשימוש עתידי
        localStorage.setItem('severanceCaps', JSON.stringify(defaultCaps));
      }
    } catch (e: any) {
      console.error("Error loading severance caps:", e);
      setCapsError(`שגיאה בטעינת תקרות פיצויים: ${e?.message || e}`);
      
      // ניסיון לטעון מ-localStorage במקרה של שגיאה
      const savedCaps = localStorage.getItem('severanceCaps');
      if (savedCaps) {
        setSeveranceCaps(JSON.parse(savedCaps));
      }
    } finally {
      setCapsLoading(false);
    }
  };
  
  // פונקציה לעריכת תקרות פיצויים
  const handleEditCaps = () => {
    setEditedCaps([...severanceCaps]);
    setIsEditingCaps(true);
  };
  
  // פונקציה לשמירת תקרות פיצויים
  const handleSaveCaps = async () => {
    try {
      // ניסיון לשמור בשרת
      await apiFetch('/tax-data/severance-caps', {
        method: 'POST',
        body: JSON.stringify(editedCaps),
      });
      
      // עדכון ה-state ושמירה ב-localStorage
      setSeveranceCaps([...editedCaps]);
      localStorage.setItem('severanceCaps', JSON.stringify(editedCaps));
      
      setIsEditingCaps(false);
      alert('תקרות הפיצויים נשמרו בהצלחה!');
    } catch (e: any) {
      console.error("Error saving severance caps:", e);
      alert(`שגיאה בשמירת תקרות פיצויים: ${e?.message || e}`);
    }
  };
  
  // פונקציה לביטול עריכת תקרות פיצויים
  const handleCancelCaps = () => {
    setEditedCaps([]);
    setIsEditingCaps(false);
  };
  
  // פונקציה לשינוי תקרת פיצויים
  const handleCapChange = (index: number, field: keyof SeveranceCap, value: any) => {
    const updated = [...editedCaps];
    updated[index] = { ...updated[index], [field]: field === 'year' ? parseInt(value) : parseFloat(value) };
    
    // עדכון אוטומטי של התקרה השנתית לפי התקרה החודשית
    if (field === 'monthly_cap') {
      updated[index].annual_cap = parseFloat(value) * 12;
    }
    
    // עדכון התיאור אם השנה השתנתה
    if (field === 'year') {
      updated[index].description = `תקרה חודשית לשנת ${value}`;
    }
    
    setEditedCaps(updated);
  };
  
  // פונקציה להוספת תקרת פיצויים חדשה
  const handleAddCap = () => {
    const currentYear = new Date().getFullYear();
    const newCap: SeveranceCap = {
      year: currentYear + 1,
      monthly_cap: 41667, // ערך ברירת מחדל
      annual_cap: 41667 * 12,
      description: `תקרה חודשית לשנת ${currentYear + 1}`
    };
    
    setEditedCaps([...editedCaps, newCap]);
  };

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

        {/* תקרות פיצויים */}
        <div style={{ marginBottom: '40px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '20px' 
          }}>
            <h2 style={{ color: '#2c3e50', fontSize: '24px', margin: 0 }}>
              תקרות פיצויים פטורות ממס
            </h2>
            
            {!isEditingCaps ? (
              <button
                onClick={handleEditCaps}
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
                ערוך תקרות פיצויים
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={handleSaveCaps}
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
                  onClick={handleCancelCaps}
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

          {capsError && (
            <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
              {capsError}
            </div>
          )}

          {capsLoading ? (
            <div style={{ padding: 16, textAlign: 'center' }}>טוען תקרות פיצויים...</div>
          ) : (
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
                      שנה
                    </th>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      תקרה חודשית
                    </th>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      תקרה שנתית
                    </th>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      תיאור
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(isEditingCaps ? editedCaps : severanceCaps).map((cap, index) => (
                    <tr key={cap.year} style={{ 
                      backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                      borderBottom: '1px solid #dee2e6'
                    }}>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCaps ? (
                          <input
                            type="number"
                            value={cap.year}
                            onChange={(e) => handleCapChange(index, 'year', e.target.value)}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          cap.year
                        )}
                      </td>
                      <td style={{ 
                        padding: '12px', 
                        textAlign: 'center',
                        fontWeight: 'bold',
                        color: '#007bff'
                      }}>
                        {isEditingCaps ? (
                          <input
                            type="number"
                            value={cap.monthly_cap}
                            onChange={(e) => handleCapChange(index, 'monthly_cap', e.target.value)}
                            style={{
                              width: '100px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          formatCurrency(cap.monthly_cap)
                        )}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCaps ? (
                          <input
                            type="number"
                            value={cap.annual_cap}
                            disabled
                            style={{
                              width: '120px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center',
                              backgroundColor: '#f8f9fa'
                            }}
                          />
                        ) : (
                          formatCurrency(cap.annual_cap)
                        )}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCaps ? (
                          <input
                            type="text"
                            value={cap.description}
                            onChange={(e) => handleCapChange(index, 'description', e.target.value)}
                            style={{
                              width: '200px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px'
                            }}
                          />
                        ) : (
                          cap.description
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {isEditingCaps && (
                <div style={{ padding: '15px', textAlign: 'center' }}>
                  <button
                    onClick={handleAddCap}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#17a2b8',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    הוסף תקרה חדשה
                  </button>
                </div>
              )}
            </div>
          )}

          <div style={{ 
            marginTop: '15px', 
            padding: '15px', 
            backgroundColor: '#e7f3ff', 
            borderRadius: '4px',
            border: '1px solid #b3d9ff'
          }}>
            <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
              <strong>הערה:</strong> תקרות הפיצויים משמשות לחישוב הפטור ממס על מענקי פרישה.
              התקרה החודשית מוכפלת במספר שנות העבודה לחישוב הסכום הפטור.
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
          </p>
        </div>
      </div>
    </div>
  );
};

export default SystemSettings;
