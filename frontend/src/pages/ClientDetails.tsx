import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getClient, ClientItem } from "../lib/api";

export default function ClientDetails() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<ClientItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadClient() {
      if (!id) return;
      
      setLoading(true);
      setError(null);
      
      try {
        const clientData = await getClient(parseInt(id));
        setClient(clientData);
      } catch (e: any) {
        setError(`שגיאה בטעינת לקוח: ${e?.message || e}`);
      } finally {
        setLoading(false);
      }
    }
    
    loadClient();
  }, [id]);

  if (loading) return <div>טוען...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!client) return <div>לקוח לא נמצא</div>;

  return (
    <div className="client-details">
      <h2>פרטי לקוח: {client.first_name} {client.last_name}</h2>
      
      <div className="client-info" style={{ marginBottom: '20px' }}>
        <p><strong>ת"ז:</strong> {client.id_number}</p>
        <p><strong>תאריך לידה:</strong> {client.birth_date}</p>
        <p><strong>אימייל:</strong> {client.email || 'לא הוזן'}</p>
        <p><strong>טלפון:</strong> {client.phone || 'לא הוזן'}</p>
      </div>
      
      <div className="module-links" style={{ 
        display: 'flex', 
        flexDirection: 'row', 
        gap: '10px', 
        flexWrap: 'wrap',
        marginBottom: '20px'
      }}>
        <ModuleLink to={`/clients/${id}/pension-funds`} label="קרנות פנסיה" />
        <ModuleLink to={`/clients/${id}/additional-income`} label="הכנסות נוספות" />
        <ModuleLink to={`/clients/${id}/capital-assets`} label="נכסי הון" />
        <ModuleLink to={`/clients/${id}/scenarios`} label="תרחישים" />
        <ModuleLink to={`/clients/${id}/fixation`} label="קיבוע מס" />
      </div>
      
      <Link to="/clients" style={{ display: 'inline-block', marginTop: '20px' }}>
        חזרה לרשימת לקוחות
      </Link>
    </div>
  );
}

function ModuleLink({ to, label }: { to: string, label: string }) {
  return (
    <Link 
      to={to}
      style={{
        padding: '10px 15px',
        backgroundColor: '#f0f0f0',
        borderRadius: '4px',
        textDecoration: 'none',
        color: '#333',
        fontWeight: 'bold',
      }}
    >
      {label}
    </Link>
  );
}
