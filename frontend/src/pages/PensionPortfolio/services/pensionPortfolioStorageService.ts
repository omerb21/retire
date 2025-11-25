import { PensionAccount } from '../types';

const getPensionStorageKey = (clientId: string | undefined): string => {
  return `pensionData_${clientId}`;
};

const getConvertedAccountsStorageKey = (clientId: string | undefined): string => {
  return `convertedAccounts_${clientId}`;
};

export function loadPensionDataFromStorage(
  clientId: string | undefined
): PensionAccount[] | null {
  try {
    const savedData = localStorage.getItem(getPensionStorageKey(clientId));
    if (!savedData) {
      return null;
    }

    const parsed = JSON.parse(savedData);
    if (!Array.isArray(parsed)) {
      return null;
    }

    return parsed as PensionAccount[];
  } catch (error) {
    console.error('Failed to load pension data from storage', error);
    return null;
  }
}

export function savePensionDataToStorage(
  clientId: string | undefined,
  data: PensionAccount[]
): void {
  try {
    localStorage.setItem(getPensionStorageKey(clientId), JSON.stringify(data));
  } catch (error) {
    console.error('Failed to save pension data to storage', error);
  }
}

export function removePensionDataFromStorage(
  clientId: string | undefined
): void {
  try {
    localStorage.removeItem(getPensionStorageKey(clientId));
  } catch (error) {
    console.error('Failed to remove pension data from storage', error);
  }
}

export function updatePensionDataInStorage(
  clientId: string | undefined,
  updater: (data: PensionAccount[]) => PensionAccount[]
): void {
  try {
    const current = loadPensionDataFromStorage(clientId);
    if (!current || current.length === 0) {
      return;
    }

    const updated = updater(current);
    savePensionDataToStorage(clientId, updated);
  } catch (error) {
    console.error('Failed to update pension data in storage', error);
  }
}

export function loadConvertedAccountsFromStorage(
  clientId: string | undefined
): Set<string> {
  try {
    const saved = localStorage.getItem(getConvertedAccountsStorageKey(clientId));
    if (!saved) {
      return new Set<string>();
    }

    const parsed = JSON.parse(saved);
    if (Array.isArray(parsed)) {
      return new Set(parsed.map((id) => String(id)));
    }

    return new Set<string>();
  } catch (error) {
    console.error('Failed to load converted accounts from storage', error);
    return new Set<string>();
  }
}

export function saveConvertedAccountsToStorage(
  clientId: string | undefined,
  convertedAccounts: Set<string>
): void {
  try {
    const asArray = Array.from(convertedAccounts);
    localStorage.setItem(
      getConvertedAccountsStorageKey(clientId),
      JSON.stringify(asArray)
    );
  } catch (error) {
    console.error('Failed to save converted accounts to storage', error);
  }
}

export function removeConvertedAccountsFromStorage(
  clientId: string | undefined
): void {
  try {
    localStorage.removeItem(getConvertedAccountsStorageKey(clientId));
  } catch (error) {
    console.error('Failed to remove converted accounts from storage', error);
  }
}

export type PensionRestorationPayload = {
  account_number: string;
  balance_to_restore: number;
  specific_amounts?: Record<string, number>;
};

export function restoreBalanceToPensionPortfolio(
  clientId: string | undefined,
  restoration: PensionRestorationPayload
): void {
  const { account_number, balance_to_restore, specific_amounts } = restoration;

  updatePensionDataInStorage(clientId, (data) => {
    const index = data.findIndex((acc) => acc.מספר_חשבון === account_number);

    if (index === -1) {
      console.warn('Account not found when restoring balance to pension portfolio', {
        clientId,
        account_number,
      });
      return data;
    }

    const account = { ...data[index] } as PensionAccount & Record<string, any>;

    if (specific_amounts && Object.keys(specific_amounts).length > 0) {
      Object.entries(specific_amounts).forEach(([field, amount]) => {
        if (Object.prototype.hasOwnProperty.call(account, field)) {
          const currentValue = parseFloat(String(account[field] ?? 0)) || 0;
          const numericAmount = parseFloat(String(amount)) || 0;
          account[field] = currentValue + numericAmount;
        }
      });
    } else {
      const currentTagmulim = parseFloat(String(account.תגמולים ?? 0)) || 0;
      const restoreBase = Number(balance_to_restore) || 0;
      account.תגמולים = currentTagmulim + restoreBase;
    }

    const restoreAmount = Number(balance_to_restore) || 0;
    if (restoreAmount > 0) {
      const currentBalance = Number(account.יתרה ?? 0) || 0;
      account.יתרה = currentBalance + restoreAmount;
    }

    const updated = [...data];
    updated[index] = account;
    return updated;
  });

  try {
    window.dispatchEvent(new Event('storage'));
  } catch {
    // ignore if window is not available (e.g. during tests)
  }
}
