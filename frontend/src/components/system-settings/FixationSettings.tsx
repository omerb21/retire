import React from 'react';
import {
  PensionCeiling,
  ExemptCapitalPercentage,
  IdfPromoterRow,
} from '../../types/system-settings.types';
import { formatCurrency } from '../../lib/validation';
import './FixationSettings.css';

interface FixationSettingsProps {
  pensionCeilings: PensionCeiling[];
  isEditingCeilings: boolean;
  editedCeilings: PensionCeiling[];
  exemptCapitalPercentages: ExemptCapitalPercentage[];
  isEditingPercentages: boolean;
  editedPercentages: ExemptCapitalPercentage[];
  onEditCeilings: () => void;
  onSaveCeilings: () => void;
  onCancelCeilings: () => void;
  onCeilingChange: (index: number, field: keyof PensionCeiling, value: any) => void;
  onAddCeiling: () => void;
  onEditPercentages: () => void;
  onSavePercentages: () => void;
  onCancelPercentages: () => void;
  onPercentageChange: (index: number, field: keyof ExemptCapitalPercentage, value: any) => void;
  onAddPercentage: () => void;
  idfPromoterTable: IdfPromoterRow[];
  isEditingIdfPromoterTable: boolean;
  editedIdfPromoterTable: IdfPromoterRow[];
  onEditIdfPromoterTable: () => void;
  onSaveIdfPromoterTable: () => void;
  onCancelIdfPromoterTable: () => void;
  onIdfPromoterRowChange: (
    index: number,
    field: keyof IdfPromoterRow,
    value: any
  ) => void;
  onAddIdfPromoterRow: () => void;
}

