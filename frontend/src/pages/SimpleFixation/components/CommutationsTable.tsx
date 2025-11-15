import React from 'react';
import { formatDateToDDMMYYYY } from '../../../utils/dateUtils';
import { Commutation } from '../types';
import { formatMoney } from '../utils/fixationCalculations';

interface CommutationsTableProps {
  commutations: Commutation[];
}

export const CommutationsTable: React.FC<CommutationsTableProps> = ({ commutations }) => {
  return (
    <div
      style={{
        marginBottom: '30px',
        padding: '20px',
        border: '1px solid #28a745',
        borderRadius: '4px',
        backgroundColor: '#f0fff4'
      }}
    >
      <h3>טבלת היוונים פטורים</h3>

      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            marginBottom: '15px'
          }}
        >
          <thead>
            <tr style={{ backgroundColor: '#d4edda' }}>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                שם המשלם
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                תיק ניכויים
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                תאריך היוון
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                סכום היוון
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                סוג ההיוון
              </th>
            </tr>
          </thead>
          <tbody>
            {commutations.map((commutation) => (
              <tr key={commutation.id}>
                <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                  {commutation.fund_name}
                </td>
                <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                  {commutation.deduction_file || '-'}
                </td>
                <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                  {commutation.commutation_date
                    ? formatDateToDDMMYYYY(new Date(commutation.commutation_date))
                    : '-'}
                </td>
                <td
                  style={{
                    padding: '10px',
                    border: '1px solid #ddd',
                    textAlign: 'left'
                  }}
                >
                  ₪{formatMoney(commutation.exempt_amount)}
                </td>
                <td style={{ padding: '10px', border: '1px solid #ddd' }}>
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
