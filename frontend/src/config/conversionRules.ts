/**
 * חוקי המרת יתרות מתיק פנסיוני
 * 
 * קובץ זה מגדיר את כל החוקים והמגבלות להמרת כספים מתיק פנסיוני
 * לנכסי הון או לקצבאות, בהתאם לחוק
 */

// סוגי המרה אפשריים
export type ConversionType = 'pension' | 'capital_asset';

// סוגי מוצרים
export type ProductType = 'pension_fund' | 'insurance_policy' | 'provident_fund' | 'education_fund' | 'investment_provident_fund';

// יכולת המרה של רכיב
export interface ComponentConversionRule {
  field: string; // שם השדה בטבלה
  displayName: string; // שם תצוגה בעברית
  canConvertToPension: boolean; // ניתן להמרה לקצבה
  canConvertToCapital: boolean; // ניתן להמרה להון
  errorMessage?: string; // הודעת שגיאה אם לא ניתן להמיר
  taxTreatmentWhenPension: 'taxable' | 'exempt'; // יחס מס בהמרה לקצבה
  taxTreatmentWhenCapital?: 'capital_gains' | 'exempt'; // יחס מס בהמרה להון
  capitalAssetType?: 'provident_fund' | 'education_fund'; // סוג נכס הון אם רלוונטי
}

