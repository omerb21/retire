/**
 * Custom hook for termination actions (submit, delete)
 */

import { apiFetch } from '../../../lib/api';
import { SimpleEmployer, TerminationDecision } from '../types';
import { convertDDMMYYToISO } from '../../../utils/dateUtils';
import { formatCurrency } from '../../../lib/validation';
import {
  saveSeveranceDistribution,
  clearSeveranceFromPension,
  restoreSeveranceToPension,
  setTerminationConfirmed,
  clearTerminationState
} from '../utils/storageHelpers';

const isNotFoundError = (err: unknown): boolean => {
  const message = (err as any)?.message?.toString() || '';
  return message.includes('404') || message.includes('Not Found') || message.includes('לא נמצא');
};

export const useTerminationActions = (
  clientId: string | undefined,
  employer: SimpleEmployer,
  setEmployer: React.Dispatch<React.SetStateAction<SimpleEmployer>>,
  terminationDecision: TerminationDecision,
  setTerminationDecision: React.Dispatch<React.SetStateAction<TerminationDecision>>,
  setLoading: (loading: boolean) => void,
  setError: (error: string | null) => void
) => {
  const handleTerminationSubmit = async (): Promise<void> => {
    if (!clientId) return;
    
    try {
      setLoading(true);
      setError(null);

      // Save severance distribution before termination
      const { sourceAccountNames, planDetails } = saveSeveranceDistribution(clientId);

      const terminationDateISO = convertDDMMYYToISO(employer.end_date || '') || employer.end_date;
      
      const payload = {
        ...terminationDecision,
        termination_date: terminationDateISO,
        confirmed: true,
        source_accounts: sourceAccountNames.length > 0 ? JSON.stringify(sourceAccountNames) : null,
        plan_details: planDetails.length > 0 ? JSON.stringify(planDetails) : null
      };
      
      console.log('🚀 SENDING TERMINATION PAYLOAD:', JSON.stringify(payload, null, 2));

      const response = await apiFetch<any>(`/clients/${clientId}/current-employer/termination`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      console.log('✅ TERMINATION RESPONSE:', JSON.stringify(response, null, 2));

      // Clear severance from pension portfolio
      clearSeveranceFromPension(clientId);

      // Update local state to freeze form
      setTerminationDecision(prev => ({ ...prev, confirmed: true }));

      // Save confirmed state to localStorage
      setTerminationConfirmed(clientId, true);

      alert('החלטות עזיבה נשמרו בהצלחה והנתונים הוקפאו');
      
      // Reload page to show delete button
      
      setLoading(false);
    } catch (err: any) {
      console.error('❌ TERMINATION ERROR:', err);
      setError('שגיאה בשמירת החלטות עזיבה: ' + err.message);
      setLoading(false);
    }
  };

  const handleDeleteTermination = async (): Promise<void> => {
    if (!clientId) return;
    
    if (!confirm('האם אתה בטוח שברצונך למחוק את החלטות העזיבה? פעולה זו תמחק את כל המענקים, הקצבאות ונכסי ההון שנוצרו מהעזיבה, ותחזיר את יתרת הפיצויים לתיק הפנסיוני.')) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Delete termination decisions from server
      const response = await apiFetch<{ deleted_count: number }>(`/clients/${clientId}/delete-termination`, {
        method: 'DELETE'
      });
      
      console.log('✅ DELETE RESPONSE:', response);
      
      // Restore severance to pension portfolio
      console.log('🔄 מחזיר פיצויים לתיק פנסיוני');
      const severanceToRestore = restoreSeveranceToPension(clientId);

      // Clear employer end_date in local state so UI doesn't think termination still exists
      setEmployer(prev => ({
        ...prev,
        end_date: undefined
      }));

      // Reset local state
      setTerminationDecision({
        termination_date: '',
        use_employer_completion: false,
        severance_amount: 0,
        exempt_amount: 0,
        taxable_amount: 0,
        exempt_choice: 'redeem_with_exemption',
        taxable_choice: 'redeem_no_exemption',
        tax_spread_years: 0,
        max_spread_years: 0,
        confirmed: false
      });

      // Clear termination state from localStorage
      clearTerminationState(clientId);

      alert(`החלטות העזיבה נמחקו בהצלחה!\n- נמחקו ${response.deleted_count} אלמנטים\n- הוחזרו ${formatCurrency(severanceToRestore)} לתיק הפנסיוני`);
      
      // Reload page
      
      setLoading(false);
    } catch (err: any) {
      console.error('❌ DELETE TERMINATION ERROR:', err);
      const errorMessage = err?.message || 'שגיאה לא ידועה';
      setError('שגיאה במחיקת החלטות עזיבה: ' + errorMessage);
      alert('שגיאה במחיקת החלטות עזיבה: ' + errorMessage);
      setLoading(false);
    }
  };

  const handleClearAllState = async (): Promise<void> => {
    if (!clientId) return;

    if (!confirm('האם אתה בטוח שברצונך לנקות את כל הנתונים של המעסיק הנוכחי?\nפעולה זו תמחק את עזיבת העבודה (אם קיימת), את כל המענקים/הקצבאות/נכסי ההון שנוצרו ממנה, תחזיר פיצויים לתיק הפנסיוני ותמחק גם את נתוני המעסיק הנוכחי עצמו.')) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      let severanceToRestore = 0;

      // מחיקת עזיבת עבודה והישויות שנוצרו ממנה (אם קיימות)
      try {
        const response = await apiFetch<any>(`/clients/${clientId}/delete-termination`, {
          method: 'DELETE'
        });
        console.log('✅ CLEAR STATE - DELETE TERMINATION RESPONSE:', response);

        console.log('🔄 CLEAR STATE - מחזיר פיצויים לתיק פנסיוני');
        severanceToRestore = restoreSeveranceToPension(clientId);
      } catch (err: any) {
        console.error('❌ CLEAR STATE - ERROR DELETING TERMINATION:', err);
        // אם אין עזיבה שמורה (404) נמשיך בכל זאת לנקות את נתוני המעסיק
        if (!isNotFoundError(err)) {
          throw err;
        }
      }

      // מחיקת רשומת המעסיק הנוכחי מהשרת (אם קיימת)
      try {
        if (employer?.id) {
          await apiFetch<void>(`/clients/${clientId}/current-employer/${employer.id}`, {
            method: 'DELETE'
          });
          console.log('✅ CLEAR STATE - Current employer deleted');
        }
      } catch (err) {
        console.error('❌ CLEAR STATE - ERROR DELETING CURRENT EMPLOYER:', err);
        // לא נעצור את כל התהליך בגלל כישלון במחיקת המעסיק, רק נדווח בלוג
      }

      // איפוס סטייט של המעסיק בצד הקליינט
      setEmployer({
        employer_name: '',
        start_date: '',
        last_salary: 0,
        severance_accrued: 0
      });

      // איפוס סטייט של החלטת העזיבה
      setTerminationDecision({
        termination_date: '',
        use_employer_completion: false,
        severance_amount: 0,
        exempt_amount: 0,
        taxable_amount: 0,
        exempt_choice: 'redeem_with_exemption',
        taxable_choice: 'redeem_no_exemption',
        tax_spread_years: 0,
        max_spread_years: 0,
        confirmed: false
      });

      // ניקוי מצב העזיבה מה-localStorage
      clearTerminationState(clientId);

      const severanceMsg = severanceToRestore ? `\nהוחזרו ${formatCurrency(severanceToRestore)} לתיק הפנסיוני (אם היו פיצויים שנמשכו).` : '';
      alert('מצב המעסיק הנוכחי נוקה בהצלחה.\nנמחקו נתוני עזיבת העבודה (אם היו) ופרטי המעסיק הנוכחי.' + severanceMsg);

      setLoading(false);
    } catch (err: any) {
      console.error('❌ CLEAR CURRENT EMPLOYER STATE ERROR:', err);

      const errorMessage = err?.message || 'שגיאה לא ידועה';

      setError('שגיאה בניקוי מצב המעסיק הנוכחי: ' + errorMessage);
      alert('שגיאה בניקוי מצב המעסיק הנוכחי: ' + errorMessage);
      setLoading(false);
    }
  };

  return {
    handleTerminationSubmit,
    handleDeleteTermination,
    handleClearAllState
  };
};
