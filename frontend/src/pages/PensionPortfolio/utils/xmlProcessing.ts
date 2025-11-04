import { PensionAccount } from '../types';
import { calculateInitialTagmulim } from './pensionCalculations';

/**
 * פונקציה לחילוץ חשבונות מתוכן XML
 */
export function extractAccountsFromXML(xmlContent: string, fileName: string): PensionAccount[] {
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
}

/**
 * פונקציה לחילוץ נתוני חשבון מאלמנט XML
 */
function extractAccountData(
  accountElem: Element, 
  fileName: string, 
  xmlDoc: Document, 
  globalShemMutzar: string, 
  globalSugMutzar: string
): PensionAccount | null {
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

  // יתרה - חיפוש מורחב
  const balance = findBalance(accountElem, getElementFloat);

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

  // סוג מוצר
  const productType = determineProductType(globalShemMutzar, globalSugMutzar);
  console.log(`✅ Final product type: ${productType}`);

  // מעסיקים היסטוריים
  const employers = extractEmployers(accountElem);

  // פיצויים ותגמולים
  const balanceRelatedFields = collectBalanceRelatedFields(accountElem);
  const tagmulPeriods = collectTagmulPeriods(accountElem);

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

  // פיצויים
  const פיצויים_מעסיק_נוכחי = getFirstBalanceValue([
    'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI',
    'YITRAT-PITZUIM-MAASIK-NOCHECHI',
    'YITRAT-PITZUIM-LELO-HITCHASHBENOT'
  ]);

  if (accountNumber === '2209575014' || accountNumber === '494930') {
    console.log(`🔍 DEBUG Plan ${accountNumber}:`, {
      balanceKeys: Object.keys(balanceRelatedFields),
      פיצויים_מעסיק_נוכחי
    });
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

  // תגמולים
  const תגמולי_עובד_עד_2000 = tagmulPeriods['תגמולי עובד עד 2000'] || 0;
  const תגמולי_עובד_אחרי_2000 = tagmulPeriods['תגמולי עובד אחרי 2000'] || 0;
  const תגמולי_עובד_אחרי_2008_לא_משלמת = tagmulPeriods['תגמולי עובד אחרי 2008 (קצבה לא משלמת)'] || 0;
  const תגמולי_מעביד_עד_2000 = tagmulPeriods['תגמולי מעביד עד 2000'] || 0;
  const תגמולי_מעביד_אחרי_2000 = tagmulPeriods['תגמולי מעביד אחרי 2000'] || 0;
  const תגמולי_מעביד_אחרי_2008_לא_משלמת = tagmulPeriods['תגמולי מעביד אחרי 2008 (קצבה לא משלמת)'] || 0;

  // תגמולים - ייבוא ישיר מהתגית YITRAT-KASPEY-TAGMULIM
  const תגמולים_מקור = parseFloat(balanceRelatedFields['YITRAT-KASPEY-TAGMULIM']?.split(' | ')[0] || '0') || 0;
  const תגמולים = Math.max(0, תגמולים_מקור - סך_פיצויים - תגמולי_עובד_אחרי_2008_לא_משלמת - תגמולי_מעביד_אחרי_2008_לא_משלמת);

  // רק אם יש מידע משמעותי, נחזיר את החשבון
  if (accountNumber === 'לא ידוע' && planName === 'לא ידוע' && balance === 0) {
    return null;
  }

  const baseAccount: PensionAccount = {
    מספר_חשבון: accountNumber,
    שם_תכנית: planName,
    debug_plan_name: planName,
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
  
  console.log('Extracted account data:', result);
  
  return result;
}

// פונקציות עזר נוספות
function findBalance(accountElem: Element, getElementFloat: (tag: string) => number): number {
  const sumFields = (xpath: string, fieldCandidates: string[]): number => {
    let total = 0;
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
              break;
            }
          }
        }
      }
    }
    
    return total;
  };

  // 1. Sum balances reported per track
  const yitrotTotal = sumFields('.//BlockItrot//PerutYitrot', ['TOTAL-CHISACHON-MTZBR', 'TOTAL-ERKEI-PIDION']);
  if (yitrotTotal > 0) {
    console.log(`Found balance in BlockItrot/PerutYitrot: ${yitrotTotal}`);
    return yitrotTotal;
  }

  // 2. Sum balances from investment track details
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

  // 4. Generic search for common balance fields
  const genericFields = [
    'SCHUM-TZVIRA-BAMASLUL', 'YITRAT-KASPEY-TAGMULIM', 'TOTAL-CHISACHON-MTZBR',
    'TOTAL-ERKEI-PIDION', 'SCHUM-HON-EFSHAR', 'SCHUM-CHISACHON', 'SCHUM-TAGMULIM',
    'SCHUM-PITURIM', 'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
    'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI'
  ];
  
  for (const field of genericFields) {
    const value = getElementFloat(field);
    if (value > 0) {
      console.log(`Found balance in generic field ${field}: ${value}`);
      return value;
    }
  }

  // 5. Fall back to scanning numeric values
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
}

