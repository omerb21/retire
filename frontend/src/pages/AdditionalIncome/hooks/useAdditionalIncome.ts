import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../../lib/api';
import { formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY } from '../../../utils/dateUtils';

export type AdditionalIncome = {
  id?: number;
  source_type: string;
  description?: string;
  amount: number;
  frequency: 'monthly' | 'annually';
  start_date: string;
  end_date?: string;
  indexation_method: 'none' | 'fixed' | 'cpi';
  fixed_rate?: number;
  tax_treatment: 'exempt' | 'taxable' | 'fixed_rate';
  tax_rate?: number;
  computed_monthly_amount?: number;
};

const initialForm: Partial<AdditionalIncome> = {
  source_type: 'rental',
  description: '',
  amount: 0,
  frequency: 'monthly',
  start_date: '',
  indexation_method: 'none',
  tax_treatment: 'taxable',
  fixed_rate: 0,
  tax_rate: 0,
};

export function useAdditionalIncome(clientId?: string) {
  const [incomes, setIncomes] = useState<AdditionalIncome[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [editingIncomeId, setEditingIncomeId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<AdditionalIncome>>(initialForm);

  async function loadIncomes() {
    if (!clientId) return;

    setLoading(true);
    setError('');

    try {
      const data = await apiFetch<AdditionalIncome[]>(`/clients/${clientId}/additional-incomes/`);
      setIncomes(data || []);
    } catch (e: any) {
      setError(`שגיאה בטעינת הכנסות נוספות: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadIncomes();
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError('');

    try {
      if (!form.source_type) {
        throw new Error('חובה לבחור סוג הכנסה');
      }
      if (!form.amount || form.amount <= 0) {
        throw new Error('חובה למלא סכום חיובי');
      }
      if (!form.start_date) {
        throw new Error('חובה למלא תאריך התחלה');
      }

      if (form.indexation_method === 'fixed' && (!form.fixed_rate || form.fixed_rate < 0)) {
        throw new Error('חובה למלא שיעור הצמדה קבוע');
      }

      if (form.tax_treatment === 'fixed_rate' && (!form.tax_rate || form.tax_rate < 0 || form.tax_rate > 100)) {
        throw new Error('חובה למלא שיעור מס בין 0-100');
      }

      const startDateISO = convertDDMMYYToISO(form.start_date);
      if (!startDateISO) {
        throw new Error('תאריך התחלה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }

      const endDateISO = form.end_date ? convertDDMMYYToISO(form.end_date) : null;

      const payload = {
        ...form,
        amount: Number(form.amount),
        fixed_rate: form.fixed_rate !== undefined ? Number(form.fixed_rate) : undefined,
        tax_rate: form.tax_rate !== undefined ? Number(form.tax_rate) : undefined,
        start_date: startDateISO,
        end_date: endDateISO,
      };

      if (editingIncomeId) {
        await apiFetch(`/clients/${clientId}/additional-incomes/${editingIncomeId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch(`/clients/${clientId}/additional-incomes/`, {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      }

      setForm(initialForm);
      setEditingIncomeId(null);
      await loadIncomes();
    } catch (e: any) {
      setError(`שגיאה ביצירת הכנסה נוספת: ${e?.message || e}`);
    }
  }

  async function handleDeleteAll() {
    if (!clientId) return;

    if (incomes.length === 0) {
      alert('אין הכנסות נוספות למחיקה');
      return;
    }

    if (!confirm(`האם אתה בטוח שברצונך למחוק את כל ${incomes.length} ההכנסות הנוספות? פעולה זו בלתי הפיכה!`)) {
      return;
    }

    try {
      setError('');

      for (const income of incomes) {
        if (income.id) {
          await apiFetch(`/clients/${clientId}/additional-incomes/${income.id}`, {
            method: 'DELETE',
          });
        }
      }

      await loadIncomes();
      alert(`נמחקו ${incomes.length} הכנסות נוספות בהצלחה`);
    } catch (e: any) {
      setError(`שגיאה במחיקת הכנסות נוספות: ${e?.message || e}`);
    }
  }

  async function handleDelete(incomeId: number) {
    if (!clientId) return;

    if (!confirm('האם אתה בטוח שברצונך למחוק את ההכנסה הנוספת?')) {
      return;
    }

    try {
      await apiFetch(`/clients/${clientId}/additional-incomes/${incomeId}`, {
        method: 'DELETE',
      });

      await loadIncomes();
    } catch (e: any) {
      setError(`שגיאה במחיקת הכנסה נוספת: ${e?.message || e}`);
    }
  }

  function handleEdit(income: AdditionalIncome) {
    setEditingIncomeId(income.id || null);

    setForm({
      source_type: income.source_type,
      description: income.description || '',
      amount: income.amount || 0,
      frequency: income.frequency,
      start_date: income.start_date ? formatDateInput(convertISOToDDMMYY(income.start_date)) : '',
      end_date: income.end_date ? formatDateInput(convertISOToDDMMYY(income.end_date)) : '',
      indexation_method: income.indexation_method,
      tax_treatment: income.tax_treatment,
      fixed_rate: income.fixed_rate || 0,
      tax_rate: income.tax_rate || 0,
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return {
    incomes,
    loading,
    error,
    form,
    setForm,
    editingIncomeId,
    setEditingIncomeId,
    handleSubmit,
    handleDeleteAll,
    handleDelete,
    handleEdit,
  };
}
