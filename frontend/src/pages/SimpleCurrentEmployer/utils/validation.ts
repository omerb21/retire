/**
 * Validation utilities for SimpleCurrentEmployer
 */

/**
 * Validate date format (DD/MM/YYYY)
 */
export const isValidDateFormat = (date: string): boolean => {
  if (!date || date.length !== 10) return false;
  
  const regex = /^\d{2}\/\d{2}\/\d{4}$/;
  return regex.test(date);
};

/**
 * Validate that termination date is after start date
 */
export const isTerminationDateValid = (startDate: string, terminationDate: string): boolean => {
  if (!startDate || !terminationDate) return false;
  
  const start = new Date(startDate);
  const end = new Date(terminationDate);
  
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return false;
  
  return end >= start;
};

/**
 * Validate employer form data
 */
export const validateEmployerData = (
  employerName: string,
  startDate: string,
  lastSalary: number
): { isValid: boolean; error?: string } => {
  if (!employerName || employerName.trim() === '') {
    return { isValid: false, error: 'שם מעסיק הוא שדה חובה' };
  }
  
  if (!startDate || !isValidDateFormat(startDate)) {
    return { isValid: false, error: 'תאריך התחלת עבודה לא תקין - יש להזין בפורמט DD/MM/YYYY' };
  }
  
  if (!lastSalary || lastSalary <= 0) {
    return { isValid: false, error: 'שכר חודשי חייב להיות גדול מ-0' };
  }
  
  return { isValid: true };
};

/**
 * Validate termination data
 */
export const validateTerminationData = (
  terminationDate: string,
  startDate: string
): { isValid: boolean; error?: string } => {
  if (!terminationDate || !isValidDateFormat(terminationDate)) {
    return { isValid: false, error: 'תאריך סיום עבודה לא תקין - יש להזין בפורמט DD/MM/YYYY' };
  }
  
  if (!isTerminationDateValid(startDate, terminationDate)) {
    return { isValid: false, error: 'תאריך סיום עבודה חייב להיות אחרי תאריך התחלת עבודה' };
  }
  
  return { isValid: true };
};
