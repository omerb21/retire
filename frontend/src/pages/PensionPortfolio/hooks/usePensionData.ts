import { useState, useEffect } from 'react';
import { PensionAccount, EditingCell } from '../types';
import { apiFetch } from '../../../lib/api';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { calculateInitialTagmulim } from '../utils/pensionCalculations';

/**
 * Hook לניהול נתוני תיק פנסיוני
 */
export function usePensionData(clientId: string | undefined) {
  const [pensionData, setPensionData] = useState<PensionAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [processingStatus, setProcessingStatus] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [convertedAccounts, setConvertedAccounts] = useState<Set<string>>(new Set());
  const [conversionTypes, setConversionTypes] = useState<Record<number, 'pension' | 'capital_asset'>>({});
  const [clientData, setClientData] = useState<any>(null);
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [showConversionRules, setShowConversionRules] = useState<boolean>(false);
  const [redemptionDate, setRedemptionDate] = useState<string>('');

  // פונקציה לעיבוד קבצי XML ו-DAT של המסלקה
  const processXMLFiles = async (files: FileList) => {
    setLoading(true);
    setError("");
    setProcessingStatus("מוחק נתונים קיימים ומעבד קבצים...");
    
    // מחיקת כל הנתונים הקיימים מה-state ומה-localStorage
    setPensionData([]);
    localStorage.removeItem(`pensionData_${clientId}`);

    try {
      const formData = new FormData();
      Array.from(files).forEach(file => {
        formData.append('files', file);
      });

      setProcessingStatus(`מעלה ומעבד ${files.length} קבצים במסלקה...`);

      const data = await apiFetch<{ accounts: PensionAccount[] }>(`/clients/${clientId}/pension-portfolio/process-xml`, {
        method: 'POST',
        body: formData
      });
      const accounts: PensionAccount[] = (data?.accounts || []).map((acc: PensionAccount) => ({
        ...acc,
        selected: false,
        selected_amounts: acc.selected_amounts || {}
      }));

      if (accounts.length > 0) {
        setPensionData(accounts);
        localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(accounts));
        setProcessingStatus(`הושלם עיבוד ${accounts.length} חשבונות פנסיוניים`);
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

  // פונקציה לסימון/ביטול סימון חשבון
  const toggleAccountSelection = (index: number) => {
    setPensionData(prev => prev.map((account, i) => {
      if (i === index) {
        const newSelected = !account.selected;
        return { 
          ...account, 
          selected: newSelected,
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
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(pensionData));
      setProcessingStatus(`✅ נשמרו בהצלחה ${selectedAccounts.length} תכניות בתיק הפנסיוני!`);
      
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
      if (account.saved_fund_id && clientId) {
        await apiFetch(`/clients/${clientId}/pension-funds/${account.saved_fund_id}`, {
          method: 'DELETE'
        });
        setProcessingStatus("תכנית נמחקה מהמערכת ומהרשימה");
      } else {
        setProcessingStatus("תכנית נמחקה מהרשימה");
      }

      const updatedData = pensionData.filter((_, i) => i !== accountIndex);
      setPensionData(updatedData);
      
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
          if (['יתרה', 'תגמולים', 'פיצויים_מעסיק_נוכחי', 'פיצויים_לאחר_התחשבנות', 'פיצויים_שלא_עברו_התחשבנות',
               'פיצויים_ממעסיקים_קודמים_רצף_זכויות', 'פיצויים_ממעסיקים_קודמים_רצף_קצבה',
               'תגמולי_עובד_עד_2000', 'תגמולי_עובד_אחרי_2000', 'תגמולי_עובד_אחרי_2008_לא_משלמת',
               'תגמולי_מעביד_עד_2000', 'תגמולי_מעביד_אחרי_2000', 'תגמולי_מעביד_אחרי_2008_לא_משלמת'].includes(field)) {
            updatedAcc = { ...acc, [field]: parseFloat(value) || 0 };
          } else {
            updatedAcc = { ...acc, [field]: value };
          }
          return updatedAcc;
        }
        return acc;
      });
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(updated));
      return updated;
    });
    setEditingCell(null);
  };

  // פונקציה להוספת תכנית ידנית
  const addManualAccount = () => {
    const name = prompt('שם התכנית:');
    if (!name) return;
    
    const balance = prompt('יתרה:', '0');
    if (balance === null) return;
    
    const startDate = prompt('תאריך התחלה (DD/MM/YYYY):', formatDateToDDMMYY(new Date()));
    if (startDate === null) return;
    
    const productType = prompt('סוג מוצר (קרן השתלמות / קופת גמל):', 'קופת גמל');
    if (productType === null) return;
    
    const baseAccount: PensionAccount = {
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

  // פונקציה להגדרת סוג המרה
  const setConversionType = (index: number, type: 'pension' | 'capital_asset') => {
    setConversionTypes(prev => ({
      ...prev,
      [index]: type
    }));
  };

  // פונקציה לטעינת נתונים קיימים מ-localStorage
  const loadExistingData = async () => {
    try {
      const savedData = localStorage.getItem(`pensionData_${clientId}`);
      const savedConvertedAccounts = localStorage.getItem(`convertedAccounts_${clientId}`);
      
      if (savedData) {
        const parsedData = JSON.parse(savedData);
        const dataWithComputed = parsedData.map((acc: PensionAccount) => calculateInitialTagmulim(acc));
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

  // טעינה מחדש כשחוזרים לדף
  useEffect(() => {
    const handleFocus = () => {
      console.log('Window focused, checking for updates...');
      const savedData = localStorage.getItem(`pensionData_${clientId}`);
      if (savedData) {
        const parsedData = JSON.parse(savedData);
        const dataWithComputed = parsedData.map((acc: PensionAccount) => calculateInitialTagmulim(acc));
        setPensionData(dataWithComputed);
      }
    };
    
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log('Page became visible, checking for updates...');
        const savedData = localStorage.getItem(`pensionData_${clientId}`);
        if (savedData) {
          const parsedData = JSON.parse(savedData);
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

  return {
    pensionData,
    setPensionData,
    loading,
    setLoading,
    error,
    setError,
    selectedFiles,
    setSelectedFiles,
    processingStatus,
    setProcessingStatus,
    saving,
    convertedAccounts,
    setConvertedAccounts,
    conversionTypes,
    setConversionTypes,
    clientData,
    editingCell,
    setEditingCell,
    showConversionRules,
    setShowConversionRules,
    redemptionDate,
    setRedemptionDate,
    processXMLFiles,
    toggleAccountSelection,
    toggleAllAccountsSelection,
    updateSelectedAmount,
    saveSelectedAccounts,
    deleteAccount,
    updateCellValue,
    addManualAccount,
    toggleAmountSelection,
    setConversionType
  };
}
