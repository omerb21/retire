import axios from 'axios';
import { PensionAccount, ConversionSourceData } from '../types';
import { formatCurrency } from '../../../lib/validation';
import { 
  validateAccountConversion, 
  validateComponentConversion,
  calculateTaxTreatment 
} from '../../../config/conversionRules';
import { apiFetch } from '../../../lib/api';

/**
 * Hook ללוגיקת המרת חשבונות פנסיוניים
 */
export function usePensionConversion(
  clientId: string | undefined,
  pensionData: PensionAccount[],
  setPensionData: React.Dispatch<React.SetStateAction<PensionAccount[]>>,
  conversionTypes: Record<number, 'pension' | 'capital_asset'>,
  setConversionTypes: React.Dispatch<React.SetStateAction<Record<number, 'pension' | 'capital_asset'>>>,
  convertedAccounts: Set<string>,
  setConvertedAccounts: React.Dispatch<React.SetStateAction<Set<string>>>,
  setLoading: (loading: boolean) => void,
  setError: (error: string) => void,
  setProcessingStatus: (status: string) => void,
  redemptionDate: string,
  clientData: any
) {
  
  // פונקציה לחישוב תאריך פרישה
  const calculateRetirementDate = async () => {
    if (!clientData?.birth_date) return null;
    
    try {
      const response: any = await apiFetch('/retirement-age/calculate-simple', {
        method: 'POST',
        body: JSON.stringify({
          birth_date: clientData.birth_date,
          gender: clientData.gender
        })
      });
      
      if (response && response.retirement_date) {
        return response.retirement_date;
      }
      
      const birthDate = new Date(clientData.birth_date);
      const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 65 : 67;
      const retirementDate = new Date(birthDate);
      retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
      return retirementDate.toISOString().split('T')[0];
    } catch (error) {
      console.error('Error calculating retirement date:', error);
      const birthDate = new Date(clientData.birth_date);
      const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 65 : 67;
      const retirementDate = new Date(birthDate);
      retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
      return retirementDate.toISOString().split('T')[0];
    }
  };

  // פונקציה להמרת חשבונות נבחרים
  const convertSelectedAccounts = async () => {
    if (!clientId) return;

    const pensionConversions: Array<{account: any, index: number, amountToConvert: number, specificAmounts: any}> = [];
    const capitalAssetConversions: Array<{account: any, index: number, amountToConvert: number, specificAmounts: any}> = [];
    const validationErrors: string[] = [];
    
    pensionData.forEach((account, index) => {
      const isPensionConversion = conversionTypes[index] === 'pension';
      const isCapitalAssetConversion = conversionTypes[index] === 'capital_asset';
      
      if (!isPensionConversion && !isCapitalAssetConversion) return;

      // בדיקה האם קיימים טורי תגמולים מפורטים (עובד/מעביד לפי תקופות)
      const hasDetailedTagmulim = (
        (Number((account as any).תגמולי_עובד_עד_2000) || 0) > 0 ||
        (Number((account as any).תגמולי_עובד_אחרי_2000) || 0) > 0 ||
        (Number((account as any).תגמולי_עובד_אחרי_2008_לא_משלמת) || 0) > 0 ||
        (Number((account as any).תגמולי_מעביד_עד_2000) || 0) > 0 ||
        (Number((account as any).תגמולי_מעביד_אחרי_2000) || 0) > 0 ||
        (Number((account as any).תגמולי_מעביד_אחרי_2008_לא_משלמת) || 0) > 0
      );
      
      let amountToConvert = 0;
      let specificAmounts: any = {};
      let selectedForValidation: any = {};
      
      if (account.selected) {
        // המרה של כל החשבון - משתמשים ביתרה הכללית, אך מפלחים רק לרכיבים הרלוונטיים
        amountToConvert = account.יתרה || 0;
        specificAmounts = {};
        selectedForValidation = {};
        Object.keys(account).forEach(key => {
          if (
            typeof (account as any)[key] === 'number' &&
            key !== 'יתרה' &&
            key !== 'סך_תגמולים' &&
            key !== 'סך_פיצויים' &&
            key !== 'סך_רכיבים' &&
            key !== 'פער_יתרה_מול_רכיבים' &&
            // אם יש פירוט תגמולים, לא נכלול את שדה "תגמולים" הכללי כדי לא לספור פעמיים
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
        // המרה לפי טורים נבחרים (selected_amounts)
        const selectedAmounts = account.selected_amounts || {};
        Object.entries(selectedAmounts).forEach(([key, isSelected]) => {
          if (!isSelected) return;
          // במקרה שקיימים טורי תגמולים מפורטים, נתעלם משדה "תגמולים" כללי גם אם סומן בעבר
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
        const conversionType = isPensionConversion ? 'pension' : 'capital_asset';
        const validation = validateAccountConversion(account, selectedForValidation, conversionType);
        
        if (!validation.valid) {
          validationErrors.push(`${account.שם_תכנית}: ${validation.errors.join(', ')}`);
        } else {
          if (isPensionConversion) {
            pensionConversions.push({account, index, amountToConvert, specificAmounts});
          } else if (isCapitalAssetConversion) {
            capitalAssetConversions.push({account, index, amountToConvert, specificAmounts});
          }
        }
      }
    });

    if (validationErrors.length > 0) {
      setError("שגיאות ולידציה:\n" + validationErrors.join('\n'));
      return;
    }

    if (pensionConversions.length === 0 && capitalAssetConversions.length === 0) {
      setError("אנא בחר לפחות תכנית אחת להמרה ובחר סוג המרה");
      return;
    }

    setLoading(true);
    setError("");

    try {
      let paymentDateISO = '';
      if (redemptionDate && redemptionDate.length === 10) {
        const parts = redemptionDate.split('/');
        if (parts.length === 3) {
          const day = parts[0].padStart(2, '0');
          const month = parts[1].padStart(2, '0');
          const year = parts[2];
          paymentDateISO = `${year}-${month}-${day}`;
        }
      }
      
      if (!paymentDateISO) {
        paymentDateISO = await calculateRetirementDate() || '';
      }

      // טיפול בהמרות לקצבה
      if (pensionConversions.length > 0) {
        for (const conversion of pensionConversions) {
          const {account, amountToConvert, specificAmounts} = conversion;
          
          let conversionDetails = '';
          if (Object.keys(specificAmounts).length > 0) {
            conversionDetails = Object.entries(specificAmounts)
              .map(([key, value]) => `${key}: ${formatCurrency(Number(value))}`)
              .join(', ');
          } else {
            conversionDetails = `כל היתרה: ${formatCurrency(amountToConvert)}`;
          }
          
          const taxTreatment = calculateTaxTreatment(account, specificAmounts, 'pension');
          
          const conversionSourceData: ConversionSourceData = {
            type: 'pension_portfolio',
            account_name: account.שם_תכנית,
            company: account.חברה_מנהלת,
            account_number: account.מספר_חשבון,
            product_type: account.סוג_מוצר,
            amount: amountToConvert,
            specific_amounts: specificAmounts,
            conversion_date: new Date().toISOString(),
            tax_treatment: taxTreatment
          };
          
          let annuityFactor = 200;
          let factorSource = 'default';
          let factorNotes = '';
          
          try {
            let retirementAge = 67;
            if (clientData) {
              const retResponse: any = await apiFetch('/retirement-age/calculate-simple', {
                method: 'POST',
                body: JSON.stringify({
                  birth_date: clientData.birth_date,
                  gender: clientData.gender
                })
              });
              retirementAge = retResponse.retirement_age;
            }

            // עבור גמל להשקעה נשתמש במקדם של קרן פנסיה
            let coefficientProductType = account.סוג_מוצר || 'ביטוח מנהלים';
            const coefficientProductLower = (coefficientProductType || '').toLowerCase();
            if (coefficientProductLower.includes('גמל להשקעה')) {
              coefficientProductType = 'קרן פנסיה';
            }
            
            const coefficientResponse: any = await apiFetch('/annuity-coefficient/calculate', {
              method: 'POST',
              body: JSON.stringify({
                product_type: coefficientProductType,
                start_date: account.תאריך_התחלה || paymentDateISO,
                gender: clientData?.gender || 'זכר',
                retirement_age: retirementAge,
                company_name: account.חברה_מנהלת,
                option_name: null,
                survivors_option: 'תקנוני',
                spouse_age_diff: 0,
                target_year: new Date(paymentDateISO).getFullYear(),
                birth_date: clientData?.birth_date || null,
                pension_start_date: paymentDateISO
              })
            });
            
            annuityFactor = coefficientResponse.factor_value;
            factorSource = coefficientResponse.source_table;
            factorNotes = coefficientResponse.notes || '';
            
            console.log(`[מקדם קצבה] ${account.שם_תכנית}: ${annuityFactor} (מקור: ${factorSource})`);
          } catch (error) {
            console.error(`[מקדם קצבה] שגיאה בחישוב מקדם:`, error);
          }
          
          let fundNamePrefix = '';
          const productType = account.סוג_מוצר || '';
          const productLower = productType.toLowerCase();
          
          if (productLower.includes('קרן פנסיה') || productLower.includes('פנסיה מקיפה') || 
              productLower.includes('פנסיה כללית') || productLower.includes('קופת גמל') || 
              productLower.includes('קרן השתלמות') || productLower.includes('גמל להשקעה')) {
            fundNamePrefix = 'קרן פנסיה שנוצרה מתכנית - ';
          } else {
            fundNamePrefix = 'קצבת ביטוח מנהלים שנוצרה מתכנית - ';
          }
          
          const pensionDataPayload: any = {
            client_id: parseInt(clientId),
            fund_name: fundNamePrefix + (account.שם_תכנית || 'קצבה מתיק פנסיוני'),
            fund_type: 'מחושב',
            input_mode: "manual" as const,
            balance: amountToConvert,
            pension_amount: Math.round(amountToConvert / annuityFactor),
            pension_start_date: paymentDateISO,
            indexation_method: "none" as const,
            tax_treatment: taxTreatment,
            annuity_factor: annuityFactor,
            remarks: `הומר מתיק פנסיוני\nתכנית: ${account.שם_תכנית} (${account.חברה_מנהלת})\nסכומים שהומרו: ${conversionDetails}\nיחס מס: ${taxTreatment === 'exempt' ? 'פטור ממס' : 'חייב במס'}\nמקדם קצבה: ${annuityFactor} (${factorSource})${factorNotes ? '\n' + factorNotes : ''}`,
            conversion_source: JSON.stringify(conversionSourceData),
            deduction_file: account.מספר_חשבון || null
          };
          
          if (pensionDataPayload.fixed_index_rate !== undefined) {
            pensionDataPayload.fixed_index_rate = null;
          }

          await apiFetch(`/clients/${clientId}/pension-funds`, {
            method: 'POST',
            body: JSON.stringify(pensionDataPayload)
          });
        }
        
        console.log('Created', pensionConversions.length, 'separate pension funds');
      }

      // טיפול בהמרות לנכס הון
      if (capitalAssetConversions.length > 0) {
        let totalAssetsCreated = 0;
        
        for (const conversion of capitalAssetConversions) {
          const {account, amountToConvert, specificAmounts} = conversion;
          
          let assetTypeValue = '';
          let assetDescription = '';
          if (account.סוג_מוצר && account.סוג_מוצר.includes('קרן השתלמות')) {
            assetTypeValue = 'education_fund';
            assetDescription = 'קרן השתלמות';
          } else {
            assetTypeValue = 'provident_fund';
            assetDescription = 'קופת גמל';
          }
          
          const exemptComponents: Record<string, number> = {};
          const capitalGainsComponents: Record<string, number> = {};
          
          Object.entries(specificAmounts).forEach(([field, isSelected]) => {
            if (!isSelected || field === 'יתרה') return;
            
            const amount = (account as any)[field] || 0;
            if (amount <= 0) return;
            
            const validation = validateComponentConversion(field, amount, 'capital_asset', account.סוג_מוצר);
            
            if (validation.canConvert) {
              if (validation.taxTreatment === 'exempt') {
                exemptComponents[field] = amount;
              } else if (validation.taxTreatment === 'capital_gains') {
                capitalGainsComponents[field] = amount;
              }
            }
          });
          
          const todayISO = new Date().toISOString().split('T')[0];
          const purchaseDateISO = account.תאריך_התחלה 
            ? (account.תאריך_התחלה.includes('-') ? account.תאריך_התחלה : todayISO)
            : todayISO;
          
          // יצירת נכס הון לסכומים פטורים ממס
          if (Object.keys(exemptComponents).length > 0) {
            const exemptAmount = Object.values(exemptComponents).reduce((sum, val) => sum + val, 0);
            const exemptDetails = Object.entries(exemptComponents)
              .map(([key, value]) => `${key}: ${formatCurrency(value as number)}`)
              .join(', ');
            
            const conversionSourceData: ConversionSourceData = {
              type: 'pension_portfolio',
              account_name: account.שם_תכנית,
              company: account.חברה_מנהלת,
              account_number: account.מספר_חשבון,
              product_type: account.סוג_מוצר,
              amount: exemptAmount,
              specific_amounts: exemptComponents,
              conversion_date: new Date().toISOString(),
              tax_treatment: 'exempt'
            };
            
            const assetData = {
              client_id: parseInt(clientId),
              asset_type: assetTypeValue,
              description: `${assetDescription} - ${account.שם_תכנית} (${exemptDetails})`,
              current_value: 0,
              purchase_value: exemptAmount,
              purchase_date: purchaseDateISO,
              annual_return: 0,
              annual_return_rate: 0.03,
              payment_frequency: 'monthly',
              liquidity: 'medium',
              risk_level: 'medium',
              monthly_income: exemptAmount,
              start_date: paymentDateISO,
              indexation_method: 'none',
              tax_treatment: 'exempt',
              conversion_source: JSON.stringify(conversionSourceData)
            };

            await apiFetch(`/clients/${clientId}/capital-assets`, {
              method: 'POST',
              body: JSON.stringify(assetData)
            });
            
            totalAssetsCreated++;
          }
          
          // יצירת נכס הון לסכומים עם מס רווח הון
          if (Object.keys(capitalGainsComponents).length > 0) {
            const capitalGainsAmount = Object.values(capitalGainsComponents).reduce((sum, val) => sum + val, 0);
            const capitalGainsDetails = Object.entries(capitalGainsComponents)
              .map(([key, value]) => `${key}: ${formatCurrency(value as number)}`)
              .join(', ');
            
            const conversionSourceData: ConversionSourceData = {
              type: 'pension_portfolio',
              account_name: account.שם_תכנית,
              company: account.חברה_מנהלת,
              account_number: account.מספר_חשבון,
              product_type: account.סוג_מוצר,
              amount: capitalGainsAmount,
              specific_amounts: capitalGainsComponents,
              conversion_date: new Date().toISOString(),
              tax_treatment: 'capital_gains'
            };
            
            const assetData = {
              client_id: parseInt(clientId),
              asset_type: assetTypeValue,
              description: `${assetDescription} - ${account.שם_תכנית} (${capitalGainsDetails})`,
              current_value: 0,
              purchase_value: capitalGainsAmount,
              purchase_date: purchaseDateISO,
              annual_return: 0,
              annual_return_rate: 0.03,
              payment_frequency: 'monthly',
              liquidity: 'medium',
              risk_level: 'medium',
              monthly_income: capitalGainsAmount,
              start_date: paymentDateISO,
              indexation_method: 'none',
              tax_treatment: 'capital_gains',
              conversion_source: JSON.stringify(conversionSourceData)
            };

            await apiFetch(`/clients/${clientId}/capital-assets`, {
              method: 'POST',
              body: JSON.stringify(assetData)
            });
            
            totalAssetsCreated++;
          }
        }
        
        console.log('Created', totalAssetsCreated, 'capital assets');
      }

      // עדכון הנתונים בטבלה
      const updatedPensionData = pensionData.map((account, index) => {
        const conversion = [...pensionConversions, ...capitalAssetConversions].find(c => c.index === index);
        
        if (!conversion) return account;
        
        const {specificAmounts, amountToConvert} = conversion as any;
        let updatedAccount = {...account};
        
        // אפס רק את הרכיבים שהומרו
        Object.keys(specificAmounts).forEach(key => {
          if ((updatedAccount as any)[key]) {
            (updatedAccount as any)[key] = 0;
          }
        });

        // עדכון יתרה: הפחתת הסכום שהומר מהיתרה המקורית
        const originalBalance = Number(updatedAccount.יתרה) || 0;
        const convertedAmount = Number(amountToConvert) || 0;
        if (convertedAmount > 0) {
          updatedAccount.יתרה = Math.max(0, originalBalance - convertedAmount);
        }
        
        updatedAccount.selected = false;
        updatedAccount.selected_amounts = {};
        
        return updatedAccount;
      });
      
      setPensionData(updatedPensionData);
      
      const allConvertedAccounts = [...pensionConversions, ...capitalAssetConversions];
      const convertedIds = allConvertedAccounts.map(conversion => 
        `${conversion.account.מספר_חשבון}_${conversion.account.שם_תכנית}_${conversion.account.חברה_מנהלת}`
      );
      
      const updatedConvertedAccounts = new Set(convertedAccounts);
      convertedIds.forEach((id: string) => updatedConvertedAccounts.add(id));
      setConvertedAccounts(updatedConvertedAccounts);
      
      setConversionTypes({});
      
      localStorage.setItem(`pensionData_${clientId}`, JSON.stringify(updatedPensionData));
      localStorage.setItem(`convertedAccounts_${clientId}`, JSON.stringify(Array.from(updatedConvertedAccounts)));
      
      let successMessage = "הומרה בהצלחה!\n";
      if (pensionConversions.length > 0) {
        const totalBalance = pensionConversions.reduce((sum, conversion) => sum + conversion.amountToConvert, 0);
        successMessage += `נוצרו ${pensionConversions.length} קצבאות נפרדות בסכום כולל: ${formatCurrency(totalBalance)}\n`;
      }
      if (capitalAssetConversions.length > 0) {
        const totalAssets = capitalAssetConversions.reduce((sum, conversion) => sum + conversion.amountToConvert, 0);
        successMessage += `נוצרו ${capitalAssetConversions.length} נכסי הון בסכום כולל: ${formatCurrency(totalAssets)}`;
      }
      
      setProcessingStatus(successMessage);
      alert(successMessage);
    } catch (e: any) {
      setError(`שגיאה בהמרת חשבונות: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  return {
    convertSelectedAccounts
  };
}
