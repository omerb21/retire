import React from 'react';
import { formatDateToDDMMYYYY } from '../../../utils/dateUtils';
import { GrantSummary } from '../types';
import { formatMoney } from '../utils/fixationCalculations';

interface GrantsTableProps {
  grantsSummary: GrantSummary[];
}

export const GrantsTable: React.FC<GrantsTableProps> = ({ grantsSummary }) => {
  return (
    <div
      style={{
        marginBottom: '30px',
        padding: '20px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        backgroundColor: '#f9f9f9'
      }}
    >
      <h3>טבלת מענקים</h3>

      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            marginBottom: '15px'
          }}
        >
          <thead>
            <tr style={{ backgroundColor: '#e9ecef' }}>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                שם מעסיק
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                תאריך קבלת המענק
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                מענק נומינאלי ששולם
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                סכום רלוונטי לקיזוז פטור
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                סכום רלוונטי לאחר הצמדה
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                פגיעה בפטור
              </th>
              <th style={{ padding: '10px', border: '1px solid #ddd', textAlign: 'right' }}>
                סטטוס
              </th>
            </tr>
          </thead>
          <tbody>
            {grantsSummary.map((grant, index) => {
              const isExcluded =
                !!grant.exclusion_reason ||
                (grant.impact_on_exemption === 0 && grant.indexed_full && grant.indexed_full > 0);

              return (
                <tr key={index}>
                  <td style={{ padding: '10px', border: '1px solid #ddd' }}>{grant.employer_name}</td>
                  <td style={{ padding: '10px', border: '1px solid #ddd' }}>
                    {grant.grant_date ? (
                      grant.grant_date.includes('-')
                        ? formatDateToDDMMYYYY(new Date(grant.grant_date))
                        : grant.grant_date
                    ) : (
                      ''
                    )}
                  </td>
                  <td
                    style={{
                      padding: '10px',
                      border: '1px solid #ddd',
                      textAlign: 'left'
                    }}
                  >
                    ₪{formatMoney(grant.grant_amount)}
                  </td>
                  <td
                    style={{
                      padding: '10px',
                      border: '1px solid #ddd',
                      textAlign: 'left'
                    }}
                  >
                    {isExcluded
                      ? 'הוחרג'
                      : `₪${formatMoney(grant.grant_amount * (grant.ratio_32y || 0))}`}
                  </td>
                  <td
                    style={{
                      padding: '10px',
                      border: '1px solid #ddd',
                      textAlign: 'left',
                      color: isExcluded ? '#6c757d' : '#007bff'
                    }}
                  >
                    {isExcluded
                      ? 'הוחרג'
                      : `₪${formatMoney(grant.limited_indexed_amount || 0)}`}
                  </td>
                  <td
                    style={{
                      padding: '10px',
                      border: '1px solid #ddd',
                      textAlign: 'left',
                      color: isExcluded ? '#6c757d' : '#dc3545'
                    }}
                  >
                    {isExcluded
                      ? 'הוחרג'
                      : `₪${formatMoney(grant.impact_on_exemption || 0)}`}
                  </td>
                  <td
                    style={{
                      padding: '10px',
                      border: '1px solid #ddd',
                      textAlign: 'right',
                      color: isExcluded ? '#dc3545' : '#28a745'
                    }}
                  >
                    {grant.exclusion_reason
                      ? grant.exclusion_reason
                      : isExcluded
                      ? 'הוחרג - חוק 15 השנים'
                      : 'נכלל בחישוב'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
