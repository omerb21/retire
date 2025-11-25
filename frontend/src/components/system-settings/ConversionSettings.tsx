import React from 'react';
import './ConversionSettings.css';
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
    <div className="conversion-settings-container">
      <h2 className="conversion-settings-title">
        חוקי המרת יתרות
      </h2>
      
      {conversionSaved && (
        <div className="conversion-saved-alert">
          ✓ השינויים נשמרו בהצלחה
        </div>
      )}
      
      <div className="conversion-description">
        <p className="conversion-description-text">
          דף זה מאפשר לך לערוך את חוקי המרת היתרות מתיק פנסיוני.<br/>
          שים לב: שינויים בחוקים ישפיעו על כל ההמרות העתידיות במערכת.
        </p>
      </div>
      
      <div className="conversion-actions">
        <button
          onClick={onSave}
          className="conversion-save-button"
        >
          💾 שמור שינויים
        </button>
        <button
          onClick={onReset}
          className="conversion-reset-button"
        >
          🔄 אפס לברירת מחדל
        </button>
      </div>
      
      <div className="conversion-table-container">
        <div className="conversion-table-scroll">
          <table className="modern-table conversion-table">
            <thead>
              <tr className="conversion-table-header-row">
                <th className="conversion-table-header-cell conversion-table-header-cell-right">רכיב כספי</th>
                <th className="conversion-table-header-cell conversion-table-header-cell-center-narrow">המרה לקצבה</th>
                <th className="conversion-table-header-cell conversion-table-header-cell-center-narrow">המרה להון</th>
                <th className="conversion-table-header-cell conversion-table-header-cell-center-wide">יחס מס (קצבה)</th>
                <th className="conversion-table-header-cell conversion-table-header-cell-center-wide">יחס מס (הון)</th>
                <th className="conversion-table-header-cell conversion-table-header-cell-error">הודעת שגיאה</th>
              </tr>
            </thead>
            <tbody>
              {conversionRules.map((rule, index) => (
                <tr
                  key={rule.field}
                  className={`conversion-table-row ${index % 2 !== 0 ? 'conversion-table-row-alt' : ''}`}
                >
                  <td className="conversion-table-cell conversion-table-cell-right">
                    <strong>{rule.displayName}</strong>
                    <br />
                    <span className="conversion-rule-field-hint">({rule.field})</span>
                  </td>
                  <td className="conversion-table-cell conversion-table-cell-center">
                    <input
                      type="checkbox"
                      checked={rule.canConvertToPension}
                      onChange={(e) => onUpdateRule(index, 'canConvertToPension', e.target.checked)}
                      className="conversion-checkbox"
                    />
                  </td>
                  <td className="conversion-table-cell conversion-table-cell-center">
                    <input
                      type="checkbox"
                      checked={rule.canConvertToCapital}
                      onChange={(e) => onUpdateRule(index, 'canConvertToCapital', e.target.checked)}
                      className="conversion-checkbox"
                    />
                  </td>
                  <td className="conversion-table-cell">
                    <select
                      value={rule.taxTreatmentWhenPension}
                      onChange={(e) => onUpdateRule(index, 'taxTreatmentWhenPension', e.target.value)}
                      className="conversion-select"
                    >
                      <option value="taxable">חייב במס</option>
                      <option value="exempt">פטור ממס</option>
                    </select>
                  </td>
                  <td className="conversion-table-cell">
                    <select
                      value={rule.taxTreatmentWhenCapital || 'capital_gain'}
                      onChange={(e) => onUpdateRule(index, 'taxTreatmentWhenCapital', e.target.value)}
                      className="conversion-select"
                      disabled={!rule.canConvertToCapital}
                    >
                      <option value="capital_gain">מס רווח הון</option>
                      <option value="exempt">פטור ממס</option>
                    </select>
                  </td>
                  <td className="conversion-table-cell">
                    <textarea
                      value={rule.errorMessage || ''}
                      onChange={(e) => onUpdateRule(index, 'errorMessage', e.target.value)}
                      className="conversion-textarea"
                      placeholder="הודעת שגיאה במקרה של המרה לא חוקית"
                    />
                  </td>
                </tr>
              ))}
              
              <tr className="conversion-summary-row">
                <td className="conversion-summary-title">
                  <strong>קופת גמל להשקעה (סוג מוצר)</strong>
                  <br />
                  <span className="conversion-summary-subtitle">
                    לוגיקה אוטומטית לפי סוג המוצר, לא לפי רכיב בודד
                  </span>
                </td>
                <td className="conversion-table-cell conversion-table-cell-center">כן</td>
                <td className="conversion-table-cell conversion-table-cell-center">כן</td>
                <td className="conversion-table-cell">פטור ממס</td>
                <td className="conversion-table-cell">מס רווח הון</td>
                <td className="conversion-table-cell">
                  <span className="conversion-summary-subtitle">
                    החוק הזה מופעל אוטומטית לכל חשבון שסוג המוצר שלו מכיל "גמל להשקעה":
                    המרה לקצבה = פטור ממס, המרה לנכס הוני = חייב במס רווח הון. לא ניתן לערוך כלל זה בטבלה.
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <div className="conversion-info-card">
        <h3 className="conversion-info-title">הסבר על השדות:</h3>
        <ul className="conversion-info-list">
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
