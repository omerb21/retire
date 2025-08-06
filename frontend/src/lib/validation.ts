// Validation utilities with Hebrew error messages

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

export interface FieldValidationResult {
  isValid: boolean;
  error?: string;
}

// Israeli ID number validation with checksum
export function validateIsraeliId(idNumber: string): FieldValidationResult {
  if (!idNumber) {
    return { isValid: false, error: 'מספר זהות הוא שדה חובה' };
  }

  // Remove non-digits and pad with zeros
  const cleanId = idNumber.replace(/\D/g, '').padStart(9, '0');
  
  if (cleanId.length !== 9) {
    return { isValid: false, error: 'מספר זהות חייב להכיל 9 ספרות' };
  }

  // Validate checksum
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    let digit = parseInt(cleanId[i]);
    if (i % 2 === 1) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    sum += digit;
  }

  if (sum % 10 !== 0) {
    return { isValid: false, error: 'מספר זהות לא תקין' };
  }

  return { isValid: true };
}

// Email validation
export function validateEmail(email: string): FieldValidationResult {
  if (!email) {
    return { isValid: true }; // Email is optional
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return { isValid: false, error: 'כתובת דוא"ל לא תקינה' };
  }

  return { isValid: true };
}

// Phone validation (Israeli format)
export function validatePhone(phone: string): FieldValidationResult {
  if (!phone) {
    return { isValid: true }; // Phone is optional
  }

  // Remove non-digits
  const cleanPhone = phone.replace(/\D/g, '');
  
  // Israeli phone patterns: 05X-XXXXXXX, 0X-XXXXXXX, 1-800-XXXXXX
  if (cleanPhone.length < 9 || cleanPhone.length > 10) {
    return { isValid: false, error: 'מספר טלפון לא תקין' };
  }

  // Must start with 0 or 1
  if (!cleanPhone.startsWith('0') && !cleanPhone.startsWith('1')) {
    return { isValid: false, error: 'מספר טלפון חייב להתחיל ב-0 או 1' };
  }

  return { isValid: true };
}

// Date validation
export function validateDate(dateString: string, fieldName: string = 'תאריך'): FieldValidationResult {
  if (!dateString) {
    return { isValid: false, error: `${fieldName} הוא שדה חובה` };
  }

  const date = new Date(dateString);
  if (isNaN(date.getTime())) {
    return { isValid: false, error: `${fieldName} לא תקין` };
  }

  return { isValid: true };
}

// Birth date validation (age between 18-120)
export function validateBirthDate(birthDate: string): FieldValidationResult {
  const dateValidation = validateDate(birthDate, 'תאריך לידה');
  if (!dateValidation.isValid) {
    return dateValidation;
  }

  const birth = new Date(birthDate);
  const today = new Date();
  const age = today.getFullYear() - birth.getFullYear();
  const monthDiff = today.getMonth() - birth.getMonth();
  
  const actualAge = monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate()) 
    ? age - 1 
    : age;

  if (actualAge < 18) {
    return { isValid: false, error: 'הגיל חייב להיות לפחות 18' };
  }

  if (actualAge > 120) {
    return { isValid: false, error: 'הגיל לא יכול להיות מעל 120' };
  }

  return { isValid: true };
}

// Future date validation
export function validateFutureDate(dateString: string, fieldName: string = 'תאריך'): FieldValidationResult {
  const dateValidation = validateDate(dateString, fieldName);
  if (!dateValidation.isValid) {
    return dateValidation;
  }

  const date = new Date(dateString);
  const today = new Date();
  today.setHours(0, 0, 0, 0); // Reset time for date-only comparison

  if (date <= today) {
    return { isValid: false, error: `${fieldName} חייב להיות בעתיד` };
  }

  return { isValid: true };
}

// Amount validation (positive numbers)
export function validateAmount(amount: string | number, fieldName: string = 'סכום'): FieldValidationResult {
  if (amount === '' || amount === null || amount === undefined) {
    return { isValid: false, error: `${fieldName} הוא שדה חובה` };
  }

  const numAmount = typeof amount === 'string' ? parseFloat(amount) : amount;
  
  if (isNaN(numAmount)) {
    return { isValid: false, error: `${fieldName} חייב להיות מספר תקין` };
  }

  if (numAmount < 0) {
    return { isValid: false, error: `${fieldName} חייב להיות חיובי` };
  }

  return { isValid: true };
}

