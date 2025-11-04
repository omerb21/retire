/**
 * Custom hook for managing employer data
 */

import { useState, useEffect } from 'react';
import axios from 'axios';
import { SimpleEmployer } from '../types';
import { getSeveranceFromPension, isTerminationConfirmed } from '../utils/storageHelpers';
import { convertISOToDDMMYY, convertDDMMYYToISO } from '../../../utils/dateUtils';

export const useEmployerData = (clientId: string | undefined) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
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
        const response = await axios.get(`/api/v1/clients/${clientId}/current-employer`);
        
        // Handle response - can be array or object
        let employerData = null;
        if (Array.isArray(response.data) && response.data.length > 0) {
          employerData = response.data[0];
        } else if (typeof response.data === 'object' && response.data.employer_name) {
          employerData = response.data;
        }
        
        // Check if termination is confirmed
        const isConfirmed = isTerminationConfirmed(clientId);
        
        console.log('🔍 בדיקת מצב עזיבה:', {
          is_array: Array.isArray(response.data),
          end_date_value: employerData?.end_date,
          is_confirmed_in_storage: isConfirmed,
          client_id: clientId,
          full_response: response.data
        });
        
        // Load severance balance from pension portfolio
        const severanceFromPension = getSeveranceFromPension(clientId);
        
        if (employerData) {
          setEmployer({
            id: employerData.id,
            employer_name: employerData.employer_name || '',
            start_date: employerData.start_date || '',
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
        if (err.response?.status !== 404) {
          setError('שגיאה בטעינת נתוני מעסיק: ' + err.message);
        }
        setLoading(false);
      }
    };

    fetchEmployer();
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
        const response = await axios.put(`/api/v1/clients/${clientId}/current-employer/${employer.id}`, employerData);
        
        const newEmployerData = { 
          id: response.data.id,
          employer_name: response.data.employer_name,
          start_date: convertISOToDDMMYY(response.data.start_date),
          end_date: response.data.end_date ? convertISOToDDMMYY(response.data.end_date) : undefined,
          last_salary: Number(response.data.monthly_salary || response.data.last_salary || 0),
          severance_accrued: employer.severance_accrued
        };
        setEmployer(newEmployerData);
      } else {
        console.log('🔍 Sending POST request with data:', employerData);
        const response = await axios.post(`/api/v1/clients/${clientId}/current-employer`, employerData);
        
        const newEmployerData = { 
          id: response.data.id,
          employer_name: response.data.employer_name,
          start_date: convertISOToDDMMYY(response.data.start_date),
          end_date: response.data.end_date ? convertISOToDDMMYY(response.data.end_date) : undefined,
          last_salary: Number(response.data.monthly_salary || response.data.last_salary || 0),
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
    saveEmployer
  };
};
