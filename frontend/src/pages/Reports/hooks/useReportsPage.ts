import { useMemo, useCallback } from 'react';
import { API_BASE } from '../../../lib/api';
import { useReportData } from '../../../components/reports/hooks/useReportData';
import { generateYearlyProjection } from '../../../components/reports/calculations/cashflowCalculations';
import { calculateNPVComparison } from '../../../components/reports/calculations/npvCalculations';
import { generateHTMLReport } from '../utils/htmlReportGenerator';

export function useReportsPage(clientId: string | undefined) {
  const {
    loading,
    error,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    client,
    fixationData,
  } = useReportData(clientId);

  const capitalAssetsWithoutFixation = useMemo(
    () =>
      capitalAssets.map((asset) => {
        if (
          asset &&
          asset.tax_treatment === 'exempt' &&
          typeof asset.remarks === 'string' &&
          asset.remarks.includes('COMMUTATION:')
        ) {
          return {
            ...asset,
            tax_treatment: 'taxable',
          };
        }
        return asset;
      }),
    [capitalAssets]
  );

  const yearlyProjectionWithExemption = useMemo(() => {
    if (!client) {
      return [];
    }

    if (
      pensionFunds.length === 0 &&
      additionalIncomes.length === 0 &&
      capitalAssets.length === 0
    ) {
      return [];
    }

    return generateYearlyProjection(
      pensionFunds,
      additionalIncomes,
      capitalAssets,
      client,
      fixationData,
      false
    );
  }, [pensionFunds, additionalIncomes, capitalAssets, client, fixationData]);

  const yearlyProjectionWithoutExemption = useMemo(() => {
    if (!client) {
      return [];
    }

    if (
      pensionFunds.length === 0 &&
      additionalIncomes.length === 0 &&
      capitalAssets.length === 0
    ) {
      return [];
    }

    return generateYearlyProjection(
      pensionFunds,
      additionalIncomes,
      capitalAssetsWithoutFixation,
      client,
      fixationData,
      true
    );
  }, [
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    capitalAssetsWithoutFixation,
    client,
    fixationData,
  ]);

  const npvComparison = useMemo(() => {
    if (
      yearlyProjectionWithExemption.length === 0 ||
      yearlyProjectionWithoutExemption.length === 0
    ) {
      return null;
    }

    return calculateNPVComparison(
      yearlyProjectionWithExemption,
      yearlyProjectionWithoutExemption,
      0.03,
      fixationData
    );
  }, [yearlyProjectionWithExemption, yearlyProjectionWithoutExemption, fixationData]);

  const totalPensionBalance = useMemo(
    () =>
      pensionFunds.reduce(
        (sum, fund) => sum + (parseFloat(fund.balance) || 0),
        0
      ),
    [pensionFunds]
  );

  const totalMonthlyPension = useMemo(
    () =>
      pensionFunds.reduce(
        (sum, fund) =>
          sum +
          (parseFloat(fund.pension_amount) ||
            parseFloat(fund.computed_monthly_amount) ||
            parseFloat(fund.monthly_amount) ||
            0),
        0
      ),
    [pensionFunds]
  );

  const totalAdditionalIncome = useMemo(
    () =>
      additionalIncomes.reduce((sum, income) => {
        const amount = parseFloat(income.amount) || 0;
        let monthlyAmount = amount;
        if (income.frequency === 'quarterly') monthlyAmount = amount / 3;
        else if (income.frequency === 'annually') monthlyAmount = amount / 12;
        return sum + monthlyAmount;
      }, 0),
    [additionalIncomes]
  );

  const totalCapitalValue = useMemo(
    () =>
      capitalAssets.reduce(
        (sum, asset) => sum + (parseFloat(asset.current_value) || 0),
        0
      ),
    [capitalAssets]
  );

  const totalMonthlyIncome = totalMonthlyPension + totalAdditionalIncome;

  const handleGenerateHTML = useCallback(() => {
    const htmlContent = generateHTMLReport(
      client,
      fixationData,
      yearlyProjectionWithExemption,
      pensionFunds,
      additionalIncomes,
      capitalAssets,
      npvComparison,
      totalPensionBalance,
      totalCapitalValue,
      totalMonthlyIncome
    );

    const reportWindow = window.open('', '_blank');

    if (!reportWindow) {
      alert('יש לאפשר פתיחת חלונות קופצים להצגת הדוח');
      return;
    }

    reportWindow.document.open();
    reportWindow.document.write(htmlContent);
    reportWindow.document.close();
    reportWindow.focus();
  }, [
    client,
    fixationData,
    yearlyProjectionWithExemption,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    npvComparison,
    totalPensionBalance,
    totalCapitalValue,
    totalMonthlyIncome,
  ]);

  const handleGenerateFixationDocuments = useCallback(async () => {
    if (!fixationData || !client) {
      alert('אין נתוני קיבוע זכויות');
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE}/fixation/${client.id}/package`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `מסמכי_קיבוע_${client?.name || 'לקוח'}.zip`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const errorText = await response.text();
        console.error('Server error:', errorText);
        alert('שגיאה בהפקת מסמכי קיבוע: ' + errorText);
      }
    } catch (error) {
      console.error('Error generating fixation documents:', error);
      alert('שגיאה בהפקת מסמכי קיבוע');
    }
  }, [client, fixationData]);

  return {
    loading,
    error,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    client,
    fixationData,
    yearlyProjectionWithExemption,
    npvComparison,
    totalCapitalValue,
    handleGenerateHTML,
    handleGenerateFixationDocuments,
  };
}
