// פונקציות עזר לפורמט תאריכים
export const formatDateToDDMMYY = (date: string | Date | null | undefined): string => {
  if (!date) return '';
  
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(dateObj.getTime())) return '';
    
    const day = dateObj.getDate().toString().padStart(2, '0');
    const month = (dateObj.getMonth() + 1).toString().padStart(2, '0');
    const year = dateObj.getFullYear().toString().slice(-2);
    
    return `${day}/${month}/${year}`;
  } catch (error) {
    console.error('Error formatting date:', error);
    return '';
  }
};

// המרה מפורמט DD/MM/YY לפורמט YYYY-MM-DD עבור input date
export const convertDDMMYYToISO = (ddmmyy: string): string => {
  if (!ddmmyy) return '';
  
  try {
    const parts = ddmmyy.split('/');
    if (parts.length === 3 && parts[0].length === 2 && parts[1].length === 2 && parts[2].length === 2) {
      const day = parts[0];
      const month = parts[1];
      const yearShort = parseInt(parts[2]);
      
      // אם השנה היא 2 ספרות, צריך להחליט אם זה 19XX או 20XX
      // השתמש בשנה הנוכחית כנקודת ייחוס
      const currentYear = new Date().getFullYear();
      const currentYearShort = currentYear % 100; // לדוגמה: 2025 -> 25
      
      let year: number;
      // אם השנה קטנה או שווה לשנה הנוכחית, זה 20XX
      // אחרת, זה 19XX
      if (yearShort <= currentYearShort) {
        year = 2000 + yearShort;
      } else {
        year = 1900 + yearShort;
      }
      
      return `${year}-${month}-${day}`;
    }
  } catch (error) {
    console.error('Error converting date:', error);
  }
  
  return '';
};

// המרה מפורמט YYYY-MM-DD לפורמט DD/MM/YY
export const convertISOToDDMMYY = (iso: string): string => {
  if (!iso) return '';
  
  try {
    const date = new Date(iso);
    return formatDateToDDMMYY(date);
  } catch (error) {
    console.error('Error converting ISO date:', error);
    return '';
  }
};

export const formatDateToDDMMYYYY = (date: string | Date | null | undefined): string => {
  if (!date) return '';
  
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(dateObj.getTime())) return '';
    
    const day = dateObj.getDate().toString().padStart(2, '0');
    const month = (dateObj.getMonth() + 1).toString().padStart(2, '0');
    const year = dateObj.getFullYear().toString();
    
    return `${day}/${month}/${year}`;
  } catch (error) {
    console.error('Error formatting date:', error);
    return '';
  }
};

export const parseDate = (dateString: string): Date | null => {
  if (!dateString) return null;
  
  try {
    // תמיכה בפורמטים שונים
    if (dateString.includes('/')) {
      const parts = dateString.split('/');
      if (parts.length === 3) {
        const day = parseInt(parts[0]);
        const month = parseInt(parts[1]) - 1; // חודשים מתחילים מ-0
        const year = parseInt(parts[2]);
        const fullYear = year < 100 ? 2000 + year : year;
        return new Date(fullYear, month, day);
      }
    }
    
    return new Date(dateString);
  } catch (error) {
    console.error('Error parsing date:', error);
    return null;
  }
};

// פונקציה לעיצוב תאריך עם מסכה
export const formatDateInput = (value: string): string => {
  if (!value) return '';
  
  // הסרת כל מה שלא מספרים
  let inputValue = value.replace(/[^0-9]/g, '');
  
  // הוספת סלאשים אוטומטית
  if (inputValue.length >= 2) {
    inputValue = inputValue.substring(0, 2) + '/' + inputValue.substring(2);
  }
  if (inputValue.length >= 5) {
    inputValue = inputValue.substring(0, 5) + '/' + inputValue.substring(5);
  }
  
  // הגבלה ל-8 תווים (DD/MM/YY)
  return inputValue.substring(0, 8);
};

// וולידציה לתאריך בפורמט DD/MM/YY
export const validateDDMMYY = (dateString: string): boolean => {
  if (!dateString) return false;
  
  const regex = /^(0[1-9]|[12][0-9]|3[01])\/(0[1-9]|1[0-2])\/\d{2}$/;
  if (!regex.test(dateString)) return false;
  
  const parts = dateString.split('/');
  const day = parseInt(parts[0]);
  const month = parseInt(parts[1]);
  const year = parseInt('20' + parts[2]);
  
  const date = new Date(year, month - 1, day);
  return date.getDate() === day && 
         date.getMonth() === month - 1 && 
         date.getFullYear() === year;
};
