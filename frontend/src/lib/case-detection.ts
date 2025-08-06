import { useState, useEffect } from 'react';

// Types for case detection
export interface ClientData {
  id?: number;
  full_name?: string;
  id_number?: string;
  birth_date?: string;
  retirement_date?: string;
  is_active?: boolean;
}

export interface EmploymentData {
  id?: number;
  client_id?: number;
  is_current?: boolean;
  start_date?: string;
  end_date?: string;
  planned_termination_date?: string;
  actual_termination_date?: string;
}

export interface TerminationEventData {
  id?: number;
  employment_id?: number;
  planned_termination_date?: string;
  actual_termination_date?: string;
  reason?: string;
}

/**
 * Determines the case (1-5) based on client and employment data
 * According to the specification:
 * Case 1: No current employer
 * Case 2: Has current employer - already left
 * Case 3: Has current employer - will leave in future
 * Case 4: Has current employer - termination date unknown
 * Case 5: Regular employee with planned departure
 */
export function detectCase(
  clientData: ClientData | null,
  employmentData: EmploymentData | null,
  terminationData: TerminationEventData | null
): number {
  // Default to Case 1 if no data
  if (!clientData) {
    return 1;
  }

  // Case 1: No current employer
  if (!employmentData || !employmentData.is_current) {
    return 1;
  }

  // Has current employer - check termination status
  if (employmentData.is_current) {
    // Case 2: Already left (has actual termination date)
    if (employmentData.actual_termination_date || terminationData?.actual_termination_date) {
      return 2;
    }

    // Case 3: Will leave in future (has planned termination date in future)
    if (employmentData.planned_termination_date || terminationData?.planned_termination_date) {
      const plannedDate = new Date(
        employmentData.planned_termination_date || terminationData?.planned_termination_date || ''
      );
      const today = new Date();
      
      if (plannedDate > today) {
        return 3;
      }
    }

    // Case 4: Termination date unknown (current employer but no termination planning)
    if (!employmentData.planned_termination_date && !terminationData?.planned_termination_date) {
      return 4;
    }

    // Case 5: Regular employee with planned departure (default for current employment with planning)
    return 5;
  }

  // Fallback to Case 1
  return 1;
}

/**
 * Hook for case detection with state management
 */
export function useCaseDetection() {
  const [currentCase, setCurrentCase] = useState<number>(1);
  const [clientData, setClientData] = useState<ClientData | null>(null);
  const [employmentData, setEmploymentData] = useState<EmploymentData | null>(null);
  const [terminationData, setTerminationEventData] = useState<TerminationEventData | null>(null);
  const [isDevMode, setIsDevMode] = useState<boolean>(false);

  // Check for dev mode from environment or localStorage
  useEffect(() => {
    const devMode = process.env.NODE_ENV === 'development' || 
                   localStorage.getItem('devMode') === 'true';
    setIsDevMode(devMode);
  }, []);

  // Recalculate case when data changes
  useEffect(() => {
    const newCase = detectCase(clientData, employmentData, terminationData);
    setCurrentCase(newCase);
  }, [clientData, employmentData, terminationData]);

  const updateClientData = (data: ClientData | null) => {
    setClientData(data);
  };

  const updateEmploymentData = (data: EmploymentData | null) => {
    setEmploymentData(data);
  };

  const updateTerminationData = (data: TerminationEventData | null) => {
    setTerminationEventData(data);
  };

  return {
    currentCase,
    clientData,
    employmentData,
    terminationData,
    isDevMode,
    updateClientData,
    updateEmploymentData,
    updateTerminationData,
  };
}

/**
 * Validates if required data is present for proceeding to next step
 */
export function validateStepData(step: string, data: any): { isValid: boolean; missingFields: string[] } {
  const missingFields: string[] = [];

  switch (step) {
    case 'client':
      if (!data?.full_name) missingFields.push('שם מלא');
      if (!data?.id_number) missingFields.push('מספר זהות');
      if (!data?.birth_date) missingFields.push('תאריך לידה');
      break;

    case 'currentEmployer':
      if (!data?.employer_name) missingFields.push('שם מעסיק');
      if (!data?.start_date) missingFields.push('תאריך התחלה');
      if (!data?.monthly_salary_nominal) missingFields.push('שכר חודשי');
      break;

    case 'pastEmployers':
      // Past employers are optional, but if provided should be valid
      break;

    case 'pensions':
      // Pension data validation if provided
      break;

    default:
      break;
  }

  return {
    isValid: missingFields.length === 0,
    missingFields,
  };
}

/**
 * Get visible steps for current case
 */
export function getVisibleSteps(caseNumber: number): string[] {
  const allSteps = ['client', 'currentEmployer', 'pastEmployers', 'pensions', 'incomeAssets', 'taxAdmin', 'scenarios', 'results'];
  
  switch (caseNumber) {
    case 1:
    case 2:
    case 3:
    case 4:
      // Skip current employer for these cases
      return allSteps.filter(step => step !== 'currentEmployer');
    
    case 5:
      // Show all steps including current employer
      return allSteps;
    
    default:
      return allSteps.filter(step => step !== 'currentEmployer');
  }
}
