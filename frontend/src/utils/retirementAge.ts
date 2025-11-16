/**
 * Utility functions for retirement age calculations
 */

import { API_BASE } from '../lib/api';

interface RetirementAgeResult {
  age_years: number;
  age_months: number;
  retirement_date: string;
  source: string;
}

interface RetirementAgeSimpleResult {
  retirement_age: number;
  retirement_date: string;
}

/**
 * Calculate retirement age for a client based on birth date and gender
 */
export async function calculateRetirementAge(
  birthDate: string,
  gender: string
): Promise<RetirementAgeResult> {
  const response = await fetch(`${API_BASE}/retirement-age/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      birth_date: birthDate,
      gender: gender
    })
  });

  if (!response.ok) {
    throw new Error('Failed to calculate retirement age');
  }

  return await response.json();
}

/**
 * Calculate simple retirement age (whole years only)
 */
export async function calculateRetirementAgeSimple(
  birthDate: string,
  gender: string
): Promise<number> {
  const response = await fetch(`${API_BASE}/retirement-age/calculate-simple`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      birth_date: birthDate,
      gender: gender
    })
  });

  if (!response.ok) {
    throw new Error('Failed to calculate retirement age');
  }

  const result: RetirementAgeSimpleResult = await response.json();
  return result.retirement_age;
}

/**
 * Get retirement age settings from the system
 */
export async function getRetirementAgeSettings(): Promise<{
  male_retirement_age: number;
  use_legal_table_for_women: boolean;
  female_retirement_age?: number;
}> {
  const response = await fetch(`${API_BASE}/retirement-age/settings`);

  if (!response.ok) {
    // Return defaults if settings not available
    return {
      male_retirement_age: 67,
      use_legal_table_for_women: true,
      female_retirement_age: 65
    };
  }

  return await response.json();
}

/**
 * Get default retirement age based on gender (for backward compatibility)
 * This uses the system settings
 */
export async function getDefaultRetirementAge(gender?: string): Promise<number> {
  const settings = await getRetirementAgeSettings();
  
  const normalizedGender = (gender || '').toLowerCase();
  if (normalizedGender === 'male' || normalizedGender === 'm' || normalizedGender === 'זכר') {
    return settings.male_retirement_age;
  } else {
    // For females, if using legal table, return 65 as a reasonable default
    // The actual age will be calculated based on birth date
    return settings.use_legal_table_for_women ? 65 : (settings.female_retirement_age || 65);
  }
}
