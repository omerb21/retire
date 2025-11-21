import React, { useState, useEffect } from 'react';
import { listClients, createClient, ClientItem, API_BASE } from '../../../lib/api';
import { convertDDMMYYToISO, convertISOToDDMMYY } from '../../../utils/dateUtils';
import { NewClientForm, EditClientForm } from '../types';

const initialNewClientForm: NewClientForm = {
  id_number: '',
  first_name: '',
  last_name: '',
  birth_date: '',
  gender: 'male',
  email: '',
  phone: '',
  address_street: '',
  address_city: '',
  address_postal_code: '',
  pension_start_date: '',
  tax_credit_points: 0,
  marital_status: ''
};

const initialEditClientForm: EditClientForm = {
  id_number: '',
  first_name: '',
  last_name: '',
  birth_date: '',
  gender: 'male',
  email: '',
  phone: '',
  address_street: '',
  address_city: '',
  address_postal_code: '',
  pension_start_date: '',
  tax_credit_points: 0,
  marital_status: ''
};

export function useClients() {
  const [items, setItems] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [form, setForm] = useState<NewClientForm>(initialNewClientForm);
  const [msg, setMsg] = useState<string>('');
  const [editingClient, setEditingClient] = useState<ClientItem | null>(null);
  const [editForm, setEditForm] = useState<EditClientForm>(initialEditClientForm);

  async function refresh() {
    setLoading(true);
    setMsg('');
    try {
      try {
        const data = await listClients();
        console.log('Clients loaded successfully:', data);

        // API now returns a paginated object: { items, total, page, page_size }
        const list = (data as any)?.items ?? data ?? [];
        setItems(list);
        setMsg(`✅ טעינה הצליחה! נמצאו ${Array.isArray(list) ? list.length : 0} לקוחות`);
      } catch (apiError: any) {
        console.error('Error with listClients API:', apiError);

        try {
          const testResponse = await fetch(`${API_BASE}/clients`);
          console.log('Direct fetch status:', testResponse.status);

          if (!testResponse.ok) {
            throw new Error(`שגיאת HTTP: ${testResponse.status} ${testResponse.statusText}`);
          }

          try {
            const testData = await testResponse.text();
            console.log('Raw response:', testData);

            if (testData) {
              try {
                const jsonData = JSON.parse(testData);
                console.log('Parsed JSON data:', jsonData);

                // Same paginated shape as the main API helper
                const list = (jsonData as any)?.items ?? jsonData ?? [];
                setItems(list);
                setMsg(`✅ טעינה הצליחה! נמצאו ${Array.isArray(list) ? list.length : 0} לקוחות`);
              } catch (jsonError) {
                console.error('JSON parsing error:', jsonError);
                setMsg('שגיאה בפענוח תגובת השרת: תגובה לא תקינה');
              }
            } else {
              setMsg('שגיאה: התקבלה תגובה ריקה מהשרת');
            }
          } catch (textError) {
            console.error('Error reading response text:', textError);
            setMsg('שגיאה בקריאת תגובת השרת');
          }
        } catch (fetchError: any) {
          console.error('Direct fetch error:', fetchError);
          setMsg('שגיאת חיבור לשרת: ' + (fetchError?.message || fetchError));
        }
      }
    } catch (e: any) {
      console.error('Unhandled error in refresh:', e);
      setMsg('שגיאה כללית בטעינת לקוחות: ' + (e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function deleteClient(clientId: number) {
    if (!confirm('האם אתה בטוח שברצונך למחוק לקוח זה?')) {
      return;
    }

    try {
      setMsg('');
      const response = await fetch(`${API_BASE}/clients/${clientId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setMsg('✅ לקוח נמחק בהצלחה');
      refresh();
    } catch (e: any) {
      console.error('Delete error:', e);
      setMsg(`❌ שגיאה במחיקת לקוח: ${e.message}`);
    }
  }

  function startEdit(client: ClientItem) {
    setEditingClient(client);
    setEditForm({
      id_number: client.id_number || '',
      first_name: client.first_name || '',
      last_name: client.last_name || '',
      birth_date: client.birth_date ? convertISOToDDMMYY(client.birth_date) : '',
      gender: client.gender || 'male',
      email: client.email || '',
      phone: client.phone || '',
      address_street: (client as any).address_street || '',
      address_city: (client as any).address_city || '',
      address_postal_code: (client as any).address_postal_code || '',
      pension_start_date: '',
      tax_credit_points: (client as any).tax_credit_points || 0,
      marital_status: (client as any).marital_status || ''
    });
  }

  function cancelEdit() {
    setEditingClient(null);
    setEditForm(initialEditClientForm);
  }

  async function saveEdit() {
    if (!editingClient) return;

    try {
      setMsg('');

      if (!editForm.id_number) throw new Error('חובה למלא ת"ז');
      if (!editForm.first_name) throw new Error('חובה למלא שם פרטי');
      if (!editForm.last_name) throw new Error('חובה למלא שם משפחה');
      if (!editForm.birth_date) throw new Error('חובה למלא תאריך לידה');

      const birthDateISO = convertDDMMYYToISO(editForm.birth_date);
      if (!birthDateISO) {
        throw new Error('תאריך לידה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }

      const response = await fetch(`${API_BASE}/clients/${editingClient.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          id_number: editForm.id_number.trim(),
          first_name: editForm.first_name.trim(),
          last_name: editForm.last_name.trim(),
          birth_date: birthDateISO,
          gender: editForm.gender,
          email: editForm.email || null,
          phone: editForm.phone || null,
          address_street: editForm.address_street || null,
          address_city: editForm.address_city || null,
          address_postal_code: editForm.address_postal_code || null,
          pension_start_date: null,
          tax_credit_points: editForm.tax_credit_points || 0,
          marital_status: editForm.marital_status || null
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setMsg('✅ פרטי לקוח עודכנו בהצלחה');
      cancelEdit();
      refresh();
    } catch (e: any) {
      console.error('Update error:', e);
      setMsg('❌ כשל בעדכון לקוח: ' + (e?.message || e));
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setMsg('');
    try {
      if (!form.id_number) throw new Error('חובה למלא ת"ז');
      if (!form.first_name) throw new Error('חובה למלא שם פרטי');
      if (!form.last_name) throw new Error('חובה למלא שם משפחה');
      if (!form.birth_date) throw new Error('חובה למלא תאריך לידה');

      const birthDateISO = convertDDMMYYToISO(form.birth_date);
      if (!birthDateISO) {
        throw new Error('תאריך לידה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }

      const birthDate = new Date(birthDateISO);
      const today = new Date();

      const minBirthDate = new Date();
      minBirthDate.setFullYear(today.getFullYear() - 120);

      const maxBirthDate = new Date();
      maxBirthDate.setFullYear(today.getFullYear() - 18);

      if (birthDate > maxBirthDate) {
        throw new Error('תאריך לידה לא הגיוני - גיל חייב להיות לפחות 18');
      }

      if (birthDate < minBirthDate) {
        throw new Error('תאריך לידה לא הגיוני - גיל מקסימלי הוא 120');
      }

      console.log('Sending client data:', form);

      await createClient({
        id_number: form.id_number.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        birth_date: birthDateISO,
        gender: form.gender,
        email: form.email || null,
        phone: form.phone || null,
        address_street: form.address_street || null,
        address_city: form.address_city || null,
        address_postal_code: form.address_postal_code || null,
        pension_start_date: null,
        tax_credit_points: form.tax_credit_points || 0,
        marital_status: form.marital_status || null
      });

      setForm(initialNewClientForm);

      setMsg('✅ לקוח נשמר');
      refresh();
    } catch (e: any) {
      setMsg('❌ כשל בשמירה: ' + (e?.message || e));
    }
  }

  return {
    items,
    loading,
    form,
    setForm,
    msg,
    editingClient,
    editForm,
    setEditForm,
    refresh,
    deleteClient,
    startEdit,
    cancelEdit,
    saveEdit,
    onCreate
  };
}