// חוקי המרה ברירת מחדל לפי רכיב כספי
const DEFAULT_COMPONENT_CONVERSION_RULES: ComponentConversionRule[] = [
  {
    field: 'פיצויים_מעסיק_נוכחי',
    displayName: 'פיצויים מעסיק נוכחי',
    canConvertToPension: false,
    canConvertToCapital: false,
    errorMessage: 'לא ניתן להמיר כספים ממעסיק נוכחי. נא לבצע סיום עבודה במסך מעסיק נוכחי',
    taxTreatmentWhenPension: 'taxable'
  },
  {
    field: 'פיצויים_לאחר_התחשבנות',
    displayName: 'פיצויים לאחר התחשבנות',
    canConvertToPension: true,
    canConvertToCapital: true,
    taxTreatmentWhenPension: 'exempt', // סכום הוני -> פטור ממס בהמרה לקצבה
    taxTreatmentWhenCapital: 'capital_gains',
    capitalAssetType: 'provident_fund'
  },
  {
    field: 'פיצויים_שלא_עברו_התחשבנות',
    displayName: 'פיצויים שלא עברו התחשבנות',
    canConvertToPension: false,
    canConvertToCapital: false,
    errorMessage: 'לא ניתן להמיר כספים שלא עברו התחשבנות',
    taxTreatmentWhenPension: 'taxable'
  },
  {
    field: 'פיצויים_ממעסיקים_קודמים_רצף_זכויות',
    displayName: 'פיצויים מעסיקים קודמים (זכויות)',
    canConvertToPension: false,
    canConvertToCapital: false,
    errorMessage: 'לא ניתן להמיר כספים ברצף זכויות. נא לבצע התחשבנות כולל במסגרת סיום עבודה מעסיק נוכחי',
    taxTreatmentWhenPension: 'taxable'
  },
  {
    field: 'פיצויים_ממעסיקים_קודמים_רצף_קצבה',
    displayName: 'פיצויים מעסיקים קודמים (קצבה)',
    canConvertToPension: true,
    canConvertToCapital: false,
    taxTreatmentWhenPension: 'taxable' // סכום קצבתי -> חייב במס
  },
  {
    field: 'תגמולי_עובד_עד_2000',
    displayName: 'תגמולי עובד עד 2000',
    canConvertToPension: true,
    canConvertToCapital: true,
    taxTreatmentWhenPension: 'exempt', // סכום הוני -> פטור ממס
    taxTreatmentWhenCapital: 'exempt', // פטור ממס גם בהמרה להון
    capitalAssetType: 'provident_fund'
  },
  {
    field: 'תגמולי_מעביד_עד_2000',
    displayName: 'תגמולי מעביד עד 2000',
    canConvertToPension: true,
    canConvertToCapital: true,
    taxTreatmentWhenPension: 'exempt', // סכום הוני -> פטור ממס
    taxTreatmentWhenCapital: 'exempt', // פטור ממס גם בהמרה להון
    capitalAssetType: 'provident_fund'
  },
  {
    field: 'תגמולי_עובד_אחרי_2000',
    displayName: 'תגמולי עובד אחרי 2000',
    canConvertToPension: true,
    canConvertToCapital: false,
    taxTreatmentWhenPension: 'taxable' // סכום קצבתי -> חייב במס
  },
  {
    field: 'תגמולי_מעביד_אחרי_2000',
    displayName: 'תגמולי מעביד אחרי 2000',
    canConvertToPension: true,
    canConvertToCapital: false,
    taxTreatmentWhenPension: 'taxable' // סכום קצבתי -> חייב במס
  },
  {
    field: 'תגמולי_עובד_אחרי_2008_לא_משלמת',
    displayName: 'תגמולי עובד אחרי 2008 (לא משלמת)',
    canConvertToPension: true,
    canConvertToCapital: false,
    taxTreatmentWhenPension: 'taxable' // סכום קצבתי -> חייב במס
  },
  {
    field: 'תגמולי_מעביד_אחרי_2008_לא_משלמת',
    displayName: 'תגמולי מעביד אחרי 2008 (לא משלמת)',
    canConvertToPension: true,
    canConvertToCapital: false,
    taxTreatmentWhenPension: 'taxable' // סכום קצבתי -> חייב במס
  },
  {
    field: 'קרן_השתלמות',
    displayName: 'קרן השתלמות',
    canConvertToPension: true,
    canConvertToCapital: true,
    taxTreatmentWhenPension: 'exempt', // סכום הוני -> פטור ממס
    taxTreatmentWhenCapital: 'exempt', // פטור ממס גם בהמרה להון
    capitalAssetType: 'education_fund'
  },
  {
    field: 'תגמולים',
    displayName: 'תגמולים (דינמי לפי סוג מוצר)',
    canConvertToPension: true,
    canConvertToCapital: true,
    taxTreatmentWhenPension: 'taxable',
    taxTreatmentWhenCapital: 'capital_gains',
    errorMessage: 'חוקי המרה לתגמולים תלויים בסוג המוצר: קרן פנסיה/ביטוח מנהלים=קצבתי בלבד; קופת גמל/קרן השתלמות=הוני פטור; קופת גמל להשקעה=הוני עם מס רווח הון'
  },
];

/**
 * מזהה סוג מוצר על פי שמו
 */
export function identifyProductType(productName: string): ProductType {
  if (!productName) return 'pension_fund';
  
  const lowerName = productName.toLowerCase();
  
  if (lowerName.includes('קרן השתלמות')) {
    return 'education_fund';
  } else if (lowerName.includes('גמל להשקעה')) {
    return 'investment_provident_fund';
  } else if (lowerName.includes('ביטוח')) {
    return 'insurance_policy';
  } else if (lowerName.includes('קופת גמל')) {
    return 'provident_fund';
  } else {
    return 'pension_fund';
  }
}

/**
 * בדיקה האם קרן השתלמות (כל היתרה ניתנת להמרה להון)
 */
export function isEducationFund(productType: string): boolean {
  return !!productType && productType.includes('קרן השתלמות');
}

/**
 * טעינת חוקי המרה מ-localStorage או ברירת מחדל
 * אם יש חוקים חדשים ב-DEFAULT_RULES שלא קיימים ב-localStorage, מוסיף אותם
 */
