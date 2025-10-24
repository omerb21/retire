import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import axios from 'axios';
import * as XLSX from 'xlsx';
import { formatDateToDDMMYY, formatDateToDDMMYYYY } from '../utils/dateUtils';
import { 
  validateAccountConversion, 
  calculateTaxTreatment, 
  getConversionRulesExplanation,
  isEducationFund
} from '../config/conversionRules';

type PensionAccount = {
  id?: number;
  מספר_חשבון: string;
  שם_תכנית: string;
  חברה_מנהלת: string;
  קוד_חברה_מנהלת?: string;
  יתרה: number; // יתרה מקורית - לא מוצגת, רק לחישובים
  תאריך_נכונות_יתרה: string;
  תאריך_התחלה?: string;
  סוג_מוצר: string;
  מעסיקים_היסטוריים?: string;
  פיצויים_מעסיק_נוכחי?: number;
  פיצויים_לאחר_התחשבנות?: number;
  פיצויים_שלא_עברו_התחשבנות?: number;
  פיצויים_ממעסיקים_קודמים_רצף_זכויות?: number;
  פיצויים_ממעסיקים_קודמים_רצף_קצבה?: number;
  תגמולי_עובד_עד_2000?: number;
  תגמולי_עובד_אחרי_2000?: number;
  תגמולי_עובד_אחרי_2008_לא_משלמת?: number;
  תגמולי_מעביד_עד_2000?: number;
  תגמולי_מעביד_אחרי_2000?: number;
  תגמולי_מעביד_אחרי_2008_לא_משלמת?: number;
  תגמולים?: number; // ערך מיובא מתגית YITRAT-KASPEY-TAGMULIM
  selected?: boolean;
  conversion_type?: 'pension' | 'capital_asset';
  selected_amounts?: {[key: string]: boolean}; // לסימון סכומים ספציפיים
  saved_fund_id?: number; // ID של התכנית השמורה במסד הנתונים
};

type ProcessedFile = {
  file: string;
  accounts: PensionAccount[];
  processed_at: string;
};

/**
 * פונקציה זו כבר לא מחשבת תגמולים - התגמולים מיובאים ישירות מהתגית YITRAT-KASPEY-TAGMULIM
 * הפונקציה נשארת לצורך תאימות לאחור אך פשוט מחזירה את החשבון כמו שהוא
 */
function calculateInitialTagmulim(account: PensionAccount): PensionAccount {
  // אין יותר חישוב - התגמולים מיובאים ישירות מה-XML
  return account;
}

/**
 * מחשב יתרה כללית מחדש (סכום כל הטורים כולל תגמולים)
 */
function calculateTotalBalance(account: PensionAccount): number {
  const allFields = [
    'פיצויים_מעסיק_נוכחי',
    'פיצויים_לאחר_התחשבנות',
    'פיצויים_שלא_עברו_התחשבנות',
    'פיצויים_ממעסיקים_קודמים_רצף_זכויות',
    'פיצויים_ממעסיקים_קודמים_רצף_קצבה',
    'תגמולי_עובד_עד_2000',
    'תגמולי_עובד_אחרי_2000',
    'תגמולי_עובד_אחרי_2008_לא_משלמת',
    'תגמולי_מעביד_עד_2000',
    'תגמולי_מעביד_אחרי_2000',
    'תגמולי_מעביד_אחרי_2008_לא_משלמת',
    'תגמולים'
  ];

  return allFields.reduce((sum, field) => {
    const value = (account as any)[field];
    return sum + (typeof value === 'number' ? value : 0);
  }, 0);
}

