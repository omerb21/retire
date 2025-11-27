import { useState, useEffect } from 'react';
import axios from 'axios';
import { ClientItem, API_BASE } from '../../../lib/api';

export const usePensionDate = (client: ClientItem | null, onUpdate: () => void) => {
  const [editMode, setEditMode] = useState(false);
  const [pensionStartDate, setPensionStartDate] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (client) {
      setPensionStartDate(client.pension_start_date || '');
    }
  }, [client]);

  const handleSavePensionDate = async () => {
    if (!client?.id) return;
    
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);
      const systemPassword = window.localStorage.getItem('systemAccessPassword');
      await axios.put(
        `${API_BASE}/clients/${client.id}`,
        {
          pension_start_date: pensionStartDate || null,
        },
        {
          headers: systemPassword
            ? { 'X-System-Password': systemPassword }
            : undefined,
        }
      );
      
      setSuccessMessage('תאריך קבלת קצבה עודכן בהצלחה');
      setEditMode(false);
      onUpdate();
      
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (e: any) {
      setError(`שגיאה בעדכון תאריך קצבה: ${e?.response?.data?.detail || e?.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setPensionStartDate(client?.pension_start_date || '');
    setEditMode(false);
    setError(null);
  };

  return {
    editMode,
    pensionStartDate,
    saving,
    error,
    successMessage,
    setEditMode,
    setPensionStartDate,
    handleSavePensionDate,
    handleCancelEdit,
  };
};
