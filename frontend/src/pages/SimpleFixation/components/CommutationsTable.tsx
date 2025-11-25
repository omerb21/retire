import React from 'react';
import { formatDateToDDMMYYYY } from '../../../utils/dateUtils';
import { Commutation } from '../types';
import { formatMoney } from '../utils/fixationCalculations';

interface CommutationsTableProps {
  commutations: Commutation[];
}

export const CommutationsTable: React.FC<CommutationsTableProps> = ({ commutations }) => {
  return (
    <div className="fixation-commutations-card">
      <h3>טבלת היוונים פטורים</h3>

      <div className="fixation-table-wrapper">
        <table className="fixation-commutations-table">
          <thead>
            <tr className="fixation-commutations-header-row">
              <th className="fixation-table-header-cell">
                שם המשלם
              </th>
              <th className="fixation-table-header-cell">
                תיק ניכויים
              </th>
              <th className="fixation-table-header-cell">
                תאריך היוון
              </th>
              <th className="fixation-table-header-cell">
                סכום היוון
              </th>
              <th className="fixation-table-header-cell">
                סוג ההיוון
              </th>
            </tr>
          </thead>
          <tbody>
            {commutations.map((commutation) => (
              <tr key={commutation.id}>
                <td className="fixation-table-cell">
                  {commutation.fund_name}
                </td>
                <td className="fixation-table-cell">
                  {commutation.deduction_file || '-'}
                </td>
                <td className="fixation-table-cell">
                  {commutation.commutation_date
                    ? formatDateToDDMMYYYY(new Date(commutation.commutation_date))
                    : '-'}
                </td>
                <td className="fixation-table-cell fixation-table-cell--left">
                  ₪{formatMoney(commutation.exempt_amount)}
                </td>
                <td className="fixation-table-cell">
                  {commutation.commutation_type === 'exempt' ? 'פטור ממס' : 'חייב במס'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
