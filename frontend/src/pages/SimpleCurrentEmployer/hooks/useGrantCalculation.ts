/**
 * Custom hook for grant calculation logic
 */

import { useState, useEffect } from 'react';
import { apiFetch } from '../../../lib/api';
import { SimpleEmployer, GrantDetails } from '../types';
import { convertDDMMYYToISO } from '../../../utils/dateUtils';
import { calculateServiceYears, calculateEmployerCompletion } from '../utils/calculations';

export const useGrantCalculation = (employer: SimpleEmployer) => {
  const [grantDetails, setGrantDetails] = useState<GrantDetails>({
    serviceYears: 0,
    expectedGrant: 0,
    taxExemptAmount: 0,
    taxableAmount: 0,
    severanceCap: 0
  });

  useEffect(() => {
    const calculateGrantDetails = async () => {
      if (!employer.start_date || employer.last_salary <= 0) return;
      
      // Convert date from DD/MM/YYYY to ISO if needed
      let startISO = employer.start_date.includes('/') 
        ? convertDDMMYYToISO(employer.start_date) 
        : employer.start_date;
      
      if (!startISO) return;
      
      const startDate = new Date(startISO);
      const referenceDate = new Date();
      
      // Calculate service years
      const serviceYears = calculateServiceYears(employer.start_date, referenceDate.toISOString().split('T')[0]);
      
      console.log('🔍 Grant calculation input:', {
        start_date: employer.start_date,
        startISO,
        last_salary: employer.last_salary,
        serviceYears: serviceYears.toFixed(2)
      });
      
      // Basic severance calculation (1 month salary per year)
      const expectedGrant = employer.last_salary * serviceYears;
      
      try {
        // Call the severance calculation API
        const calculation = await apiFetch<any>(`/current-employer/calculate-severance`, {
          method: 'POST',
          body: JSON.stringify({
            start_date: employer.start_date,
            last_salary: employer.last_salary
          })
        });
        
        // If severance accrued is higher than expected grant, use accrued amount
        const actualExpectedGrant = Math.max(calculation.severance_amount, employer.severance_accrued);
        
        // Calculate employer completion
        const employerCompletion = calculateEmployerCompletion(actualExpectedGrant, employer.severance_accrued);
        
        console.log('💰 Grant calculation (API):', {
          calculated_grant: calculation.severance_amount,
          severance_accrued: employer.severance_accrued,
          actual_expected_grant: actualExpectedGrant,
          employer_completion: employerCompletion
        });
        
        setGrantDetails({
          serviceYears: calculation.service_years || 0,
          expectedGrant: actualExpectedGrant || 0,
          taxExemptAmount: calculation.exempt_amount || 0,
          taxableAmount: calculation.taxable_amount || 0,
          severanceCap: calculation.annual_exemption_cap || 165240
        });
      } catch (error) {
        console.error('Error calculating severance:', error);
        
        // Fallback calculation
        const currentYearCap = 13750; // 2025 cap
        const severanceExemption = currentYearCap * serviceYears;
        
        const actualExpectedGrant = Math.max(Math.round(expectedGrant), employer.severance_accrued);
        const taxExemptAmount = Math.min(actualExpectedGrant, severanceExemption);
        const taxableAmount = Math.max(0, actualExpectedGrant - taxExemptAmount);
        
        const employerCompletion = calculateEmployerCompletion(actualExpectedGrant, employer.severance_accrued);
        
        console.log('💰 Grant calculation (Fallback):', {
          calculated_grant: Math.round(expectedGrant),
          severance_accrued: employer.severance_accrued,
          actual_expected_grant: actualExpectedGrant,
          employer_completion: employerCompletion
        });
        
        setGrantDetails({
          serviceYears: Math.round(serviceYears * 100) / 100,
          expectedGrant: actualExpectedGrant,
          taxExemptAmount: Math.round(taxExemptAmount),
          taxableAmount: Math.round(taxableAmount),
          severanceCap: currentYearCap
        });
      }
    };
    
    // Debounce to prevent excessive API calls
    const timeoutId = setTimeout(() => {
      calculateGrantDetails();
    }, 500);
    
    return () => clearTimeout(timeoutId);
  }, [employer.start_date, employer.last_salary, employer.severance_accrued]);

  return { grantDetails };
};
