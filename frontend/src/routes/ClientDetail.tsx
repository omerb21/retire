import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { clientApi, ClientResponse, handleApiError } from '../lib/api';

const ClientDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [client, setClient] = useState<ClientResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      fetchClientDetails(parseInt(id));
    }
  }, [id]);

  const fetchClientDetails = async (clientId: number) => {
    try {
      setLoading(true);
      const data = await clientApi.get(clientId);
      setClient(data);
      setError(null);
    } catch (err: any) {
      setError(handleApiError(err));
      console.error('Error fetching client details:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!client || !window.confirm('האם אתה בטוח שברצונך למחוק לקוח זה?')) {
      return;
    }

    try {
      setLoading(true);
      await clientApi.delete(client.id);
      navigate('/clients', { replace: true });
    } catch (err: any) {
      setError(handleApiError(err));
      console.error('Error deleting client:', err);
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8">טוען נתונים...</div>;
  }

  if (error) {
    return (
      <div className="container mx-auto p-4">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
        <Link to="/clients" className="text-blue-600 hover:text-blue-800">
          &larr; חזרה לרשימת הלקוחות
        </Link>
      </div>
    );
  }

  if (!client) {
    return (
      <div className="container mx-auto p-4">
        <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-4">
          לקוח לא נמצא
        </div>
        <Link to="/clients" className="text-blue-600 hover:text-blue-800">
          &larr; חזרה לרשימת הלקוחות
        </Link>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">פרטי לקוח</h1>
        <div className="space-x-2">
          <Link
            to={`/clients/${client.id}/edit`}
            className="bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded"
          >
            עריכה
          </Link>
          <button
            onClick={handleDelete}
            className="bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded"
            disabled={loading}
          >
            מחיקה
          </button>
        </div>
      </div>

      <div className="bg-white shadow-md rounded p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-gray-600">שם מלא</h3>
            <p className="text-lg">{client.full_name}</p>
          </div>
          <div>
            <h3 className="text-gray-600">מספר זהות</h3>
            <p className="text-lg">{client.id_number}</p>
          </div>
          <div>
            <h3 className="text-gray-600">תאריך לידה</h3>
            <p className="text-lg">{client.birth_date}</p>
          </div>
          <div>
            <h3 className="text-gray-600">אימייל</h3>
            <p className="text-lg">{client.email || '-'}</p>
          </div>
          <div>
            <h3 className="text-gray-600">טלפון</h3>
            <p className="text-lg">{client.phone || '-'}</p>
          </div>
          <div>
            <h3 className="text-gray-600">תאריך פרישה</h3>
            <p className="text-lg">{client.retirement_date || '-'}</p>
          </div>
          <div>
            <h3 className="text-gray-600">סטטוס</h3>
            <p className="text-lg">
              {client.is_active ? (
                <span className="text-green-600">פעיל</span>
              ) : (
                <span className="text-red-600">לא פעיל</span>
              )}
            </p>
          </div>
          <div>
            <h3 className="text-gray-600">נוצר בתאריך</h3>
            <p className="text-lg">{new Date(client.created_at).toLocaleDateString('he-IL')}</p>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <Link to="/clients" className="text-blue-600 hover:text-blue-800">
          &larr; חזרה לרשימת הלקוחות
        </Link>
      </div>
    </div>
  );
};

export default ClientDetail;
