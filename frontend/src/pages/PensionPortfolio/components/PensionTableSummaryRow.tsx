import React from 'react';
import { formatMoney } from './pensionTableFormatting';

interface PensionTableSummaryTotals {
  totalBalance: number;
  totalCurrentSeverance: number;
  totalPostSettlementSeverance: number;
  totalUnsettledSeverance: number;
  totalPrevEmployersRights: number;
  totalPrevEmployersPension: number;
  totalEmployeeTo2000: number;
  totalEmployeeAfter2000: number;
  totalEmployeeAfter2008NonPaying: number;
  totalEmployerTo2000: number;
  totalEmployerAfter2000: number;
  totalEmployerAfter2008NonPaying: number;
}

interface PensionTableSummaryRowProps {
  summaryTotals: PensionTableSummaryTotals;
}

export const PensionTableSummaryRow: React.FC<PensionTableSummaryRowProps> = ({
  summaryTotals,
}) => {
  return (
    <tr className="pension-table-summary-row">
      <td></td>
      <td className="pension-table-summary-label-cell" colSpan={3}>
        סה"כ
      </td>
      <td className="pension-table-summary-balance-cell">
        {formatMoney(summaryTotals.totalBalance)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalCurrentSeverance)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalPostSettlementSeverance)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalUnsettledSeverance)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalPrevEmployersRights)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalPrevEmployersPension)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalEmployeeTo2000)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalEmployeeAfter2000)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalEmployeeAfter2008NonPaying)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalEmployerTo2000)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalEmployerAfter2000)}
      </td>
      <td className="pension-table-summary-cell">
        {formatMoney(summaryTotals.totalEmployerAfter2008NonPaying)}
      </td>
      <td colSpan={4}></td>
    </tr>
  );
};