export function loadConversionRules(): ComponentConversionRule[] {
  try {
    const savedRules = localStorage.getItem('conversion_rules');
    if (savedRules) {
      const parsed = JSON.parse(savedRules);
      
      // בדוק אם יש חוקים חדשים ב-DEFAULT_RULES שלא קיימים ב-parsed
      const existingFields = new Set(parsed.map((r: ComponentConversionRule) => r.field));
      const newRules = DEFAULT_COMPONENT_CONVERSION_RULES.filter(
        defaultRule => !existingFields.has(defaultRule.field)
      );
      
      // אם יש חוקים חדשים, הוסף אותם
      if (newRules.length > 0) {
        console.log(`Adding ${newRules.length} new conversion rules:`, newRules.map(r => r.displayName));
        return [...parsed, ...newRules];
      }
      
      return parsed;
    }
  } catch (error) {
    console.warn('Failed to load conversion rules from localStorage:', error);
  }
  return [...DEFAULT_COMPONENT_CONVERSION_RULES];
}

/**
 * חוקי המרה פעילים (לטעינה דינמית)
 */
export const COMPONENT_CONVERSION_RULES = loadConversionRules();

/**
 * ייצוא חוקי המרה ברירת מחדל לשימוש בדף הגדרות
 */
export const DEFAULT_RULES = DEFAULT_COMPONENT_CONVERSION_RULES;

/**
 * קבלת חוק המרה עבור רכיב מסוים
 */
export function getComponentRule(fieldName: string): ComponentConversionRule | undefined {
  const rules = loadConversionRules();
  return rules.find((rule: ComponentConversionRule) => rule.field === fieldName);
}

/**
 * תוצאת ולידציה
 */
export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * ולידציה של המרה מוצעת
 */
export interface ConversionValidation {
  canConvert: boolean;
  errors: string[];
  warnings: string[];
  taxTreatment: 'taxable' | 'exempt' | 'capital_gains';
}

/**
 * ולידציית המרה של רכיב בודד
 */
export function validateComponentConversion(
  fieldName: string,
  amount: number,
  conversionType: ConversionType,
  productType: string
): ConversionValidation {
  const result: ConversionValidation = {
    canConvert: false,
    errors: [],
    warnings: [],
    taxTreatment: 'taxable'
  };

  // טיפול מיוחד בשדה תגמולים - תלוי בסוג המוצר
  if (fieldName === 'תגמולים') {
    const lowerProductType = productType.toLowerCase();
    
    // קרן פנסיה או ביטוח מנהלים - סכום קצבתי
    if (lowerProductType.includes('קרן פנסיה') || lowerProductType.includes('ביטוח מנהלים')) {
      if (conversionType === 'pension') {
        result.canConvert = true;
        result.taxTreatment = 'taxable'; // חייב במס
      } else {
        result.canConvert = false;
        result.errors.push('תגמולים בקרן פנסיה/ביטוח מנהלים ניתנים להמרה לקצבה בלבד');
      }
      return result;
    }
    
    // קופת גמל או קרן השתלמות - סכום הוני
    if (lowerProductType.includes('קופת גמל') && !lowerProductType.includes('להשקעה')) {
      result.canConvert = true;
      result.taxTreatment = 'exempt'; // פטור ממס
      return result;
    }
    
    if (lowerProductType.includes('קרן השתלמות')) {
      result.canConvert = true;
      result.taxTreatment = 'exempt'; // פטור ממס
      return result;
    }
    
    // קופת גמל להשקעה - סכום הוני עם יחס מס שונה
    if (lowerProductType.includes('גמל להשקעה')) {
      result.canConvert = true;
      if (conversionType === 'pension') {
        result.taxTreatment = 'exempt'; // פטור ממס
      } else {
        result.taxTreatment = 'capital_gains'; // חייב במס רווח הון
      }
      return result;
    }
    
    // ברירת מחדל - אם לא זוהה סוג מוצר
    result.canConvert = false;
    result.errors.push('לא ניתן לקבוע חוקי המרה עבור תגמולים - סוג מוצר לא מזוהה');
    return result;
  }

  // קרן השתלמות - כל היתרה היא הונית
  if (isEducationFund(productType)) {
    if (conversionType === 'capital_asset') {
      result.canConvert = true;
      result.taxTreatment = 'capital_gains';
    } else if (conversionType === 'pension') {
      result.canConvert = true;
      result.taxTreatment = 'exempt'; // הוני -> פטור ממס
    }
    return result;
  }

  // בדיקה לפי חוקי הרכיב
  const rule = getComponentRule(fieldName);
  
  if (!rule) {
    result.errors.push(`לא נמצאו חוקים עבור רכיב: ${fieldName}`);
    return result;
  }

  // בדיקה לפי סוג ההמרה
  if (conversionType === 'pension') {
    if (rule.canConvertToPension) {
      result.canConvert = true;
      result.taxTreatment = rule.taxTreatmentWhenPension;
    } else {
      result.canConvert = false;
      result.errors.push(rule.errorMessage || `לא ניתן להמיר ${rule.displayName} לקצבה`);
    }
  } else if (conversionType === 'capital_asset') {
    if (rule.canConvertToCapital) {
      result.canConvert = true;
      result.taxTreatment = rule.taxTreatmentWhenCapital || 'capital_gains';
    } else {
      result.canConvert = false;
      result.errors.push(rule.errorMessage || `לא ניתן להמיר ${rule.displayName} להון`);
    }
  }

  return result;
}

