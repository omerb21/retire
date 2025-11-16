/**
 * Custom hook for termination calculation logic
 */

import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../../../lib/api';
import { SimpleEmployer, TerminationDecision, GrantDetails } from '../types';
import { convertDDMMYYToISO } from '../../../utils/dateUtils';
import {
  calculateServiceYears,
  calculateMaxSpreadYears,
  calculateSeveranceAmount,
  calculateExemptAndTaxable
} from '../utils/calculations';

export const useTerminationCalculation = (
  employer: SimpleEmployer,
  terminationDecision: TerminationDecision,
  setTerminationDecision: React.Dispatch<React.SetStateAction<TerminationDecision>>,
  grantDetails: GrantDetails
) => {
  useEffect(() => {
    const calculateTermination = async () => {
      // Validate that date is complete (DD/MM/YYYY = 10 characters)
      if (!terminationDecision.termination_date || 
          terminationDecision.termination_date.length < 10 ||
          !employer.start_date || 
          !employer.last_salary) {
        return;
      }
      
      // Parse dates properly - handle both DD/MM/YYYY and ISO formats
      let startDateISO = employer.start_date;
      if (employer.start_date.includes('/')) {
        startDateISO = convertDDMMYYToISO(employer.start_date) || employer.start_date;
      }
      
      let endDateISO = terminationDecision.termination_date;
      if (terminationDecision.termination_date.includes('/')) {
        endDateISO = convertDDMMYYToISO(terminationDecision.termination_date) || terminationDecision.termination_date;
      }
      
      const startDate = new Date(startDateISO);
      const endDate = new Date(endDateISO);
      
      console.log('Date parsing debug:', {
        original_termination: terminationDecision.termination_date,
        endDateISO,
        endDate: endDate.toString(),
        terminationYear: endDate.getFullYear()
      });
      
      if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
        console.error('Invalid dates:', { startDate: startDateISO, endDate: endDateISO });
        return;
      }
      
      const serviceYears = calculateServiceYears(employer.start_date, terminationDecision.termination_date);
      const expectedGrant = employer.last_salary * serviceYears;
      
      // Calculate max spread years
      const maxSpreadYears = calculateMaxSpreadYears(serviceYears);
      
      // Calculate severance amount based on employer completion flag
      const severanceAmount = calculateSeveranceAmount(
        terminationDecision.use_employer_completion,
        expectedGrant,
        employer.severance_accrued
      );
      
      // Get severance cap for termination year from API
      const terminationYear = endDate.getFullYear();
      console.log('Fetching cap for year:', terminationYear);
      let monthlyCap = 13750; // Default for 2024-2025
      
      try {
        const response = await axios.get(`${API_BASE}/tax-data/severance-cap?year=${terminationYear}`);
        if (response.data && response.data.monthly_cap) {
          monthlyCap = response.data.monthly_cap;
        }
      } catch (err) {
        console.warn('Failed to fetch severance cap, using default:', err);
      }
      
      // Calculate exempt and taxable amounts
      const apiServiceYears = grantDetails.serviceYears || serviceYears;
      const { exemptAmount, taxableAmount } = calculateExemptAndTaxable(
        severanceAmount,
        monthlyCap,
        apiServiceYears
      );
      
      console.log('Exemption calculation:', {
        terminationYear,
        monthlyCap,
        serviceYears,
        exemptCap: monthlyCap * apiServiceYears,
        severanceAmount,
        exemptAmount,
        taxableAmount
      });
      
      setTerminationDecision(prev => ({
        ...prev,
        severance_amount: Math.round(severanceAmount),
        exempt_amount: exemptAmount,
        taxable_amount: taxableAmount,
        max_spread_years: maxSpreadYears,
        // Only initialize tax_spread_years if not already set
        tax_spread_years: prev.tax_spread_years || maxSpreadYears
      }));
    };
    
    // Add debouncing to avoid excessive API calls while user is typing
    const timeoutId = setTimeout(() => {
      calculateTermination();
    }, 500);
    
    return () => clearTimeout(timeoutId);
  }, [
    terminationDecision.termination_date,
    terminationDecision.use_employer_completion, 
    employer.start_date, 
    employer.last_salary, 
    employer.severance_accrued,
    grantDetails.serviceYears
  ]);
};
