import React from 'react';
import { PensionAccount, EditingCell } from '../types';

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
    <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <input
          type="checkbox"
          checked={(account.selected_amounts as any)?.[field] || false}
          onChange={(e) => toggleAmountSelection(index, field, e.target.checked)}
          style={{ transform: "scale(0.8)" }}
        />
        <div 
          style={{ flex: 1, cursor: 'pointer' }} 
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
              style={{ width: '100%', padding: 2, fontSize: '12px', textAlign: 'right' }}
            />
          ) : (value > 0 ? value.toLocaleString() : '-')}
        </div>
      </div>
    </td>
  );
};