// Date range validation (end after start)
export function validateDateRange(startDate: string, endDate: string): FieldValidationResult {
  const startValidation = validateDate(startDate, 'תאריך התחלה');
  if (!startValidation.isValid) {
    return startValidation;
  }

  const endValidation = validateDate(endDate, 'תאריך סיום');
  if (!endValidation.isValid) {
    return endValidation;
  }

  const start = new Date(startDate);
  const end = new Date(endDate);

  if (end <= start) {
    return { isValid: false, error: 'תאריך הסיום חייב להיות אחרי תאריך ההתחלה' };
  }

  return { isValid: true };
}

// Required field validation
export function validateRequired(value: any, fieldName: string): FieldValidationResult {
  if (value === null || value === undefined || value === '' || 
      (typeof value === 'string' && value.trim() === '')) {
    return { isValid: false, error: `${fieldName} הוא שדה חובה` };
  }

  return { isValid: true };
}

// Client form validation
export function validateClientForm(formData: any): ValidationResult {
  const errors: string[] = [];

  // Required fields
  const fullNameValidation = validateRequired(formData.full_name, 'שם מלא');
  if (!fullNameValidation.isValid) errors.push(fullNameValidation.error!);

  const idValidation = validateIsraeliId(formData.id_number_raw);
  if (!idValidation.isValid) errors.push(idValidation.error!);

  const birthDateValidation = validateBirthDate(formData.birth_date);
  if (!birthDateValidation.isValid) errors.push(birthDateValidation.error!);

  // Optional fields
  if (formData.email) {
    const emailValidation = validateEmail(formData.email);
    if (!emailValidation.isValid) errors.push(emailValidation.error!);
  }

  if (formData.phone) {
    const phoneValidation = validatePhone(formData.phone);
    if (!phoneValidation.isValid) errors.push(phoneValidation.error!);
  }

  if (formData.retirement_date) {
    const retirementValidation = validateFutureDate(formData.retirement_date, 'תאריך פרישה');
    if (!retirementValidation.isValid) errors.push(retirementValidation.error!);
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

// Employment form validation
export function validateEmploymentForm(formData: any): ValidationResult {
  const errors: string[] = [];

  // Required fields
  const employerNameValidation = validateRequired(formData.employer_name, 'שם מעסיק');
  if (!employerNameValidation.isValid) errors.push(employerNameValidation.error!);

  const startDateValidation = validateDate(formData.start_date, 'תאריך התחלה');
  if (!startDateValidation.isValid) errors.push(startDateValidation.error!);

  const salaryValidation = validateAmount(formData.monthly_salary_nominal, 'שכר חודשי');
  if (!salaryValidation.isValid) errors.push(salaryValidation.error!);

  // Date range validation if end date provided
  if (formData.end_date) {
    const endDateValidation = validateDate(formData.end_date, 'תאריך סיום');
    if (!endDateValidation.isValid) {
      errors.push(endDateValidation.error!);
    } else {
      const rangeValidation = validateDateRange(formData.start_date, formData.end_date);
      if (!rangeValidation.isValid) errors.push(rangeValidation.error!);
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

// Sanity checks for calculation results
export function performSanityChecks(calculationResult: any): string[] {
  const warnings: string[] = [];

  if (!calculationResult) {
    return warnings;
  }

  // Check for negative tax
  if (calculationResult.cash_flow) {
    const negativeTax = calculationResult.cash_flow.some((item: any) => item.tax_amount < 0);
    if (negativeTax) {
      warnings.push('זוהה מס שלילי - יש לבדוק את הנתונים');
    }
  }

  // Check for unreasonable values
  if (calculationResult.summary) {
    if (calculationResult.summary.total_gross < 0) {
      warnings.push('זוהה הכנסה ברוטו שלילית');
    }

    if (calculationResult.summary.total_net > calculationResult.summary.total_gross * 1.1) {
      warnings.push('ההכנסה הנטו גבוהה מהברוטו - יש לבדוק את החישוב');
    }
  }

  return warnings;
}

// Format Israeli ID for display
export function formatIsraeliId(idNumber: string): string {
  const clean = idNumber.replace(/\D/g, '').padStart(9, '0');
  return `${clean.slice(0, 3)}-${clean.slice(3, 5)}-${clean.slice(5)}`;
}

// Format phone number for display
export function formatPhone(phone: string): string {
  const clean = phone.replace(/\D/g, '');
  if (clean.length === 10 && clean.startsWith('05')) {
    return `${clean.slice(0, 3)}-${clean.slice(3)}`;
  }
  if (clean.length === 9 && clean.startsWith('0')) {
    return `${clean.slice(0, 2)}-${clean.slice(2)}`;
  }
  return phone;
}

// Format currency for display
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: 'ILS',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}
