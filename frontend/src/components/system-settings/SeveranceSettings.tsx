import React from 'react';
import { SeveranceCap } from '../../types/system-settings.types';
import './SeveranceSettings.css';

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
    <div className="severance-settings-container">
      <div className="severance-header">
        <h2 className="severance-title">
          תקרות פיצויים פטורות ממס
        </h2>
        
        {!isEditingCaps ? (
          <button
            onClick={onEditCaps}
            className="severance-edit-button"
          >
            ערוך תקרות פיצויים
          </button>
        ) : (
          <div className="severance-actions">
            <button
              onClick={onSaveCaps}
              className="severance-save-button"
            >
              שמור
            </button>
            <button
              onClick={onCancelCaps}
              className="severance-cancel-button"
            >
              ביטול
            </button>
          </div>
        )}
      </div>

      {capsError && (
        <div className="severance-error">
          {capsError}
        </div>
      )}

      {capsLoading ? (
        <div className="severance-loading">טוען תקרות פיצויים...</div>
      ) : (
        <div className="severance-table-container">
          <table className="severance-table">
            <thead>
              <tr className="severance-table-header-row">
                <th className="severance-table-header-cell">
                  שנה
                </th>
                <th className="severance-table-header-cell">
                  תקרה חודשית
                </th>
                <th className="severance-table-header-cell">
                  תקרה שנתית
                </th>
                <th className="severance-table-header-cell">
                  תיאור
                </th>
              </tr>
            </thead>
            <tbody>
              {(isEditingCaps ? editedCaps : severanceCaps).map((cap, index) => (
                <tr
                  key={cap.year}
                  className={
                    index % 2 === 0
                      ? 'severance-table-row'
                      : 'severance-table-row severance-table-row-alt'
                  }
                >
                  <td className="severance-table-cell severance-table-cell-center">
                    {isEditingCaps ? (
                      <input
                        type="number"
                        value={cap.year}
                        onChange={(e) => onCapChange(index, 'year', e.target.value)}
                        className="severance-input-year"
                      />
                    ) : (
                      cap.year
                    )}
                  </td>
                  <td className="severance-table-cell severance-monthly-cell">
                    {isEditingCaps ? (
                      <input
                        type="number"
                        value={cap.monthly_cap}
                        onChange={(e) => onCapChange(index, 'monthly_cap', e.target.value)}
                        className="severance-input-number"
                      />
                    ) : (
                      formatCurrency(cap.monthly_cap)
                    )}
                  </td>
                  <td className="severance-table-cell severance-table-cell-center">
                    {isEditingCaps ? (
                      <input
                        type="number"
                        value={cap.annual_cap}
                        disabled
                        className="severance-input-annual"
                      />
                    ) : (
                      formatCurrency(cap.annual_cap)
                    )}
                  </td>
                  <td className="severance-table-cell severance-table-cell-center">
                    {isEditingCaps ? (
                      <input
                        type="text"
                        value={cap.description}
                        onChange={(e) => onCapChange(index, 'description', e.target.value)}
                        className="severance-input-description"
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
            <div className="severance-add-row">
              <button
                onClick={onAddCap}
                className="severance-add-button"
              >
                הוסף תקרה חדשה
              </button>
            </div>
          )}
        </div>
      )}

      <div className="severance-note-box">
        <p className="severance-note-text">
          <strong>הערה:</strong> תקרות הפיצויים משמשות לחישוב הפטור ממס על מענקי פרישה.
          התקרה החודשית מוכפלת במספר שנות העבודה לחישוב הסכום הפטור.
        </p>
      </div>
    </div>
  );
};

export default SeveranceSettings;
