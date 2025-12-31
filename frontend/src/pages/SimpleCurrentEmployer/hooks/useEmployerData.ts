/**
 * Custom hook for managing employer data
 */

import { useState, useEffect } from 'react';
import { apiFetch } from '../../../lib/api';
import { SimpleEmployer } from '../types';
import { getSeveranceFromPension, isTerminationConfirmed, setTerminationConfirmed } from '../utils/storageHelpers';
import { convertISOToDDMMYY, convertDDMMYYToISO } from '../../../utils/dateUtils';

const isNotFoundError = (message: string): boolean => {
  const msg = (message || '').toString();
  if (!msg) return false;
  if (msg.includes('404') || msg.includes('Not Found')) return true;
  if (msg.includes('אין מעסיק נוכחי') || msg.includes('Current employer not found')) return true;
  return false;
};

export const useEmployerData = (clientId: string | undefined) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [terminationConfirmed, setTerminationConfirmedState] = useState<boolean>(false);
  const [employer, setEmployer] = useState<SimpleEmployer>({
    employer_name: '',
    start_date: '',
    last_salary: 0,
    severance_accrued: 0
  });

  // Load existing employer data
  useEffect(() => {
    const fetchEmployer = async () => {
      if (!clientId) return;
      
      try {
        setLoading(true);
        const data = await apiFetch<any>(`/clients/${clientId}/current-employer`);
        
        // Handle response - can be array or object
        let employerData = null;
        if (Array.isArray(data) && data.length > 0) {
          employerData = data[0];
        } else if (typeof data === 'object' && (data as any)?.employer_name) {
          employerData = data;
        }
        
        // Reconcile termination confirmed state (server is authoritative)
        const localConfirmed = isTerminationConfirmed(clientId);
        const serverConfirmed = !!(employerData?.other_grants as any)?.termination_confirmed;
        if (serverConfirmed !== localConfirmed) {
          setTerminationConfirmed(clientId, serverConfirmed);
        }
        setTerminationConfirmedState(serverConfirmed);
        
        console.log('🔍 בדיקת מצב עזיבה:', {
          is_array: Array.isArray(data),
          end_date_value: employerData?.end_date,
          is_confirmed_in_storage: localConfirmed,
          is_confirmed_in_server: serverConfirmed,
          client_id: clientId,
          full_response: data
        });
        
        // Load severance balance from pension portfolio
        const severanceFromPension = getSeveranceFromPension(clientId);
        
        if (employerData) {
          setEmployer({
            id: employerData.id,
            employer_name: employerData.employer_name || '',
            start_date: employerData.start_date ? convertISOToDDMMYY(employerData.start_date) : '',
            end_date: employerData.end_date ? convertISOToDDMMYY(employerData.end_date) : undefined,
            last_salary: Number(employerData.monthly_salary || employerData.last_salary || employerData.average_salary || 0),
            severance_accrued: severanceFromPension
          });
          
          console.log('📦 Loaded employer data:', {
            id: employerData.id,
            employer_name: employerData.employer_name,
            end_date: employerData.end_date,
            has_termination: !!employerData.end_date,
            severance_accrued: severanceFromPension
          });
        } else {
          console.log('⚠️ אין employerData, מעדכן רק severance_accrued:', severanceFromPension);
          setEmployer(prev => ({
            ...prev,
            severance_accrued: severanceFromPension
          }));
        }
        setLoading(false);
      } catch (err: any) {
        const message = err?.message || '';
        // 404 "אין מעסיק נוכחי" אינו נחשב כשגיאה לוגית במסך זה
        const isClientMissing = message.includes('לקוח לא נמצא');
        if (!isClientMissing && isNotFoundError(message)) {
          setTerminationConfirmed(clientId, false);
          setTerminationConfirmedState(false);
        } else {
          setError('שגיאה בטעינת נתוני מעסיק: ' + message);
        }
        setLoading(false);
      }
    };

    fetchEmployer();
  }, [clientId]);

  // Sync severance balance with pension portfolio when returning to the page
  useEffect(() => {
    if (!clientId) return;

    const refreshSeveranceFromPension = () => {
      const severanceFromPension = getSeveranceFromPension(clientId);
      setEmployer((prev) => {
        if (prev.severance_accrued === severanceFromPension) {
          return prev;
        }
        return {
          ...prev,
          severance_accrued: severanceFromPension
        };
      });
    };

    const handleFocus = () => {
      refreshSeveranceFromPension();
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        refreshSeveranceFromPension();
      }
    };

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [clientId]);

  // Save employer data
  const saveEmployer = async (): Promise<boolean> => {
    if (!clientId) return false;
    
    try {
      setLoading(true);
      setError(null);

      // Convert start_date to ISO format
      const startDateISO = convertDDMMYYToISO(employer.start_date);
      if (!startDateISO) {
        throw new Error('תאריך התחלת עבודה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }

      // Convert end_date to ISO format if exists
      let endDateISO = undefined;
      if (employer.end_date) {
        endDateISO = convertDDMMYYToISO(employer.end_date);
        if (!endDateISO) {
          throw new Error('תאריך סיום עבודה לא תקין - יש להזין בפורמט DD/MM/YYYY');
        }
      }

      const employerData = {
        ...employer,
        start_date: startDateISO,
        end_date: endDateISO
      };

      if (employer.id) {
        console.log('🔍 Sending PUT request with data:', {
          employer_name: employerData.employer_name,
          start_date: employerData.start_date,
          end_date: employerData.end_date,
          last_salary: employerData.last_salary
        });
        const updatedEmployer = await apiFetch<any>(`/clients/${clientId}/current-employer/${employer.id}`, {
          method: 'PUT',
          body: JSON.stringify(employerData)
        });

        const newEmployerData = { 
          id: updatedEmployer.id,
          employer_name: updatedEmployer.employer_name,
          start_date: convertISOToDDMMYY(updatedEmployer.start_date),
          end_date: updatedEmployer.end_date ? convertISOToDDMMYY(updatedEmployer.end_date) : undefined,
          last_salary: Number(updatedEmployer.monthly_salary || updatedEmployer.last_salary || 0),
          severance_accrued: employer.severance_accrued
        };
        setEmployer(newEmployerData);
      } else {
        console.log('🔍 Sending POST request with data:', employerData);
        const createdEmployer = await apiFetch<any>(`/clients/${clientId}/current-employer`, {
          method: 'POST',
          body: JSON.stringify(employerData)
        });

        const newEmployerData = { 
          id: createdEmployer.id,
          employer_name: createdEmployer.employer_name,
          start_date: convertISOToDDMMYY(createdEmployer.start_date),
          end_date: createdEmployer.end_date ? convertISOToDDMMYY(createdEmployer.end_date) : undefined,
          last_salary: Number(createdEmployer.monthly_salary || createdEmployer.last_salary || 0),
          severance_accrued: employer.severance_accrued
        };
        setEmployer(newEmployerData);
      }

      setLoading(false);
      return true;
    } catch (err: any) {
      setError('שגיאה בשמירת נתוני מעסיק: ' + err.message);
      setLoading(false);
      return false;
    }
  };

  return {
    employer,
    setEmployer,
    loading,
    setLoading,
    error,
    setError,
    terminationConfirmed,
    saveEmployer
  };
};
