/**
 * Calculation utilities for SimpleCurrentEmployer
 */

import { convertDDMMYYToISO } from '../../../utils/dateUtils';

/**
 * Calculate service years between two dates
 */
export const calculateServiceYears = (startDate: string, endDate: string): number => {
  let startISO = startDate.includes('/') ? convertDDMMYYToISO(startDate) : startDate;
  let endISO = endDate.includes('/') ? convertDDMMYYToISO(endDate) : endDate;
  
  if (!startISO || !endISO) return 0;
  
  const start = new Date(startISO);
  const end = new Date(endISO);
  
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return 0;
  
  const years = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
  return Math.max(0, years);
};

/**
 * Calculate expected severance grant
 */
export const calculateExpectedGrant = (
  lastSalary: number,
  serviceYears: number
): number => {
  return Math.round(lastSalary * serviceYears);
};

/**
 * Calculate employer completion amount
 */
export const calculateEmployerCompletion = (
  expectedGrant: number,
  severanceAccrued: number
): number => {
  return Math.max(0, expectedGrant - severanceAccrued);
};

/**
 * Calculate maximum spread years based on service years
 * Rules:
 * - Up to 2 years: 0 spread years
 * - 2+ years: 1 spread year
 * - 6+ years: 2 spread years
 * - 10+ years: 3 spread years
 * - 14+ years: 4 spread years
 * - 18+ years: 5 spread years
 * - 22+ years: 6 spread years (maximum)
 */
export const calculateMaxSpreadYears = (serviceYears: number): number => {
  if (serviceYears >= 22) return 6;
  if (serviceYears >= 18) return 5;
  if (serviceYears >= 14) return 4;
  if (serviceYears >= 10) return 3;
  if (serviceYears >= 6) return 2;
  if (serviceYears >= 2) return 1;
  return 0;
};

/**
 * Calculate severance amount based on employer completion flag
 */
export const calculateSeveranceAmount = (
  useEmployerCompletion: boolean,
  expectedGrant: number,
  severanceAccrued: number
): number => {
  if (useEmployerCompletion) {
    return Math.max(expectedGrant, severanceAccrued);
  }
  return severanceAccrued;
};

/**
 * Calculate exempt and taxable amounts
 */
export const calculateExemptAndTaxable = (
  severanceAmount: number,
  monthlyCap: number,
  serviceYears: number
): { exemptAmount: number; taxableAmount: number } => {
  const exemptCap = monthlyCap * serviceYears;
  const exemptAmount = Math.min(severanceAmount, exemptCap);
  const taxableAmount = Math.max(0, severanceAmount - exemptAmount);
  
  return {
    exemptAmount: Math.round(exemptAmount),
    taxableAmount: Math.round(taxableAmount)
  };
};
