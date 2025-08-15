import React, { useState, useEffect } from 'react';
import { clientApi, ClientResponse } from '../lib/api';
import { Link } from 'react-router-dom';

const Clients: React.FC = () => {
  const [clients, setClients] = useState<ClientResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      setLoading(true);
      const data = await clientApi.list();
      setClients(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'שגיאה בטעינת רשימת הלקוחות');
      console.error('Error fetching clients:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredClients = clients.filter(client => 
    client.full_name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    client.id_number.includes(searchTerm)
  );

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">ניהול לקוחות</h1>
        <Link 
          to="/clients/new" 
          className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
        >
          לקוח חדש +
        </Link>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="חיפוש לפי שם או מספר זהות..."
          className="w-full p-2 border rounded"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="text-center py-4">טוען נתונים...</div>
      ) : error ? (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border">
            <thead>
              <tr className="bg-gray-100">
                <th className="py-2 px-4 border">שם מלא</th>
                <th className="py-2 px-4 border">מספר זהות</th>
                <th className="py-2 px-4 border">תאריך לידה</th>
                <th className="py-2 px-4 border">אימייל</th>
                <th className="py-2 px-4 border">טלפון</th>
                <th className="py-2 px-4 border">פעולות</th>
              </tr>
            </thead>
            <tbody>
              {filteredClients.length > 0 ? (
                filteredClients.map((client) => (
                  <tr key={client.id} className="hover:bg-gray-50">
                    <td className="py-2 px-4 border">{client.full_name}</td>
                    <td className="py-2 px-4 border">{client.id_number}</td>
                    <td className="py-2 px-4 border">{client.birth_date}</td>
                    <td className="py-2 px-4 border">{client.email || '-'}</td>
                    <td className="py-2 px-4 border">{client.phone || '-'}</td>
                    <td className="py-2 px-4 border">
                      <Link 
                        to={`/clients/${client.id}`}
                        className="text-blue-600 hover:text-blue-800 mr-2"
                      >
                        צפייה
                      </Link>
                      <Link 
                        to={`/clients/${client.id}/edit`}
                        className="text-green-600 hover:text-green-800"
                      >
                        עריכה
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-4 text-center">
                    {searchTerm ? 'לא נמצאו לקוחות התואמים את החיפוש' : 'אין לקוחות במערכת'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Clients;
