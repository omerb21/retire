import React from 'react';
import { PensionAccount, EditingCell } from '../types';
import { EditableNumberCell } from './EditableNumberCell';
import { formatMoney } from './pensionTableFormatting';

interface PensionTableRowProps {
  account: PensionAccount;
  index: number;
  editingCell: EditingCell | null;
  setEditingCell: (cell: EditingCell | null) => void;
  conversionType: 'pension' | 'capital_asset' | undefined;
  toggleAccountSelection: (index: number) => void;
  updateCellValue: (index: number, field: string, value: any) => void;
  toggleAmountSelection: (index: number, field: string, checked: boolean) => void;
  setConversionType: (index: number, type: 'pension' | 'capital_asset') => void;
  deleteAccount: (index: number) => void;
}

export const PensionTableRow: React.FC<PensionTableRowProps> = ({
  account,
  index,
  editingCell,
  setEditingCell,
  conversionType,
  toggleAccountSelection,
  updateCellValue,
  toggleAmountSelection,
  setConversionType,
  deleteAccount,
}) => {
  const hasSelectedAmounts = React.useMemo(
    () => Object.values(account.selected_amounts || {}).some(Boolean),
    [account.selected_amounts]
  );

  return (
    <tr
      className={
        account.selected
          ? 'pension-table-row pension-table-row--selected'
          : 'pension-table-row'
      }
    >
      <td className="pension-table-select-cell">
        <input
          type="checkbox"
          checked={account.selected || false}
          onChange={() => toggleAccountSelection(index)}
        />
      </td>

      {/* מספר חשבון - עריכה */}
      <td
        className="pension-table-editable-text"
        onClick={() => setEditingCell({ row: index, field: 'מספר_חשבון' })}
      >
        {editingCell?.row === index && editingCell?.field === 'מספר_חשבון' ? (
          <input
            type="text"
            defaultValue={account.מספר_חשבון}
            onBlur={(e) => updateCellValue(index, 'מספר_חשבון', e.target.value)}
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateCellValue(index, 'מספר_חשבון', e.currentTarget.value)
            }
            autoFocus
            className="pension-table-text-input"
          />
        ) : (
          account.מספר_חשבון
        )}
      </td>

      {/* שם תכנית - עריכה */}
      <td
        className="pension-table-editable-text"
        onClick={() => setEditingCell({ row: index, field: 'שם_תכנית' })}
      >
        {editingCell?.row === index && editingCell?.field === 'שם_תכנית' ? (
          <input
            type="text"
            defaultValue={account.שם_תכנית}
            onBlur={(e) => updateCellValue(index, 'שם_תכנית', e.target.value)}
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateCellValue(index, 'שם_תכנית', e.currentTarget.value)
            }
            autoFocus
            className="pension-table-text-input"
          />
        ) : (
          account.שם_תכנית
        )}
      </td>

      {/* חברה מנהלת - עריכה */}
      <td
        className="pension-table-editable-text"
        onClick={() => setEditingCell({ row: index, field: 'חברה_מנהלת' })}
      >
        {editingCell?.row === index && editingCell?.field === 'חברה_מנהלת' ? (
          <input
            type="text"
            defaultValue={account.חברה_מנהלת}
            onBlur={(e) => updateCellValue(index, 'חברה_מנהלת', e.target.value)}
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateCellValue(index, 'חברה_מנהלת', e.currentTarget.value)
            }
            autoFocus
            className="pension-table-text-input"
          />
        ) : (
          account.חברה_מנהלת
        )}
      </td>

      {/* יתרה - ערך מקור מהקובץ (לא ניתנת לעריכה) */}
      <td className="pension-table-balance-cell">{formatMoney(account.יתרה)}</td>

      <EditableNumberCell
        account={account}
        index={index}
        field="פיצויים_מעסיק_נוכחי"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="פיצויים_לאחר_התחשבנות"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="פיצויים_שלא_עברו_התחשבנות"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="פיצויים_ממעסיקים_קודמים_רצף_זכויות"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="פיצויים_ממעסיקים_קודמים_רצף_קצבה"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="תגמולי_עובד_עד_2000"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="תגמולי_עובד_אחרי_2000"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="תגמולי_עובד_אחרי_2008_לא_משלמת"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="תגמולי_מעביד_עד_2000"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="תגמולי_מעביד_אחרי_2000"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />
      <EditableNumberCell
        account={account}
        index={index}
        field="תגמולי_מעביד_אחרי_2008_לא_משלמת"
        editingCell={editingCell}
        setEditingCell={setEditingCell}
        updateCellValue={updateCellValue}
        toggleAmountSelection={toggleAmountSelection}
      />

      <td className="pension-table-components-total-cell">
        {formatMoney(account.סך_תגמולים)}
      </td>
      <td className="pension-table-components-total-cell">
        {formatMoney(account.סך_פיצויים)}
      </td>
      <td className="pension-table-components-total-cell pension-table-components-total-cell--strong">
        {formatMoney(account.סך_רכיבים)}
      </td>
      <td
        className={`pension-table-diff-cell ${
          (account.פער_יתרה_מול_רכיבים || 0) === 0
            ? 'pension-table-diff-cell--ok'
            : 'pension-table-diff-cell--mismatch'
        }`}
        title="פער בין יתרה מדווחת לסכום הרכיבים שהתקבלו מה-XML"
      >
        {formatMoney(account.פער_יתרה_מול_רכיבים || 0)}
      </td>

      {/* סוג מוצר - עריכה */}
      <td
        className="pension-table-editable-text"
        onClick={() => setEditingCell({ row: index, field: 'סוג_מוצר' })}
      >
        {editingCell?.row === index && editingCell?.field === 'סוג_מוצר' ? (
          <input
            type="text"
            defaultValue={account.סוג_מוצר}
            onBlur={(e) => updateCellValue(index, 'סוג_מוצר', e.target.value)}
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateCellValue(index, 'סוג_מוצר', e.currentTarget.value)
            }
            autoFocus
            className="pension-table-text-input"
          />
        ) : (
          account.סוג_מוצר
        )}
      </td>

      {/* תאריך התחלה - עריכה */}
      <td
        className="pension-table-editable-text"
        onClick={() => setEditingCell({ row: index, field: 'תאריך_התחלה' })}
      >
        {editingCell?.row === index && editingCell?.field === 'תאריך_התחלה' ? (
          <input
            type="text"
            defaultValue={account.תאריך_התחלה || ''}
            onBlur={(e) => updateCellValue(index, 'תאריך_התחלה', e.target.value)}
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateCellValue(index, 'תאריך_התחלה', e.currentTarget.value)
            }
            autoFocus
            className="pension-table-text-input"
            placeholder="DD/MM/YYYY"
          />
        ) : (
          account.תאריך_התחלה || 'לא ידוע'
        )}
      </td>

      {/* מעסיקים היסטוריים - עריכה */}
      <td
        className="pension-table-editable-text"
        onClick={() => setEditingCell({ row: index, field: 'מעסיקים_היסטוריים' })}
      >
        {editingCell?.row === index && editingCell?.field === 'מעסיקים_היסטוריים' ? (
          <input
            type="text"
            defaultValue={account.מעסיקים_היסטוריים || ''}
            onBlur={(e) =>
              updateCellValue(index, 'מעסיקים_היסטוריים', e.target.value)
            }
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateCellValue(index, 'מעסיקים_היסטוריים', e.currentTarget.value)
            }
            autoFocus
            className="pension-table-text-input"
          />
        ) : (
          account.מעסיקים_היסטוריים
        )}
      </td>

      {/* סוג המרה */}
      <td className="pension-table-conversion-cell">
        {(account.selected || hasSelectedAmounts) && (
          <select
            value={conversionType || ''}
            onChange={(e) =>
              setConversionType(index, e.target.value as 'pension' | 'capital_asset')
            }
            className="pension-table-conversion-select"
          >
            <option value="">בחר סוג המרה</option>
            <option value="pension">קצבה</option>
            <option value="capital_asset">נכס הון</option>
          </select>
        )}
      </td>

      {/* עמודת פעולות */}
      <td className="pension-table-actions-cell">
        <button
          onClick={() => deleteAccount(index)}
          className="pension-table-delete-button"
          title="מחק תכנית זו מהרשימה"
        >
          מחק
        </button>
      </td>
    </tr>
  );
};
