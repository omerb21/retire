import { PensionAccount } from '../types';

const getPensionStorageKey = (clientId: string | undefined): string => {
  return `pensionData_${clientId}`;
};

const getConvertedAccountsStorageKey = (clientId: string | undefined): string => {
  return `convertedAccounts_${clientId}`;
};

const BALANCE_ZERO_EPSILON = 0.01;

const PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION = new Set<string>([
  'פיצויים_מעסיק_נוכחי',
  'פיצויים_שלא_עברו_התחשבנות',
  'פיצויים_ממעסיקים_קודמים_רצף_זכויות',
]);

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

export type PensionPortfolioConversionUpdate = {
  account_number: string;
  converted_amount: number;
  specific_amounts?: Record<string, number> | null;
  account_name?: string;
  company?: string;
};

export function applyConversionUpdatesToPensionPortfolio(
  clientId: string | undefined,
  updates: PensionPortfolioConversionUpdate[],
): void {
  if (!clientId) {
    return;
  }

  if (!Array.isArray(updates) || updates.length === 0) {
    return;
  }

  updatePensionDataInStorage(clientId, (data) => {
    const updated = [...data];

    const computeRemainingBalanceFromComponents = (account: any): number => {
      if (!account || typeof account !== 'object') {
        return 0;
      }
      let sum = 0;
      let sawComponent = false;
      Object.keys(account).forEach((field) => {
        if (
          field.startsWith('תגמולי_') ||
          field.startsWith('פיצויים_') ||
          field === 'קרן_השתלמות'
        ) {
          sawComponent = true;
          const v = Number((account as any)[field] ?? 0) || 0;
          if (v > 0) {
            sum += v;
          }
        }
      });
      if (!sawComponent) {
        return 0;
      }
      return sum;
    };

    updates.forEach((u) => {
      const accountNumber = String(u.account_number || '').trim();
      if (!accountNumber) {
        return;
      }

      const idx = updated.findIndex((acc) => String(acc.מספר_חשבון || '').trim() === accountNumber);
      if (idx === -1) {
        return;
      }

      const account = { ...updated[idx] } as any;

      const specific = u.specific_amounts && typeof u.specific_amounts === 'object'
        ? u.specific_amounts
        : null;

      const hasSpecific = !!(specific && Object.keys(specific).length > 0);

      if (hasSpecific) {
        Object.keys(specific).forEach((field) => {
          if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
            return;
          }
          const rawDelta = (specific as any)[field];
          const delta = Number(rawDelta ?? 0) || 0;
          if (delta <= 0) {
            return;
          }
          const currentVal = Number(account[field] ?? 0) || 0;
          const remaining = Math.max(0, currentVal - delta);
          account[field] = Math.abs(remaining) < BALANCE_ZERO_EPSILON ? 0 : remaining;
        });

        const eduDelta = Number((specific as any).קרן_השתלמות ?? 0) || 0;
        if (eduDelta > 0) {
          Object.keys(account).forEach((field) => {
            if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
              return;
            }
            if (
              field.startsWith('תגמולי_') ||
              field === 'תגמולים' ||
              field === 'סך_תגמולים' ||
              field === 'קרן_השתלמות'
            ) {
              account[field] = 0;
            }
          });
          account.יתרה = 0;
        }
      }

      const originalBalance = Number(account.יתרה ?? 0) || 0;
      const convertedAmount = Number(u.converted_amount ?? 0) || 0;
      if (hasSpecific) {
        const remainingFromComponents = computeRemainingBalanceFromComponents(account);
        if (remainingFromComponents > 0 || convertedAmount > 0) {
          account.יתרה = remainingFromComponents;
        }
      } else {
        if (convertedAmount > 0) {
          account.יתרה = Math.max(0, originalBalance - convertedAmount);
        }
      }

      if (Math.abs(Number(account.יתרה ?? 0) || 0) < BALANCE_ZERO_EPSILON) {
        account.יתרה = 0;
      }

      if (!hasSpecific && Number(account.יתרה ?? 0) === 0) {
        Object.keys(account).forEach((field) => {
          if (PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION.has(field)) {
            return;
          }
          if (
            field.startsWith('תגמולי_') ||
            field.startsWith('פיצויים_') ||
            field === 'תגמולים' ||
            field === 'סך_תגמולים' ||
            field === 'סך_פיצויים' ||
            field === 'סך_רכיבים' ||
            field === 'קרן_השתלמות'
          ) {
            account[field] = 0;
          }
        });
      }

      account.selected = false;
      account.selected_amounts = {};

      updated[idx] = account;
    });

    return updated;
  });

  try {
    const convertedAccounts = loadConvertedAccountsFromStorage(clientId);
    updates.forEach((u) => {
      const accountNumber = String(u.account_number || '').trim();
      if (!accountNumber) {
        return;
      }
      const name = String(u.account_name || '').trim();
      const company = String(u.company || '').trim();
      convertedAccounts.add(`${accountNumber}_${name}_${company}`);
    });
    saveConvertedAccountsToStorage(clientId, convertedAccounts);
  } catch (error) {
    console.error('Failed to persist converted accounts after conversion updates', error);
  }

  try {
    window.dispatchEvent(new Event('storage'));
  } catch {
    // ignore
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
