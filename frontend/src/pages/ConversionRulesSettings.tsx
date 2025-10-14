import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { DEFAULT_RULES, ComponentConversionRule, loadConversionRules } from '../config/conversionRules';

/**
 * דף הגדרות לעריכת חוקי המרת יתרות
 */
export default function ConversionRulesSettings() {
  const [rules, setRules] = useState<ComponentConversionRule[]>(loadConversionRules());
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    // כאן ניתן להוסיף שמירה ל-localStorage או לשרת
    localStorage.setItem('conversion_rules', JSON.stringify(rules));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
    alert('חוקי ההמרה נשמרו בהצלחה!\nהשינויים ייכנסו לתוקף בהמרות הבאות.');
  };

  const handleReset = () => {
    if (confirm('האם אתה בטוח שברצונך לאפס את כל החוקים לברירת המחדל?')) {
      setRules([...DEFAULT_RULES]);
      localStorage.removeItem('conversion_rules');
      alert('החוקים אופסו לברירת המחדל');
    }
  };

  const updateRule = (index: number, field: keyof ComponentConversionRule, value: any) => {
    const newRules = [...rules];
    (newRules[index] as any)[field] = value;
    setRules(newRules);
  };

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: 20 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to="/">← חזרה לדף הבית</Link>
      </div>

      <h1>הגדרות חוקי המרת יתרות</h1>

      {saved && (
        <div style={{ 
          padding: 12, 
          backgroundColor: '#d4edda', 
          border: '1px solid #c3e6cb',
          borderRadius: 4,
          marginBottom: 16,
          color: '#155724'
        }}>
          ✓ השינויים נשמרו בהצלחה
        </div>
      )}

      <div style={{ marginBottom: 20 }}>
        <p style={{ fontSize: 14, color: '#666' }}>
          דף זה מאפשר לך לערוך את חוקי המרת היתרות מתיק פנסיוני.<br/>
          שים לב: שינויים בחוקים ישפיעו על כל ההמרות העתידיות במערכת.
        </p>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 10 }}>
        <button
          onClick={handleSave}
          style={{
            padding: '10px 20px',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          💾 שמור שינויים
        </button>
        <button
          onClick={handleReset}
          style={{
            padding: '10px 20px',
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          🔄 אפס לברירת מחדל
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <th style={{ border: '1px solid #ddd', padding: 8, minWidth: 200 }}>רכיב כספי</th>
              <th style={{ border: '1px solid #ddd', padding: 8, minWidth: 100 }}>המרה לקצבה</th>
              <th style={{ border: '1px solid #ddd', padding: 8, minWidth: 100 }}>המרה להון</th>
              <th style={{ border: '1px solid #ddd', padding: 8, minWidth: 120 }}>יחס מס (קצבה)</th>
              <th style={{ border: '1px solid #ddd', padding: 8, minWidth: 120 }}>יחס מס (הון)</th>
              <th style={{ border: '1px solid #ddd', padding: 8, minWidth: 300 }}>הודעת שגיאה</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule, index) => (
              <tr key={rule.field}>
                <td style={{ border: '1px solid #ddd', padding: 8 }}>
                  <strong>{rule.displayName}</strong>
                  <br/>
                  <span style={{ fontSize: 11, color: '#666' }}>({rule.field})</span>
                </td>
                <td style={{ border: '1px solid #ddd', padding: 8, textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={rule.canConvertToPension}
                    onChange={(e) => updateRule(index, 'canConvertToPension', e.target.checked)}
                    style={{ transform: 'scale(1.2)' }}
                  />
                </td>
                <td style={{ border: '1px solid #ddd', padding: 8, textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={rule.canConvertToCapital}
                    onChange={(e) => updateRule(index, 'canConvertToCapital', e.target.checked)}
                    style={{ transform: 'scale(1.2)' }}
                  />
                </td>
                <td style={{ border: '1px solid #ddd', padding: 8 }}>
                  <select
                    value={rule.taxTreatmentWhenPension}
                    onChange={(e) => updateRule(index, 'taxTreatmentWhenPension', e.target.value)}
                    style={{ width: '100%', padding: 4 }}
                  >
                    <option value="taxable">חייב במס</option>
                    <option value="exempt">פטור ממס</option>
                  </select>
                </td>
                <td style={{ border: '1px solid #ddd', padding: 8 }}>
                  <select
                    value={rule.taxTreatmentWhenCapital || 'capital_gain'}
                    onChange={(e) => updateRule(index, 'taxTreatmentWhenCapital', e.target.value)}
                    style={{ width: '100%', padding: 4 }}
                    disabled={!rule.canConvertToCapital}
                  >
                    <option value="capital_gain">מס רווח הון</option>
                    <option value="exempt">פטור ממס</option>
                  </select>
                </td>
                <td style={{ border: '1px solid #ddd', padding: 8 }}>
                  <textarea
                    value={rule.errorMessage || ''}
                    onChange={(e) => updateRule(index, 'errorMessage', e.target.value)}
                    style={{ width: '100%', padding: 4, minHeight: 40, fontSize: 12 }}
                    placeholder="הודעת שגיאה במקרה של המרה לא חוקית"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 32, padding: 16, backgroundColor: '#f8f9fa', borderRadius: 4 }}>
        <h3>הסבר על השדות:</h3>
        <ul style={{ fontSize: 13, lineHeight: 1.8 }}>
          <li><strong>המרה לקצבה:</strong> האם ניתן להמיר את הרכיב הזה לקצבה</li>
          <li><strong>המרה להון:</strong> האם ניתן להמיר את הרכיב הזה לנכס הון</li>
          <li><strong>יחס מס (קצבה):</strong> יחס המס שיחול על הקצבה שתיווצר מהרכיב הזה</li>
          <li><strong>יחס מס (הון):</strong> יחס המס שיחול על נכס ההון שייווצר מהרכיב הזה</li>
          <li><strong>הודעת שגיאה:</strong> הודעה שתוצג למשתמש אם ינסה לבצע המרה לא חוקית</li>
        </ul>
      </div>
    </div>
  );
}
