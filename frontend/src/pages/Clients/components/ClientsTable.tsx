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
    <div className="modern-card" style={{ marginTop: '2rem' }}>
      <div className="card-header">
        <h3 className="card-title">רשימת לקוחות</h3>
      </div>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
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
                <td style={td}>{c.id ?? ''}</td>
                <td style={td}>{c.id_number ?? ''}</td>
                <td style={td}>
                  <Link to={`/clients/${c.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    {c.first_name ?? ''}
                  </Link>
                </td>
                <td style={td}>
                  <Link to={`/clients/${c.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    {c.last_name ?? ''}
                  </Link>
                </td>
                <td style={td}>{c.birth_date ? formatDateToDDMMYY(new Date(c.birth_date)) : ''}</td>
                <td style={td}>{c.gender === 'male' ? 'זכר' : 'נקבה'}</td>
                <td style={td}>{c.email ?? ''}</td>
                <td>
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                    <Link
                      to={`/clients/${c.id}`}
                      className="btn btn-primary"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                    >
                      פתח
                    </Link>
                    <button
                      onClick={() => onStartEdit(c)}
                      className="btn btn-secondary"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                    >
                      ערוך
                    </button>
                    <button
                      onClick={() => onDeleteClient(c.id!)}
                      className="btn btn-danger"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
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

const td: React.CSSProperties = { textAlign: 'right', borderBottom: '1px solid #f0f0f0', padding: 8 };
