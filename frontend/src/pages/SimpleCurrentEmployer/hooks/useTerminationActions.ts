/**
 * Custom hook for termination actions (submit, delete)
 */

import { useState } from 'react';
import axios from 'axios';
import { SimpleEmployer, TerminationDecision } from '../types';
import { convertDDMMYYToISO } from '../../../utils/dateUtils';
import {
  saveSeveranceDistribution,
  clearSeveranceFromPension,
  restoreSeveranceToPension,
  setTerminationConfirmed,
  clearTerminationState
} from '../utils/storageHelpers';

export const useTerminationActions = (
  clientId: string | undefined,
  employer: SimpleEmployer,
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
      
      const response = await axios.post(`/api/v1/clients/${clientId}/current-employer/termination`, payload);
      
      console.log('✅ TERMINATION RESPONSE:', JSON.stringify(response.data, null, 2));

      // Clear severance from pension portfolio
      clearSeveranceFromPension(clientId);

      // Update local state to freeze form
      setTerminationDecision(prev => ({ ...prev, confirmed: true }));

      // Save confirmed state to localStorage
      setTerminationConfirmed(clientId, true);

      alert('החלטות עזיבה נשמרו בהצלחה והנתונים הוקפאו');
      
      // Reload page to show delete button
      window.location.reload();
      
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
      const response = await axios.delete(`/api/v1/clients/${clientId}/delete-termination`);
      
      console.log('✅ DELETE RESPONSE:', response.data);
      
      // Restore severance to pension portfolio
      console.log('🔄 מחזיר פיצויים לתיק פנסיוני');
      const severanceToRestore = restoreSeveranceToPension(clientId);

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

      alert(`החלטות העזיבה נמחקו בהצלחה!\n- נמחקו ${response.data.deleted_count} אלמנטים\n- הוחזרו ${severanceToRestore.toLocaleString()} ₪ לתיק הפנסיוני`);
      
      // Reload page
      window.location.reload();
      
      setLoading(false);
    } catch (err: any) {
      console.error('❌ DELETE TERMINATION ERROR:', err);
      console.error('Error details:', {
        status: err.response?.status,
        data: err.response?.data,
        detail: err.response?.data?.detail
      });
      
      let errorMessage = 'שגיאה לא ידועה';
      if (err.response?.data?.detail) {
        if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else if (err.response.data.detail.error) {
          errorMessage = err.response.data.detail.error;
        } else {
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError('שגיאה במחיקת החלטות עזיבה: ' + errorMessage);
      alert('שגיאה במחיקת החלטות עזיבה: ' + errorMessage);
      setLoading(false);
    }
  };

  return {
    handleTerminationSubmit,
    handleDeleteTermination
  };
};
