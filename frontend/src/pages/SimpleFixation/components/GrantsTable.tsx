import React from 'react';
import { formatDateToDDMMYYYY } from '../../../utils/dateUtils';
import { GrantSummary } from '../types';
import { formatMoney } from '../utils/fixationCalculations';

interface GrantsTableProps {
  grantsSummary: GrantSummary[];
}

export const GrantsTable: React.FC<GrantsTableProps> = ({ grantsSummary }) => {
  return (
    <div className="fixation-grants-card">
      <h3>טבלת מענקים</h3>

      <div className="fixation-table-wrapper">
        <table className="fixation-grants-table">
          <thead>
            <tr className="fixation-grants-header-row">
              <th className="fixation-table-header-cell">
                שם מעסיק
              </th>
              <th className="fixation-table-header-cell">
                תאריך קבלת המענק
              </th>
              <th className="fixation-table-header-cell">
                מענק נומינאלי ששולם
              </th>
              <th className="fixation-table-header-cell">
                סכום רלוונטי לקיזוז פטור
              </th>
              <th className="fixation-table-header-cell">
                סכום רלוונטי לאחר הצמדה
              </th>
              <th className="fixation-table-header-cell">
                פגיעה בפטור
              </th>
              <th className="fixation-table-header-cell">
                סטטוס
              </th>
            </tr>
          </thead>
          <tbody>
            {grantsSummary.map((grant, index) => {
              const isExcluded = !!grant.exclusion_reason

              const isNoImpact =
                !isExcluded &&
                grant.impact_on_exemption === 0 &&
                grant.indexed_full !== undefined &&
                (grant.indexed_full || 0) > 0

              const statusText = grant.exclusion_reason
                ? grant.exclusion_reason
                : isNoImpact
                ? (grant.ratio_32y || 0) === 0
                  ? 'לא נכלל בחישוב (יחס 32 שנים = 0)'
                  : 'לא נכלל בחישוב (פגיעה = 0)'
                : 'נכלל בחישוב'

              return (
                <tr key={index}>
                  <td className="fixation-table-cell">{grant.employer_name}</td>
                  <td className="fixation-table-cell">
                    {grant.grant_date ? (
                      grant.grant_date.includes('-')
                        ? formatDateToDDMMYYYY(new Date(grant.grant_date))
                        : grant.grant_date
                    ) : (
                      ''
                    )}
                  </td>
                  <td className="fixation-table-cell fixation-table-cell--left">
                    ₪{formatMoney(grant.grant_amount)}
                  </td>
                  <td className="fixation-table-cell fixation-table-cell--left">
                    {isExcluded
                      ? 'הוחרג'
                      : `₪${formatMoney(grant.grant_amount * (grant.ratio_32y || 0))}`}
                  </td>
                  <td
                    className={`fixation-table-cell fixation-table-cell--left ${
                      isExcluded ? 'fixation-table-cell--muted' : 'fixation-table-cell--primary'
                    }`}
                  >
                    {isExcluded
                      ? 'הוחרג'
                      : `₪${formatMoney(grant.limited_indexed_amount || 0)}`}
                  </td>
                  <td
                    className={`fixation-table-cell fixation-table-cell--left ${
                      isExcluded ? 'fixation-table-cell--muted' : 'fixation-table-cell--danger'
                    }`}
                  >
                    {isExcluded
                      ? 'הוחרג'
                      : `₪${formatMoney(grant.impact_on_exemption || 0)}`}
                  </td>
                  <td
                    className={`fixation-table-cell fixation-table-cell--right ${
                      isExcluded ? 'fixation-table-cell--danger' : 'fixation-table-cell--success'
                    }`}
                  >
                    {statusText}
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
