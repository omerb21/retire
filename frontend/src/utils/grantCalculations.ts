/**
 * Grant Calculations Utilities
 * פונקציות עזר לחישובי מענקים
 */

import { Grant, GrantDetails } from '../types/grant.types';
import { GrantService } from '../services/grantService';

/**
 * Calculate service years between two dates
 */
export function calculateServiceYears(startDate: Date, endDate: Date): number {
  const milliseconds = endDate.getTime() - startDate.getTime();
  const years = milliseconds / (1000 * 60 * 60 * 24 * 365.25);
  return Math.round(years * 100) / 100;
}

/**
 * Calculate tax details for a grant
 */
export async function calculateGrantDetails(grant: Grant): Promise<GrantDetails | null> {
  if (!grant.work_start_date || !grant.work_end_date) {
    return null;
  }

  const startDate = new Date(grant.work_start_date);
  const endDate = new Date(grant.work_end_date);
  const serviceYears = calculateServiceYears(startDate, endDate);
  
  // וודא שיש ערך לסכום המענק
  const grantAmount = grant.grant_amount || grant.amount || 0;
  
  try {
    // Get official severance exemption from API
    const maxExemption = await GrantService.getSeveranceExemption(serviceYears);
    
    const exemptAmount = Math.min(grantAmount, maxExemption);
    const taxableAmount = Math.max(0, grantAmount - exemptAmount);
    
    // Tax calculation on taxable amount (10% rate for simplicity)
    const taxRate = 0.10;
    const taxOwed = taxableAmount * taxRate;
    
    return {
      serviceYears,
      taxExemptAmount: Math.round(exemptAmount),
      taxableAmount: Math.round(taxableAmount),
      taxDue: Math.round(taxOwed)
    };
  } catch (error) {
    console.error('Error calculating grant details:', error);
    return null;
  }
}

/**
 * Get grant amount (handles both amount and grant_amount fields)
 */
export function getGrantAmount(grant: Grant): number {
  return grant.grant_amount || grant.amount || 0;
}
