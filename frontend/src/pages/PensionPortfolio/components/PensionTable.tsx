import React from 'react';
import { PensionAccount, EditingCell } from '../types';
import { formatMoney } from './pensionTableFormatting';
import { PensionTableRow } from './PensionTableRow';
import { PensionTableSummaryRow } from './PensionTableSummaryRow';

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
const PensionTableComponent: React.FC<PensionTableProps> = ({
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
  const allSelected = React.useMemo(
    () => pensionData.length > 0 && pensionData.every((a) => a.selected),
    [pensionData]
  );

  const summaryTotals = React.useMemo(
    () =>
      pensionData.reduce(
        (totals, acc) => {
          totals.totalBalance += Number(acc.יתרה) || 0;
          totals.totalCurrentSeverance += Number(acc.פיצויים_מעסיק_נוכחי) || 0;
          totals.totalPostSettlementSeverance += Number(acc.פיצויים_לאחר_התחשבנות) || 0;
          totals.totalUnsettledSeverance += Number(acc.פיצויים_שלא_עברו_התחשבנות) || 0;
          totals.totalPrevEmployersRights += Number(acc.פיצויים_ממעסיקים_קודמים_רצף_זכויות) || 0;
          totals.totalPrevEmployersPension += Number(acc.פיצויים_ממעסיקים_קודמים_רצף_קצבה) || 0;
          totals.totalEmployeeTo2000 += Number(acc.תגמולי_עובד_עד_2000) || 0;
          totals.totalEmployeeAfter2000 += Number(acc.תגמולי_עובד_אחרי_2000) || 0;
          totals.totalEmployeeAfter2008NonPaying += Number(acc.תגמולי_עובד_אחרי_2008_לא_משלמת) || 0;
          totals.totalEmployerTo2000 += Number(acc.תגמולי_מעביד_עד_2000) || 0;
          totals.totalEmployerAfter2000 += Number(acc.תגמולי_מעביד_אחרי_2000) || 0;
          totals.totalEmployerAfter2008NonPaying += Number(acc.תגמולי_מעביד_אחרי_2008_לא_משלמת) || 0;
          return totals;
        },
        {
          totalBalance: 0,
          totalCurrentSeverance: 0,
          totalPostSettlementSeverance: 0,
          totalUnsettledSeverance: 0,
          totalPrevEmployersRights: 0,
          totalPrevEmployersPension: 0,
          totalEmployeeTo2000: 0,
          totalEmployeeAfter2000: 0,
          totalEmployeeAfter2008NonPaying: 0,
          totalEmployerTo2000: 0,
          totalEmployerAfter2000: 0,
          totalEmployerAfter2008NonPaying: 0,
        }
      ),
    [pensionData]
  );

  return (
    <div className="pension-table-container">
      <table className="pension-table">
        <thead>
          <tr>
            <th className="pension-table-header-select">
              <div className="pension-table-select-all-wrapper">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAllAccountsSelection}
                  className="pension-table-checkbox"
                />
                <span>בחר</span>
              </div>
            </th>
            <th className="pension-table-header-account">מספר חשבון</th>
            <th className="pension-table-header-plan">שם תכנית</th>
            <th className="pension-table-header-company">חברה מנהלת</th>
            <th className="pension-table-header-balance">יתרה</th>
            <th className="pension-table-header-generic">פיצויים מעסיק נוכחי</th>
            <th className="pension-table-header-generic">פיצויים לאחר התחשבנות</th>
            <th className="pension-table-header-generic">פיצויים שלא עברו התחשבנות</th>
            <th className="pension-table-header-generic">פיצויים מעסיקים קודמים (זכויות)</th>
            <th className="pension-table-header-generic">פיצויים מעסיקים קודמים (קצבה)</th>
            <th className="pension-table-header-generic">תגמולי עובד עד 2000</th>
            <th className="pension-table-header-generic">תגמולי עובד אחרי 2000</th>
            <th className="pension-table-header-generic">תגמולי עובד אחרי 2008 (לא משלמת)</th>
            <th className="pension-table-header-generic">תגמולי מעביד עד 2000</th>
            <th className="pension-table-header-generic">תגמולי מעביד אחרי 2000</th>
            <th className="pension-table-header-generic">תגמולי מעביד אחרי 2008 (לא משלמת)</th>
            <th className="pension-table-header-generic">סך תגמולים</th>
            <th className="pension-table-header-generic">סך פיצויים</th>
            <th className="pension-table-header-generic">סה"כ רכיבים</th>
            <th className="pension-table-header-generic">פער יתרה מול רכיבים</th>
            <th className="pension-table-header-generic">סוג מוצר</th>
            <th className="pension-table-header-generic">תאריך התחלה</th>
            <th className="pension-table-header-generic">מעסיקים היסטוריים</th>
            <th className="pension-table-header-generic">המר ל...</th>
            <th className="pension-table-header-generic">פעולות</th>
          </tr>
        </thead>
        <tbody>
          {pensionData.map((account, index) => (
            <PensionTableRow
              key={index}
              account={account}
              index={index}
              editingCell={editingCell}
              setEditingCell={setEditingCell}
              conversionType={conversionTypes[index]}
              toggleAccountSelection={toggleAccountSelection}
              updateCellValue={updateCellValue}
              toggleAmountSelection={toggleAmountSelection}
              setConversionType={setConversionType}
              deleteAccount={deleteAccount}
            />
          ))}

          {/* שורת סה"כ */}
          {pensionData.length > 0 && (
            <PensionTableSummaryRow summaryTotals={summaryTotals} />
          )}
        </tbody>
      </table>
    </div>
  );
};

export const PensionTable = React.memo(PensionTableComponent);
