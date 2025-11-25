import React from 'react';
import { Link } from 'react-router-dom';
import { ClientItem } from '../../../lib/api';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';

interface ClientsTableProps {
  items: ClientItem[];
  loading: boolean;
  onStartEdit: (client: ClientItem) => void;
  onDeleteClient: (clientId: number) => void;
}

export const ClientsTable: React.FC<ClientsTableProps> = ({ items, loading, onStartEdit, onDeleteClient }) => {
  return (
    <div className="modern-card clients-table-card">
      <div className="card-header">
        <h3 className="card-title">רשימת לקוחות</h3>
      </div>
      {loading ? (
        <div className="clients-table-loading">
          <div className="spinner"></div>
        </div>
      ) : items.length === 0 ? (
        <div className="alert alert-info">אין לקוחות במערכת</div>
      ) : (
        <table className="modern-table">
          <thead>
            <tr>
              <th>#</th>
              <th>ת"ז</th>
              <th>שם פרטי</th>
              <th>שם משפחה</th>
              <th>תאריך לידה</th>
              <th>מין</th>
              <th>Email</th>
              <th>פעולות</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c, i) => (
              <tr key={`${c.id}-${i}`}>
                <td className="clients-table-cell">{c.id ?? ''}</td>
                <td className="clients-table-cell">{c.id_number ?? ''}</td>
                <td className="clients-table-cell">
                  <Link to={`/clients/${c.id}`} className="clients-table-link">
                    {c.first_name ?? ''}
                  </Link>
                </td>
                <td className="clients-table-cell">
                  <Link to={`/clients/${c.id}`} className="clients-table-link">
                    {c.last_name ?? ''}
                  </Link>
                </td>
                <td className="clients-table-cell">{c.birth_date ? formatDateToDDMMYY(new Date(c.birth_date)) : ''}</td>
                <td className="clients-table-cell">{c.gender === 'male' ? 'זכר' : 'נקבה'}</td>
                <td className="clients-table-cell">{c.email ?? ''}</td>
                <td>
                  <div className="clients-table-actions">
                    <Link
                      to={`/clients/${c.id}`}
                      className="btn btn-primary clients-table-action-button"
                    >
                      פתח
                    </Link>
                    <button
                      onClick={() => onStartEdit(c)}
                      className="btn btn-secondary clients-table-action-button"
                    >
                      ערוך
                    </button>
                    <button
                      onClick={() => onDeleteClient(c.id!)}
                      className="btn btn-danger clients-table-action-button"
                    >
                      מחק
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
