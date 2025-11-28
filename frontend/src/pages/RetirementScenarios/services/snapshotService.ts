import { API_BASE, apiFetch } from "../../../lib/api";
import { CapitalAsset } from "../../../types/capitalAsset";
import {
  isTerminationConfirmed,
  restoreSeveranceToPension,
  clearTerminationState,
} from "../../SimpleCurrentEmployer/utils/storageHelpers";
import { loadSnapshotRawFromStorage } from "../../../services/snapshotStorageService";
import {
  loadPensionFunds,
  deleteCommutation,
  deletePensionFund,
  updatePensionFund,
} from "../../PensionFunds/api";
import {
  restorePensionFromCommutation,
  recalculateClientPensionStartDate,
} from "../../PensionFunds/handlers";
import {
  savePensionDataToStorage,
  removePensionDataFromStorage,
  saveConvertedAccountsToStorage,
  removeConvertedAccountsFromStorage,
  restoreBalanceToPensionPortfolio,
} from "../../PensionPortfolio/services/pensionPortfolioStorageService";

export async function restoreSnapshotBeforeScenario(
  clientId: string | undefined,
  setError: (message: string) => void
): Promise<boolean> {
  if (!clientId) {
    setError("מזהה לקוח חסר");
    return false;
  }

  const stored = loadSnapshotRawFromStorage(clientId);

  if (!stored) {
    setError("לא נמצא מצב שמור (snapshot). אנא שמור מצב לפני ביצוע תרחיש.");
    return false;
  }

  let snapshotData: any;
  try {
    snapshotData = JSON.parse(stored);
  } catch (e) {
    console.error("Failed to parse snapshot from localStorage before scenario execution", e);
    setError("שגיאה בקריאת מצב שמור. אנא שמור מצב מחדש לפני ביצוע תרחיש.");
    return false;
  }

  try {
    const systemPassword = window.localStorage.getItem('systemAccessPassword');
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    if (systemPassword) {
      (headers as any)['X-System-Password'] = systemPassword;
    }

    const response = await fetch(`${API_BASE}/clients/${clientId}/snapshot/restore`, {
      method: "POST",
      headers,
      body: JSON.stringify(snapshotData),
    });

    if (!response.ok) {
      let errorMessage = `שגיאה בשחזור מצב לפני ביצוע התרחיש: ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = (errorData as any).detail || errorMessage;
      } catch {
        const textError = await response.text();
        errorMessage = textError || errorMessage;
      }
      setError(errorMessage);
      return false;
    }

    try {
      await response.json();
    } catch {
      // ignore
    }

    const pensionPortfolio = snapshotData.pension_portfolio;
    if (Array.isArray(pensionPortfolio)) {
      savePensionDataToStorage(clientId, pensionPortfolio);
    } else {
      removePensionDataFromStorage(clientId);
    }

    if (snapshotData.converted_accounts) {
      const convertedSet = new Set<string>(
        (Array.isArray(snapshotData.converted_accounts)
          ? snapshotData.converted_accounts
          : [snapshotData.converted_accounts]
        ).map((id: any) => String(id))
      );
      saveConvertedAccountsToStorage(clientId, convertedSet);
    } else {
      removeConvertedAccountsFromStorage(clientId);
    }

    return true;
  } catch (err: any) {
    console.error("Snapshot restore before scenario execution failed:", err);
    setError(err.message || "שגיאה בשחזור מצב לפני ביצוע התרחיש");
    return false;
  }
}

export async function resetStateWithoutSnapshot(
  clientId: string | undefined,
  setError: (message: string) => void
): Promise<boolean> {
  if (!clientId) {
    setError("מזהה לקוח חסר");
    return false;
  }

  try {
    if (isTerminationConfirmed(clientId)) {
      await apiFetch(`/clients/${clientId}/delete-termination`, {
        method: "DELETE",
      });

      restoreSeveranceToPension(clientId);
      clearTerminationState(clientId);
    }

    const { funds, commutations } = await loadPensionFunds(clientId);

    for (const commutation of commutations) {
      if (!commutation.id) {
        continue;
      }

      const relatedFund = funds.find((f) => f.id === commutation.pension_fund_id);

      if (!relatedFund) {
        await restorePensionFromCommutation(clientId, commutation);
        await deleteCommutation(clientId, commutation.id);
        continue;
      }

      const currentBalance = relatedFund.balance || 0;
      const commutationAmount = commutation.exempt_amount || 0;
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
        indexation_method: relatedFund.indexation_method || "none",
      });

      await deleteCommutation(clientId, commutation.id);
    }

    const { funds: fundsAfterCommutations } = await loadPensionFunds(clientId);

    for (const fund of fundsAfterCommutations) {
      if (!fund.id) {
        continue;
      }

      const deleteResponse = await deletePensionFund(clientId, fund.id);
      const restoration = deleteResponse?.restoration;

      if (restoration && restoration.reason === "pension_portfolio") {
        restoreBalanceToPensionPortfolio(clientId, {
          account_number: restoration.account_number,
          balance_to_restore: restoration.balance_to_restore,
          specific_amounts: restoration.specific_amounts,
        });
      }
    }

    try {
      await recalculateClientPensionStartDate(clientId);
    } catch (updateError) {
      console.error(
        "Error updating client pension start date after reset:",
        updateError
      );
    }

    const assets = await apiFetch<CapitalAsset[]>(
      `/clients/${clientId}/capital-assets/`
    );

    for (const asset of assets) {
      if (!asset.id) {
        continue;
      }

      const deleteResponse = await apiFetch<any>(
        `/clients/${clientId}/capital-assets/${asset.id}`,
        {
          method: "DELETE",
        }
      );

      const restoration = deleteResponse?.restoration;
      if (restoration && restoration.reason === "pension_portfolio") {
        restoreBalanceToPensionPortfolio(clientId, {
          account_number: restoration.account_number,
          balance_to_restore: restoration.balance_to_restore,
          specific_amounts: restoration.specific_amounts,
        });
      }
    }

    return true;
  } catch (err: any) {
    console.error("State reset before scenarios failed:", err);
    setError(err.message || "שגיאה באיפוס המצב לפני חישוב תרחישים");
    return false;
  }
}
