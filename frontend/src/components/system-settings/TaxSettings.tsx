import React from 'react';
import { TaxBracket } from '../../types/system-settings.types';

interface TaxSettingsProps {
  taxBrackets: TaxBracket[];
  isEditing: boolean;
  editedBrackets: TaxBracket[];
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onBracketChange: (index: number, field: keyof TaxBracket, value: number) => void;
  formatCurrency: (amount: number) => string;
}

const TaxSettings: React.FC<TaxSettingsProps> = ({
  taxBrackets,
  isEditing,
  editedBrackets,
  onEdit,
  onSave,
  onCancel,
  onBracketChange,
  formatCurrency,
}) => {
  const currentBrackets = isEditing ? editedBrackets : taxBrackets;

  return (
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
          <button onClick={onEdit} className="btn btn-primary">
            ✏️ ערוך מדרגות מס
          </button>
        ) : (
          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={onSave} className="btn btn-success">
              ✅ שמור
            </button>
            <button onClick={onCancel} className="btn btn-secondary">
              ❌ ביטול
            </button>
          </div>
        )}
      </div>

      <div>
        <table className="modern-table">
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
                      onChange={(e) => onBracketChange(index, 'rate', parseInt(e.target.value))}
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
                        onChange={(e) => onBracketChange(index, 'minMonthly', parseInt(e.target.value))}
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
                          onChange={(e) => onBracketChange(index, 'maxMonthly', parseInt(e.target.value))}
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
                        onChange={(e) => onBracketChange(index, 'minAnnual', parseInt(e.target.value))}
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
                          onChange={(e) => onBracketChange(index, 'maxAnnual', parseInt(e.target.value))}
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
  );
};

export default TaxSettings;
