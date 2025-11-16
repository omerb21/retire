import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useClientData } from './hooks/useClientData';
import { ClientInfo } from './components/ClientInfo';
import { ClientNavigation } from './components/ClientNavigation';
import { ClientSystemSnapshot } from './components/ClientSystemSnapshot';

export default function ClientDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { client, loading, error, refreshClient } = useClientData(id);

  if (loading) return <div>טוען...</div>;
  if (error && !client) return <div className="error">{error}</div>;
  if (!client) return <div>לקוח לא נמצא</div>;

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      minHeight: 'calc(100vh - 100px)' /* Adjust 100px based on your header height */
    }}>
      <div className="client-details" style={{ flex: 1, position: 'relative' }}>
        {/* Back to clients link - positioned top-left */}
        <Link 
          to="/clients" 
          style={{
            position: 'absolute',
            left: '20px',
            top: '10px',
            textDecoration: 'none',
            color: '#007bff',
            fontWeight: 'bold',
            padding: '5px 10px',
            borderRadius: '4px',
            border: '1px solid #dee2e6',
            backgroundColor: '#f8f9fa'
          }}
        >
          ← חזרה לרשימת לקוחות
        </Link>
        
        <h2 style={{ marginBottom: '30px', textAlign: 'center' }}>
          תהליך פרישה - {client.first_name} {client.last_name} (ת"ז: {client.id_number})
        </h2>

        <ClientInfo client={client} />
        <ClientNavigation clientId={id!} />
      </div>
      
      {/* System Snapshot - שמירה ושחזור מצב - Fixed at bottom */}
      <div style={{ 
        marginTop: 'auto',
        padding: '20px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '8px 8px 0 0',
        borderBottom: 'none'
      }}>
            <ClientSystemSnapshot 
          clientId={parseInt(id!)} 
          onSnapshotRestored={refreshClient}
        />
      </div>
    </div>
  );
}
