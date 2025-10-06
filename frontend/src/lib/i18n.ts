import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Hebrew translations
const resources = {
  he: {
    translation: {
      // Navigation
      'nav.client': 'פרטי לקוח',
      'nav.currentEmployer': 'מעסיק נוכחי',
      'nav.pastEmployers': 'מעסיקים קודמים',
      'nav.pensions': 'קצבאות',
      'nav.incomeAssets': 'הכנסות ונכסים',
      'nav.taxAdmin': 'פרמטרי מס ומדד',
      'nav.scenarios': 'בניית תרחישים',
      'nav.results': 'תוצאות',
      
      // Common
      'common.save': 'שמור',
      'common.cancel': 'ביטול',
      'common.next': 'הבא',
      'common.previous': 'הקודם',
      'common.calculate': 'חשב',
      'common.loading': 'טוען...',
      'common.error': 'שגיאה',
      'common.success': 'הצלחה',
      'common.required': 'שדה חובה',
      'common.optional': 'אופציונלי',
      
      // Client form
      'client.title': 'פרטי לקוח',
      'client.fullName': 'שם מלא',
      'client.idNumber': 'מספר זהות',
      'client.birthDate': 'תאריך לידה',
      'client.email': 'דוא"ל',
      'client.phone': 'טלפון',
      'client.retirementDate': 'תאריך פרישה מתוכנן',
      
      // Validation messages
      'validation.required': 'שדה זה הוא חובה',
      'validation.email': 'כתובת דוא"ל לא תקינה',
      'validation.phone': 'מספר טלפון לא תקין',
      'validation.idNumber': 'מספר זהות לא תקין',
      'validation.dateInvalid': 'תאריך לא תקין',
      'validation.dateInFuture': 'התאריך חייב להיות בעתיד',
      'validation.ageRange': 'הגיל חייב להיות בין 18 ל-120',
      'validation.amountPositive': 'הסכום חייב להיות חיובי',
      'validation.endAfterStart': 'תאריך הסיום חייב להיות אחרי תאריך ההתחלה',
      
      // Cases
      'case.1': 'לקוח ללא מעסיק נוכחי',
      'case.2': 'לקוח עם מעסיק נוכחי - עזב',
      'case.3': 'לקוח עם מעסיק נוכחי - יעזוב בעתיד',
      'case.4': 'לקוח עם מעסיק נוכחי - תאריך עזיבה לא ידוע',
      'case.5': 'עובד רגיל עם תכנון עזיבה',
      
      // Process control
      'process.missingData': 'חסרים נתונים קריטיים. אנא השלם את השדות הנדרשים.',
      'process.cannotProceed': 'לא ניתן להמשיך ללא השלמת הנתונים.',
      
      // QA messages
      'qa.warning': 'אזהרה',
      'qa.negativeTax': 'זוהה מס שלילי - יש לבדוק את הנתונים',
      'qa.exemptionExceeded': 'הפטור חורג מהסכום המותר',
      'qa.unreasonableValue': 'זוהה ערך לא סביר',
      
      // Dev mode
      'dev.mode': 'מצב פיתוח',
      'dev.debugValues': 'ערכי דיבאג',
      'dev.formulas': 'נוסחאות'
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    lng: 'he', // Default language
    fallbackLng: 'he',
    
    interpolation: {
      escapeValue: false, // React already does escaping
    },
    
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;
