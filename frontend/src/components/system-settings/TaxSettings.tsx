import React from 'react';
import { TaxBracket } from '../../types/system-settings.types';
import './TaxSettings.css';

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
    <div className="tax-settings-container">
      <div className="tax-header">
        <h2 className="tax-title">
          מדרגות מס הכנסה לשנת 2025
        </h2>
        
        {!isEditing ? (
          <button onClick={onEdit} className="btn btn-primary">
            ✏️ ערוך מדרגות מס
          </button>
        ) : (
          <div className="tax-actions">
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
            <tr className="tax-table-header-row">
              <th className="tax-table-header-cell">
                שיעור מס
              </th>
              <th className="tax-table-header-cell">
                הכנסה חודשית
              </th>
              <th className="tax-table-header-cell">
                הכנסה שנתית
              </th>
            </tr>
          </thead>
          <tbody>
            {currentBrackets.map((bracket, index) => (
              <tr
                key={bracket.id}
                className={
                  index % 2 === 0
                    ? 'tax-table-row'
                    : 'tax-table-row tax-table-row-alt'
                }
              >
                <td className="tax-rate-cell">
                  {isEditing ? (
                    <input
                      type="number"
                      value={bracket.rate}
                      onChange={(e) => onBracketChange(index, 'rate', parseInt(e.target.value))}
                      className="tax-input-rate"
                    />
                  ) : (
                    `${bracket.rate}%`
                  )}
                </td>
                <td className="tax-range-cell">
                  {isEditing ? (
                    <div className="tax-range-editor">
                      <input
                        type="number"
                        value={bracket.minMonthly}
                        onChange={(e) => onBracketChange(index, 'minMonthly', parseInt(e.target.value))}
                        className="tax-input-monthly"
                      />
                      <span>-</span>
                      {bracket.maxMonthly === Infinity ? (
                        <span>ומעלה</span>
                      ) : (
                        <input
                          type="number"
                          value={bracket.maxMonthly}
                          onChange={(e) => onBracketChange(index, 'maxMonthly', parseInt(e.target.value))}
                          className="tax-input-monthly"
                        />
                      )}
                    </div>
                  ) : (
                    bracket.maxMonthly === Infinity ? 
                      `${formatCurrency(bracket.minMonthly)} ומעלה` :
                      `${formatCurrency(bracket.minMonthly)} - ${formatCurrency(bracket.maxMonthly)}`
                  )}
                </td>
                <td className="tax-annual-cell">
                  {isEditing ? (
                    <div className="tax-range-editor">
                      <input
                        type="number"
                        value={bracket.minAnnual}
                        onChange={(e) => onBracketChange(index, 'minAnnual', parseInt(e.target.value))}
                        className="tax-input-annual-wide"
                      />
                      <span>-</span>
                      {bracket.maxAnnual === Infinity ? (
                        <span>ומעלה</span>
                      ) : (
                        <input
                          type="number"
                          value={bracket.maxAnnual}
                          onChange={(e) => onBracketChange(index, 'maxAnnual', parseInt(e.target.value))}
                          className="tax-input-annual-wide"
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

      <div className="tax-note-box">
        <p className="tax-note-text">
          <strong>הערה:</strong> מדרגות המס מתעדכנות אוטומטית בכל חישובי המס במערכת. 
          שינויים נשמרים במחשב המקומי ויישמרו עד לעדכון הבא.
        </p>
      </div>
    </div>
  );
};

export default TaxSettings;