export default function PensionPortfolio() {
  const { id: clientId } = useParams<{ id: string }>();
  const [pensionData, setPensionData] = useState<PensionAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [processingStatus, setProcessingStatus] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [convertedAccounts, setConvertedAccounts] = useState<Set<string>>(new Set()); // זיכרון תכניות שהומרו
  const [conversionTypes, setConversionTypes] = useState<Record<number, 'pension' | 'capital_asset'>>({}); // סוגי המרה לפי אינדקס
  const [clientData, setClientData] = useState<any>(null); // נתוני הלקוח
  const [editingCell, setEditingCell] = useState<{row: number, field: string} | null>(null); // תא בעריכה
  const [showConversionRules, setShowConversionRules] = useState<boolean>(false); // הצגת חוקי המרה

  // פונקציה לעיבוד קבצי XML ו-DAT של המסלקה
  const processXMLFiles = async (files: FileList) => {
    setLoading(true);
    setError("");
    setProcessingStatus("מוחק נתונים קיימים ומעבד קבצים...");
    
    // מחיקת כל הנתונים הקיימים מה-state ומה-localStorage
    setPensionData([]);
    localStorage.removeItem(`pensionData_${clientId}`);

    try {
      const processedAccounts: PensionAccount[] = [];
      const supportedExtensions = ['.xml', '.dat'];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fileName = file.name.toLowerCase();
        
        // בדיקה אם הקובץ נתמך
        if (!supportedExtensions.some(ext => fileName.endsWith(ext))) {
          console.log(`דילוג על קובץ ${file.name} - סוג קובץ לא נתמך`);
          continue;
        }

        const fileType = fileName.endsWith('.dat') ? 'DAT' : 'XML';
        setProcessingStatus(`מעבד קובץ ${fileType} ${i + 1} מתוך ${files.length}: ${file.name}`);

        const text = await file.text();
        const accounts = extractAccountsFromXML(text, file.name);
        console.log(`File ${file.name} (${fileType}) produced ${accounts.length} accounts`);
        processedAccounts.push(...accounts);
      }

      console.log(`Total processed accounts:`, processedAccounts.length);
      if (processedAccounts.length > 0) {
        // סינון תכניות שהומרו
        const filteredAccounts = processedAccounts.filter(account => {
          const accountId = `${account.מספר_חשבון}_${account.שם_תכנית}_${account.חברה_מנהלת}`;
          return !convertedAccounts.has(accountId);
        });
        
        setPensionData(filteredAccounts);
        // שמירה ל-localStorage
        localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(filteredAccounts));
        setProcessingStatus(`הושלם עיבוד ${filteredAccounts.length} חשבונות פנסיוניים (${processedAccounts.length - filteredAccounts.length} הומרו בעבר)`);
      } else {
        setProcessingStatus("לא נמצאו חשבונות פנסיוניים בקבצים שנבחרו");
      }
    } catch (e: any) {
      setError(`שגיאה בעיבוד קבצים: ${e?.message || e}`);
      setProcessingStatus("");
    } finally {
      setLoading(false);
    }
  };

  // פונקציה לחילוץ חשבונות מתוכן XML
  const extractAccountsFromXML = (xmlContent: string, fileName: string): PensionAccount[] => {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlContent, "text/xml");
    
    // חילוץ תגיות גלובליות של סוג מוצר (פעם אחת לכל הקובץ)
    const globalShemMutzar = xmlDoc.getElementsByTagName('SHEM-MUTZAR')[0]?.textContent?.trim() || '';
    const globalSugMutzar = xmlDoc.getElementsByTagName('SUG-MUTZAR')[0]?.textContent?.trim() || '';
    
    console.log(`${fileName}: Global SHEM-MUTZAR="${globalShemMutzar}", SUG-MUTZAR="${globalSugMutzar}"`);
    
    // חיפוש אלמנטי חשבונות בשמות שונים
    const accountSelectors = [
      'HeshbonOPolisa', 'Heshbon', 'Account', 'Policy', 'Polisa',
      'PensionAccount', 'PensionPolicy', 'KupatGemel', 'BituachMenahalim', 'KerenPensia'
    ];

    const accounts: PensionAccount[] = [];

    for (const selector of accountSelectors) {
      const accountElements = xmlDoc.getElementsByTagName(selector);
      console.log(`Found ${accountElements.length} elements with tag ${selector}`);
      for (let i = 0; i < accountElements.length; i++) {
        const account = extractAccountData(accountElements[i], fileName, xmlDoc, globalShemMutzar, globalSugMutzar);
        if (account) {
          console.log(`Adding account to list:`, account);
          accounts.push(account);
        } else {
          console.log(`Account was null, not adding`);
        }
      }
    }

    console.log(`Total accounts extracted from ${fileName}:`, accounts.length);
    return accounts;
  };

  // פונקציה לחילוץ נתוני חשבון מאלמנט XML
  const extractAccountData = (accountElem: Element, fileName: string, xmlDoc: Document, globalShemMutzar: string, globalSugMutzar: string): PensionAccount | null => {
    const getElementText = (tagName: string): string => {
      // חיפוש ראשון בתוך האלמנט הספציפי
      const elements = accountElem.getElementsByTagName(tagName);
      for (let i = 0; i < elements.length; i++) {
        const text = elements[i].textContent?.trim();
        if (text) {
          return text;
        }
      }
      return '';
    };

    const getElementTextGlobal = (tagName: string): string => {
      // חיפוש גלובלי בכל המסמך (לשדות כמו SHEM-YATZRAN)
      const elements = xmlDoc.getElementsByTagName(tagName);
      for (let i = 0; i < elements.length; i++) {
        const text = elements[i].textContent?.trim();
        if (text) {
          return text;
        }
      }
      return '';
    };

    const getElementFloat = (tagName: string): number => {
      const text = getElementText(tagName);
      const num = parseFloat(text.replace(/,/g, ''));
      return isNaN(num) ? 0 : num;
    };

    const getElementFloatGlobal = (tagName: string): number => {
      const text = getElementTextGlobal(tagName);
      const num = parseFloat(text.replace(/,/g, ''));
      return isNaN(num) ? 0 : num;
    };

    // מספר חשבון
    const accountNumber = getElementText('MISPAR-POLISA-O-HESHBON') ||
                         getElementText('MISPAR-HESHBON') ||
                         getElementText('MISPAR-POLISA') ||
                         'לא ידוע';

    // שם תכנית
    const planName = getElementText('SHEM-TOCHNIT') ||
                    getElementText('TOCHNIT') ||
                    getElementText('SHEM_TOCHNIT') ||
                    'לא ידוע';

    // חברה מנהלת - חיפוש גלובלי ואז מקומי
    const managingCompany = getElementTextGlobal('SHEM-YATZRAN') ||
                           getElementTextGlobal('SHEM-METAFEL') ||
                           getElementText('SHEM_HA_MOSAD') ||
                           getElementText('Provider') ||
                           getElementText('Company') ||
                           'לא ידוע';
    
    console.log(`Managing company found: ${managingCompany}`);

    // קוד חברה מנהלת
    const companyCode = getElementText('KOD-MEZAHE-YATZRAN') ||
                       getElementText('KOD-MEZAHE-METAFEL') ||
                       getElementText('KOD-YATZRAN') ||
                       getElementText('MEZAHE-YATZRAN');

    // יתרה - לפי הקוד המקורי, TOTAL-CHISACHON-MTZBR הוא השדה העיקרי
    let balance = 0;
    const balanceFields = [
      'TOTAL-CHISACHON-MTZBR',  // השדה העיקרי לפי הקוד המקורי
      'TOTAL-ERKEI-PIDION', 
      'YITRAT-KASPEY-TAGMULIM',
      'YITRAT-PITZUIM'
    ];

    // חיפוש יתרה לפי המערכת הקיימת המלאה מ-process_pensions.py
    const findBalance = (): number => {
      // 1. Sum balances reported per track in BlockItrot/PerutYitrot sections
      const yitrotTotal = sumFields('.//BlockItrot//PerutYitrot', ['TOTAL-CHISACHON-MTZBR', 'TOTAL-ERKEI-PIDION']);
      if (yitrotTotal > 0) {
        console.log(`Found balance in BlockItrot/PerutYitrot: ${yitrotTotal}`);
        return yitrotTotal;
      }

      // 2. Sum balances from investment track details if BlockItrot missing
      const maslulTotal = sumFields('.//PerutMasluleiHashkaa', ['SCHUM-TZVIRA-BAMASLUL', 'TOTAL-CHISACHON-MTZBR']);
      if (maslulTotal > 0) {
        console.log(`Found balance in PerutMasluleiHashkaa: ${maslulTotal}`);
        return maslulTotal;
      }

      // 3. Look for end-of-year balance summaries
      const endYearTotal = sumFields('.//PerutYitrotLesofShanaKodemet', ['YITRAT-SOF-SHANA', 'TOTAL-CHISACHON-MTZBR']);
      if (endYearTotal > 0) {
        console.log(`Found balance in PerutYitrotLesofShanaKodemet: ${endYearTotal}`);
        return endYearTotal;
      }

      // 4. Generic search for common balance fields anywhere under the account
      const genericFields = [
        'SCHUM-TZVIRA-BAMASLUL',
        'YITRAT-KASPEY-TAGMULIM',
        'TOTAL-CHISACHON-MTZBR',
        'TOTAL-ERKEI-PIDION',
        'SCHUM-HON-EFSHAR',
        'SCHUM-CHISACHON',
        'SCHUM-TAGMULIM',
        'SCHUM-PITURIM',
        'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
        'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI'
      ];
      
      for (const field of genericFields) {
        const value = getElementFloat(field);
        if (value > 0) {
          console.log(`Found balance in generic field ${field}: ${value}`);
          return value;
        }
      }

      // 5. Fall back to scanning numeric values as a last resort
      const potentialBalances: Array<{weight: number, value: number, tag: string}> = [];
      const allElements = accountElem.getElementsByTagName('*');
      
      for (let i = 0; i < allElements.length; i++) {
        const elem = allElements[i];
        if (elem.textContent && /\d/.test(elem.textContent)) {
          try {
            const value = parseFloat(elem.textContent.replace(/,/g, ''));
            if (value > 0) {
              const tag = elem.tagName.toUpperCase();
              let weight = 1.0;
              if (tag.includes('SCHUM') || tag.includes('YITRAT') || tag.includes('ERECH')) {
                weight = 2.0;
              }
              potentialBalances.push({weight, value, tag});
            }
          } catch (e) {
            // ignore parsing errors
          }
        }
      }

      if (potentialBalances.length > 0) {
        potentialBalances.sort((a, b) => b.weight - a.weight || b.value - a.value);
        console.log(`Found balance as fallback from ${potentialBalances[0].tag}: ${potentialBalances[0].value}`);
        return potentialBalances[0].value;
      }

      return 0;
    };

    // פונקציה עזר לסיכום שדות
    const sumFields = (xpath: string, fieldCandidates: string[]): number => {
      let total = 0;
      
      // מחפש אלמנטים לפי xpath (מתאים ל-XPath פשוט)
      const pathParts = xpath.replace(/^\.\/\//, '').split('//');
      let elements: Element[] = [accountElem];
      
      for (const part of pathParts) {
        const newElements: Element[] = [];
        for (const elem of elements) {
          const found = elem.getElementsByTagName(part);
          for (let i = 0; i < found.length; i++) {
            newElements.push(found[i]);
          }
        }
        elements = newElements;
      }
      
      for (const node of elements) {
        for (const field of fieldCandidates) {
          const fieldElements = node.getElementsByTagName(field);
          if (fieldElements.length > 0) {
            const text = fieldElements[0].textContent?.trim();
            if (text) {
              const value = parseFloat(text.replace(/,/g, ''));
              if (!isNaN(value) && value > 0) {
                total += value;
                break; // מצא שדה, עובר לצומת הבא
              }
            }
          }
        }
      }
      
      return total;
    };
    
    balance = findBalance();

    // תאריך נכונות יתרה
    const balanceDate = getElementText('TAARICH-NECHONUT-YITROT') ||
                       getElementText('TAARICH-YITROT') ||
                       getElementText('TAARICH-NECHONUT') ||
                       'לא ידוע';

    // תאריך התחלה
    const startDate = getElementText('TAARICH-TCHILAT-HAFRASHA') ||
                     getElementText('TAARICH-TCHILA') ||
                     getElementText('TAARICH-HITZTARFUT-RISHON') ||
                     getElementText('TAARICH-HITZTARFUT') ||
                     'לא ידוע';

    // סוג מוצר - שימוש בתגיות הגלובליות שהועברו
    let productType = 'לא ידוע';
    
    console.log(`🔍 Product type detection: SHEM-MUTZAR="${globalShemMutzar}", SUG-MUTZAR="${globalSugMutzar}"`);
    
    // זיהוי לפי SHEM-MUTZAR (עדיפות ראשונה)
    if (globalShemMutzar) {
      const mutzarLower = globalShemMutzar.toLowerCase();
      // סדר הבדיקה חשוב! השתלמות לפני פנסיה
      if (mutzarLower.includes('השתלמות')) {
        productType = 'קרן השתלמות';
      } else if (mutzarLower.includes('קרן פנסיה')) {
        productType = 'קרן פנסיה';
      } else if (mutzarLower.includes('קופת גמל')) {
        productType = 'קופת גמל';
      } else if (mutzarLower.includes('ביטוח חיים משולב') || mutzarLower.includes('משולב חיסכון')) {
        productType = 'פוליסת ביטוח חיים משולב חיסכון';
      } else if (mutzarLower.includes('ביטוח חיים')) {
        productType = 'פוליסת ביטוח חיים';
      } else if (mutzarLower.includes('חיסכון טהור') || mutzarLower.includes('חסכון טהור')) {
        productType = 'פוליסת חיסכון טהור';
      } else {
        productType = globalShemMutzar; // השתמש בשם המדויק מהתגית
      }
    }
    // זיהוי לפי SUG-MUTZAR (עדיפות שנייה)
    else if (globalSugMutzar) {
      const PRODUCT_TYPE_MAP: {[key: string]: string} = {
        '1': 'פוליסת ביטוח חיים משולב חיסכון',
        '2': 'קרן פנסיה',  // תוקן: 2 = קרן פנסיה (לפי קבצי PNN)
        '3': 'קופת גמל',
        '4': 'קרן השתלמות',
        '5': 'פוליסת חיסכון טהור',
        '6': 'קרן השתלמות',
        '7': 'פוליסת ביטוח חיים',
        '8': 'ביטוח מנהלים',
        '9': 'קופת גמל להשקעה'
      };
      productType = PRODUCT_TYPE_MAP[globalSugMutzar] || globalSugMutzar;
    }
    
    console.log(`✅ Final product type: ${productType}`);

    // מעסיקים היסטוריים - חיפוש מורחב
    const employerTags = ['SHEM-MAASIK', 'SHEM-MESHALEM', 'SHEM-BAAL-POLISA', 'SHEM-MAFKID'];
    const employers: string[] = [];
    
    for (const tag of employerTags) {
      const employerElements = accountElem.getElementsByTagName(tag);
      for (let i = 0; i < employerElements.length; i++) {
        const employer = employerElements[i].textContent?.trim();
        if (employer && !employers.includes(employer)) {
          employers.push(employer);
        }
      }
    }

    // פיצויים ותגמולים - לפי המערכת הקיימת מ-process_pensions.py
    const collectBalanceRelatedFields = (): {[key: string]: string} => {
      const collected: {[key: string]: string[]} = {};
      const balanceExplicitTags = [
        'TOTAL-CHISACHON-MTZBR',
        'TOTAL-ERKEI-PIDION',
        'YITRAT-KASPEY-TAGMULIM',
        'YITRAT-PITZUIM',
        'YITRAT-PITZUIM-MAASIK-NOCHECHI',
        'YITRAT-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
        'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI',
        'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
        'TOTAL-HAFKADOT-OVED-TAGMULIM-SHANA-NOCHECHIT',
        'TOTAL-HAFKADOT-MAAVID-TAGMULIM-SHANA-NOCHECHIT',
        'TOTAL-HAFKADOT-PITZUIM-SHANA-NOCHECHIT',
        'SCHUM-HAFKADA-SHESHULAM',
        'SCHUM-TAGMULIM',
        'SCHUM-PITURIM',
        'YITRAT-PITZUIM-LELO-HITCHASHBENOT',
        'KAYAM-RETZEF-PITZUIM-KITZBA',
        'KAYAM-RETZEF-ZECHUYOT-PITZUIM',
        'YITRAT-PITZUIM',
        'YITRAT-PITZUIM-MAASIK-NOCHECHI',
        'ERECH-PIDION-MARKIV-PITZUIM-LEMAS-NOCHECHI',
        'TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM',
        'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT',
        'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-KITZBA'
      ];
      
      const balanceKeywords = ['TAGMUL', 'PITZ', 'PITZU', 'PITZUI'];
      const explicitSet = new Set(balanceExplicitTags.map(tag => tag.toUpperCase()));
      
      const allElements = accountElem.getElementsByTagName('*');
      for (let i = 0; i < allElements.length; i++) {
        const node = allElements[i];
        if (!node.textContent || !node.textContent.trim()) continue;
        
        const tagUpper = node.tagName.toUpperCase();
        const isExplicit = explicitSet.has(tagUpper);
        const hasKeyword = balanceKeywords.some(keyword => tagUpper.includes(keyword));

        if (!(isExplicit || hasKeyword)) continue;

        const value = node.textContent.trim();
        if (!collected[tagUpper]) collected[tagUpper] = [];
        collected[tagUpper].push(value);
      }
      
      const result: {[key: string]: string} = {};
      for (const [tag, values] of Object.entries(collected)) {
        const seen = new Set<string>();
        const uniqueValues: string[] = [];
        for (const value of values) {
          if (!seen.has(value)) {
            seen.add(value);
            uniqueValues.push(value);
          }
        }
        result[tag] = uniqueValues.join(' | ');
      }
      
      return result;
    };

    const collectTagmulPeriods = (): {[key: string]: number} => {
      const tagmulPeriodColumns = {
        'employee_before_2000': 'תגמולי עובד עד 2000',
        'employee_after_2000': 'תגמולי עובד אחרי 2000',
        'employee_after_2008_non_paying': 'תגמולי עובד אחרי 2008 (קצבה לא משלמת)',
        'employer_before_2000': 'תגמולי מעביד עד 2000',
        'employer_after_2000': 'תגמולי מעביד אחרי 2000',
        'employer_after_2008_non_paying': 'תגמולי מעביד אחרי 2008 (קצבה לא משלמת)'
      };
      
      const techulatCodePeriod: {[key: string]: string} = {
        '1': 'before_2000',
        '2': 'after_2000',
        '7': 'after_2008_non_paying'
      };
      
      const totalsByKey: {[key: string]: number} = {};
      Object.keys(tagmulPeriodColumns).forEach(key => totalsByKey[key] = 0);
      
      // חיפוש ב-BlockItrot//PerutYitraLeTkufa
      const blockItrotElements = accountElem.getElementsByTagName('BlockItrot');
      for (let i = 0; i < blockItrotElements.length; i++) {
        const blockItrot = blockItrotElements[i];
        const perutElements = blockItrot.getElementsByTagName('PerutYitraLeTkufa');
        
        for (let j = 0; j < perutElements.length; j++) {
          const period = perutElements[j];
          
          const rekivElements = period.getElementsByTagName('REKIV-ITRA-LETKUFA');
          const techulatElements = period.getElementsByTagName('KOD-TECHULAT-SHICHVA');
          const amountElements = period.getElementsByTagName('SACH-ITRA-LESHICHVA-BESHACH');
          
          if (rekivElements.length === 0 || techulatElements.length === 0 || amountElements.length === 0) continue;
          
          const rekiv = rekivElements[0].textContent?.trim();
          const techulat = techulatElements[0].textContent?.trim();
          const amountText = amountElements[0].textContent?.trim();
          
          if (!rekiv || !techulat || !amountText) continue;
          
          const amount = parseFloat(amountText.replace(/,/g, ''));
          if (isNaN(amount)) continue;
          
          let role = '';
          if (rekiv === '2') role = 'employee';
          else if (rekiv === '3') role = 'employer';
          else continue;
          
          const periodKey = techulatCodePeriod[techulat];
          if (!periodKey) continue;
          
          const key = `${role}_${periodKey}`;
          if (totalsByKey.hasOwnProperty(key)) {
            totalsByKey[key] += amount;
          }
        }
      }
      
      const result: {[key: string]: number} = {};
      for (const [key, total] of Object.entries(totalsByKey)) {
        if (total > 0) {
          const columnName = tagmulPeriodColumns[key as keyof typeof tagmulPeriodColumns];
          result[columnName] = total;
        }
      }
      
      return result;
    };

    // חילוץ הנתונים
    const balanceRelatedFields = collectBalanceRelatedFields();
    const tagmulPeriods = collectTagmulPeriods();

    const getFirstBalanceValue = (tags: string[]): number => {
      for (const tag of tags) {
        const raw = balanceRelatedFields[tag];
        if (!raw) continue;
        const parts = raw.split(' | ');
        for (const part of parts) {
          const valueText = part?.trim();
          if (!valueText) continue;
          const numeric = parseFloat(valueText.replace(/,/g, ''));
          if (!isNaN(numeric) && numeric !== 0) {
            return numeric;
          }
        }
      }
      return 0;
    };

    // פיצויים - לפי השדות הנכונים מהמערכת הקיימת
    const פיצויים_מעסיק_נוכחי = getFirstBalanceValue([
      'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI',
      'YITRAT-PITZUIM-MAASIK-NOCHECHI',
      'YITRAT-PITZUIM-LELO-HITCHASHBENOT'
    ]);

    if (accountNumber === '2209575014') {
      console.log('🔍 DEBUG Plan 2209575014:');
      console.log('  balance keys:', Object.keys(balanceRelatedFields));
      console.log('  balance entries:', JSON.stringify(balanceRelatedFields, null, 2));
      console.log('  פיצויים_מעסיק_נוכחי:', פיצויים_מעסיק_נוכחי);
    }

    if (accountNumber === '494930') {
      console.log('🔍 DEBUG Plan 494930:');
      console.log('  balance keys:', Object.keys(balanceRelatedFields));
      console.log('  balance entries:', JSON.stringify(balanceRelatedFields, null, 2));
      console.log('  פיצויים_מעסיק_נוכחי:', פיצויים_מעסיק_נוכחי);
    }
    const פיצויים_לאחר_התחשבנות = getFirstBalanceValue([
      'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
      'YITRAT-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM'
    ]);
    const פיצויים_שלא_עברו_התחשבנות = getFirstBalanceValue([
      'TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM'
    ]);
    const פיצויים_ממעסיקים_קודמים_רצף_זכויות = getFirstBalanceValue([
      'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT'
    ]);
    const פיצויים_ממעסיקים_קודמים_רצף_קצבה = getFirstBalanceValue([
      'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-KITZBA'
    ]);

    const סך_פיצויים = פיצויים_מעסיק_נוכחי + פיצויים_לאחר_התחשבנות + פיצויים_שלא_עברו_התחשבנות +
                     פיצויים_ממעסיקים_קודמים_רצף_זכויות + פיצויים_ממעסיקים_קודמים_רצף_קצבה;

    // תגמולים - לפי התקופות מהמערכת הקיימת
    const תגמולי_עובד_עד_2000 = tagmulPeriods['תגמולי עובד עד 2000'] || 0;
    const תגמולי_עובד_אחרי_2000 = tagmulPeriods['תגמולי עובד אחרי 2000'] || 0;
    const תגמולי_עובד_אחרי_2008_לא_משלמת = tagmulPeriods['תגמולי עובד אחרי 2008 (קצבה לא משלמת)'] || 0;
    const תגמולי_מעביד_עד_2000 = tagmulPeriods['תגמולי מעביד עד 2000'] || 0;
    const תגמולי_מעביד_אחרי_2000 = tagmulPeriods['תגמולי מעביד אחרי 2000'] || 0;
    const תגמולי_מעביד_אחרי_2008_לא_משלמת = tagmulPeriods['תגמולי מעביד אחרי 2008 (קצבה לא משלמת)'] || 0;

    // תגמולים - ייבוא ישיר מהתגית YITRAT-KASPEY-TAGMULIM, ואז ניכוי רכיבי פיצויים ותגמולים לא משלמים
    const תגמולים_מקור = parseFloat(balanceRelatedFields['YITRAT-KASPEY-TAGMULIM']?.split(' | ')[0] || '0') || 0;
    const תגמולים = Math.max(0, תגמולים_מקור - סך_פיצויים - תגמולי_עובד_אחרי_2008_לא_משלמת - תגמולי_מעביד_אחרי_2008_לא_משלמת);

    // רק אם יש מידע משמעותי, נחזיר את החשבון
    if (accountNumber === 'לא ידוע' && planName === 'לא ידוע' && balance === 0) {
      return null;
    }

    const baseAccount = {
      מספר_חשבון: accountNumber,
      שם_תכנית: planName,
      debug_plan_name: planName, // לצורך debug
      חברה_מנהלת: managingCompany,
      קוד_חברה_מנהלת: companyCode,
      יתרה: balance,
      תאריך_נכונות_יתרה: balanceDate,
      תאריך_התחלה: startDate,
      סוג_מוצר: productType,
      מעסיקים_היסטוריים: employers.join(', '),
      תגמולים,
      פיצויים_מעסיק_נוכחי,
      פיצויים_לאחר_התחשבנות,
      פיצויים_שלא_עברו_התחשבנות,
      פיצויים_ממעסיקים_קודמים_רצף_זכויות,
      פיצויים_ממעסיקים_קודמים_רצף_קצבה,
      תגמולי_עובד_עד_2000,
      תגמולי_עובד_אחרי_2000,
      תגמולי_עובד_אחרי_2008_לא_משלמת,
      תגמולי_מעביד_עד_2000,
      תגמולי_מעביד_אחרי_2000,
      תגמולי_מעביד_אחרי_2008_לא_משלמת,
      selected: false,
      selected_amounts: {}
    };

    if (accountNumber === '494930') {
      console.log('📦 Account 494930 object:', JSON.stringify(baseAccount, null, 2));
    }

    // חישוב תגמולים (פעם אחת בלבד)
    const result = calculateInitialTagmulim(baseAccount);
    
    // Debug: הדפסת התוצאה
    console.log('Extracted account data:', result);
    
    return result;
  };

  // פונקציה לסימון/ביטול סימון חשבון
  const toggleAccountSelection = (index: number) => {
    setPensionData(prev => prev.map((account, i) => {
      if (i === index) {
        const newSelected = !account.selected;
        return { 
          ...account, 
          selected: newSelected,
          // מבטל סוג המרה כשמבטל בחירה
          conversion_type: newSelected ? account.conversion_type : undefined
        };
      }
      return account;
    }));
  };

  // פונקציה לסימון/ביטול סימון כל החשבונות
  const toggleAllAccountsSelection = () => {
    const allSelected = pensionData.every(account => account.selected);
    const newSelected = !allSelected;
    setPensionData(prev => prev.map(account => ({
      ...account,
      selected: newSelected,
      // מבטל סוג המרה כשמבטל בחירה
      conversion_type: newSelected ? account.conversion_type : undefined
    })));
  };

  // פונקציה לעדכון סכום נבחר
  const updateSelectedAmount = (accountIndex: number, field: string, selected: boolean) => {
    setPensionData(prev => prev.map((account, i) => 
      i === accountIndex ? {
        ...account,
        selected_amounts: {
          ...account.selected_amounts,
          [field]: selected
        }
      } : account
    ));
  };

  // פונקציה לשמירת כל התכניות הנבחרות (רק שמירה, ללא המרה)
  const saveSelectedAccounts = async () => {
    if (!clientId) return;
    
    const selectedAccounts = pensionData.filter(account => account.selected);
    if (selectedAccounts.length === 0) {
      setError("אנא בחר לפחות תכנית אחת לשמירה");
      return;
    }

    setSaving(true);
    setError("");

    try {
      // שמירה ב-localStorage בלבד - ללא המרה
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(pensionData));
      
      setProcessingStatus(`✅ נשמרו בהצלחה ${selectedAccounts.length} תכניות בתיק הפנסיוני!`);
      
      // סימון התכניות שנשמרו כלא נבחרות
      setPensionData(prev => prev.map(account => ({
        ...account,
        selected: false
      })));
      
    } catch (e: any) {
      setError(`שגיאה בשמירת תכניות: ${e?.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  // פונקציה למחיקת תכנית
  const deleteAccount = async (accountIndex: number) => {
    const account = pensionData[accountIndex];
    const isConfirmed = confirm(`האם אתה בטוח שברצונך למחוק את התכנית "${account.שם_תכנית}"?`);
    
    if (!isConfirmed) return;

    try {
      // אם התכנית נשמרה במסד הנתונים, נמחק אותה גם משם
      if (account.saved_fund_id && clientId) {
        await apiFetch(`/clients/${clientId}/pension-funds/${account.saved_fund_id}`, {
          method: 'DELETE'
        });
        
        setProcessingStatus("תכנית נמחקה מהמערכת ומהרשימה");
      } else {
        setProcessingStatus("תכנית נמחקה מהרשימה");
      }

      // מחיקה מהרשימה המוצגת
      const updatedData = pensionData.filter((_, i) => i !== accountIndex);
      setPensionData(updatedData);
      
      // שמירה ל-localStorage כדי שהמחיקה תישמר
      if (clientId) {
        localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(updatedData));
      }
      
    } catch (error: any) {
      setError(`שגיאה במחיקת התכנית: ${error.message}`);
    }
  };

  // פונקציה לעדכון ערך בתא
  const updateCellValue = (accountIndex: number, field: string, value: any) => {
    setPensionData(prev => {
      const updated = prev.map((acc, i) => {
        if (i === accountIndex) {
          let updatedAcc;
          // המרת ערכים מספריים
          if (['יתרה', 'תגמולים', 'פיצויים_מעסיק_נוכחי', 'פיצויים_לאחר_התחשבנות', 'פיצויים_שלא_עברו_התחשבנות',
               'פיצויים_ממעסיקים_קודמים_רצף_זכויות', 'פיצויים_ממעסיקים_קודמים_רצף_קצבה',
               'תגמולי_עובד_עד_2000', 'תגמולי_עובד_אחרי_2000', 'תגמולי_עובד_אחרי_2008_לא_משלמת',
               'תגמולי_מעביד_עד_2000', 'תגמולי_מעביד_אחרי_2000', 'תגמולי_מעביד_אחרי_2008_לא_משלמת'].includes(field)) {
            updatedAcc = { ...acc, [field]: parseFloat(value) || 0 };
          } else {
            updatedAcc = { ...acc, [field]: value };
          }
          // לא מחשבים תגמולים מחדש - הם ערך קבוע
          return updatedAcc;
        }
        return acc;
      });
      // שמירה ל-localStorage
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(updated));
      return updated;
    });
    setEditingCell(null);
  };

  // קומפוננטת עזר לתא מספרי עם checkbox
  const EditableNumberCell = ({ account, index, field, label }: { account: PensionAccount, index: number, field: string, label?: string }) => {
    const value = (account as any)[field] || 0;
    return (
      <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <input
            type="checkbox"
            checked={(account.selected_amounts as any)?.[field] || false}
            onChange={(e) => toggleAmountSelection(index, field, e.target.checked)}
            style={{ transform: "scale(0.8)" }}
          />
          <div style={{ flex: 1 }} onClick={(e) => { e.stopPropagation(); setEditingCell({row: index, field}); }}>
            {editingCell?.row === index && editingCell?.field === field ? (
              <input
                type="number"
                defaultValue={value}
                onBlur={(e) => updateCellValue(index, field, e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, field, e.currentTarget.value)}
                autoFocus
                style={{ width: '100%', padding: 2, fontSize: '12px', textAlign: 'right' }}
              />
            ) : (value > 0 ? value.toLocaleString() : '-')}
          </div>
        </div>
      </td>
    );
  };

  // פונקציה להוספת תכנית ידנית
  const addManualAccount = () => {
    const name = prompt('שם התכנית:');
    if (!name) return;
    
    const balance = prompt('יתרה:', '0');
    if (balance === null) return;
    
    const startDate = prompt('תאריך התחלה (DD/MM/YY):', formatDateToDDMMYY(new Date()));
    if (startDate === null) return;
    
    const productType = prompt('סוג מוצר (קרן השתלמות / קופת גמל):', 'קופת גמל');
    if (productType === null) return;
    
    // יצירת חשבון חדש
    const baseAccount = {
      מספר_חשבון: `MANUAL-${Date.now()}`,
      שם_תכנית: name,
      חברה_מנהלת: 'הוסף ידני',
      קוד_חברה_מנהלת: '',
      יתרה: parseFloat(balance) || 0,
      תאריך_נכונות_יתרה: formatDateToDDMMYY(new Date()),
      תאריך_התחלה: startDate,
      סוג_מוצר: productType,
      מעסיקים_היסטוריים: '',
      פיצויים_מעסיק_נוכחי: 0,
      פיצויים_לאחר_התחשבנות: 0,
      פיצויים_שלא_עברו_התחשבנות: 0,
      פיצויים_ממעסיקים_קודמים_רצף_זכויות: 0,
      פיצויים_ממעסיקים_קודמים_רצף_קצבה: 0,
      תגמולי_עובד_עד_2000: 0,
      תגמולי_עובד_אחרי_2000: 0,
      תגמולי_עובד_אחרי_2008_לא_משלמת: 0,
      תגמולי_מעביד_עד_2000: 0,
      תגמולי_מעביד_אחרי_2000: 0,
      תגמולי_מעביד_אחרי_2008_לא_משלמת: 0,
      selected: false,
      selected_amounts: {}
    };
    
    // חישוב תגמולים (פעם אחת בלבד)
    const newAccount = calculateInitialTagmulim(baseAccount);
    
    setPensionData(prev => [...prev, newAccount]);
    setProcessingStatus(`תכנית "${name}" נוספה בהצלחה`);
  };

  // פונקציה לסימון/ביטול סימון סכום ספציפי
  const toggleAmountSelection = (index: number, amountKey: string, checked: boolean) => {
    setPensionData(prev => prev.map((account, i) => 
      i === index ? { 
        ...account, 
        selected_amounts: { 
          ...account.selected_amounts, 
          [amountKey]: checked 
        } 
      } : account
    ));
  };

  // פונקציה להגדרת סוג המרה - שמירה נפרדת
  const setConversionType = (index: number, type: 'pension' | 'capital_asset') => {
    setConversionTypes(prev => ({
      ...prev,
      [index]: type
    }));
  };

  // פונקציה לניקוי conversion_type מתכניות שלא נבחרות
  const cleanupConversionTypes = () => {
    setPensionData(prev => prev.map(account => ({
      ...account,
      conversion_type: (account.selected || Object.values(account.selected_amounts || {}).some(Boolean)) 
        ? account.conversion_type 
        : undefined
    })));
  };

  // פונקציה לחישוב תאריך פרישה - מחזיר פורמט ISO (YYYY-MM-DD)
  const calculateRetirementDate = async () => {
    if (!clientData?.birth_date) return null;
    
    try {
      // שימוש ב-API דינמי לחישוב גיל פרישה
      const response = await axios.post('/api/v1/retirement-age/calculate-simple', {
        birth_date: clientData.birth_date,
        gender: clientData.gender
      });
      
      if (response.data && response.data.retirement_date) {
        return response.data.retirement_date;
      }
      
      // fallback למקרה של שגיאה
      const birthDate = new Date(clientData.birth_date);
      const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 65 : 67;
      const retirementDate = new Date(birthDate);
      retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
      return retirementDate.toISOString().split('T')[0];
    } catch (error) {
      console.error('Error calculating retirement date:', error);
      // fallback
      const birthDate = new Date(clientData.birth_date);
      const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 65 : 67;
      const retirementDate = new Date(birthDate);
      retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
      return retirementDate.toISOString().split('T')[0];
    }
  };

  // פונקציה להמרת חשבונות נבחרים לקצבאות ונכסי הון
  const convertSelectedAccounts = async () => {
    if (!clientId) return;

    // חיפוש תכניות שנבחרו עם conversion_type='pension'
    const pensionConversions: Array<{account: any, index: number, amountToConvert: number, specificAmounts: any}> = [];
    const capitalAssetConversions: Array<{account: any, index: number, amountToConvert: number, specificAmounts: any}> = [];
    const validationErrors: string[] = [];
    
    pensionData.forEach((account, index) => {
      const isPensionConversion = conversionTypes[index] === 'pension';
      const isCapitalAssetConversion = conversionTypes[index] === 'capital_asset';
      
      if (!isPensionConversion && !isCapitalAssetConversion) return;
      
      // חישוב הסכום להמרה
      let amountToConvert = 0;
      let specificAmounts: any = {}; // סכומים מקוריים לשמירה
      let selectedForValidation: any = {}; // boolean לולידציה
      
      if (account.selected) {
        // אם כל התכנית נבחרה - המר את כל היתרה
        amountToConvert = account.יתרה || 0;
        // צור selected_amounts עבור כל השדות הקיימים
        specificAmounts = {};
        selectedForValidation = {};
        Object.keys(account).forEach(key => {
          // רק שדות מספריים שאינם metadata
          if (typeof (account as any)[key] === 'number' && key !== 'יתרה') {
            const fieldAmount = (account as any)[key];
            if (fieldAmount && fieldAmount > 0) {
              specificAmounts[key] = fieldAmount; // שמור את הסכום המקורי
              selectedForValidation[key] = true; // לולידציה
            }
          }
        });
        // אם אין שדות ספציפיים, סמן את היתרה הכללית
        if (Object.keys(selectedForValidation).length === 0) {
          selectedForValidation['יתרה'] = true;
        }
      } else {
        // אם רק סכומים ספציפיים נבחרו - חשב את הסכום הכולל
        const selectedAmounts = account.selected_amounts || {};
        Object.entries(selectedAmounts).forEach(([key, isSelected]) => {
          if (isSelected && (account as any)[key]) {
            const fieldAmount = parseFloat((account as any)[key]) || 0;
            amountToConvert += fieldAmount;
            specificAmounts[key] = fieldAmount; // שמור את הסכום המקורי
            selectedForValidation[key] = true; // לולידציה
          }
        });
      }
      
      if (amountToConvert > 0) {
        // ולידציה לפי חוקי ההמרה
        const conversionType = isPensionConversion ? 'pension' : 'capital_asset';
        const validation = validateAccountConversion(account, selectedForValidation, conversionType);
        
        if (!validation.valid) {
          validationErrors.push(`${account.שם_תכנית}: ${validation.errors.join(', ')}`);
        } else {
          // המרה תקינה - הוסף לרשימה
          if (isPensionConversion) {
            pensionConversions.push({account, index, amountToConvert, specificAmounts});
          } else if (isCapitalAssetConversion) {
            capitalAssetConversions.push({account, index, amountToConvert, specificAmounts});
          }
        }
      }
    });

    // בדיקה שיש שגיאות ולידציה
    if (validationErrors.length > 0) {
      setError("שגיאות ולידציה:\n" + validationErrors.join('\n'));
      return;
    }

    // בדיקה שיש לפחות המרה אחת
    if (pensionConversions.length === 0 && capitalAssetConversions.length === 0) {
      setError("אנא בחר לפחות תכנית אחת להמרה ובחר סוג המרה");
      return;
    }

    setLoading(true);
    setError("");

    try {
      // טיפול בהמרות לקצבה - יצירת קצבה נפרדת לכל תכנית
      if (pensionConversions.length > 0) {
        const retirementDate = await calculateRetirementDate();
        
        for (const conversion of pensionConversions) {
          const {account, amountToConvert, specificAmounts} = conversion;
          
          // יצירת תיאור מפורט של מה הומר
          let conversionDetails = '';
          if (Object.keys(specificAmounts).length > 0) {
            conversionDetails = Object.entries(specificAmounts)
              .map(([key, value]) => `${key}: ₪${parseFloat(value as string).toLocaleString()}`)
              .join(', ');
          } else {
            conversionDetails = `כל היתרה: ₪${amountToConvert.toLocaleString()}`;
          }
          
          // חישוב יחס מס לפי חוקי ההמרה
          const taxTreatment = calculateTaxTreatment(account, specificAmounts, 'pension');
          
          // יצירת מידע מקור להחזרה במקרה של מחיקה
          const conversionSourceData = {
            type: 'pension_portfolio',
            account_name: account.שם_תכנית,
            company: account.חברה_מנהלת,
            account_number: account.מספר_חשבון,
            product_type: account.סוג_מוצר,
            amount: amountToConvert,
            specific_amounts: specificAmounts,
            conversion_date: new Date().toISOString(),
            tax_treatment: taxTreatment
          };
          
          const pensionData: any = {
            client_id: parseInt(clientId),
            fund_name: account.שם_תכנית || 'קצבה מתיק פנסיוני',
            fund_type: 'מחושב',
            input_mode: "manual" as const,
            balance: amountToConvert,
            pension_amount: Math.round(amountToConvert / 200), // מקדם קצבה 200
            pension_start_date: retirementDate,
            indexation_method: "none" as const, // ללא הצמדה
            tax_treatment: taxTreatment, // יחס מס מחושב לפי חוקי המערכת
            remarks: `הומר מתיק פנסיוני\nתכנית: ${account.שם_תכנית} (${account.חברה_מנהלת})\nסכומים שהומרו: ${conversionDetails}\nיחס מס: ${taxTreatment === 'exempt' ? 'פטור ממס' : 'חייב במס'}`,
            conversion_source: JSON.stringify(conversionSourceData)
          };
          
          console.log('DEBUG: retirementDate =', retirementDate);
          console.log('DEBUG: pensionData before send =', JSON.stringify(pensionData, null, 2));
          
          // הוספת שדות אופציונליים רק אם יש להם ערך
          if (pensionData.fixed_index_rate !== undefined) {
            pensionData.fixed_index_rate = null;
          }
          if (pensionData.deduction_file !== undefined) {
            pensionData.deduction_file = null;
          }

          try {
            await apiFetch(`/clients/${clientId}/pension-funds`, {
              method: 'POST',
              body: JSON.stringify(pensionData)
            });
            console.log('SUCCESS: Pension fund created');
          } catch (error) {
            console.error('ERROR creating pension fund:', error);
            throw error;
          }
        }
        
        console.log('Created', pensionConversions.length, 'separate pension funds');
      }

      // טיפול בהמרות לנכס הון
      if (capitalAssetConversions.length > 0) {
        for (const conversion of capitalAssetConversions) {
          const {account, amountToConvert, specificAmounts} = conversion;
          
          // יצירת תיאור מפורט של מה הומר
          let conversionDetails = '';
          if (Object.keys(specificAmounts).length > 0) {
            conversionDetails = Object.entries(specificAmounts)
              .map(([key, value]) => `${key}: ₪${parseFloat(value as string).toLocaleString()}`)
              .join(', ');
          } else {
            conversionDetails = `כל היתרה: ₪${amountToConvert.toLocaleString()}`;
          }
          
          // קביעת סוג הנכס לפי סוג המוצר - לפי בקשת המשתמש
          let assetTypeValue = '';
          let assetDescription = '';
          if (account.סוג_מוצר && account.סוג_מוצר.includes('קרן השתלמות')) {
            assetTypeValue = 'education_fund'; // קרן השתלמות
            assetDescription = 'קרן השתלמות';
          } else {
            assetTypeValue = 'provident_fund'; // קופת גמל
            assetDescription = 'קופת גמל';
          }
          
          // חישוב יחס מס לפי חוקי ההמרה
          const taxTreatment = calculateTaxTreatment(account, specificAmounts, 'capital_asset');
          
          // יצירת מידע מקור להחזרה במקרה של מחיקה
          const conversionSourceData = {
            type: 'pension_portfolio',
            account_name: account.שם_תכנית,
            company: account.חברה_מנהלת,
            account_number: account.מספר_חשבון,
            product_type: account.סוג_מוצר,
            amount: amountToConvert,
            specific_amounts: specificAmounts,
            conversion_date: new Date().toISOString(),
            tax_treatment: taxTreatment
          };
          
          // המרת תאריכים לפורמט ISO
          const todayISO = new Date().toISOString().split('T')[0];
          const purchaseDateISO = account.תאריך_התחלה 
            ? (account.תאריך_התחלה.includes('-') ? account.תאריך_התחלה : todayISO)
            : todayISO;
          
          const assetData = {
            client_id: parseInt(clientId),
            asset_type: assetTypeValue, // ערך באנגלית לשרת: 'mutual_funds' או 'deposits'
            description: `${assetDescription} - ${account.שם_תכנית} (${conversionDetails})` || 'נכס הון מתיק פנסיוני',
            current_value: amountToConvert,
            purchase_value: amountToConvert,
            purchase_date: purchaseDateISO,
            annual_return: 0,
            annual_return_rate: 0.03,
            payment_frequency: 'monthly',
            liquidity: 'medium',
            risk_level: 'medium',
            monthly_income: 0, // אין תשלום חודשי
            start_date: todayISO,
            indexation_method: 'none', // ללא הצמדה
            tax_treatment: taxTreatment, // מס רווח הון - מחושב לפי חוקי המערכת
            conversion_source: JSON.stringify(conversionSourceData)
          };

          await apiFetch(`/clients/${clientId}/capital-assets`, {
            method: 'POST',
            body: JSON.stringify(assetData)
          });
        }
        
        console.log('Created capital assets for', capitalAssetConversions.length, 'accounts');
      }

      
      // עדכון הנתונים בטבלה - הפחתת הסכומים שהומרו
      const updatedPensionData = pensionData.map((account, index) => {
        const conversion = [...pensionConversions, ...capitalAssetConversions].find(c => c.index === index);
        
        if (!conversion) return account; // לא הומר כלום
        
        const {amountToConvert, specificAmounts} = conversion;
        
        // יצירת עותק מעודכן של החשבון
        let updatedAccount = {...account};
        
        // מחיקת הסכומים הספציפיים שהומרו (מאפס את השדות)
        Object.keys(specificAmounts).forEach(key => {
          if ((updatedAccount as any)[key]) {
            (updatedAccount as any)[key] = 0; // מאפס את השדה שהומר
          }
        });
        
        // לא מחשבים תגמולים מחדש - הם נשארים כערך קבוע
        // רק היתרה הכללית מחושבת דינמית בתצוגה
        
        // איפוס הסימונים
        updatedAccount.selected = false;
        updatedAccount.selected_amounts = {};
        
        return updatedAccount;
      }); // לא מסננים - שומרים את כל החשבונות גם עם יתרה 0
      
      // עדכון ה-state
      setPensionData(updatedPensionData);
      
      // עדכון רשימת התכניות שהומרו
      const allConvertedAccounts = [...pensionConversions, ...capitalAssetConversions];
      const convertedIds = allConvertedAccounts.map(conversion => 
        `${conversion.account.מספר_חשבון}_${conversion.account.שם_תכנית}_${conversion.account.חברה_מנהלת}`
      );
      
      const updatedConvertedAccounts = new Set(convertedAccounts);
      convertedIds.forEach((id: string) => updatedConvertedAccounts.add(id));
      setConvertedAccounts(updatedConvertedAccounts);
      
      // ניקוי סוגי ההמרה של התכניות שהומרו
      setConversionTypes({});
      
      // שמירה ל-localStorage עם הנתונים המעודכנים
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(updatedPensionData));
      localStorage.setItem(`convertedAccounts_${clientId}`, JSON.stringify(Array.from(updatedConvertedAccounts)));
      
      // הודעות הצלחה
      let successMessage = "הומרה בהצלחה!\n";
      if (pensionConversions.length > 0) {
        const totalBalance = pensionConversions.reduce((sum, conversion) => sum + conversion.amountToConvert, 0);
        successMessage += `נוצרו ${pensionConversions.length} קצבאות נפרדות בסכום כולל: ${totalBalance.toLocaleString()} ש"ח\n`;
      }
      if (capitalAssetConversions.length > 0) {
        const totalAssets = capitalAssetConversions.reduce((sum, conversion) => sum + conversion.amountToConvert, 0);
        successMessage += `נוצרו ${capitalAssetConversions.length} נכסי הון בסכום כולל: ${totalAssets.toLocaleString()} ש"ח`;
      }
      
      setProcessingStatus(successMessage);
      alert(successMessage);
    } catch (e: any) {
      setError(`שגיאה בהמרת חשבונות: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  // פונקציה לטעינת נתונים קיימים מ-localStorage
  const loadExistingData = async () => {
    try {
      // טעינת נתונים מ-localStorage
      const savedData = localStorage.getItem(`pensionData_${clientId}`);
      const savedConvertedAccounts = localStorage.getItem(`convertedAccounts_${clientId}`);
      
      if (savedData) {
        const parsedData = JSON.parse(savedData);
        // חישוב תגמולים רק אם חסר (פעם אחת בלבד)
        const dataWithComputed = parsedData.map((acc: PensionAccount) => calculateInitialTagmulim(acc));
        // עדכון רק אם יש שינוי בנתונים
        const currentDataStr = JSON.stringify(pensionData);
        const newDataStr = JSON.stringify(dataWithComputed);
        if (currentDataStr !== newDataStr) {
          console.log('Pension data changed in localStorage, reloading...');
          setPensionData(dataWithComputed);
          setProcessingStatus(`נטענו ${dataWithComputed.length} תכניות פנסיוניות שמורות`);
        }
      }
      
      if (savedConvertedAccounts) {
        const parsedConverted = JSON.parse(savedConvertedAccounts);
        setConvertedAccounts(new Set(parsedConverted));
      }
      
      if (!savedData && pensionData.length === 0) {
        setProcessingStatus("טען קבצי XML כדי לראות את התיק הפנסיוני");
      }
    } catch (e) {
      console.log("No existing data found in localStorage");
      if (pensionData.length === 0) {
        setProcessingStatus("טען קבצי XML כדי לראות את התיק הפנסיוני");
      }
    }
  };

  // פונקציה עזר לחילוץ שם החברה מה-remarks
  const extractCompanyFromRemarks = (remarks: string): string => {
    if (!remarks) return '';
    const match = remarks.match(/חברה מנהלת:\s*([^\n]+)/);
    return match ? match[1].trim() : '';
  };

  // פונקציה ליצירת דוח Excel של הטבלה
  const generateExcelReport = () => {
    if (pensionData.length === 0) {
      setError("אין נתונים לייצוא לאקסל");
      return;
    }

    try {
      // יצירת נתוני CSV
      const headers = [
        'מספר חשבון',
        'שם תכנית', 
        'חברה מנהלת',
        'יתרה',
        'תאריך נכונות יתרה',
        'תאריך התחלה',
        'סוג מוצר',
        'מעסיקים היסטוריים',
        'פיצויים מעסיק נוכחי',
        'פיצויים לאחר התחשבנות',
        'פיצויים שלא עברו התחשבנות',
        'פיצויים מעסיקים קודמים (זכויות)',
        'פיצויים מעסיקים קודמים (קצבה)',
        'תגמולי עובד עד 2000',
        'תגמולי עובד אחרי 2000',
        'תגמולי עובד אחרי 2008 (לא משלמת)',
        'תגמולי מעביד עד 2000',
        'תגמולי מעביד אחרי 2000',
        'תגמולי מעביד אחרי 2008 (לא משלמת)'
      ];

      const csvContent = [
        headers.join(','),
        ...pensionData.map(account => [
          `"${account.מספר_חשבון}"`,
          `"${account.שם_תכנית}"`,
          `"${account.חברה_מנהלת}"`,
          account.יתרה || 0,
          `"${account.תאריך_נכונות_יתרה}"`,
          `"${account.תאריך_התחלה || ''}"`,
          `"${account.סוג_מוצר}"`,
          `"${account.מעסיקים_היסטוריים || ''}"`,
          account.פיצויים_מעסיק_נוכחי || 0,
          account.פיצויים_לאחר_התחשבנות || 0,
          account.פיצויים_שלא_עברו_התחשבנות || 0,
          account.פיצויים_ממעסיקים_קודמים_רצף_זכויות || 0,
          account.פיצויים_ממעסיקים_קודמים_רצף_קצבה || 0,
          account.תגמולי_עובד_עד_2000 || 0,
          account.תגמולי_עובד_אחרי_2000 || 0,
          account.תגמולי_עובד_אחרי_2008_לא_משלמת || 0,
          account.תגמולי_מעביד_עד_2000 || 0,
          account.תגמולי_מעביד_אחרי_2000 || 0,
          account.תגמולי_מעביד_אחרי_2008_לא_משלמת || 0
        ].join(','))
      ].join('\n');

      // הוספת BOM עבור תמיכה בעברית
      const BOM = '\uFEFF';
      const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
      
      // יצירת קישור להורדה
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `pension_portfolio_client_${clientId}_${formatDateToDDMMYY(new Date()).replace(/\//g, '_')}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setProcessingStatus(`יוצא דוח Excel עם ${pensionData.length} תכניות פנסיוניות`);
    } catch (error: any) {
      setError(`שגיאה ביצירת דוח Excel: ${error.message}`);
    }
  };

  // פונקציה לטעינת נתוני הלקוח
  const loadClientData = async () => {
    try {
      const client = await apiFetch<any>(`/clients/${clientId}`);
      setClientData(client);
    } catch (e) {
      console.warn('Failed to load client data:', e);
    }
  };

  useEffect(() => {
    loadExistingData();
    loadClientData();
  }, [clientId]);

  // טעינה מחדש כשחוזרים לדף (למשל אחרי מחיקת נכס)
  useEffect(() => {
    const handleFocus = () => {
      console.log('Window focused, checking for updates...');
      const savedData = localStorage.getItem(`pensionData_${clientId}`);
      if (savedData) {
        const parsedData = JSON.parse(savedData);
        // חישוב תגמולים רק אם חסר (פעם אחת בלבד)
        const dataWithComputed = parsedData.map((acc: PensionAccount) => calculateInitialTagmulim(acc));
        setPensionData(dataWithComputed);
      }
    };
    
    // טעינה מחדש כשהדף הופך לגלוי
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log('Page became visible, checking for updates...');
        const savedData = localStorage.getItem(`pensionData_${clientId}`);
        if (savedData) {
          const parsedData = JSON.parse(savedData);
          // חישוב תגמולים רק אם חסר (פעם אחת בלבד)
          const dataWithComputed = parsedData.map((acc: PensionAccount) => calculateInitialTagmulim(acc));
          setPensionData(dataWithComputed);
        }
      }
    };
    
    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [clientId]);

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💼 תיק פנסיוני</h1>
            <p className="card-subtitle">ניהול יתרות קרנות פנסיה וקופות גמל{clientData && ` - ${clientData.first_name} ${clientData.last_name}`}</p>
          </div>
          <Link to={`/clients/${clientId}`} className="btn btn-secondary">
            ← חזרה
          </Link>
        </div>

      {error && (
        <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
          {error}
        </div>
      )}

      {processingStatus && (
        <div style={{ color: "blue", marginBottom: 16, padding: 8, backgroundColor: "#e7f3ff" }}>
          {processingStatus}
        </div>
      )}

      {/* קליטת קבצים */}
      <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
        <h3>קליטת נתוני מסלקה</h3>
        
        {/* הוראות שימוש */}
        <div style={{ marginBottom: 16, padding: 12, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
          <h4 style={{ margin: "0 0 8px 0", color: "#495057" }}>אפשרויות עיבוד:</h4>
          <ul style={{ margin: 0, paddingRight: 20, fontSize: "14px", color: "#666" }}>
            <li><strong>עיבוד ידני:</strong> בחר קבצי XML או DAT ולחץ "עבד קבצי מסלקה"</li>
            <li><strong>תמיכה בפורמטים:</strong> המערכת תומכת בקבצי XML ו-DAT (קבצי מסלקה לאחר מניפולציה)</li>
          </ul>
        </div>

        <div style={{ marginBottom: 16 }}>
          <input
            type="file"
            multiple
            accept=".xml,.dat"
            onChange={(e) => setSelectedFiles(e.target.files)}
            style={{ marginBottom: 10 }}
          />
          <div style={{ fontSize: "14px", color: "#666" }}>
            בחר קבצי XML או DAT של המסלקה לעיבוד ידני (תמיכה בשני הפורמטים)
          </div>
        </div>
        
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => selectedFiles && processXMLFiles(selectedFiles)}
            disabled={!selectedFiles || loading}
            style={{
              padding: "10px 16px",
              backgroundColor: selectedFiles && !loading ? "#007bff" : "#ccc",
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: selectedFiles && !loading ? "pointer" : "not-allowed"
            }}
          >
            {loading ? "מעבד..." : "עבד קבצי מסלקה"}
          </button>
          
          <button
            onClick={generateExcelReport}
            disabled={pensionData.length === 0}
            style={{
              padding: "10px 16px",
              backgroundColor: pensionData.length > 0 ? "#28a745" : "#ccc",
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: pensionData.length > 0 ? "pointer" : "not-allowed"
            }}
          >
            יצא דוח Excel
          </button>
        </div>
      </section>

      {/* טבלת נתונים */}
      {pensionData.length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <h3>נתוני התיק הפנסיוני ({pensionData.length} חשבונות)</h3>
          
          {/* הוראות שימוש */}
          <div style={{ marginBottom: 16, padding: 12, backgroundColor: "#fff3cd", borderRadius: 4, border: "1px solid #ffeaa7" }}>
            <h4 style={{ margin: "0 0 8px 0", color: "#856404" }}>הוראות שימוש:</h4>
            <ol style={{ margin: 0, paddingRight: 20, fontSize: "14px", color: "#856404" }}>
              <li><strong>שמירת תכניות:</strong> סמן תכניות בעמודה "בחר" ולחץ "שמור תכניות נבחרות" לשמירה בטבלת התכניות הפנסיוניות</li>
              <li><strong>מחיקת תכנית:</strong> לחץ "מחק" בעמודת הפעולות להסרת תכנית מהרשימה</li>
              <li><strong>המרה לקצבאות/נכסים:</strong> סמן חשבונות או סכומים ספציפיים, בחר סוג המרה ולחץ "המר חשבונות/סכומים נבחרים"</li>
              <li><strong>חוקי המרה:</strong> לחץ על הכפתור "חוקי המרה לפי חוק" כדי לצפות במגבלות המרת יתרות</li>
            </ol>
          </div>
          
          {/* כפתור חוקי המרה */}
          <div style={{ marginBottom: 16 }}>
            <button
              onClick={() => setShowConversionRules(!showConversionRules)}
              style={{
                padding: "10px 20px",
                backgroundColor: "#17a2b8",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: "bold"
              }}
              title="הצג/הסתר חוקי המרה לפי חוק"
            >
              📋 {showConversionRules ? 'הסתר חוקי המרה' : 'חוקי המרה לפי חוק'}
            </button>
          </div>
          
          {/* הצגת חוקי המרה */}
          {showConversionRules && (
            <div style={{ 
              marginBottom: 16, 
              padding: 16, 
              backgroundColor: "#e7f3ff", 
              borderRadius: 4, 
              border: "2px solid #007bff",
              whiteSpace: "pre-wrap",
              fontSize: "13px",
              lineHeight: "1.6"
            }}>
              <h4 style={{ marginTop: 0, color: "#007bff" }}>חוקי המרת יתרות מתיק פנסיוני</h4>
              {getConversionRulesExplanation()}
            </div>
          )}
          
          {/* כפתור הוספה ידנית */}
          <div style={{ marginBottom: 16 }}>
            <button
              onClick={addManualAccount}
              style={{
                padding: "10px 20px",
                backgroundColor: "#28a745",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: "bold"
              }}
              title="הוסף תכנית פנסיונית חדשה ידנית"
            >
              + הוסף תכנית חדשה
            </button>
          </div>
          
          {/* כפתורי פעולה */}
          <div style={{ marginBottom: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button
              onClick={toggleAllAccountsSelection}
              style={{
                padding: "8px 12px",
                backgroundColor: "#6c757d",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
                fontSize: "14px"
              }}
            >
              {pensionData.every(a => a.selected) ? "בטל בחירת הכל" : "בחר הכל"}
            </button>
            
            <button
              onClick={saveSelectedAccounts}
              disabled={saving || !pensionData.some(a => a.selected)}
              style={{
                padding: "10px 16px",
                backgroundColor: !saving && pensionData.some(a => a.selected) ? "#007bff" : "#ccc",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: !saving && pensionData.some(a => a.selected) ? "pointer" : "not-allowed"
              }}
            >
              {saving ? "שומר..." : "שמור תכניות נבחרות"}
            </button>
            
            <button
              onClick={convertSelectedAccounts}
              disabled={loading || !pensionData.some(a => 
                a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
              )}
              style={{
                padding: "10px 16px",
                backgroundColor: !loading && pensionData.some(a => 
                  a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
                ) ? "#28a745" : "#ccc",
                color: "white",
                border: "none",
                borderRadius: 4,
                cursor: !loading && pensionData.some(a => 
                  a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
                ) ? "pointer" : "not-allowed"
              }}
            >
              המר חשבונות/סכומים נבחרים
            </button>
          </div>

          {/* טבלה מורחבת */}
          <div style={{ marginBottom: 8, padding: 8, backgroundColor: "#e7f3ff", borderRadius: 4, fontSize: "13px" }}>
            💡 <strong>טיפ:</strong> לחץ על כל תא בטבלה כדי לערוך את הערך ישירות. לחץ Enter או לחץ מחוץ לתא לשמור.
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
              <thead>
                <tr style={{ backgroundColor: "#f8f9fa" }}>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 50 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <input
                        type="checkbox"
                        checked={pensionData.length > 0 && pensionData.every(a => a.selected)}
                        onChange={toggleAllAccountsSelection}
                        style={{ transform: "scale(0.9)" }}
                      />
                      <span>בחר</span>
                    </div>
                  </th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>מספר חשבון</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 150 }}>שם תכנית</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 120 }}>חברה מנהלת</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 80, backgroundColor: "#f0f8ff" }}>יתרה כללית (מחושב)</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולים</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים מעסיק נוכחי</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים לאחר התחשבנות</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים שלא עברו התחשבנות</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים מעסיקים קודמים (זכויות)</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>פיצויים מעסיקים קודמים (קצבה)</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי עובד עד 2000</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי עובד אחרי 2000</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי עובד אחרי 2008 (לא משלמת)</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי מעביד עד 2000</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי מעביד אחרי 2000</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תגמולי מעביד אחרי 2008 (לא משלמת)</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>סוג מוצר</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>תאריך התחלה</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 150 }}>מעסיקים היסטוריים</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 100 }}>המר ל...</th>
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 80 }}>פעולות</th>
                </tr>
              </thead>
              <tbody>
                {pensionData.map((account, index) => (
                  <tr key={index} style={{ backgroundColor: account.selected ? "#e7f3ff" : "white" }}>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "center" }}>
                      <input
                        type="checkbox"
                        checked={account.selected || false}
                        onChange={() => toggleAccountSelection(index)}
                      />
                    </td>
                    {/* מספר חשבון - עריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4 }} onClick={() => setEditingCell({row: index, field: 'מספר_חשבון'})}>
                      {editingCell?.row === index && editingCell?.field === 'מספר_חשבון' ? (
                        <input
                          type="text"
                          defaultValue={account.מספר_חשבון}
                          onBlur={(e) => updateCellValue(index, 'מספר_חשבון', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'מספר_חשבון', e.currentTarget.value)}
                          autoFocus
                          style={{ width: '100%', padding: 2, fontSize: '12px' }}
                        />
                      ) : account.מספר_חשבון}
                    </td>
                    
                    {/* שם תכנית - עריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4 }} onClick={() => setEditingCell({row: index, field: 'שם_תכנית'})}>
                      {editingCell?.row === index && editingCell?.field === 'שם_תכנית' ? (
                        <input
                          type="text"
                          defaultValue={account.שם_תכנית}
                          onBlur={(e) => updateCellValue(index, 'שם_תכנית', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'שם_תכנית', e.currentTarget.value)}
                          autoFocus
                          style={{ width: '100%', padding: 2, fontSize: '12px' }}
                        />
                      ) : account.שם_תכנית}
                    </td>
                    
                    {/* חברה מנהלת - עריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4 }} onClick={() => setEditingCell({row: index, field: 'חברה_מנהלת'})}>
                      {editingCell?.row === index && editingCell?.field === 'חברה_מנהלת' ? (
                        <input
                          type="text"
                          defaultValue={account.חברה_מנהלת}
                          onBlur={(e) => updateCellValue(index, 'חברה_מנהלת', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'חברה_מנהלת', e.currentTarget.value)}
                          autoFocus
                          style={{ width: '100%', padding: 2, fontSize: '12px' }}
                        />
                      ) : account.חברה_מנהלת}
                    </td>
                    
                    {/* יתרה כללית - מחושבת (סכום כל הטורים) - לא ניתנת לעריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4, textAlign: "right", backgroundColor: "#f0f8ff", fontWeight: "bold" }}>
                      {calculateTotalBalance(account).toLocaleString()}
                    </td>
                    
                    {/* תגמולים - טור רגיל (ניתן לעריכה והמרה) */}
                    <EditableNumberCell account={account} index={index} field="תגמולים" />
                    
                    <EditableNumberCell account={account} index={index} field="פיצויים_מעסיק_נוכחי" />
                    <EditableNumberCell account={account} index={index} field="פיצויים_לאחר_התחשבנות" />
                    <EditableNumberCell account={account} index={index} field="פיצויים_שלא_עברו_התחשבנות" />
                    <EditableNumberCell account={account} index={index} field="פיצויים_ממעסיקים_קודמים_רצף_זכויות" />
                    <EditableNumberCell account={account} index={index} field="פיצויים_ממעסיקים_קודמים_רצף_קצבה" />
                    <EditableNumberCell account={account} index={index} field="תגמולי_עובד_עד_2000" />
                    <EditableNumberCell account={account} index={index} field="תגמולי_עובד_אחרי_2000" />
                    <EditableNumberCell account={account} index={index} field="תגמולי_עובד_אחרי_2008_לא_משלמת" />
                    <EditableNumberCell account={account} index={index} field="תגמולי_מעביד_עד_2000" />
                    <EditableNumberCell account={account} index={index} field="תגמולי_מעביד_אחרי_2000" />
                    <EditableNumberCell account={account} index={index} field="תגמולי_מעביד_אחרי_2008_לא_משלמת" />
                    
                    {/* סוג מוצר - עריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4 }} onClick={() => setEditingCell({row: index, field: 'סוג_מוצר'})}>
                      {editingCell?.row === index && editingCell?.field === 'סוג_מוצר' ? (
                        <input
                          type="text"
                          defaultValue={account.סוג_מוצר}
                          onBlur={(e) => updateCellValue(index, 'סוג_מוצר', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'סוג_מוצר', e.currentTarget.value)}
                          autoFocus
                          style={{ width: '100%', padding: 2, fontSize: '12px' }}
                        />
                      ) : account.סוג_מוצר}
                    </td>
                    
                    {/* תאריך התחלה - עריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4 }} onClick={() => setEditingCell({row: index, field: 'תאריך_התחלה'})}>
                      {editingCell?.row === index && editingCell?.field === 'תאריך_התחלה' ? (
                        <input
                          type="text"
                          defaultValue={account.תאריך_התחלה || ''}
                          onBlur={(e) => updateCellValue(index, 'תאריך_התחלה', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'תאריך_התחלה', e.currentTarget.value)}
                          autoFocus
                          style={{ width: '100%', padding: 2, fontSize: '12px' }}
                          placeholder="DD/MM/YY"
                        />
                      ) : (account.תאריך_התחלה || 'לא ידוע')}
                    </td>
                    
                    {/* מעסיקים היסטוריים - עריכה */}
                    <td style={{ border: "1px solid #ddd", padding: 4 }} onClick={() => setEditingCell({row: index, field: 'מעסיקים_היסטוריים'})}>
                      {editingCell?.row === index && editingCell?.field === 'מעסיקים_היסטוריים' ? (
                        <input
                          type="text"
                          defaultValue={account.מעסיקים_היסטוריים || ''}
                          onBlur={(e) => updateCellValue(index, 'מעסיקים_היסטוריים', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && updateCellValue(index, 'מעסיקים_היסטוריים', e.currentTarget.value)}
                          autoFocus
                          style={{ width: '100%', padding: 2, fontSize: '12px' }}
                        />
                      ) : account.מעסיקים_היסטוריים}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>
                      {(account.selected || Object.values(account.selected_amounts || {}).some(Boolean)) && (
                        <select
                          value={conversionTypes[index] || ''}
                          onChange={(e) => setConversionType(index, e.target.value as 'pension' | 'capital_asset')}
                          style={{ width: "100%" }}
                        >
                          <option value="">בחר סוג המרה</option>
                          <option value="pension">קצבה</option>
                          <option value="capital_asset">נכס הון</option>
                        </select>
                      )}
                    </td>
                    
                    {/* עמודת פעולות */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "center" }}>
                      <button
                        onClick={() => deleteAccount(index)}
                        style={{
                          padding: "4px 8px",
                          backgroundColor: "#dc3545",
                          color: "white",
                          border: "none",
                          borderRadius: 3,
                          cursor: "pointer",
                          fontSize: "12px"
                        }}
                        title="מחק תכנית זו מהרשימה"
                      >
                        מחק
                      </button>
                    </td>
                  </tr>
                ))}

                {/* שורת סה"כ */}
                {pensionData.length > 0 && (
                  <tr style={{ backgroundColor: "#fff8e1", fontWeight: "bold", borderTop: "3px solid #ff9800" }}>
                    {/* Checkbox column */}
                    <td style={{ border: "1px solid #ddd", padding: 6 }}></td>
                    {/* מספר חשבון, שם תכנית, חברה מנהלת */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "center" }} colSpan={3}>
                      סה"כ
                    </td>
                    {/* יתרה כללית מחושבת */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right", backgroundColor: "#f0f8ff" }}>
                      {pensionData.reduce((sum, acc) => sum + calculateTotalBalance(acc), 0).toLocaleString()}
                    </td>
                    {/* תגמולים */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולים) || 0), 0).toLocaleString()}
                    </td>
                    {/* פיצויים מעסיק נוכחי */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_מעסיק_נוכחי) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_לאחר_התחשבנות) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_שלא_עברו_התחשבנות) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_ממעסיקים_קודמים_רצף_זכויות) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.פיצויים_ממעסיקים_קודמים_רצף_קצבה) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_עובד_עד_2000) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_עובד_אחרי_2000) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_עובד_אחרי_2008_לא_משלמת) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_מעביד_עד_2000) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_מעביד_אחרי_2000) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      {pensionData.reduce((sum, acc) => sum + (Number(acc.תגמולי_מעביד_אחרי_2008_לא_משלמת) || 0), 0).toLocaleString()}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6 }} colSpan={4}></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {pensionData.length === 0 && !loading && (
        <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4, textAlign: "center" }}>
          אין נתוני תיק פנסיוני. אנא טען קבצי מסלקה לעיבוד.
        </div>
      )}
      </div>
    </div>
  );
}
