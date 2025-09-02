import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createClient, ClientItem } from '../../lib/api';

interface ClientFormProps {
  onSuccess?: (clientId: number) => void;
}

interface ClientFormData {
  id_number: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  email?: string | null;
  phone?: string | null;
  retirement_date?: string | null;
}

const ClientForm: React.FC<ClientFormProps> = ({ onSuccess }) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<ClientFormData>({
    first_name: '',
    last_name: '',
    id_number: '',
    birth_date: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Use the createClient function from our updated API utilities
      const newClient = await createClient({
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        id_number: formData.id_number.trim(),
        birth_date: formData.birth_date,
        email: formData.email || null,
        phone: formData.phone || null
      });
      
      if (onSuccess && newClient.id) {
        onSuccess(newClient.id);
      } else if (newClient.id) {
        navigate(`/clients/${newClient.id}`);
      }
    } catch (err: any) {
      // Error message is now correctly formatted by our API utility
      setError(`כשל בשמירה: ${err.message || "שגיאה לא מוכרת"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">
          שם פרטי *
          <input
            type="text"
            name="first_name"
            value={formData.first_name || ''}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          שם משפחה *
          <input
            type="text"
            name="last_name"
            value={formData.last_name || ''}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          מספר זהות *
          <input
            type="text"
            name="id_number"
            value={formData.id_number}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          תאריך לידה *
          <input
            type="date"
            name="birth_date"
            value={formData.birth_date}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          אימייל
          <input
            type="email"
            name="email"
            value={formData.email || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          טלפון
          <input
            type="tel"
            name="phone"
            value={formData.phone || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          תאריך פרישה צפוי
          <input
            type="date"
            name="retirement_date"
            value={formData.retirement_date || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div className="flex justify-end space-x-2">
        <button
          type="button"
          onClick={() => navigate('/clients')}
          className="px-4 py-2 border rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          ביטול
        </button>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          {loading ? 'שומר...' : 'שמירה'}
        </button>
      </div>
    </form>
  );
};

export default ClientForm;