/**
 * ולידציית המרה מלאה של חשבון
 */
export function validateAccountConversion(
  account: any,
  selectedAmounts: Record<string, boolean>,
  conversionType: ConversionType
): ValidationResult {
  const result: ValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  };

  const productType = account.סוג_מוצר || '';

  // אם זו קרן השתלמות, אין צורך בבדיקות נוספות
  if (isEducationFund(productType)) {
    if (conversionType === 'capital_asset') {
      result.warnings.push('קרן השתלמות - כל היתרה ניתנת להמרה להון');
    } else {
      result.warnings.push('קרן השתלמות - כל היתרה ניתנת להמרה לקצבה (פטור ממס)');
    }
    return result;
  }

  // בדיקת כל הסכומים שנבחרו
  const selectedFields = Object.entries(selectedAmounts)
    .filter(([_, isSelected]) => isSelected)
    .map(([field]) => field);

  if (selectedFields.length === 0) {
    result.valid = false;
    result.errors.push('לא נבחרו סכומים להמרה');
    return result;
  }

  // ולידציה של כל רכיב שנבחר
  for (const fieldName of selectedFields) {
    if (fieldName === 'יתרה') continue; // יתרה כללית - דלג

    const amount = account[fieldName];
    if (!amount || amount <= 0) continue;

    const validation = validateComponentConversion(
      fieldName,
      amount,
      conversionType,
      productType
    );

    if (!validation.canConvert) {
      result.valid = false;
      result.errors.push(...validation.errors);
    } else {
      result.warnings.push(...validation.warnings);
    }
  }

  return result;
}

/**
 * חישוב יחס מס עבור המרה
 * מחזיר את יחס המס הדומיננטי בהתאם לסכומים
 */
