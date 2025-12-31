// פונקציות עזר לפורמט תאריכים
export const formatDateToDDMMYY = (date: string | Date | null | undefined): string => {
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

// המרה מפורמט DD/MM/YYYY לפורמט YYYY-MM-DD עבור input date
export const convertDDMMYYToISO = (ddmmyyyy: string): string => {
  if (!ddmmyyyy) return '';
  
  try {
    const raw = ddmmyyyy.trim();
    if (!raw) return '';

    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      return raw;
    }

    const normalized = raw.replace(/\./g, '/').replace(/-/g, '/');
    const parts = normalized.split('/').map(p => p.trim());
    if (parts.length === 3) {
      const [p1, p2, p3] = parts;

      if (p1.length === 4 && p2.length === 2 && p3.length === 2) {
        const year = p1;
        const month = p2;
        const day = p3;
        if (validateDDMMYY(`${day}/${month}/${year}`)) {
          return `${year}-${month}-${day}`;
        }
        return '';
      }

      if (p1.length === 2 && p2.length === 2 && p3.length === 4) {
        const day = p1;
        const month = p2;
        const year = p3;
        if (validateDDMMYY(`${day}/${month}/${year}`)) {
          return `${year}-${month}-${day}`;
        }
        return '';
      }
    }

    if (/^\d{8}$/.test(raw)) {
      const y = raw.slice(0, 4);
      const m = raw.slice(4, 6);
      const d = raw.slice(6, 8);
      if ((y.startsWith('19') || y.startsWith('20')) && validateDDMMYY(`${d}/${m}/${y}`)) {
        return `${y}-${m}-${d}`;
      }

      const day = raw.slice(0, 2);
      const month = raw.slice(2, 4);
      const year = raw.slice(4, 8);
      if (validateDDMMYY(`${day}/${month}/${year}`)) {
        return `${year}-${month}-${day}`;
      }
    }
  } catch (error) {
    console.error('Error converting date:', error);
  }
  
  return '';
};

// המרה מפורמט YYYY-MM-DD לפורמט DD/MM/YYYY
export const convertISOToDDMMYY = (iso: string): string => {
  if (!iso) return '';
  
  try {
    const raw = iso.trim();
    if (!raw) return '';

    const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) {
      const year = match[1];
      const month = match[2];
      const day = match[3];
      return `${day}/${month}/${year}`;
    }

    const date = new Date(raw);
    return formatDateToDDMMYYYY(date);
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
    const raw = dateString.trim();
    if (!raw) return null;

    // ISO yyyy-mm-dd
    const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) {
      const year = parseInt(iso[1]);
      const month = parseInt(iso[2]) - 1;
      const day = parseInt(iso[3]);
      const dt = new Date(year, month, day);
      if (dt.getFullYear() === year && dt.getMonth() === month && dt.getDate() === day) {
        return dt;
      }
      return null;
    }

    // תמיכה בפורמטים שונים
    const normalized = raw.replace(/\./g, '/').replace(/-/g, '/');
    if (normalized.includes('/')) {
      const parts = normalized.split('/');
      if (parts.length === 3) {
        const day = parseInt(parts[0]);
        const month = parseInt(parts[1]) - 1; // חודשים מתחילים מ-0
        const year = parseInt(parts[2]);
        const fullYear = year < 100 ? 2000 + year : year;
        return new Date(fullYear, month, day);
      }
    }

    if (/^\d{8}$/.test(raw)) {
      const y = raw.slice(0, 4);
      const m = raw.slice(4, 6);
      const d = raw.slice(6, 8);
      if (y.startsWith('19') || y.startsWith('20')) {
        const dt = new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
        return dt;
      }

      const day = raw.slice(0, 2);
      const month = raw.slice(2, 4);
      const year = raw.slice(4, 8);
      const dt = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
      return dt;
    }

    return new Date(raw);
  } catch (error) {
    console.error('Error parsing date:', error);
    return null;
  }
};

// פונקציה לעיצוב תאריך עם מסכה DD/MM/YYYY
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
  
  // הגבלה ל-10 תווים (DD/MM/YYYY)
  return inputValue.substring(0, 10);
};

// וולידציה לתאריך בפורמט DD/MM/YYYY
export const validateDDMMYY = (dateString: string): boolean => {
  if (!dateString) return false;
  
  const regex = /^(0[1-9]|[12][0-9]|3[01])\/(0[1-9]|1[0-2])\/\d{4}$/;
  if (!regex.test(dateString)) return false;
  
  const parts = dateString.split('/');
  const day = parseInt(parts[0]);
  const month = parseInt(parts[1]);
  const year = parseInt(parts[2]);
  
  const date = new Date(year, month - 1, day);
  return date.getDate() === day && 
         date.getMonth() === month - 1 && 
         date.getFullYear() === year;
};
