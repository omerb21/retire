import { apiFetch, LlmPensionPortfolioAccount } from "../../lib/api";

import {
  loadPensionDataFromStorage,
  updatePensionDataInStorage,
} from "../PensionPortfolio/services/pensionPortfolioStorageService";

export async function persistPortfolioUpdateToDb(
  clientId: string | undefined,
  updater: (accounts: any[]) => any[],
) {
  if (!clientId) return;

  const portfolio = await apiFetch<any[]>(`/clients/${clientId}/pension-portfolio/`);
  const updated = updater(Array.isArray(portfolio) ? portfolio : []);
  await apiFetch(`/clients/${clientId}/pension-portfolio/save`, {
    method: "POST",
    body: JSON.stringify({ accounts: updated }),
  });
}

export function loadPensionPortfolioForLlm(clientId: string | undefined): LlmPensionPortfolioAccount[] {
  if (!clientId) return [];

  try {
    const rawData = loadPensionDataFromStorage(clientId);
    if (!rawData || rawData.length === 0) return [];

    return rawData.map((account) => ({
      מספר_חשבון: account.מספר_חשבון,
      שם_תכנית: account.שם_תכנית,
      חברה_מנהלת: account.חברה_מנהלת,
      סוג_מוצר: account.סוג_מוצר,
      יתרה: account.יתרה,
      תאריך_התחלה: account.תאריך_התחלה,
      פיצויים_מעסיק_נוכחי: account.פיצויים_מעסיק_נוכחי,
      פיצויים_ממעסיקים_קודמים_רצף_קצבה: account.פיצויים_ממעסיקים_קודמים_רצף_קצבה,
      תגמולי_עובד_עד_2000: account.תגמולי_עובד_עד_2000,
      תגמולי_עובד_אחרי_2000: account.תגמולי_עובד_אחרי_2000,
      תגמולי_מעביד_עד_2000: account.תגמולי_מעביד_עד_2000,
      תגמולי_מעביד_אחרי_2000: account.תגמולי_מעביד_אחרי_2000,
      תגמולים: account.תגמולים,
      סך_תגמולים: account.סך_תגמולים,
      סך_פיצויים: account.סך_פיצויים,
    }));
  } catch (e) {
    console.warn("Failed to load pension portfolio for LLM:", e);
    return [];
  }
}

export function resetSeveranceInPortfolio(clientId: string | undefined) {
  updatePensionDataInStorage(clientId, (accounts) => {
    return accounts.map((acc) => ({
      ...acc,
      פיצויים_מעסיק_נוכחי: 0,
    }));
  });
}
