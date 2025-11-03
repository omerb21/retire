/**
 * Custom Hook לניהול נתוני מעסיק נוכחי
 */

import { useState, useEffect } from 'react';
import axios from 'axios';
import { SimpleEmployer, TerminationDecision, GrantDetails } from '../types/employerTypes';
import { calculateGrantDetails } from '../calculations/grantCalculations';
import { 
  loadSeveranceFromPension, 
  isTerminationConfirmed,
  formatEmployerData 
} from '../utils/employerUtils';
import { convertDDMMYYToISO, convertISOToDDMMYY } from '../../../utils/dateUtils';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

export const useEmployerData = (clientId: string | undefined) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [employer, setEmployer] = useState<SimpleEmployer>({
    employer_name: '',
    start_date: '',
    last_salary: 0,
    severance_accrued: 0
  });
  const [terminationDecision, setTerminationDecision] = useState<TerminationDecision>({
    termination_date: '',
    use_employer_completion: false,
    severance_amount: 0,
    exempt_amount: 0,
    taxable_amount: 0,
    exempt_choice: 'redeem_with_exemption',
    taxable_choice: 'redeem_no_exemption',
    tax_spread_years: 0,
    max_spread_years: 0
  });
  const [grantDetails, setGrantDetails] = useState<GrantDetails>({
    serviceYears: 0,
    expectedGrant: 0,
    taxExemptAmount: 0,
    taxableAmount: 0,
    severanceCap: 0
  });
  const [originalSeveranceAmount, setOriginalSeveranceAmount] = useState<number>(0);

  /**
   * טעינת נתוני מעסיק מה-API
   */
  const fetchEmployer = async () => {
    if (!clientId) return;

    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get(`${API_BASE}/clients/${clientId}/current-employer`);
      
      // טיפול בתגובה - יכול להיות מערך או אובייקט
      let employerData = null;
      if (Array.isArray(response.data) && response.data.length > 0) {
        employerData = response.data[0];
      } else if (typeof response.data === 'object' && response.data.employer_name) {
        employerData = response.data;
      }
      
      // בדיקה אם העזיבה כבר אושרה
      const isConfirmed = isTerminationConfirmed(clientId);
      
      console.log('🔍 בדיקת מצב עזיבה:', {
        is_array: Array.isArray(response.data),
        end_date_value: employerData?.end_date,
        is_confirmed_in_storage: isConfirmed,
        client_id: clientId,
        full_response: response.data
      });
      
      if (isConfirmed) {
        console.log('✅ העזיבה אושרה בעבר - מסמן מצב מוקפא');
        setTerminationDecision(prev => ({ 
          ...prev, 
          confirmed: true,
          termination_date: employerData?.end_date || prev.termination_date
        }));
      } else {
        console.log('📝 העזיבה לא אושרה - מסך עזיבה פתוח לעריכה');
        setTerminationDecision(prev => ({ 
          ...prev, 
          confirmed: false,
          termination_date: employerData?.end_date || prev.termination_date
        }));
      }
      
      // טעינת יתרת פיצויים מתיק פנסיוני
      const severanceFromPension = loadSeveranceFromPension(clientId);
      
      if (employerData) {
        const formattedEmployer = formatEmployerData(employerData, severanceFromPension);
        setEmployer(formattedEmployer);
        
        console.log('📦 Loaded employer data:', {
          id: employerData.id,
          employer_name: employerData.employer_name,
          end_date: employerData.end_date,
          has_termination: !!employerData.end_date,
          severance_accrued: severanceFromPension
        });
      } else {
        // אם אין employerData, עדיין צריך לעדכן את severance_accrued
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

  /**
   * שמירת נתוני מעסיק
   */
  const saveEmployer = async (data: SimpleEmployer) => {
    if (!clientId) return;

    try {
      setLoading(true);
      setError(null);

      const response = await axios.post(`${API_BASE}/clients/${clientId}/current-employer`, {
        employer_name: data.employer_name,
        start_date: data.start_date,
        end_date: data.end_date,
        last_salary: data.last_salary,
        severance_accrued: data.severance_accrued
      });

      console.log('✅ Employer saved successfully:', response.data);
      setEmployer(data);
      setLoading(false);
      
      return response.data;
    } catch (err: any) {
      setError('שגיאה בשמירת נתוני מעסיק: ' + err.message);
      setLoading(false);
      throw err;
    }
  };

  /**
   * חישוב פרטי מענק כאשר נתוני המעסיק משתנים
   */
  useEffect(() => {
    const calculateGrant = async () => {
      if (employer.start_date && employer.last_salary > 0) {
        try {
          const details = await calculateGrantDetails(
            employer.start_date,
            employer.last_salary,
            employer.severance_accrued
          );
          
          setGrantDetails(details);
          
          // עדכון השלמת המעסיק
          const employerCompletion = Math.max(0, details.expectedGrant - employer.severance_accrued);
          setEmployer(prev => ({
            ...prev,
            employer_completion: employerCompletion
          }));
        } catch (error) {
          console.error('Error calculating grant details:', error);
        }
      }
    };

    // Add debouncing to prevent excessive calculations
    const timeoutId = setTimeout(() => {
      calculateGrant();
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [employer.start_date, employer.last_salary, employer.severance_accrued]);

  /**
   * סנכרון termination_date עם employer.end_date
   */
  useEffect(() => {
    if (employer.end_date && employer.end_date !== terminationDecision.termination_date) {
      setTerminationDecision(prev => ({ 
        ...prev, 
        termination_date: employer.end_date || '' 
      }));
    }
  }, [employer.end_date]);

  /**
   * טעינה ראשונית
   */
  useEffect(() => {
    if (clientId) {
      fetchEmployer();
    }
  }, [clientId]);

  return {
    loading,
    error,
    employer,
    setEmployer,
    terminationDecision,
    setTerminationDecision,
    grantDetails,
    setGrantDetails,
    originalSeveranceAmount,
    setOriginalSeveranceAmount,
    fetchEmployer,
    saveEmployer
  };
};