const FixationSettings: React.FC<FixationSettingsProps> = ({
  pensionCeilings,
  isEditingCeilings,
  editedCeilings,
  exemptCapitalPercentages,
  isEditingPercentages,
  editedPercentages,
  onEditCeilings,
  onSaveCeilings,
  onCancelCeilings,
  onCeilingChange,
  onAddCeiling,
  onEditPercentages,
  onSavePercentages,
  onCancelPercentages,
  onPercentageChange,
  onAddPercentage,
  idfPromoterTable,
  isEditingIdfPromoterTable,
  editedIdfPromoterTable,
  onEditIdfPromoterTable,
  onSaveIdfPromoterTable,
  onCancelIdfPromoterTable,
  onIdfPromoterRowChange,
  onAddIdfPromoterRow,
}) => {
  return (
    <div className="fixation-settings-container">
      <h2 className="fixation-settings-title">
        נתוני קיבוע זכויות
      </h2>
      
      {/* Pension Ceilings Table */}
      <div className="fixation-ceilings-section">
        <div className="fixation-section-header">
          <h3 className="fixation-section-title">
            תקרות קצבה מזכה (2012-2028)
          </h3>
          
          {!isEditingCeilings ? (
            <button
              onClick={onEditCeilings}
              className="fixation-button-primary"
            >
              ערוך תקרות
            </button>
          ) : (
            <div className="fixation-actions">
              <button
                onClick={onSaveCeilings}
                className="fixation-button-success"
              >
                שמור
              </button>
              <button
                onClick={onCancelCeilings}
                className="fixation-button-secondary"
              >
                ביטול
              </button>
            </div>
          )}
        </div>
        
        <div className="fixation-table-container">
          <table className="fixation-table">
            <thead>
              <tr className="fixation-table-header-row">
                <th className="fixation-table-header-cell fixation-table-header-cell-center">שנה</th>
                <th className="fixation-table-header-cell fixation-table-header-cell-center">תקרה חודשית (₪)</th>
                <th className="fixation-table-header-cell fixation-table-header-cell-right">תיאור</th>
              </tr>
            </thead>
            <tbody>
              {(isEditingCeilings ? editedCeilings : pensionCeilings).map((ceiling, index) => (
                <tr
                  key={ceiling.year}
                  className={
                    index % 2 === 0
                      ? 'fixation-table-row'
                      : 'fixation-table-row fixation-table-row-alt'
                  }
                >
                  <td className="fixation-table-cell fixation-table-cell-center">
                    {isEditingCeilings ? (
                      <input
                        type="number"
                        value={ceiling.year}
                        onChange={(e) => onCeilingChange(index, 'year', e.target.value)}
                        className="fixation-input-year"
                      />
                    ) : (
                      ceiling.year
                    )}
                  </td>
                  <td className="fixation-table-cell fixation-ceiling-value-cell">
                    {isEditingCeilings ? (
                      <input
                        type="number"
                        value={ceiling.monthly_ceiling}
                        onChange={(e) => onCeilingChange(index, 'monthly_ceiling', e.target.value)}
                        className="fixation-input-number"
                      />
                    ) : (
                      formatCurrency(ceiling.monthly_ceiling)
                    )}
                  </td>
                  <td className="fixation-table-cell">
                    {isEditingCeilings ? (
                      <input
                        type="text"
                        value={ceiling.description}
                        onChange={(e) => onCeilingChange(index, 'description', e.target.value)}
                        className="fixation-input-full"
                      />
                    ) : (
                      ceiling.description
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {isEditingCeilings && (
            <div className="fixation-add-row">
              <button
                onClick={onAddCeiling}
                className="fixation-add-button"
              >
                הוסף שנה חדשה
              </button>
            </div>
          )}
        </div>
        
        <div className="fixation-info-box">
          <p className="fixation-info-text">
            <strong>הערה:</strong> תקרות הקצבה המזכה משמשות לחישוב הקצבה הפטורה ממס בקיבוע זכויות.
          </p>
        </div>
      </div>
      
      {/* Exempt Capital Percentages Table */}
      <div className="fixation-percentages-section">
        <div className="fixation-section-header">
          <h3 className="fixation-section-title">
            אחוזי הון פטור לחישוב יתרת הון (2012-2028)
          </h3>
          
          {!isEditingPercentages ? (
            <button
              onClick={onEditPercentages}
              className="fixation-button-primary"
            >
              ערוך אחוזים
            </button>
          ) : (
            <div className="fixation-actions">
              <button
                onClick={onSavePercentages}
                className="fixation-button-success"
              >
                שמור
              </button>
              <button
                onClick={onCancelPercentages}
                className="fixation-button-secondary"
              >
                ביטול
              </button>
            </div>
          )}
        </div>
        
        <div className="fixation-table-container">
          <table className="fixation-table">
            <thead>
              <tr className="fixation-table-header-row">
                <th className="fixation-table-header-cell fixation-table-header-cell-center">שנה</th>
                <th className="fixation-table-header-cell fixation-table-header-cell-center">אחוז (%)</th>
                <th className="fixation-table-header-cell fixation-table-header-cell-right">תיאור</th>
              </tr>
            </thead>
            <tbody>
              {(isEditingPercentages ? editedPercentages : exemptCapitalPercentages).map((percentage, index) => (
                <tr
                  key={percentage.year}
                  className={
                    index % 2 === 0
                      ? 'fixation-table-row'
                      : 'fixation-table-row fixation-table-row-alt'
                  }
                >
                  <td className="fixation-table-cell fixation-table-cell-center">
                    {isEditingPercentages ? (
                      <input
                        type="number"
                        value={percentage.year}
                        onChange={(e) => onPercentageChange(index, 'year', e.target.value)}
                        className="fixation-input-year"
                      />
                    ) : (
                      percentage.year
                    )}
                  </td>
                  <td className="fixation-table-cell fixation-percentage-value-cell">
                    {isEditingPercentages ? (
                      <input
                        type="number"
                        value={percentage.percentage}
                        onChange={(e) => onPercentageChange(index, 'percentage', e.target.value)}
                        className="fixation-input-number"
                      />
                    ) : (
                      `${percentage.percentage}%`
                    )}
                  </td>
                  <td className="fixation-table-cell">
                    {isEditingPercentages ? (
                      <input
                        type="text"
                        value={percentage.description}
                        onChange={(e) => onPercentageChange(index, 'description', e.target.value)}
                        className="fixation-input-full"
                      />
                    ) : (
                      percentage.description
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {isEditingPercentages && (
            <div className="fixation-add-row">
              <button
                onClick={onAddPercentage}
                className="fixation-add-button"
              >
                הוסף שנה חדשה
              </button>
            </div>
          )}
        </div>
        
        <div className="fixation-info-box">
          <p className="fixation-info-text">
            <strong>הערה:</strong> אחוזי ההון הפטור משמשים לחישוב יתרת ההון הפטורה בקיבוע זכויות.
          </p>
        </div>
      </div>

      <div className="fixation-idf-section">
        <div className="fixation-section-header">
          <h3 className="fixation-section-title">
            טבלת גיל מקדם לפורשי צה"ל וכוחות ביטחון
          </h3>
          {!isEditingIdfPromoterTable ? (
            <button
              onClick={onEditIdfPromoterTable}
              className="fixation-button-primary"
            >
              ערוך טבלת מקדמים
            </button>
          ) : (
            <div className="fixation-actions">
              <button
                onClick={onSaveIdfPromoterTable}
                className="fixation-button-success"
              >
                שמור
              </button>
              <button
                onClick={onCancelIdfPromoterTable}
                className="fixation-button-secondary"
              >
                ביטול
              </button>
            </div>
          )}
        </div>
        
        <div className="fixation-table-container">
          <table className="fixation-table">
            <thead>
              <tr className="fixation-table-header-row">
                <th className="fixation-table-header-cell fixation-table-header-cell-center">
                  מגדר
                </th>
                <th className="fixation-table-header-cell fixation-table-header-cell-center">
                  גיל בעת היוון (שנים)
                </th>
                <th className="fixation-table-header-cell fixation-table-header-cell-center">
                  גיל מקדם (שנים)
                </th>
                <th className="fixation-table-header-cell fixation-table-header-cell-center">
                  גיל מקדם (חודשים)
                </th>
                <th className="fixation-table-header-cell fixation-table-header-cell-right">
                  תיאור
                </th>
              </tr>
            </thead>
            <tbody>
              {(isEditingIdfPromoterTable ? editedIdfPromoterTable : idfPromoterTable).map(
                (row, index) => (
                  <tr
                    key={index}
                    className={
                      index % 2 === 0
                        ? 'fixation-table-row'
                        : 'fixation-table-row fixation-table-row-alt'
                    }
                  >
                    <td className="fixation-table-cell fixation-table-cell-center">
                      {isEditingIdfPromoterTable ? (
                        <select
                          className="fixation-idf-gender-select"
                          value={row.gender}
                          onChange={(e) =>
                            onIdfPromoterRowChange(index, 'gender', e.target.value)
                          }
                        >
                          <option value="male">זכר</option>
                          <option value="female">נקבה</option>
                        </select>
                      ) : row.gender === 'female' ? (
                        'נקבה'
                      ) : (
                        'זכר'
                      )}
                    </td>
                    <td className="fixation-table-cell fixation-table-cell-center">
                      {isEditingIdfPromoterTable ? (
                        <input
                          type="number"
                          className="fixation-input-number"
                          value={row.age_at_commutation}
                          onChange={(e) =>
                            onIdfPromoterRowChange(
                              index,
                              'age_at_commutation',
                              e.target.value
                            )
                          }
                        />
                      ) : (
                        row.age_at_commutation
                      )}
                    </td>
                    <td className="fixation-table-cell fixation-table-cell-center">
                      {isEditingIdfPromoterTable ? (
                        <input
                          type="number"
                          className="fixation-input-number"
                          value={row.promoter_age_years}
                          onChange={(e) =>
                            onIdfPromoterRowChange(
                              index,
                              'promoter_age_years',
                              e.target.value
                            )
                          }
                        />
                      ) : (
                        row.promoter_age_years
                      )}
                    </td>
                    <td className="fixation-table-cell fixation-table-cell-center">
                      {isEditingIdfPromoterTable ? (
                        <input
                          type="number"
                          className="fixation-input-number"
                          value={row.promoter_age_months}
                          onChange={(e) =>
                            onIdfPromoterRowChange(
                              index,
                              'promoter_age_months',
                              e.target.value
                            )
                          }
                        />
                      ) : (
                        row.promoter_age_months
                      )}
                    </td>
                    <td className="fixation-table-cell">
                      {isEditingIdfPromoterTable ? (
                        <input
                          type="text"
                          className="fixation-input-full"
                          value={row.description || ''}
                          onChange={(e) =>
                            onIdfPromoterRowChange(
                              index,
                              'description',
                              e.target.value
                            )
                          }
                        />
                      ) : (
                        row.description || ''
                      )}
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
          
          {isEditingIdfPromoterTable && (
            <div className="fixation-add-row">
              <button
                onClick={onAddIdfPromoterRow}
                className="fixation-add-button"
              >
                הוסף שורת מקדם חדשה
              </button>
            </div>
          )}
        </div>
        
        <div className="fixation-info-box">
          <p className="fixation-info-text">
            הערכים בטבלה זו ישמשו לחישוב גיל מקדם עבור פורשי צה"ל וכוחות ביטחון.
          </p>
        </div>
      </div>

      {/* תיעוד מפורט של לוגיקת החישובים */}
      <div className="fixation-doc-card">
        <h3 className="fixation-doc-main-title">
          📚 תיעוד: לוגיקת חישובי קיבוע זכויות וקצבה פטורה
        </h3>
        
        <div className="fixation-doc-section-info">
          <h4 className="fixation-doc-section-title">🔹 גיל זכאות:</h4>
          <p className="fixation-doc-text">
            <strong>גיל זכאות</strong> = התאריך המאוחר מבין:<br/>
            • גיל פרישה על פי חוק<br/>
            • תאריך קבלת קצבה ראשונה
          </p>
          <p className="fixation-doc-hint">
            💡 כדי להיות רשמית בגיל זכאות יש צורך בקיום <strong>שני התנאים</strong>: גם הגעה לגיל פרישה וגם קבלת קצבה ראשונה.
          </p>
        </div>
        
        <div className="fixation-doc-section">
          <h4 className="fixation-doc-section-title">🔹 חישוב במסך קיבוע זכויות:</h4>
          <ol className="fixation-doc-list">
            <li><strong>יתרת הון פטורה ראשונית</strong> = תקרת קצבה מזכה לשנת גיל הזכאות × 180 × אחוז הון פטור</li>
            <li><strong>פגיעה בפטור למענק</strong> = ערך מענק מוצמד × 1.35<br/>
              <span className="fixation-doc-small-note">
                (חובה לבדוק יחס 32 שנה ויחס גיל פרישה. פגיעה של היוונים = ערך ללא ×1.35)
              </span>
            </li>
            <li><strong>יתרה נותרת</strong> = יתרה ראשונית - סך פגיעות</li>
            <li><strong>אחוז פטור מחושב</strong> = (יתרה נותרת / 180) / תקרת הקצבה המזכה לשנת גיל הזכאות<br/>
              <span className="fixation-doc-highlight">
                דוגמה: (622,966.1 / 180) / 8,380 = 3,461 / 8,380 = 41.29%
              </span>
            </li>
          </ol>
          <p className="fixation-doc-success-box">
            ✅ <strong>אחוז זה נשמר ומשמש לחישוב הקצבה הפטורה במסך התוצאות!</strong>
          </p>
        </div>
        
        <div className="fixation-doc-section">
          <h4 className="fixation-doc-section-title">🔹 חישוב במסך תוצאות:</h4>
          <div className="fixation-doc-warning-box">
            <p className="fixation-doc-warning-title">
              קצבה פטורה = אחוז פטור מקיבוע × תקרת קצבה של השנה הראשונה בתזרים
            </p>
          </div>
          <p className="fixation-doc-example"><strong>דוגמה:</strong> 41.29% × 9,430 (תקרה 2025) = 3,893 ₪</p>
          <p className="fixation-doc-error-note">
            ⚠️ לא להכפיל באחוז כללי! לא לחשב מחדש! רק אחוז מקיבוע × תקרה!
          </p>
        </div>
        
        <div className="fixation-doc-section">
          <h4 className="fixation-doc-section-title">🔹 כללים חשובים:</h4>
          <ul className="fixation-doc-rules-list">
            <li>אחוז הפטור מחושב <strong>פעם אחת</strong> במסך קיבוע זכויות</li>
            <li>השנה הראשונה בתזרים = <strong>השנה הנוכחית</strong> (לא שנת הזכאות!)</li>
            <li>הקצבה הפטורה <strong>תמיד מוצגת</strong> במסך התוצאות (גם אם 0)</li>
            <li>בדוחות - אחוז הפטור מוצג <strong>כפי שחושב במסך הקיבוע</strong></li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default FixationSettings;