function determineProductType(globalShemMutzar: string, globalSugMutzar: string): string {
  console.log(`🔍 Product type detection: SHEM-MUTZAR="${globalShemMutzar}", SUG-MUTZAR="${globalSugMutzar}"`);
  
  // זיהוי לפי SHEM-MUTZAR (עדיפות ראשונה)
  if (globalShemMutzar) {
    const mutzarLower = globalShemMutzar.toLowerCase();
    if (mutzarLower.includes('השתלמות')) {
      return 'קרן השתלמות';
    } else if (mutzarLower.includes('קרן פנסיה')) {
      return 'קרן פנסיה';
    } else if (mutzarLower.includes('קופת גמל')) {
      return 'קופת גמל';
    } else if (mutzarLower.includes('ביטוח חיים משולב') || mutzarLower.includes('משולב חיסכון')) {
      return 'פוליסת ביטוח חיים משולב חיסכון';
    } else if (mutzarLower.includes('ביטוח חיים')) {
      return 'פוליסת ביטוח חיים';
    } else if (mutzarLower.includes('חיסכון טהור') || mutzarLower.includes('חסכון טהור')) {
      return 'פוליסת חיסכון טהור';
    } else {
      return globalShemMutzar;
    }
  }
  
  // זיהוי לפי SUG-MUTZAR (עדיפות שנייה)
  if (globalSugMutzar) {
    const PRODUCT_TYPE_MAP: {[key: string]: string} = {
      '1': 'פוליסת ביטוח חיים משולב חיסכון',
      '2': 'קרן פנסיה',
      '3': 'קופת גמל',
      '4': 'קרן השתלמות',
      '5': 'פוליסת חיסכון טהור',
      '6': 'קרן השתלמות',
      '7': 'פוליסת ביטוח חיים',
      '8': 'ביטוח מנהלים',
      '9': 'קופת גמל להשקעה'
    };
    return PRODUCT_TYPE_MAP[globalSugMutzar] || globalSugMutzar;
  }
  
  return 'לא ידוע';
}

function extractEmployers(accountElem: Element): string[] {
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
  
  return employers;
}

function collectBalanceRelatedFields(accountElem: Element): {[key: string]: string} {
  const collected: {[key: string]: string[]} = {};
  const balanceExplicitTags = [
    'TOTAL-CHISACHON-MTZBR', 'TOTAL-ERKEI-PIDION', 'YITRAT-KASPEY-TAGMULIM',
    'YITRAT-PITZUIM', 'YITRAT-PITZUIM-MAASIK-NOCHECHI', 'YITRAT-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
    'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI', 'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
    'TOTAL-HAFKADOT-OVED-TAGMULIM-SHANA-NOCHECHIT', 'TOTAL-HAFKADOT-MAAVID-TAGMULIM-SHANA-NOCHECHIT',
    'TOTAL-HAFKADOT-PITZUIM-SHANA-NOCHECHIT', 'SCHUM-HAFKADA-SHESHULAM', 'SCHUM-TAGMULIM',
    'SCHUM-PITURIM', 'YITRAT-PITZUIM-LELO-HITCHASHBENOT', 'KAYAM-RETZEF-PITZUIM-KITZBA',
    'KAYAM-RETZEF-ZECHUYOT-PITZUIM', 'ERECH-PIDION-MARKIV-PITZUIM-LEMAS-NOCHECHI',
    'TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM', 'TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT',
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
}

function collectTagmulPeriods(accountElem: Element): {[key: string]: number} {
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
}
