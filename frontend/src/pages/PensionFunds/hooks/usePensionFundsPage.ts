import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { PensionFund, Commutation } from '../types';
import { formatCurrency } from '../../../lib/validation';
import {
  loadPensionFunds,
  loadClientData,
  computePensionFund,
  deletePensionFund,
  deleteCommutation,
  updatePensionFund,
} from '../api';
import {
  handleSubmitPensionFund,
  handleCommutationSubmitLogic,
  recalculateClientPensionStartDate,
  restorePensionFromCommutation,
} from '../handlers';
import { restoreBalanceToPensionPortfolio } from '../../PensionPortfolio/services/pensionPortfolioStorageService';

export const usePensionFundsPage = () => {
  const { id: clientId } = useParams<{ id: string }>();

  const [funds, setFunds] = useState<PensionFund[]>([]);
  const [commutations, setCommutations] = useState<Commutation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [clientData, setClientData] = useState<any>(null);
  const [editingFundId, setEditingFundId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<PensionFund>>({
    fund_name: '',
    calculation_mode: 'calculated',
    balance: 0,
    annuity_factor: 0,
    indexation_method: 'none',
    indexation_rate: 0,
    deduction_file: '',
    pension_start_date: '',
    tax_treatment: 'taxable',
  });
  const [commutationForm, setCommutationForm] = useState<Commutation>({
    pension_fund_id: undefined,
    exempt_amount: 0,
    commutation_date: '',
    commutation_type: 'taxable',
  });

  useEffect(() => {
    if (commutationForm.pension_fund_id) {
      const selectedFund = funds.find(
        (f) => f.id === commutationForm.pension_fund_id,
      );
      if (selectedFund?.tax_treatment === 'exempt') {
        setCommutationForm((prev) => ({ ...prev, commutation_type: 'exempt' }));
      }
    }
  }, [commutationForm.pension_fund_id, funds]);

  async function loadFunds() {
    if (!clientId) return;

    setLoading(true);
    setError('');

    try {
      const { funds: loadedFunds, commutations: loadedCommutations } =
        await loadPensionFunds(clientId);
      setFunds(loadedFunds);
      setCommutations(loadedCommutations);
    } catch (e: any) {
      setError(e?.message || e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!clientId) return;

    const fetchClientData = async () => {
      try {
        const data = await loadClientData(clientId);
        setClientData(data);
      } catch (error) {
        console.error('Error fetching client data:', error);
      }
    };

    fetchClientData();
    loadFunds();
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError('');

    try {
      await handleSubmitPensionFund(
        clientId,
        form,
        editingFundId,
        funds,
        clientData,
      );

      setForm({
        fund_name: '',
        calculation_mode: 'calculated',
        balance: 0,
        annuity_factor: 0,
        indexation_method: 'none',
        indexation_rate: 0,
        deduction_file: '',
        pension_start_date: '',
      });

      setEditingFundId(null);
      await loadFunds();
    } catch (e: any) {
      setError(`שגיאה ביצירת קצבה: ${e?.message || e}`);
    }
  }

  async function handleCompute(fundId: number) {
    if (!clientId) return;

    try {
      const fund = funds.find((f) => f.id === fundId);
      if (!fund) {
        throw new Error('קרן לא נמצאה');
      }

      const balance = fund.current_balance || fund.balance || 0;
      const factor = fund.annuity_factor || 0;

      if (balance <= 0 || factor <= 0) {
        throw new Error('יתרה ומקדם קצבה חייבים להיות חיוביים');
      }

      await computePensionFund(clientId, fundId);
      await loadFunds();
    } catch (e: any) {
      console.error('Compute error:', e);
      setError(`שגיאה בחישוב: ${e?.message || e}`);
    }
  }

  async function handleDeleteAll() {
    if (!clientId) return;

    const totalItems = funds.length + commutations.length;

    if (totalItems === 0) {
      alert('אין קצבאות או היוונים למחיקה');
      return;
    }

    if (
      !confirm(
        `האם אתה בטוח שברצונך למחוק את כל ${funds.length} הקצבאות ו-${commutations.length} ההיוונים? פעולה זו בלתי הפיכה!`,
      )
    ) {
      return;
    }

    try {
      setError('');

      const commutationsSnapshot = [...commutations];
      for (const commutation of commutationsSnapshot) {
        if (commutation.id) {
          await handleCommutationDelete(commutation.id, {
            skipConfirm: true,
            suppressAlert: true,
          });
        }
      }

      const fundsSnapshot = [...funds];
      for (const fund of fundsSnapshot) {
        if (fund.id) {
          await handleDelete(fund.id, { skipConfirm: true, suppressAlert: true });
        }
      }

      await loadFunds();
      alert(
        `נמחקו ${funds.length} קצבאות ו-${commutations.length} היוונים בהצלחה`,
      );
    } catch (e: any) {
      setError(`שגיאה במחיקה: ${e?.message || e}`);
    }
  }

  async function handleDelete(
    fundId: number,
    options?: { skipConfirm?: boolean; suppressAlert?: boolean },
  ) {
    if (!clientId) return;

    if (!options?.skipConfirm) {
      if (!confirm('האם אתה בטוח שברצונך למחוק את הקצבה?')) {
        return;
      }
    }

    try {
      const fund = funds.find((f) => f.id === fundId);

      const relatedCommutations = commutations.filter(
        (c) => c.pension_fund_id === fundId,
      );
      if (relatedCommutations.length > 0) {
        console.log(
          `🗑️ Deleting ${relatedCommutations.length} commutations linked to pension fund ${fundId}`,
        );
        for (const commutation of relatedCommutations) {
          if (commutation.id) {
            await deleteCommutation(clientId, commutation.id);
            console.log(`✅ Deleted commutation ${commutation.id}`);
          }
        }
      }

      const deleteResponse = await deletePensionFund(clientId, fundId);

      if (!options?.suppressAlert) {
        alert(
          `🔥 NEW CODE LOADED! Response: ${JSON.stringify(
            deleteResponse,
          ).substring(0, 200)}`,
        );
      }
      console.log('🗑️ Delete response:', JSON.stringify(deleteResponse, null, 2));
      console.log('🔍 Restoration object:', deleteResponse?.restoration);
      console.log('🔍 Restoration reason:', deleteResponse?.restoration?.reason);

      if (
        deleteResponse?.restoration &&
        deleteResponse.restoration.reason === 'pension_portfolio'
      ) {
        const accountNumber = deleteResponse.restoration.account_number;
        const balanceToRestore = deleteResponse.restoration.balance_to_restore;

        console.log(
          `📋 ✅ RESTORING ₪${balanceToRestore} to account ${accountNumber}`,
        );
        console.log(
          '🔍 Specific amounts to restore:',
          deleteResponse.restoration.specific_amounts,
        );

        restoreBalanceToPensionPortfolio(clientId, {
          account_number: accountNumber,
          balance_to_restore: balanceToRestore,
          specific_amounts: deleteResponse.restoration.specific_amounts,
        });
      }

      await loadFunds();

      try {
        await recalculateClientPensionStartDate(clientId);
      } catch (updateError) {
        console.error('שגיאה בעדכון תאריך הקצבה הראשונה:', updateError);
      }
    } catch (e: any) {
      setError(`שגיאה במחיקת קצבה: ${e?.message || e}`);
    }
  }

  function handleEdit(fund: PensionFund) {
    setEditingFundId(fund.id || null);

    setForm({
      fund_name: fund.fund_name || '',
      calculation_mode: fund.input_mode || fund.calculation_mode || 'calculated',
      balance: fund.balance || 0,
      annuity_factor: fund.annuity_factor || 0,
      monthly_amount: fund.pension_amount || fund.monthly_amount || 0,
      indexation_method: fund.indexation_method || 'none',
      indexation_rate: fund.fixed_index_rate || fund.indexation_rate || 0,
      deduction_file: fund.deduction_file || '',
      pension_start_date: fund.pension_start_date || fund.start_date || '',
      tax_treatment: fund.tax_treatment || 'taxable',
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function handleCancelEdit() {
    setEditingFundId(null);
    setForm({
      fund_name: '',
      calculation_mode: 'calculated',
      balance: 0,
      annuity_factor: 0,
      indexation_method: 'none',
      indexation_rate: 0,
      deduction_file: '',
      pension_start_date: '',
      tax_treatment: 'taxable',
    });
  }

  async function handleCommutationSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError('');

    try {
      const { shouldDeleteFund, fundBalance, createdAsset } =
        await handleCommutationSubmitLogic(clientId, commutationForm, funds);

      const selectedFund = funds.find(
        (f) => f.id === commutationForm.pension_fund_id,
      );
      if (selectedFund) {
        const newCommutableBalance =
          fundBalance - (commutationForm.exempt_amount || 0);
        const annuityFactor = selectedFund.annuity_factor || 200;
        const safeNewBalance = Math.max(0, newCommutableBalance);
        const newMonthlyAmount =
          safeNewBalance > 0
            ? Math.round(safeNewBalance / annuityFactor)
            : 0;

        setFunds(
          funds.map((f) =>
            f.id === commutationForm.pension_fund_id
              ? {
                  ...f,
                  balance: safeNewBalance,
                  commutable_balance: safeNewBalance,
                  pension_amount: newMonthlyAmount,
                  monthly: newMonthlyAmount,
                }
              : f,
          ),
        );
      }

      const newCommutation: Commutation = {
        id: (createdAsset as any).id,
        pension_fund_id: commutationForm.pension_fund_id,
        exempt_amount: commutationForm.exempt_amount,
        commutation_date: commutationForm.commutation_date,
        commutation_type: commutationForm.commutation_type,
      };

      setCommutations([...commutations, newCommutation]);
      await loadFunds();

      setCommutationForm({
        pension_fund_id: undefined,
        exempt_amount: 0,
        commutation_date: '',
        commutation_type: 'taxable',
      });

      const remaining = fundBalance - (commutationForm.exempt_amount || 0);
      alert(
        `היוון נוצר בהצלחה!\n` +
          (shouldDeleteFund
            ? 'הקצבה הומרה במלואה – יתרת הקצבה כעת 0. ניתן למחוק את ההיוון כדי להחזיר את הקצבה.'
            : `נותרה יתרה של ${formatCurrency(remaining)}`),
      );
    } catch (e: any) {
      setError(`שגיאה ביצירת היוון: ${e?.message || e}`);
    }
  }

  async function handleCommutationDelete(
    commutationId: number,
    options?: { skipConfirm?: boolean; suppressAlert?: boolean },
  ) {
    if (!clientId) return;

    if (!options?.skipConfirm) {
      if (
        !confirm(
          'האם אתה בטוח שברצונך למחוק את ההיוון? היתרה תוחזר לקצבה.',
        )
      ) {
        return;
      }
    }

    try {
      const commutationToDelete = commutations.find(
        (c) => c.id === commutationId,
      );
      if (!commutationToDelete) {
        throw new Error('היוון לא נמצא');
      }

      const relatedFund = funds.find(
        (f) => f.id === commutationToDelete.pension_fund_id,
      );

      if (!relatedFund) {
        await restorePensionFromCommutation(clientId, commutationToDelete);

        await deleteCommutation(clientId, commutationId);

        setCommutations(commutations.filter((c) => c.id !== commutationId));

        await loadFunds();

        if (!options?.suppressAlert) {
          alert(
            'ההיוון נמחק והקצבה שוחזרה כקצבה חדשה במערכת מתוך נתוני ההיוון.',
          );
        }

        return;
      }

      const currentBalance = relatedFund.balance || 0;
      const commutationAmount = commutationToDelete.exempt_amount || 0;
      const newBalance = currentBalance + commutationAmount;

      const annuityFactor = relatedFund.annuity_factor || 200;
      const newMonthlyAmount = Math.round(newBalance / annuityFactor);

      await updatePensionFund(relatedFund.id!, {
        fund_name: relatedFund.fund_name,
        fund_type: relatedFund.fund_type,
        input_mode: relatedFund.input_mode,
        balance: newBalance,
        pension_amount: newMonthlyAmount,
        annuity_factor: annuityFactor,
        pension_start_date: relatedFund.pension_start_date,
        indexation_method: relatedFund.indexation_method || 'none',
      });

      await deleteCommutation(clientId, commutationId);

      setCommutations(commutations.filter((c) => c.id !== commutationId));

      setFunds(
        funds.map((f) =>
          f.id === relatedFund.id
            ? {
                ...f,
                balance: newBalance,
                commutable_balance: newBalance,
                pension_amount: newMonthlyAmount,
                monthly: newMonthlyAmount,
              }
            : f,
        ),
      );

      if (!options?.suppressAlert) {
        alert(
          `ההיוון נמחק בהצלחה!\nהיתרה הוחזרה לקצבה: ${formatCurrency(
            newBalance,
          )}\nקצבה חודשית חדשה: ${formatCurrency(newMonthlyAmount)}`,
        );
      }
    } catch (e: any) {
      setError(`שגיאה במחיקת היוון: ${e?.message || e}`);
    }
  }

  return {
    clientId,
    loading,
    error,
    funds,
    commutations,
    clientData,
    form,
    setForm,
    editingFundId,
    commutationForm,
    setCommutationForm,
    handleSubmit,
    handleCompute,
    handleDeleteAll,
    handleEdit,
    handleCancelEdit,
    handleDelete,
    handleCommutationSubmit,
    handleCommutationDelete,
  };
};
