import React from 'react';
import { ComponentConversionRule } from '../../config/conversionRules';

interface ConversionSettingsProps {
  conversionRules: ComponentConversionRule[];
  conversionSaved: boolean;
  onSave: () => void;
  onReset: () => void;
  onUpdateRule: (index: number, field: keyof ComponentConversionRule, value: any) => void;
}

const ConversionSettings: React.FC<ConversionSettingsProps> = ({
  conversionRules,
  conversionSaved,
  onSave,
  onReset,
  onUpdateRule,
}) => {
  return (
    <div style={{ marginBottom: '40px' }}>
      <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '20px' }}>
        חוקי המרת יתרות
      </h2>
      
      {conversionSaved && (
        <div style={{ 
          padding: '12px', 
          backgroundColor: '#d4edda', 
          border: '1px solid #c3e6cb',
          borderRadius: '4px',
          marginBottom: '16px',
          color: '#155724'
        }}>
          ✓ השינויים נשמרו בהצלחה
        </div>
      )}
      
      <div style={{ marginBottom: '20px' }}>
        <p style={{ fontSize: '14px', color: '#666' }}>
          דף זה מאפשר לך לערוך את חוקי המרת היתרות מתיק פנסיוני.<br/>
          שים לב: שינויים בחוקים ישפיעו על כל ההמרות העתידיות במערכת.
        </p>
      </div>
      
      <div style={{ marginBottom: '16px', display: 'flex', gap: '10px' }}>
        <button
          onClick={onSave}
          style={{
            padding: '10px 20px',
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '14px'
          }}
        >
          💾 שמור שינויים
        </button>
        <button
          onClick={onReset}
          style={{
            padding: '10px 20px',
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '14px'
          }}
        >
          🔄 אפס לברירת מחדל
        </button>
      </div>
      
      <div style={{ 
        border: '1px solid #dee2e6', 
        borderRadius: '8px', 
        overflow: 'hidden',
        backgroundColor: 'white'
      }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '200px', textAlign: 'right' }}>רכיב כספי</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '100px', textAlign: 'center' }}>המרה לקצבה</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '100px', textAlign: 'center' }}>המרה להון</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '120px', textAlign: 'center' }}>יחס מס (קצבה)</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '120px', textAlign: 'center' }}>יחס מס (הון)</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '300px', textAlign: 'right' }}>הודעת שגיאה</th>
              </tr>
            </thead>
            <tbody>
              {conversionRules.map((rule, index) => (
                <tr
                  key={rule.field}
                  style={{
                    backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                    borderBottom: '1px solid #dee2e6',
                  }}
                >
                  <td style={{ padding: '12px' }}>
                    <strong>{rule.displayName}</strong>
                    <br />
                    <span style={{ fontSize: '11px', color: '#666' }}>({rule.field})</span>
                  </td>
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={rule.canConvertToPension}
                      onChange={(e) => onUpdateRule(index, 'canConvertToPension', e.target.checked)}
                      style={{ transform: 'scale(1.2)', cursor: 'pointer' }}
                    />
                  </td>
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={rule.canConvertToCapital}
                      onChange={(e) => onUpdateRule(index, 'canConvertToCapital', e.target.checked)}
                      style={{ transform: 'scale(1.2)', cursor: 'pointer' }}
                    />
                  </td>
                  <td style={{ padding: '12px' }}>
                    <select
                      value={rule.taxTreatmentWhenPension}
                      onChange={(e) => onUpdateRule(index, 'taxTreatmentWhenPension', e.target.value)}
                      style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #ccc' }}
                    >
                      <option value="taxable">חייב במס</option>
                      <option value="exempt">פטור ממס</option>
                    </select>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <select
                      value={rule.taxTreatmentWhenCapital || 'capital_gain'}
                      onChange={(e) => onUpdateRule(index, 'taxTreatmentWhenCapital', e.target.value)}
                      style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #ccc' }}
                      disabled={!rule.canConvertToCapital}
                    >
                      <option value="capital_gain">מס רווח הון</option>
                      <option value="exempt">פטור ממס</option>
                    </select>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <textarea
                      value={rule.errorMessage || ''}
                      onChange={(e) => onUpdateRule(index, 'errorMessage', e.target.value)}
                      style={{
                        width: '100%',
                        padding: '6px',
                        minHeight: '40px',
                        fontSize: '12px',
                        borderRadius: '4px',
                        border: '1px solid #ccc',
                      }}
                      placeholder="הודעת שגיאה במקרה של המרה לא חוקית"
                    />
                  </td>
                </tr>
              ))}

              <tr
                style={{
                  backgroundColor: '#fffbe6',
                  borderTop: '2px solid #ffc107',
                  borderBottom: '1px solid #dee2e6',
                }}
              >
                <td style={{ padding: '12px' }}>
                  <strong>קופת גמל להשקעה (סוג מוצר)</strong>
                  <br />
                  <span style={{ fontSize: '11px', color: '#666' }}>
                    לוגיקה אוטומטית לפי סוג המוצר, לא לפי רכיב בודד
                  </span>
                </td>
                <td style={{ padding: '12px', textAlign: 'center' }}>כן</td>
                <td style={{ padding: '12px', textAlign: 'center' }}>כן</td>
                <td style={{ padding: '12px' }}>פטור ממס</td>
                <td style={{ padding: '12px' }}>מס רווח הון</td>
                <td style={{ padding: '12px', fontSize: '12px' }}>
                  החוק הזה מופעל אוטומטית לכל חשבון שסוג המוצר שלו מכיל "גמל להשקעה":
                  המרה לקצבה = פטור ממס, המרה לנכס הוני = חייב במס רווח הון. לא ניתן לערוך כלל זה בטבלה.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <div style={{ 
        marginTop: '20px', 
        padding: '16px', 
        backgroundColor: '#e7f3ff', 
        borderRadius: '4px',
        border: '1px solid #b3d9ff'
      }}>
        <h3 style={{ color: '#0056b3', marginBottom: '10px', fontSize: '16px' }}>הסבר על השדות:</h3>
        <ul style={{ fontSize: '13px', lineHeight: 1.8, color: '#0056b3', margin: 0 }}>
          <li><strong>המרה לקצבה:</strong> האם ניתן להמיר את הרכיב הזה לקצבה</li>
          <li><strong>המרה להון:</strong> האם ניתן להמיר את הרכיב הזה לנכס הון</li>
          <li><strong>יחס מס (קצבה):</strong> יחס המס שיחול על הקצבה שתיווצר מהרכיב הזה</li>
          <li><strong>יחס מס (הון):</strong> יחס המס שיחול על נכס ההון שייווצר מהרכיב הזה</li>
          <li><strong>הודעת שגיאה:</strong> הודעה שתוצג למשתמש אם ינסה לבצע המרה לא חוקית</li>
        </ul>
      </div>
    </div>
  );
};

export default ConversionSettings;
