import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useClientData } from './hooks/useClientData';
import { ClientInfo } from './components/ClientInfo';
import { ClientNavigation } from './components/ClientNavigation';
import { ClientSystemSnapshot } from './components/ClientSystemSnapshot';
import './ClientDetails.css';

export default function ClientDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { client, loading, error, refreshClient } = useClientData(id);

  if (loading) return <div>טוען...</div>;
  if (error && !client) return <div className="error">{error}</div>;
  if (!client) return <div>לקוח לא נמצא</div>;

  return (
    <div className="client-details-page">
      {/* Adjust 100px based on your header height */}
      <div className="client-details client-details-main">
        {/* Back to clients link - positioned top-left */}
        <Link 
          to="/clients" 
          className="client-details-back-link"
        >
          ← חזרה לרשימת לקוחות
        </Link>
        
        <h2 className="client-details-title">
          תהליך פרישה - {client.first_name} {client.last_name} (ת"ז: {client.id_number})
        </h2>

        <ClientInfo client={client} />
        <ClientNavigation clientId={id!} />
      </div>
      
      {/* System Snapshot - שמירה ושחזור מצב - Fixed at bottom */}
      <div className="client-details-snapshot-wrapper">
        <ClientSystemSnapshot 
          clientId={parseInt(id!)} 
          onSnapshotRestored={refreshClient}
        />
      </div>
    </div>
  );
}
