import React from 'react';
import { PensionCeiling, ExemptCapitalPercentage } from '../../types/system-settings.types';

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
}) => {
  return (
    <div style={{ marginBottom: '40px' }}>
      <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '30px' }}>
        נתוני קיבוע זכויות
      </h2>
      
      {/* Pension Ceilings Table */}
      <div style={{ marginBottom: '50px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '20px' 
        }}>
          <h3 style={{ color: '#2c3e50', fontSize: '20px', margin: 0 }}>
            תקרות קצבה מזכה (2012-2025)
          </h3>
          
          {!isEditingCeilings ? (
            <button
              onClick={onEditCeilings}
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
              ערוך תקרות
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={onSaveCeilings}
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
                onClick={onCancelCeilings}
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
        
        <div style={{ 
          border: '1px solid #dee2e6', 
          borderRadius: '8px', 
          overflow: 'hidden',
          backgroundColor: 'white'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>שנה</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>תקרה חודשית (₪)</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'right' }}>תיאור</th>
              </tr>
            </thead>
            <tbody>
              {(isEditingCeilings ? editedCeilings : pensionCeilings).map((ceiling, index) => (
                <tr key={ceiling.year} style={{ 
                  backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                  borderBottom: '1px solid #dee2e6'
                }}>
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    {isEditingCeilings ? (
                      <input
                        type="number"
                        value={ceiling.year}
                        onChange={(e) => onCeilingChange(index, 'year', e.target.value)}
                        style={{
                          width: '80px',
                          padding: '5px',
                          border: '1px solid #ccc',
                          borderRadius: '4px',
                          textAlign: 'center'
                        }}
                      />
                    ) : (
                      ceiling.year
                    )}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#007bff' }}>
                    {isEditingCeilings ? (
                      <input
                        type="number"
                        value={ceiling.monthly_ceiling}
                        onChange={(e) => onCeilingChange(index, 'monthly_ceiling', e.target.value)}
                        style={{
                          width: '100px',
                          padding: '5px',
                          border: '1px solid #ccc',
                          borderRadius: '4px',
                          textAlign: 'center'
                        }}
                      />
                    ) : (
                      ceiling.monthly_ceiling.toLocaleString()
                    )}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {isEditingCeilings ? (
                      <input
                        type="text"
                        value={ceiling.description}
                        onChange={(e) => onCeilingChange(index, 'description', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '5px',
                          border: '1px solid #ccc',
                          borderRadius: '4px'
                        }}
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
            <div style={{ padding: '15px', textAlign: 'center', borderTop: '1px solid #dee2e6' }}>
              <button
                onClick={onAddCeiling}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#17a2b8',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                הוסף שנה חדשה
              </button>
            </div>
          )}
        </div>
        
        <div style={{ 
          marginTop: '15px', 
          padding: '15px', 
          backgroundColor: '#e7f3ff', 
          borderRadius: '4px',
          border: '1px solid #b3d9ff'
        }}>
          <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
            <strong>הערה:</strong> תקרות הקצבה המזכה משמשות לחישוב הקצבה הפטורה ממס בקיבוע זכויות.
          </p>
        </div>
      </div>
      
      {/* Exempt Capital Percentages Table */}
      <div style={{ marginBottom: '40px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '20px' 
        }}>
          <h3 style={{ color: '#2c3e50', fontSize: '20px', margin: 0 }}>
            אחוזי הון פטור לחישוב יתרת הון (2012-2025)
          </h3>
          
          {!isEditingPercentages ? (
            <button
              onClick={onEditPercentages}
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
              ערוך אחוזים
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={onSavePercentages}
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
                onClick={onCancelPercentages}
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
        
        <div style={{ 
          border: '1px solid #dee2e6', 
          borderRadius: '8px', 
          overflow: 'hidden',
          backgroundColor: 'white'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>שנה</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>אחוז (%)</th>
                <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'right' }}>תיאור</th>
              </tr>
            </thead>
            <tbody>
              {(isEditingPercentages ? editedPercentages : exemptCapitalPercentages).map((percentage, index) => (
                <tr key={percentage.year} style={{ 
                  backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                  borderBottom: '1px solid #dee2e6'
                }}>
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    {isEditingPercentages ? (
                      <input
                        type="number"
                        value={percentage.year}
                        onChange={(e) => onPercentageChange(index, 'year', e.target.value)}
                        style={{
                          width: '80px',
                          padding: '5px',
                          border: '1px solid #ccc',
                          borderRadius: '4px',
                          textAlign: 'center'
                        }}
                      />
                    ) : (
                      percentage.year
                    )}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>
                    {isEditingPercentages ? (
                      <input
                        type="number"
                        value={percentage.percentage}
                        onChange={(e) => onPercentageChange(index, 'percentage', e.target.value)}
                        style={{
                          width: '80px',
                          padding: '5px',
                          border: '1px solid #ccc',
                          borderRadius: '4px',
                          textAlign: 'center'
                        }}
                      />
                    ) : (
                      `${percentage.percentage}%`
                    )}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {isEditingPercentages ? (
                      <input
                        type="text"
                        value={percentage.description}
                        onChange={(e) => onPercentageChange(index, 'description', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '5px',
                          border: '1px solid #ccc',
                          borderRadius: '4px'
                        }}
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
            <div style={{ padding: '15px', textAlign: 'center', borderTop: '1px solid #dee2e6' }}>
              <button
                onClick={onAddPercentage}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#17a2b8',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                הוסף שנה חדשה
              </button>
            </div>
          )}
        </div>
        
        <div style={{ 
          marginTop: '15px', 
          padding: '15px', 
          backgroundColor: '#e7f3ff', 
          borderRadius: '4px',
          border: '1px solid #b3d9ff'
        }}>
          <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
            <strong>הערה:</strong> אחוזי ההון הפטור משמשים לחישוב יתרת ההון הפטורה בקיבוע זכויות.
          </p>
        </div>
      </div>

      {/* תיעוד מפורט של לוגיקת החישובים */}
      <div style={{ 
        backgroundColor: '#fff8dc', 
        border: '2px solid #ffa500', 
        borderRadius: '8px', 
        padding: '20px', 
        marginTop: '30px' 
      }}>
        <h3 style={{ color: '#ff8c00', marginTop: 0, fontSize: '18px' }}>
          📚 תיעוד: לוגיקת חישובי קיבוע זכויות וקצבה פטורה
        </h3>
        
        <div style={{ backgroundColor: '#e8f4fd', padding: '15px', borderRadius: '6px', marginBottom: '20px', border: '1px solid #007bff' }}>
          <h4 style={{ color: '#2c3e50', marginTop: 0 }}>🔹 גיל זכאות:</h4>
          <p style={{ margin: '5px 0', lineHeight: '1.8' }}>
            <strong>גיל זכאות</strong> = התאריך המאוחר מבין:<br/>
            • גיל פרישה על פי חוק<br/>
            • תאריך קבלת קצבה ראשונה
          </p>
          <p style={{ margin: '10px 0 0 0', padding: '8px', backgroundColor: '#fff', borderRadius: '4px', fontSize: '14px' }}>
            💡 כדי להיות רשמית בגיל זכאות יש צורך בקיום <strong>שני התנאים</strong>: גם הגעה לגיל פרישה וגם קבלת קצבה ראשונה.
          </p>
        </div>
        
        <div style={{ backgroundColor: '#fff', padding: '15px', borderRadius: '6px', marginBottom: '20px', border: '1px solid #ddd' }}>
          <h4 style={{ color: '#2c3e50', marginTop: 0 }}>🔹 חישוב במסך קיבוע זכויות:</h4>
          <ol style={{ lineHeight: '1.8', margin: '10px 0' }}>
            <li><strong>יתרת הון פטורה ראשונית</strong> = תקרת קצבה מזכה לשנת גיל הזכאות × 180 × אחוז הון פטור</li>
            <li><strong>פגיעה בפטור למענק</strong> = ערך מענק מוצמד × 1.35<br/>
              <span style={{ fontSize: '13px', color: '#666' }}>
                (חובה לבדוק יחס 32 שנה ויחס גיל פרישה. פגיעה של היוונים = ערך ללא ×1.35)
              </span>
            </li>
            <li><strong>יתרה נותרת</strong> = יתרה ראשונית - סך פגיעות</li>
            <li><strong>אחוז פטור מחושב</strong> = (יתרה נותרת / 180) / תקרת הקצבה המזכה לשנת גיל הזכאות<br/>
              <span style={{ fontSize: '13px', color: '#28a745', fontWeight: 'bold' }}>
                דוגמה: (622,966.1 / 180) / 8,380 = 3,461 / 8,380 = 41.29%
              </span>
            </li>
          </ol>
          <p style={{ margin: '10px 0 0 0', padding: '10px', backgroundColor: '#d4edda', borderRadius: '4px', color: '#155724' }}>
            ✅ <strong>אחוז זה נשמר ומשמש לחישוב הקצבה הפטורה במסך התוצאות!</strong>
          </p>
        </div>
        
        <div style={{ backgroundColor: '#fff', padding: '15px', borderRadius: '6px', marginBottom: '20px', border: '1px solid #ddd' }}>
          <h4 style={{ color: '#2c3e50', marginTop: 0 }}>🔹 חישוב במסך תוצאות:</h4>
          <div style={{ padding: '15px', backgroundColor: '#f8d7da', borderRadius: '4px', marginBottom: '10px', border: '1px solid #f5c6cb' }}>
            <p style={{ margin: 0, fontWeight: 'bold', color: '#721c24', fontSize: '16px' }}>
              קצבה פטורה = אחוז פטור מקיבוע × תקרת קצבה של השנה הראשונה בתזרים
            </p>
          </div>
          <p style={{ margin: '10px 0' }}><strong>דוגמה:</strong> 41.29% × 9,430 (תקרה 2025) = 3,893 ₪</p>
          <p style={{ color: '#dc3545', fontWeight: 'bold', margin: '10px 0 0 0' }}>
            ⚠️ לא להכפיל באחוז כללי! לא לחשב מחדש! רק אחוז מקיבוע × תקרה!
          </p>
        </div>
        
        <div style={{ backgroundColor: '#fff', padding: '15px', borderRadius: '6px', border: '1px solid #ddd' }}>
          <h4 style={{ color: '#2c3e50', marginTop: 0 }}>🔹 כללים חשובים:</h4>
          <ul style={{ lineHeight: '1.8', margin: 0 }}>
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
