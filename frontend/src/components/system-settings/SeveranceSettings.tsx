import React from 'react';
import { SeveranceCap } from '../../types/system-settings.types';

interface SeveranceSettingsProps {
  severanceCaps: SeveranceCap[];
  isEditingCaps: boolean;
  editedCaps: SeveranceCap[];
  capsLoading: boolean;
  capsError: string;
  onEditCaps: () => void;
  onSaveCaps: () => void;
  onCancelCaps: () => void;
  onCapChange: (index: number, field: keyof SeveranceCap, value: any) => void;
  onAddCap: () => void;
  formatCurrency: (amount: number) => string;
}

const SeveranceSettings: React.FC<SeveranceSettingsProps> = ({
  severanceCaps,
  isEditingCaps,
  editedCaps,
  capsLoading,
  capsError,
  onEditCaps,
  onSaveCaps,
  onCancelCaps,
  onCapChange,
  onAddCap,
  formatCurrency,
}) => {
  return (
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
            onClick={onEditCaps}
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
              onClick={onSaveCaps}
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
              onClick={onCancelCaps}
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
                        onChange={(e) => onCapChange(index, 'year', e.target.value)}
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
                        onChange={(e) => onCapChange(index, 'monthly_cap', e.target.value)}
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
                        onChange={(e) => onCapChange(index, 'description', e.target.value)}
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
                onClick={onAddCap}
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
  );
};

export default SeveranceSettings;
