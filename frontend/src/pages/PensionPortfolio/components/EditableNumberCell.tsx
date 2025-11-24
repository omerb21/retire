import React from 'react';
import { PensionAccount, EditingCell } from '../types';
import { formatCurrency } from '../../../lib/validation';

interface EditableNumberCellProps {
  account: PensionAccount;
  index: number;
  field: string;
  label?: string;
  editingCell: EditingCell | null;
  setEditingCell: (cell: EditingCell | null) => void;
  updateCellValue: (index: number, field: string, value: any) => void;
  toggleAmountSelection: (index: number, field: string, checked: boolean) => void;
}

/**
 * קומפוננטת עזר לתא מספרי עם checkbox
 */
const formatMoney = (value: number): string => {
  const formatted = formatCurrency(value);
  return formatted.replace('₪', '').trim();
};

export const EditableNumberCell: React.FC<EditableNumberCellProps> = ({
  account,
  index,
  field,
  label,
  editingCell,
  setEditingCell,
  updateCellValue,
  toggleAmountSelection
}) => {
  const value = (account as any)[field] || 0;
  
  return (
    <td className="pension-table-cell-number">
      <div className="pension-table-number-wrapper">
        <input
          type="checkbox"
          checked={(account.selected_amounts as any)?.[field] || false}
          onChange={(e) => toggleAmountSelection(index, field, e.target.checked)}
          className="pension-table-checkbox-small"
        />
        <div 
          className="pension-table-number-input-wrapper"
          onClick={(e) => { 
            e.stopPropagation(); 
            setEditingCell({row: index, field}); 
          }}
        >
          {editingCell?.row === index && editingCell?.field === field ? (
            <input
              type="number"
              defaultValue={value}
              onBlur={(e) => updateCellValue(index, field, e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, field, e.currentTarget.value)}
              autoFocus
              className="pension-table-number-input"
            />
          ) : (value > 0 ? formatMoney(value) : '-')}
        </div>
      </div>
    </td>
  );
};
