import { updatePensionDataInStorage } from "../../PensionPortfolio/services/pensionPortfolioStorageService";

export const clearPensionPortfolioBalancesAfterScenario = (
  clientId: string,
  options?: { includeCurrentEmployerTermination?: boolean }
) => {
  try {
    const includeCurrentEmployerTermination =
      options?.includeCurrentEmployerTermination ?? false;

    const numericFields = [
      "יתרה",
      "פיצויים_מעסיק_נוכחי",
      "פיצויים_לאחר_התחשבנות",
      "פיצויים_שלא_עברו_התחשבנות",
      "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
      "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
      "תגמולי_עובד_עד_2000",
      "תגמולי_עובד_אחרי_2000",
      "תגמולי_עובד_אחרי_2008_לא_משלמת",
      "תגמולי_מעביד_עד_2000",
      "תגמולי_מעביד_אחרי_2000",
      "תגמולי_מעביד_אחרי_2008_לא_משלמת",
      "תגמולים",
    ];

    const summaryFields = [
      "סך_תגמולים",
      "סך_פיצויים",
      "סך_רכיבים",
      "פער_יתרה_מול_רכיבים",
    ];

    updatePensionDataInStorage(clientId, (data) => {
      return data.map((account: any) => {
        const updatedAccount = { ...account };

        numericFields.forEach((field) => {
          if (field === "פיצויים_מעסיק_נוכחי" && !includeCurrentEmployerTermination) {
            return;
          }
          if (field in updatedAccount) {
            updatedAccount[field] = 0;
          }
        });

        summaryFields.forEach((field) => {
          if (field in updatedAccount) {
            updatedAccount[field] = 0;
          }
        });

        updatedAccount.selected = false;
        updatedAccount.selected_amounts = {};

        return updatedAccount;
      });
    });
  } catch (e) {
    console.error("Failed to clear pension portfolio balances after scenario execution", e);
  }
};
