import React from 'react';
import { PensionAccount, EditingCell } from '../types';
import { EditableNumberCell } from './EditableNumberCell';

interface PensionTableProps {
  pensionData: PensionAccount[];
  editingCell: EditingCell | null;
  setEditingCell: (cell: EditingCell | null) => void;
  conversionTypes: Record<number, 'pension' | 'capital_asset'>;
  toggleAccountSelection: (index: number) => void;
  toggleAllAccountsSelection: () => void;
  updateCellValue: (index: number, field: string, value: any) => void;
  toggleAmountSelection: (index: number, field: string, checked: boolean) => void;
  setConversionType: (index: number, type: 'pension' | 'capital_asset') => void;
  deleteAccount: (index: number) => void;
}

/**
 * קומפוננטת הטבלה הראשית של התיק הפנסיוני
 */
export const PensionTable: React.FC<PensionTableProps> = ({
  pensionData,
  editingCell,
  setEditingCell,
  conversionTypes,
  toggleAccountSelection,
  toggleAllAccountsSelection,
  updateCellValue,
  toggleAmountSelection,
  setConversionType,
  deleteAccount
}) => {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
        <thead>
          <tr style={{ backgroundColor: "#f8f9fa" }}>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 50 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <input
                  type="checkbox"
                  checked={pensionData.length > 0 && pensionData.every(a => a.selected)}
                  onChange={toggleAllAccountsSelection}
                  style={{ transform: "scale(0.9)" }}
                />
                <span>בחר</span>
              </div>
            </th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>מספר חשבון</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 150 }}>שם תכנית</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 120 }}>חברה מנהלת</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 80, backgroundColor: "#f0f8ff" }}>יתרה</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים מעסיק נוכחי</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים לאחר התחשבנות</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים שלא עברו התחשבנות</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים מעסיקים קודמים (זכויות)</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים מעסיקים קודמים (קצבה)</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי עובד עד 2000</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי עובד אחרי 2000</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי עובד אחרי 2008 (לא משלמת)</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי מעביד עד 2000</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי מעביד אחרי 2000</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי מעביד אחרי 2008 (לא משלמת)</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 110 }}>סך תגמולים</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 110 }}>סך פיצויים</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 120 }}>סה"כ רכיבים</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 120 }}>פער יתרה מול רכיבים</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>סוג מוצר</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תאריך התחלה</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 150 }}>מעסיקים היסטוריים</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>המר ל...</th>
            <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 80 }}>פעולות</th>
          </tr>
        </thead>
        <tbody>
          {pensionData.map((account, index) => (
            <tr key={index} style={{ backgroundColor: account.selected ? "#e7f3ff" : "white" }}>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={account.selected || false}
                  onChange={() => toggleAccountSelection(index)}
                />
              </td>
              
              {/* מספר חשבון - עריכה */}
              <td 
                style={{ border: "1px solid #ddd", padding: 4, cursor: 'pointer' }} 
                onClick={() => setEditingCell({row: index, field: 'מספר_חשבון'})}
              >
                {editingCell?.row === index && editingCell?.field === 'מספר_חשבון' ? (
                  <input
                    type="text"
                    defaultValue={account.מספר_חשבון}
                    onBlur={(e) => updateCellValue(index, 'מספר_חשבון', e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'מספר_חשבון', e.currentTarget.value)}
                    autoFocus
                    style={{ width: '100%', padding: 2, fontSize: '12px' }}
                  />
                ) : account.מספר_חשבון}
              </td>
              
              {/* שם תכנית - עריכה */}
              <td 
                style={{ border: "1px solid #ddd", padding: 4, cursor: 'pointer' }} 
                onClick={() => setEditingCell({row: index, field: 'שם_תכנית'})}
              >
                {editingCell?.row === index && editingCell?.field === 'שם_תכנית' ? (
                  <input
                    type="text"
                    defaultValue={account.שם_תכנית}
                    onBlur={(e) => updateCellValue(index, 'שם_תכנית', e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'שם_תכנית', e.currentTarget.value)}
                    autoFocus
                    style={{ width: '100%', padding: 2, fontSize: '12px' }}
                  />
                ) : account.שם_תכנית}
              </td>
              
              {/* חברה מנהלת - עריכה */}
              <td 
                style={{ border: "1px solid #ddd", padding: 4, cursor: 'pointer' }} 
                onClick={() => setEditingCell({row: index, field: 'חברה_מנהלת'})}
              >
                {editingCell?.row === index && editingCell?.field === 'חברה_מנהלת' ? (
                  <input
                    type="text"
                    defaultValue={account.חברה_מנהלת}
                    onBlur={(e) => updateCellValue(index, 'חברה_מנהלת', e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'חברה_מנהלת', e.currentTarget.value)}
                    autoFocus
                    style={{ width: '100%', padding: 2, fontSize: '12px' }}
                  />
                ) : account.חברה_מנהלת}
              </td>
              
              {/* יתרה - ערך מקור מהקובץ (לא ניתנת לעריכה) */}
              <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right", backgroundColor: "#f0f8ff", fontWeight: "bold" }}>
                {(Number(account.יתרה) || 0).toLocaleString()}
              </td>

              <EditableNumberCell account={account} index={index} field="פיצויים_מעסיק_נוכחי" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="פיצויים_לאחר_התחשבנות" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="פיצויים_שלא_עברו_התחשבנות" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="פיצויים_ממעסיקים_קודמים_רצף_זכויות" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="פיצויים_ממעסיקים_קודמים_רצף_קצבה" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="תגמולי_עובד_עד_2000" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="תגמולי_עובד_אחרי_2000" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="תגמולי_עובד_אחרי_2008_לא_משלמת" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="תגמולי_מעביד_עד_2000" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="תגמולי_מעביד_אחרי_2000" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              <EditableNumberCell account={account} index={index} field="תגמולי_מעביד_אחרי_2008_לא_משלמת" editingCell={editingCell} setEditingCell={setEditingCell} updateCellValue={updateCellValue} toggleAmountSelection={toggleAmountSelection} />
              
              <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right", backgroundColor: "#f7fbff" }}>
                {(account.סך_תגמולים || 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right", backgroundColor: "#f7fbff" }}>
                {(account.סך_פיצויים || 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right", backgroundColor: "#eef7ff", fontWeight: "bold" }}>
                {(account.סך_רכיבים || 0).toLocaleString()}
              </td>
              <td
                style={{
                  border: "1px solid #ddd",
                  padding: 4,
                  textAlign: "right",
                  color: (account.פער_יתרה_מול_רכיבים || 0) === 0 ? "#155724" : "#721c24",
                  backgroundColor: (account.פער_יתרה_מול_רכיבים || 0) === 0 ? "#d4edda" : "#f8d7da",
                  fontWeight: "bold"
                }}
                title="פער בין יתרה מדווחת לסכום הרכיבים שהתקבלו מה-XML"
              >
                {(account.פער_יתרה_מול_רכיבים || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </td>

              {/* סוג מוצר - עריכה */}
              <td 
                style={{ border: "1px solid #ddd", padding: 4, cursor: 'pointer' }} 
                onClick={() => setEditingCell({row: index, field: 'סוג_מוצר'})}
              >
                {editingCell?.row === index && editingCell?.field === 'סוג_מוצר' ? (
                  <input
                    type="text"
                    defaultValue={account.סוג_מוצר}
                    onBlur={(e) => updateCellValue(index, 'סוג_מוצר', e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'סוג_מוצר', e.currentTarget.value)}
                    autoFocus
                    style={{ width: '100%', padding: 2, fontSize: '12px' }}
                  />
                ) : account.סוג_מוצר}
              </td>
              
              {/* תאריך התחלה - עריכה */}
              <td 
                style={{ border: "1px solid #ddd", padding: 4, cursor: 'pointer' }} 
                onClick={() => setEditingCell({row: index, field: 'תאריך_התחלה'})}
              >
                {editingCell?.row === index && editingCell?.field === 'תאריך_התחלה' ? (
                  <input
                    type="text"
                    defaultValue={account.תאריך_התחלה || ''}
                    onBlur={(e) => updateCellValue(index, 'תאריך_התחלה', e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'תאריך_התחלה', e.currentTarget.value)}
                    autoFocus
                    style={{ width: '100%', padding: 2, fontSize: '12px' }}
                    placeholder="DD/MM/YYYY"
                  />
                ) : (account.תאריך_התחלה || 'לא ידוע')}
              </td>
              
              {/* מעסיקים היסטוריים - עריכה */}
              <td 
                style={{ border: "1px solid #ddd", padding: 4, cursor: 'pointer' }} 
                onClick={() => setEditingCell({row: index, field: 'מעסיקים_היסטוריים'})}
              >
                {editingCell?.row === index && editingCell?.field === 'מעסיקים_היסטוריים' ? (
                  <input
                    type="text"
                    defaultValue={account.מעסיקים_היסטוריים || ''}
                    onBlur={(e) => updateCellValue(index, 'מעסיקים_היסטוריים', e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'מעסיקים_היסטוריים', e.currentTarget.value)}
                    autoFocus
                    style={{ width: '100%', padding: 2, fontSize: '12px' }}
                  />
                ) : account.מעסיקים_היסטוריים}
              </td>
              
              {/* סוג המרה */}
              <td style={{ border: "1px solid #ddd", padding: 6 }}>
                {(account.selected || Object.values(account.selected_amounts || {}).some(Boolean)) && (
                  <select
                    value={conversionTypes[index] || ''}
                    onChange={(e) => setConversionType(index, e.target.value as 'pension' | 'capital_asset')}
                    style={{ width: "100%" }}
                  >
                    <option value="">בחר סוג המרה</option>
                    <option value="pension">קצבה</option>
                    <option value="capital_asset">נכס הון</option>
                  </select>
                )}
              </td>
              
              {/* עמודת פעולות */}
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "center" }}>
                <button
                  onClick={() => deleteAccount(index)}
                  style={{
                    padding: "4px 8px",
                    backgroundColor: "#dc3545",
                    color: "white",
                    border: "none",
                    borderRadius: 3,
                    cursor: "pointer",
                    fontSize: "12px"
                  }}
                  title="מחק תכנית זו מהרשימה"
                >
                  מחק
                </button>
              </td>
            </tr>
          ))}

          {/* שורת סה"כ */}
          {pensionData.length > 0 && (
            <tr style={{ backgroundColor: "#fff8e1", fontWeight: "bold", borderTop: "3px solid #ff9800" }}>
              <td style={{ border: "1px solid #ddd", padding: 6 }}></td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "center" }} colSpan={3}>
                סה"כ
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right", backgroundColor: "#f0f8ff" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.יתרה) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_מעסיק_נוכחי) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_לאחר_התחשבנות) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_שלא_עברו_התחשבנות) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_ממעסיקים_קודמים_רצף_זכויות) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_ממעסיקים_קודמים_רצף_קצבה) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_עובד_עד_2000) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_עובד_אחרי_2000) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_עובד_אחרי_2008_לא_משלמת) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_מעביד_עד_2000) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_מעביד_אחרי_2000) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_מעביד_אחרי_2008_לא_משלמת) || 0), 0).toLocaleString()}
              </td>
              <td style={{ border: "1px solid #ddd", padding: 6 }} colSpan={4}></td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};