export function calculateTaxTreatment(
  account: any,
  selectedAmounts: Record<string, boolean>,
  conversionType: ConversionType
): 'taxable' | 'exempt' | 'capital_gains' {
  const productType = account.סוג_מוצר || '';
  const lowerProductType = productType.toLowerCase();

  // קרן השתלמות - פטור ממס תמיד (גם להון וגם לקצבה)
  if (isEducationFund(productType)) {
    return 'exempt';
  }

  // חישוב לפי רכיבים
  let totalAmount = 0;
  let taxableAmount = 0;
  let exemptAmount = 0;
  let capitalGainsAmount = 0;

  Object.entries(selectedAmounts).forEach(([field, isSelected]) => {
    if (!isSelected || field === 'יתרה') return;

    const amount = account[field] || 0;
    if (amount <= 0) return;

    const validation = validateComponentConversion(field, amount, conversionType, productType);
    
    if (validation.canConvert) {
      totalAmount += amount;
      
      if (validation.taxTreatment === 'taxable') {
        taxableAmount += amount;
      } else if (validation.taxTreatment === 'exempt') {
        exemptAmount += amount;
      } else if (validation.taxTreatment === 'capital_gains') {
        capitalGainsAmount += amount;
      }
    }
  });

  // החזרת יחס המס הדומיננטי
  if (conversionType === 'capital_asset') {
    // קופת גמל רגילה (לא להשקעה) - פטור ממס
    if (lowerProductType.includes('קופת גמל') && !lowerProductType.includes('להשקעה')) {
      return 'exempt';
    }
    
    // קופת גמל להשקעה - מס רווח הון
    if (lowerProductType.includes('גמל להשקעה')) {
      return 'capital_gains';
    }
    
    // החלטה לפי הסכומים - אם רוב הסכום פטור, נחזיר פטור
    if (exemptAmount > capitalGainsAmount && exemptAmount > taxableAmount) {
      return 'exempt';
    } else if (capitalGainsAmount > 0) {
      return 'capital_gains';
    } else {
      return 'exempt'; // ברירת מחדל להון
    }
  } else {
    // להמרה לקצבה - אם רוב הסכום הוא פטור, נחזיר פטור
    return exemptAmount > taxableAmount ? 'exempt' : 'taxable';
  }
}

/**
 * קבלת הסבר טקסטואלי על החוקים
 */
export function getConversionRulesExplanation(): string {
  return `
חוקי המרת יתרות מתיק פנסיוני:

סוגי מוצרים:
- קרן פנסיה
- פוליסת ביטוח (כל טקסט הכולל "ביטוח")
- קופת גמל
- קרן השתלמות

חוקים כלליים:
✓ כל הנכסים ניתנים להמרה לקצבה (אין מגבלות)
✓ לא כל הנכסים ניתנים להמרה להון (יש הגבלות)
✓ קרן השתלמות - כל היתרה ניתנת להמרה להון ללא מגבלה

חוקי המרה לפי רכיב:
1. פיצויים מעסיק נוכחי - אסור להמיר (נדרש סיום עבודה)
2. פיצויים לאחר התחשבנות - הון או קצבה ✓ (מס רווח הון / פטור ממס)
3. פיצויים שלא עברו התחשבנות - אסור להמיר
4. פיצויים מעסיקים קודמים (זכויות) - אסור להמיר (נדרשת התחשבנות)
5. פיצויים מעסיקים קודמים (קצבה) - קצבה בלבד ✓ (חייב במס)
6. תגמולי עובד עד 2000 - הון או קצבה ✓ (מס רווח הון / פטור ממס)
7. תגמולי מעביד עד 2000 - הון או קצבה ✓ (מס רווח הון / פטור ממס)
8. תגמולי עובד אחרי 2000 - קצבה בלבד ✓ (חייב במס)
9. תגמולי מעביד אחרי 2000 - קצבה בלבד ✓ (חייב במס)
10. תגמולי עובד אחרי 2008 (לא משלמת) - קצבה בלבד ✓ (חייב במס)
11. תגמולי מעביד אחרי 2008 (לא משלמת) - קצבה בלבד ✓ (חייב במס)
12. תגמולים - חוקי המרה דינמיים לפי סוג מוצר:
    - קרן פנסיה/ביטוח מנהלים: קצבתי - קצבה בלבד ✓ (חייב במס)
    - קופת גמל/קרן השתלמות: הוני - הון או קצבה ✓ (פטור ממס)
    - קופת גמל להשקעה: הוני - הון (מס רווח הון) או קצבה (פטור ממס) ✓

יחס מס:
• סכום קצבתי -> קצבה: חייב במס
• סכום הוני -> קצבה: פטור ממס
• סכום הוני -> הון: מס רווח הון
`;
}
