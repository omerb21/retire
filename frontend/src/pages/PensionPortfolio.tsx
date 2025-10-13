import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import * as XLSX from 'xlsx';
import { formatDateToDDMMYY, formatDateToDDMMYYYY } from '../utils/dateUtils';

type PensionAccount = {
  id?: number;
  מספר_חשבון: string;
  שם_תכנית: string;
  חברה_מנהלת: string;
  קוד_חברה_מנהלת?: string;
  יתרה: number;
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

  // פונקציה לעיבוד קבצי XML של המסלקה
  const processXMLFiles = async (files: FileList) => {
    setLoading(true);
    setError("");
    setProcessingStatus("מוחק נתונים קיימים ומעבד קבצי XML...");
    
    // מחיקת כל הנתונים הקיימים
    setPensionData([]);

    try {
      const processedAccounts: PensionAccount[] = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file.name.toLowerCase().endsWith('.xml')) {
          continue;
        }

        setProcessingStatus(`מעבד קובץ ${i + 1} מתוך ${files.length}: ${file.name}`);

        const text = await file.text();
        const accounts = extractAccountsFromXML(text, file.name);
        console.log(`File ${file.name} produced ${accounts.length} accounts`);
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
      setError(`שגיאה בעיבוד קבצי XML: ${e?.message || e}`);
      setProcessingStatus("");
    } finally {
      setLoading(false);
    }
  };

  // פונקציה לחילוץ חשבונות מתוכן XML
  const extractAccountsFromXML = (xmlContent: string, fileName: string): PensionAccount[] => {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlContent, "text/xml");
    
    // Debug: חיפוש ספציפי של SHEM-YATZRAN ו-TOTAL-CHISACHON-MTZBR
    const schemYatzranElements = xmlDoc.getElementsByTagName('SHEM-YATZRAN');
    const totalChisachonElements = xmlDoc.getElementsByTagName('TOTAL-CHISACHON-MTZBR');
    console.log(`${fileName}: Found ${schemYatzranElements.length} SHEM-YATZRAN, ${totalChisachonElements.length} TOTAL-CHISACHON-MTZBR`);
    
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
        const account = extractAccountData(accountElements[i], fileName, xmlDoc);
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
  const extractAccountData = (accountElem: Element, fileName: string, xmlDoc: Document): PensionAccount | null => {
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

    // סוג מוצר - לפי שם התכנית בלבד (כמו במערכת המקורית)
    let productType = 'קופת גמל'; // ברירת מחדל
    
    // זיהוי לפי שם התכנית (הדרך הכי מהימנה)
    if (planName) {
      const planLower = planName.toLowerCase();
      console.log(`Analyzing plan name: "${planName}"`);
      
      if (planLower.includes('השתלמות')) {
        productType = 'קרן השתלמות';
        console.log('Identified as קרן השתלמות by plan name');
      } else if (planLower.includes('פנסיה')) {
        productType = 'קרן פנסיה';
        console.log('Identified as קרן פנסיה by plan name');
      } else if (planLower.includes('ביטוח מנהלים') || planLower.includes('מנהלים')) {
        productType = 'ביטוח מנהלים';
        console.log('Identified as ביטוח מנהלים by plan name');
      } else if (planLower.includes('חיסכון') && !planLower.includes('גמל')) {
        productType = 'פוליסת חיסכון';
        console.log('Identified as פוליסת חיסכון by plan name');
      } else if (planLower.includes('ביטוח חיים')) {
        productType = 'פוליסת ביטוח חיים';
        console.log('Identified as פוליסת ביטוח חיים by plan name');
      } else {
        // ברירת מחדל לקופת גמל
        console.log('Using default: קופת גמל');
      }
    } else {
      console.log('No plan name found, using default: קופת גמל');
    }

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
        'TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM',
        'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT',
        'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-KITZBA'
      ];
      
      const balanceKeywords = ['TAGMUL', 'PITZ', 'PITZU', 'PITZUI'];
      const explicitSet = new Set(balanceExplicitTags);
      
      const allElements = accountElem.getElementsByTagName('*');
      for (let i = 0; i < allElements.length; i++) {
        const node = allElements[i];
        if (!node.textContent || !node.textContent.trim()) continue;
        
        const tagUpper = node.tagName.toUpperCase();
        const isExplicit = explicitSet.has(node.tagName);
        const hasKeyword = balanceKeywords.some(keyword => tagUpper.includes(keyword));
        
        if (!(isExplicit || hasKeyword)) continue;
        
        const value = node.textContent.trim();
        if (!collected[node.tagName]) collected[node.tagName] = [];
        collected[node.tagName].push(value);
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

    // פיצויים - לפי השדות הנכונים מהמערכת הקיימת
    const פיצויים_מעסיק_נוכחי = parseFloat(balanceRelatedFields['ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI']?.split(' | ')[0] || '0') || 0;
    const פיצויים_לאחר_התחשבנות = parseFloat(balanceRelatedFields['ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM']?.split(' | ')[0] || '0') || 0;
    const פיצויים_שלא_עברו_התחשבנות = parseFloat(balanceRelatedFields['TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM']?.split(' | ')[0] || '0') || 0;
    const פיצויים_ממעסיקים_קודמים_רצף_זכויות = parseFloat(balanceRelatedFields['TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT']?.split(' | ')[0] || '0') || 0;
    const פיצויים_ממעסיקים_קודמים_רצף_קצבה = parseFloat(balanceRelatedFields['TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-KITZBA']?.split(' | ')[0] || '0') || 0;

    // תגמולים - לפי התקופות מהמערכת הקיימת
    const תגמולי_עובד_עד_2000 = tagmulPeriods['תגמולי עובד עד 2000'] || 0;
    const תגמולי_עובד_אחרי_2000 = tagmulPeriods['תגמולי עובד אחרי 2000'] || 0;
    const תגמולי_עובד_אחרי_2008_לא_משלמת = tagmulPeriods['תגמולי עובד אחרי 2008 (קצבה לא משלמת)'] || 0;
    const תגמולי_מעביד_עד_2000 = tagmulPeriods['תגמולי מעביד עד 2000'] || 0;
    const תגמולי_מעביד_אחרי_2000 = tagmulPeriods['תגמולי מעביד אחרי 2000'] || 0;
    const תגמולי_מעביד_אחרי_2008_לא_משלמת = tagmulPeriods['תגמולי מעביד אחרי 2008 (קצבה לא משלמת)'] || 0;

    // רק אם יש מידע משמעותי, נחזיר את החשבון
    if (accountNumber === 'לא ידוע' && planName === 'לא ידוע' && balance === 0) {
      return null;
    }

    const result = {
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

  // פונקציה לשמירת כל התכניות הנבחרות - כעת רק שמירה מקומית
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
      // שמירה מקומית בלבד - לא יוצרים קצבאות בשרת
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(pensionData));
      
      setProcessingStatus(`נשמרו מקומית ${selectedAccounts.length} תכניות פנסיה`);
      
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
      setPensionData(prev => prev.filter((_, i) => i !== accountIndex));
      
    } catch (error: any) {
      setError(`שגיאה במחיקת התכנית: ${error.message}`);
    }
  };

  // פונקציה לעריכת תכנית
  const editAccount = (accountIndex: number) => {
    const account = pensionData[accountIndex];
    
    // הצגת דיאלוג עריכה פשוט
    const newName = prompt('ערוך שם תכנית:', account.שם_תכנית || '');
    if (newName === null) return; // ביטול
    
    const newBalance = prompt('ערוך יתרה:', account.יתרה?.toString() || '0');
    if (newBalance === null) return; // ביטול
    
    const newStartDate = prompt('ערוך תאריך התחלה (DD/MM/YY):', account.תאריך_התחלה ? formatDateToDDMMYY(new Date(account.תאריך_התחלה)) : '');
    if (newStartDate === null) return; // ביטול
    
    // עדכון הנתונים
    setPensionData(prev => prev.map((acc, i) => 
      i === accountIndex ? {
        ...acc,
        שם_תכנית: newName,
        יתרה: parseFloat(newBalance) || 0,
        תאריך_התחלה: newStartDate
      } : acc
    ));
    
    setProcessingStatus(`תכנית "${newName}" עודכנה בהצלחה`);
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
    const newAccount = {
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
      פיצויים_מעסיקים_קודמים_זכויות: 0,
      פיצויים_מעסיקים_קודמים_קצבה: 0,
      תגמולי_עובד_עד_2000: 0,
      תגמולי_עובד_אחרי_2000: 0,
      תגמולי_עובד_אחרי_2008_לא_משלמת: 0,
      תגמולי_מעביד_עד_2000: 0,
      תגמולי_מעביד_אחרי_2000: 0,
      תגמולי_מעביד_אחרי_2008_לא_משלמת: 0,
      selected: false,
      selected_amounts: {}
    };
    
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
  const calculateRetirementDate = () => {
    if (!clientData?.birth_date) return null;
    
    try {
      const birthDate = new Date(clientData.birth_date);
      const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 62 : 67;
      const retirementDate = new Date(birthDate);
      retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
      // החזרת פורמט ISO לשרת
      return retirementDate.toISOString().split('T')[0];
    } catch (error) {
      console.error('Error calculating retirement date:', error);
      return null;
    }
  };

  // פונקציה להמרת חשבונות נבחרים לקצבאות ונכסי הון
  const convertSelectedAccounts = async () => {
    if (!clientId) return;

    // חיפוש תכניות שנבחרו עם conversion_type='pension'
    const pensionConversions: Array<{account: any, index: number, amountToConvert: number, specificAmounts: any}> = [];
    const capitalAssetConversions: Array<{account: any, index: number, amountToConvert: number, specificAmounts: any}> = [];
    
    pensionData.forEach((account, index) => {
      const isPensionConversion = conversionTypes[index] === 'pension';
      const isCapitalAssetConversion = conversionTypes[index] === 'capital_asset';
      
      // חישוב הסכום להמרה
      let amountToConvert = 0;
      let specificAmounts: any = {};
      
      if (account.selected) {
        // אם כל התכנית נבחרה - המר את כל היתרה
        amountToConvert = account.יתרה || 0;
      } else {
        // אם רק סכומים ספציפיים נבחרו - חשב את הסכום הכולל
        const selectedAmounts = account.selected_amounts || {};
        Object.entries(selectedAmounts).forEach(([key, isSelected]) => {
          if (isSelected && (account as any)[key]) {
            amountToConvert += parseFloat((account as any)[key]) || 0;
            specificAmounts[key] = (account as any)[key];
          }
        });
      }
      
      if (amountToConvert > 0) {
        if (isPensionConversion) {
          pensionConversions.push({account, index, amountToConvert, specificAmounts});
        } else if (isCapitalAssetConversion) {
          capitalAssetConversions.push({account, index, amountToConvert, specificAmounts});
        }
      }
    });

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
        const retirementDate = calculateRetirementDate();
        
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
          
          // יצירת מידע מקור להחזרה במקרה של מחיקה
          const conversionSourceData = {
            type: 'pension_portfolio',
            account_name: account.שם_תכנית,
            company: account.חברה_מנהלת,
            account_number: account.מספר_תכנית,
            product_type: account.סוג_מוצר,
            amount: amountToConvert,
            specific_amounts: specificAmounts,
            conversion_date: new Date().toISOString()
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
            remarks: `הומר מתיק פנסיוני\nתכנית: ${account.שם_תכנית} (${account.חברה_מנהלת})\nסכומים שהומרו: ${conversionDetails}`,
            conversion_source: JSON.stringify(conversionSourceData)
          };
          
          // הוספת שדות אופציונליים רק אם יש להם ערך
          if (pensionData.fixed_index_rate !== undefined) {
            pensionData.fixed_index_rate = null;
          }
          if (pensionData.deduction_file !== undefined) {
            pensionData.deduction_file = null;
          }

          await apiFetch(`/clients/${clientId}/pension-funds`, {
            method: 'POST',
            body: JSON.stringify(pensionData)
          });
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
          let assetDescription = '';
          let assetTypeValue = '';
          if (account.סוג_מוצר && account.סוג_מוצר.includes('קרן השתלמות')) {
            assetDescription = 'קרן השתלמות';
            assetTypeValue = 'mutual_funds'; // קרן השתלמות - ערך מותר
          } else {
            assetDescription = 'קופת גמל';
            assetTypeValue = 'deposits'; // קופת גמל - ערך מותר
          }
          
          // יצירת מידע מקור להחזרה במקרה של מחיקה
          const conversionSourceData = {
            type: 'pension_portfolio',
            account_name: account.שם_תכנית,
            company: account.חברה_מנהלת,
            account_number: account.מספר_תכנית,
            product_type: account.סוג_מוצר,
            amount: amountToConvert,
            specific_amounts: specificAmounts,
            conversion_date: new Date().toISOString()
          };
          
          const assetData = {
            client_id: parseInt(clientId),
            asset_type: assetTypeValue, // שימוש בערך מאושר מהרשימה
            description: `${assetDescription} - ${account.שם_תכנית} (${conversionDetails})` || 'נכס הון מתיק פנסיוני',
            current_value: amountToConvert,
            purchase_value: amountToConvert,
            purchase_date: account.תאריך_התחלה || formatDateToDDMMYY(new Date()),
            annual_return: 0,
            annual_return_rate: 0.03,
            payment_frequency: 'monthly',
            liquidity: 'medium',
            risk_level: 'medium',
            monthly_income: 0, // אין תשלום חודשי
            start_date: formatDateToDDMMYY(new Date()),
            indexation_method: 'none', // ללא הצמדה
            tax_treatment: 'exempt', // פטור מס
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
      setPensionData(prev => {
        return prev.map((account, index) => {
          const conversion = [...pensionConversions, ...capitalAssetConversions].find(c => c.index === index);
          
          if (!conversion) return account; // לא הומר כלום
          
          const {amountToConvert, specificAmounts} = conversion;
          
          // אם כל התכנית הומרה - הסר אותה לגמרי
          if (account.selected) {
            return null; // יוסר בסינון
          }
          
          // אם רק סכומים ספציפיים הומרו - הפחת אותם
          const updatedAccount = {...account};
          
          // הפחתת הסכומים הספציפיים שהומרו
          Object.keys(specificAmounts).forEach(key => {
            if ((updatedAccount as any)[key]) {
              (updatedAccount as any)[key] = 0; // מאפס את השדה שהומר
            }
          });
          
          // הפחתת הסכום מהיתרה הכללית
          updatedAccount.יתרה = (updatedAccount.יתרה || 0) - amountToConvert;
          
          // איפוס הסימונים
          updatedAccount.selected = false;
          updatedAccount.selected_amounts = {};
          
          return updatedAccount;
        }).filter(account => account !== null); // הסרת התכניות שהומרו לגמרי
      });
      
      // עדכון רשימת התכניות שהומרו
      const allConvertedAccounts = [...pensionConversions, ...capitalAssetConversions];
      const convertedIds = allConvertedAccounts.map(conversion => 
        `${conversion.account.מספר_חשבון}_${conversion.account.שם_תכנית}_${conversion.account.חברה_מנהלת}`
      );
      
      setConvertedAccounts(prev => {
        const newSet = new Set(prev);
        convertedIds.forEach((id: string) => newSet.add(id));
        return newSet;
      });
      
      // ניקוי סוגי ההמרה של התכניות שהומרו
      setConversionTypes({});
      
      // שמירה ל-localStorage
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(pensionData));
      localStorage.setItem(`convertedAccounts_${clientId}`, JSON.stringify(Array.from(convertedAccounts)));
      
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
        setPensionData(parsedData);
        setProcessingStatus(`נטענו ${parsedData.length} תכניות פנסיוניות שמורות`);
      }
      
      if (savedConvertedAccounts) {
        const parsedConverted = JSON.parse(savedConvertedAccounts);
        setConvertedAccounts(new Set(parsedConverted));
      }
      
      if (!savedData) {
        setProcessingStatus("טען קבצי XML כדי לראות את התיק הפנסיוני");
      }
    } catch (e) {
      console.log("No existing data found in localStorage");
      setProcessingStatus("טען קבצי XML כדי לראות את התיק הפנסיוני");
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

  return (
    <div style={{ maxWidth: 1200 }}>
      <div style={{ marginBottom: 20 }}>
        <Link to={`/clients/${clientId}`}>← חזרה לפרטי לקוח</Link>
      </div>
      
      <h2>תיק פנסיוני</h2>

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
            <li><strong>עיבוד ידני:</strong> בחר קבצי XML ולחץ "עבד קבצי מסלקה"</li>
            <li><strong>עיבוד אוטומטי:</strong> לחץ "השתמש בסקריפט NESS" לעיבוד קבצים מתיקיית DATA</li>
          </ul>
        </div>

        <div style={{ marginBottom: 16 }}>
          <input
            type="file"
            multiple
            accept=".xml"
            onChange={(e) => setSelectedFiles(e.target.files)}
            style={{ marginBottom: 10 }}
          />
          <div style={{ fontSize: "14px", color: "#666" }}>
            בחר קבצי XML של המסלקה לעיבוד ידני
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
            </ol>
          </div>
          
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
                  <th style={{ border: "1px solid #ddd", padding: 6, minWidth: 80 }}>יתרה כללית</th>
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
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>{account.מספר_חשבון}</td>
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>{account.שם_תכנית}</td>
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>{account.חברה_מנהלת}</td>
                    
                    {/* יתרה כללית עם אפשרות סימון */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.יתרה || false}
                          onChange={(e) => toggleAmountSelection(index, 'יתרה', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{account.יתרה > 0 ? account.יתרה.toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* פיצויים מעסיק נוכחי */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.פיצויים_מעסיק_נוכחי || false}
                          onChange={(e) => toggleAmountSelection(index, 'פיצויים_מעסיק_נוכחי', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.פיצויים_מעסיק_נוכחי || 0) > 0 ? (account.פיצויים_מעסיק_נוכחי || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* פיצויים לאחר התחשבנות */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.פיצויים_לאחר_התחשבנות || false}
                          onChange={(e) => toggleAmountSelection(index, 'פיצויים_לאחר_התחשבנות', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.פיצויים_לאחר_התחשבנות || 0) > 0 ? (account.פיצויים_לאחר_התחשבנות || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* פיצויים שלא עברו התחשבנות */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.פיצויים_שלא_עברו_התחשבנות || false}
                          onChange={(e) => toggleAmountSelection(index, 'פיצויים_שלא_עברו_התחשבנות', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.פיצויים_שלא_עברו_התחשבנות || 0) > 0 ? (account.פיצויים_שלא_עברו_התחשבנות || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* פיצויים מעסיקים קודמים רצף זכויות */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.פיצויים_ממעסיקים_קודמים_רצף_זכויות || false}
                          onChange={(e) => toggleAmountSelection(index, 'פיצויים_ממעסיקים_קודמים_רצף_זכויות', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.פיצויים_ממעסיקים_קודמים_רצף_זכויות || 0) > 0 ? (account.פיצויים_ממעסיקים_קודמים_רצף_זכויות || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* פיצויים מעסיקים קודמים רצף קצבה */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.פיצויים_ממעסיקים_קודמים_רצף_קצבה || false}
                          onChange={(e) => toggleAmountSelection(index, 'פיצויים_ממעסיקים_קודמים_רצף_קצבה', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.פיצויים_ממעסיקים_קודמים_רצף_קצבה || 0) > 0 ? (account.פיצויים_ממעסיקים_קודמים_רצף_קצבה || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* תגמולי עובד עד 2000 */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.תגמולי_עובד_עד_2000 || false}
                          onChange={(e) => toggleAmountSelection(index, 'תגמולי_עובד_עד_2000', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.תגמולי_עובד_עד_2000 || 0) > 0 ? (account.תגמולי_עובד_עד_2000 || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* תגמולי עובד אחרי 2000 */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.תגמולי_עובד_אחרי_2000 || false}
                          onChange={(e) => toggleAmountSelection(index, 'תגמולי_עובד_אחרי_2000', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.תגמולי_עובד_אחרי_2000 || 0) > 0 ? (account.תגמולי_עובד_אחרי_2000 || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* תגמולי עובד אחרי 2008 לא משלמת */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.תגמולי_עובד_אחרי_2008_לא_משלמת || false}
                          onChange={(e) => toggleAmountSelection(index, 'תגמולי_עובד_אחרי_2008_לא_משלמת', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.תגמולי_עובד_אחרי_2008_לא_משלמת || 0) > 0 ? (account.תגמולי_עובד_אחרי_2008_לא_משלמת || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* תגמולי מעביד עד 2000 */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.תגמולי_מעביד_עד_2000 || false}
                          onChange={(e) => toggleAmountSelection(index, 'תגמולי_מעביד_עד_2000', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.תגמולי_מעביד_עד_2000 || 0) > 0 ? (account.תגמולי_מעביד_עד_2000 || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* תגמולי מעביד אחרי 2000 */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.תגמולי_מעביד_אחרי_2000 || false}
                          onChange={(e) => toggleAmountSelection(index, 'תגמולי_מעביד_אחרי_2000', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.תגמולי_מעביד_אחרי_2000 || 0) > 0 ? (account.תגמולי_מעביד_אחרי_2000 || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    {/* תגמולי מעביד אחרי 2008 לא משלמת */}
                    <td style={{ border: "1px solid #ddd", padding: 6, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <input
                          type="checkbox"
                          checked={account.selected_amounts?.תגמולי_מעביד_אחרי_2008_לא_משלמת || false}
                          onChange={(e) => toggleAmountSelection(index, 'תגמולי_מעביד_אחרי_2008_לא_משלמת', e.target.checked)}
                          style={{ transform: "scale(0.8)" }}
                        />
                        <span>{(account.תגמולי_מעביד_אחרי_2008_לא_משלמת || 0) > 0 ? (account.תגמולי_מעביד_אחרי_2008_לא_משלמת || 0).toLocaleString() : '-'}</span>
                      </div>
                    </td>
                    
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>{account.סוג_מוצר}</td>
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>
                      {account.תאריך_התחלה || 'לא ידוע'}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: 6 }}>{account.מעסיקים_היסטוריים}</td>
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
                      <div style={{ display: "flex", gap: 4, justifyContent: "center" }}>
                        <button
                          onClick={() => editAccount(index)}
                          style={{
                            padding: "4px 8px",
                            backgroundColor: "#007bff",
                            color: "white",
                            border: "none",
                            borderRadius: 3,
                            cursor: "pointer",
                            fontSize: "12px"
                          }}
                          title="ערוך תכנית זו"
                        >
                          ערוך
                        </button>
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
                      </div>
                    </td>
                  </tr>
                ))}
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
  );
}
