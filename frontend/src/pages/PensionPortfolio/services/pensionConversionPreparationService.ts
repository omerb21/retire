import { PensionAccount } from '../types';
import { validateAccountConversion } from '../../../config/conversionRules';

export type ConversionType = 'pension' | 'capital_asset';

export interface PreparedConversion {
  account: PensionAccount;
  index: number;
  amountToConvert: number;
  specificAmounts: Record<string, number>;
}

export interface PreparedConversionsResult {
  pensionConversions: PreparedConversion[];
  capitalAssetConversions: PreparedConversion[];
  validationErrors: string[];
}

export function preparePensionConversions(
  pensionData: PensionAccount[],
  conversionTypes: Record<number, ConversionType>
): PreparedConversionsResult {
  const pensionConversions: PreparedConversion[] = [];
  const capitalAssetConversions: PreparedConversion[] = [];
  const validationErrors: string[] = [];

  pensionData.forEach((account, index) => {
    const isPensionConversion = conversionTypes[index] === 'pension';
    const isCapitalAssetConversion = conversionTypes[index] === 'capital_asset';

    if (!isPensionConversion && !isCapitalAssetConversion) return;

    const hasDetailedTagmulim =
      (Number((account as any).תגמולי_עובד_עד_2000) || 0) > 0 ||
      (Number((account as any).תגמולי_עובד_אחרי_2000) || 0) > 0 ||
      (Number((account as any).תגמולי_עובד_אחרי_2008_לא_משלמת) || 0) > 0 ||
      (Number((account as any).תגמולי_מעביד_עד_2000) || 0) > 0 ||
      (Number((account as any).תגמולי_מעביד_אחרי_2000) || 0) > 0 ||
      (Number((account as any).תגמולי_מעביד_אחרי_2008_לא_משלמת) || 0) > 0;

    let amountToConvert = 0;
    const specificAmounts: Record<string, number> = {};
    const selectedForValidation: Record<string, boolean> = {};

    if (account.selected) {
      amountToConvert = account.יתרה || 0;

      Object.keys(account).forEach((key) => {
        if (
          typeof (account as any)[key] === 'number' &&
          key !== 'יתרה' &&
          key !== 'סך_תגמולים' &&
          key !== 'סך_פיצויים' &&
          key !== 'סך_רכיבים' &&
          key !== 'פער_יתרה_מול_רכיבים' &&
          !(key === 'תגמולים' && hasDetailedTagmulim)
        ) {
          const fieldAmount = (account as any)[key];
          if (fieldAmount && fieldAmount > 0) {
            specificAmounts[key] = fieldAmount;
            selectedForValidation[key] = true;
          }
        }
      });

      if (Object.keys(selectedForValidation).length === 0) {
        selectedForValidation['יתרה'] = true;
      }
    } else {
      const selectedAmounts = account.selected_amounts || {};
      Object.entries(selectedAmounts).forEach(([key, isSelected]) => {
        if (!isSelected) return;
        if (key === 'תגמולים' && hasDetailedTagmulim) return;

        if ((account as any)[key]) {
          const fieldAmount = parseFloat((account as any)[key]) || 0;
          amountToConvert += fieldAmount;
          specificAmounts[key] = fieldAmount;
          selectedForValidation[key] = true;
        }
      });
    }

    if (amountToConvert > 0) {
      const conversionType: ConversionType = isPensionConversion
        ? 'pension'
        : 'capital_asset';

      const validation = validateAccountConversion(
        account,
        selectedForValidation,
        conversionType
      );

      if (!validation.valid) {
        validationErrors.push(
          `${account.שם_תכנית}: ${validation.errors.join(', ')}`
        );
      } else {
        const prepared: PreparedConversion = {
          account,
          index,
          amountToConvert,
          specificAmounts,
        };

        if (isPensionConversion) {
          pensionConversions.push(prepared);
        } else if (isCapitalAssetConversion) {
          capitalAssetConversions.push(prepared);
        }
      }
    }
  });

  return {
    pensionConversions,
    capitalAssetConversions,
    validationErrors,
  };
}
