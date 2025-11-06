import React from 'react';
import { ClientItem } from '../../../../lib/api';
import { formatDateToDDMMYY } from '../../../../utils/dateUtils';

interface ClientInfoProps {
  client: ClientItem;
}

export const ClientInfo: React.FC<ClientInfoProps> = ({ client }) => {
  return (
    <div className="client-info" style={{ marginBottom: '20px' }}>
      <p><strong>ת"ז:</strong> {client.id_number}</p>
      <p><strong>תאריך לידה:</strong> {client.birth_date}</p>
      <p><strong>מין:</strong> {client.gender === 'male' ? 'זכר' : client.gender === 'female' ? 'נקבה' : 'לא צוין'}</p>
      <p><strong>אימייל:</strong> {client.email || 'לא הוזן'}</p>
      <p><strong>טלפון:</strong> {client.phone || 'לא הוזן'}</p>
      
      {/* תאריך קבלת קצבה ראשונה - תצוגה בלבד */}
      <div style={{ marginTop: '15px' }}>
        <p>
          <strong>תאריך קבלת קצבה ראשונה:</strong>{' '}
          <span style={{ color: client.pension_start_date ? '#28a745' : '#dc3545' }}>
            {client.pension_start_date
              ? formatDateToDDMMYY(new Date(client.pension_start_date))
              : 'טרם הוזן תאריך קבלת קצבה'}
          </span>
        </p>
      </div>
    </div>
  );
};
