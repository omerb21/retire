import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../../../lib/api';
import { formatDateToDDMMYY, formatDateToDDMMYYYY } from '../../../utils/dateUtils';
import {
  FixationData,
  GrantSummary,
  ExemptionSummary,
  Commutation
} from '../types';
import { calculatePensionSummary } from '../utils/fixationCalculations';

interface UseFixationDataResult {
  loading: boolean;
  error: string | null;
  fixationData: FixationData | null;
  grantsSummary: GrantSummary[];
  exemptionSummary: ExemptionSummary | null;
  eligibilityDate: string;
  fixationAmount: number;
  hasGrants: boolean;
  clientData: any;
  commutations: Commutation[];
  futureGrantReserved: number;
  setFutureGrantReserved: (value: number) => void;
  retirementAge: string;
  savedEffectivePensionDate: string | null;
  currentPensionStartDate: string | null;
  isFixationStale: boolean;
  handleCalculateFixation: () => Promise<void>;
  handleDeleteFixation: () => Promise<void>;
}

export const useFixationData = (id: string | undefined): UseFixationDataResult => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [fixationData, setFixationData] = useState<FixationData | null>(null);
  const [grantsSummary, setGrantsSummary] = useState<GrantSummary[]>([]);
  const [exemptionSummary, setExemptionSummary] = useState<ExemptionSummary | null>(null);
  const [eligibilityDate, setEligibilityDate] = useState<string>('');
  const [fixationAmount, setFixationAmount] = useState<number>(0);
  const [hasGrants, setHasGrants] = useState<boolean>(false);
  const [clientData, setClientData] = useState<any>(null);
  const [commutations, setCommutations] = useState<Commutation[]>([]);
  const [futureGrantReserved, setFutureGrantReserved] = useState<number>(0);
  const [retirementAge, setRetirementAge] = useState<string>('לא ניתן לחשב');
  const [savedEffectivePensionDate, setSavedEffectivePensionDate] = useState<string | null>(null);
  const [currentPensionStartDate, setCurrentPensionStartDate] = useState<string | null>(null);
  const [isFixationStale, setIsFixationStale] = useState<boolean>(false);

  useEffect(() => {
    const fetchFixationData = async () => {
      try {
        setLoading(true);
        setError(null);

        try {
          const clientResponse = await axios.get(`${API_BASE}/clients/${id}`);
          setClientData(clientResponse.data);
          setCurrentPensionStartDate(clientResponse.data?.pension_start_date || null);

          if (clientResponse.data?.birth_date && clientResponse.data?.gender) {
            try {
              const retirementResponse = await axios.post(`${API_BASE}/retirement-age/calculate-simple`, {
                birth_date: clientResponse.data.birth_date,
                gender: clientResponse.data.gender
              });

              if (retirementResponse.data?.retirement_age) {
                setRetirementAge(retirementResponse.data.retirement_age.toString());
              } else {
                const age = clientResponse.data.gender?.toLowerCase() === 'female' ? 65 : 67;
                setRetirementAge(age.toString());
              }
            } catch (retErr) {
              console.error('Error calculating retirement age:', retErr);
              const age = clientResponse.data.gender?.toLowerCase() === 'female' ? 65 : 67;
              setRetirementAge(age.toString());
            }
          }
        } catch (err) {
          console.error('Error fetching client data:', err);
        }

        try {
          const savedFixation = await axios.get(`${API_BASE}/rights-fixation/client/${id}`);
          if (savedFixation.data.success && savedFixation.data.raw_payload) {
            const savedFutureGrant = savedFixation.data.raw_payload.future_grant_reserved || 0;
            setFutureGrantReserved(savedFutureGrant);
            console.log('Loaded saved future grant:', savedFutureGrant);

            const savedEffective = savedFixation.data.raw_payload.effective_pension_start_date || null;
            setSavedEffectivePensionDate(savedEffective);
          }
        } catch (err: any) {
          if (err.response?.status !== 404) {
            console.error('Error loading saved fixation:', err);
          }
        }

        try {
          const capitalAssets = await axios.get(`${API_BASE}/clients/${id}/capital-assets/`);
          const pensionFunds = await axios.get(`${API_BASE}/clients/${id}/pension-funds`);
          const fundsMap = new Map(pensionFunds.data.map((f: any) => [f.id, f]));

          // שלב 1: בוחרים רק נכסים הוניים שהם היוונים פטורים (COMMUTATION + tax_treatment === 'exempt')
          const commutationAssets = (capitalAssets.data || []).filter((asset: any) =>
            asset.remarks && asset.remarks.includes('COMMUTATION:') && asset.tax_treatment === 'exempt'
          );

          // שלב 2: מסננים החוצה היוונים שהמקור שלהם הוא קצבה עם יחס מס "פטור ממס"
          const filteredAssets = commutationAssets.filter((asset: any) => {
            const match = asset.remarks.match(/pension_fund_id=(\d+)/);
            const pensionFundId = match ? parseInt(match[1]) : undefined;
            if (!pensionFundId) {
              return false;
            }

            const fund: any = fundsMap.get(pensionFundId);
            if (!fund) {
              return false;
            }

            const fundTax = fund.tax_treatment || 'taxable';
            // נכלול רק היוונים שהמקור שלהם הוא קצבה שלא מסומנת כ"פטורה ממס"
            return fundTax !== 'exempt';
          });

          const loadedCommutations: Commutation[] = filteredAssets.map((asset: any) => {
            const match = asset.remarks.match(/pension_fund_id=(\d+)/);
            const pensionFundId = match ? parseInt(match[1]) : undefined;
            const fund: any = pensionFundId ? fundsMap.get(pensionFundId) : undefined;

            const amountMatch = asset.remarks?.match(/amount=([\d.]+)/);
            const amount = amountMatch ? parseFloat(amountMatch[1]) : asset.current_value;

            return {
              id: asset.id,
              pension_fund_id: pensionFundId,
              fund_name: fund?.fund_name || 'לא ידוע',
              deduction_file: fund?.deduction_file || '',
              exempt_amount: amount,
              commutation_date: asset.start_date || asset.purchase_date,
              commutation_type: asset.tax_treatment
            };
          });

          setCommutations(loadedCommutations);
        } catch (err) {
          console.error('Error loading commutations:', err);
          setCommutations([]);
        }

        let grants: any[] = [];
        try {
          const grantsResponse = await axios.get(`${API_BASE}/clients/${id}/grants`);
          grants = grantsResponse.data || [];
          setHasGrants(grants.length > 0);
        } catch (err: any) {
          if (err.response?.status === 404) {
            grants = [];
            setHasGrants(false);
          } else {
            throw err;
          }
        }

        const currentEligibilityDate = eligibilityDate || formatDateToDDMMYY(new Date());
        setEligibilityDate(currentEligibilityDate);

        console.log('DEBUG: grants array:', grants);
        console.log('DEBUG: grants.length:', grants.length);

        try {
          const fixationResponse = await axios.post(`${API_BASE}/rights-fixation/calculate`, {
            client_id: parseInt(id!)
          });

          console.log('DEBUG: Full API response:', fixationResponse.data);

          const processedGrants = fixationResponse.data.grants || [];
          const exemptionData = fixationResponse.data.exemption_summary || {};

          console.log('DEBUG: processedGrants:', processedGrants);
          console.log('DEBUG: exemptionData:', exemptionData);

          const mappedGrants = processedGrants.map((grant: any) => {
            console.log('DEBUG: Processing grant:', grant);
            console.log('DEBUG: grant.grant_date:', grant.grant_date);
            return {
              employer_name: grant.employer_name,
              grant_amount: grant.grant_amount,
              work_start_date: grant.work_start_date,
              work_end_date: grant.work_end_date,
              grant_date: grant.grant_date,
              indexed_full: grant.indexed_full,
              ratio_32y: grant.ratio_32y,
              limited_indexed_amount: grant.limited_indexed_amount,
              impact_on_exemption: grant.impact_on_exemption,
              exclusion_reason: grant.exclusion_reason
            };
          });

          console.log('DEBUG: mappedGrants:', mappedGrants);
          setGrantsSummary(mappedGrants);

          setExemptionSummary(exemptionData);

          setFixationData({
            client_id: parseInt(id!),
            grants: processedGrants,
            exemption_summary: exemptionData,
            eligibility_date: fixationResponse.data.eligibility_date,
            eligibility_year: fixationResponse.data.eligibility_year,
            status: 'calculated'
          });
        } catch (error: any) {
          if (error.response?.status === 400 || error.response?.status === 409) {
            const errorData = error.response.data.detail || error.response.data;
            const reasons = errorData.reasons || [];
            const eligibilityDateFromError = errorData.eligibility_date || '';
            const suggestion = errorData.suggestion || '';

            let errorMessage = errorData.error || 'לא ניתן לבצע קיבוע זכויות';

            if (reasons.length > 0) {
              errorMessage += '\n\nסיבות:\n';
              reasons.forEach((reason: string, index: number) => {
                errorMessage += `${index + 1}. ${reason}\n`;
              });
            }

            if (eligibilityDateFromError) {
              errorMessage += `\nתאריך זכאות צפוי: ${formatDateToDDMMYY(new Date(eligibilityDateFromError))}`;
            }

            if (suggestion) {
              errorMessage += `\n\n💡 ${suggestion}`;
            }

            setError(errorMessage);
            setHasGrants(false);
          } else {
            console.error('Error using rights fixation service:', error);
            console.error('Full error object:', JSON.stringify(error, null, 2));

            const errorDetail = error.response?.data?.detail;
            let errorMsg = 'שגיאה בחישוב קיבוע זכויות';

            if (typeof errorDetail === 'string' && errorDetail.trim()) {
              errorMsg += ':\n' + errorDetail;
            } else if (errorDetail && typeof errorDetail === 'object') {
              if (errorDetail.error) {
                errorMsg += ':\n' + errorDetail.error;
              }
              if (errorDetail.message) {
                errorMsg += '\n' + errorDetail.message;
              }
              if (errorDetail.suggestion) {
                errorMsg += '\n\n💡 ' + errorDetail.suggestion;
              }
            } else if (error.message && error.message.trim()) {
              errorMsg += ':\n' + error.message;
            } else {
              errorMsg += '\nשגיאה לא ידועה. אנא בדוק את הקונסול לפרטים נוספים.';
            }

            setError(errorMsg);
            setGrantsSummary([]);
            setExemptionSummary(null);
            setHasGrants(false);
          }
        }

        setLoading(false);
      } catch (err: any) {
        setError('שגיאה בטעינת נתוני קיבוע: ' + err.message);
        setLoading(false);
      }
    };

    if (id) {
      fetchFixationData();
    }
  }, [id]);

  useEffect(() => {
    if (!savedEffectivePensionDate) {
      setIsFixationStale(false);
      return;
    }

    if (!currentPensionStartDate) {
      setIsFixationStale(true);
      return;
    }

    setIsFixationStale(savedEffectivePensionDate !== currentPensionStartDate);
  }, [savedEffectivePensionDate, currentPensionStartDate]);

  const handleCalculateFixation = async (): Promise<void> => {
    if (!fixationData) {
      alert('אין נתוני חישוב לשמירה');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const pensionSummary = calculatePensionSummary(
        grantsSummary,
        exemptionSummary,
        futureGrantReserved,
        commutations,
        fixationData
      );

      const saveResponse = await axios.post(`${API_BASE}/rights-fixation/save`, {
        client_id: parseInt(id!),
        calculation_result: {
          grants: fixationData.grants,
          exemption_summary: {
            ...fixationData.exemption_summary,
            future_grant_reserved: futureGrantReserved,
            future_grant_impact: futureGrantReserved * 1.35,
            total_commutations: pensionSummary.total_discounts,
            final_remaining_exemption: pensionSummary.remaining_exemption,
            remaining_exempt_capital: pensionSummary.remaining_exemption,
            remaining_monthly_exemption: pensionSummary.exempt_pension_calculated.base_amount,
            exempt_pension_percentage:
              pensionSummary.exempt_pension_calculated.percentage / 100
          },
          eligibility_date: fixationData.eligibility_date,
          eligibility_year: fixationData.eligibility_year
        },
        formatted_data: {
          id: parseInt(id!),
          eligibility_date: fixationData.eligibility_date,
          eligibility_year: fixationData.eligibility_year,
          future_grant_reserved: futureGrantReserved
        }
      });

      alert(
        `קיבוע זכויות נשמר בהצלחה!\nתאריך חישוב: ${formatDateToDDMMYYYY(
          new Date(saveResponse.data.calculation_date)
        )}\n\nהנתונים נשמרו במערכת`
      );
    } catch (err: any) {
      setError('שגיאה בשמירת קיבוע זכויות: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteFixation = async (): Promise<void> => {
    if (!id) {
      return;
    }

    const confirmed = window.confirm(
      'האם אתה בטוח שברצונך למחוק את קיבוע הזכויות השמור?\nהקצבה הפטורה לא תילקח עוד בחשבון בחישובי המס והדוחות עד שמירת קיבוע חדש.'
    );
    if (!confirmed) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await axios.delete(`${API_BASE}/rights-fixation/client/${id}`);

      setFixationData((prev) => prev);
      setFutureGrantReserved(0);
      setSavedEffectivePensionDate(null);
      setIsFixationStale(false);

      alert(
        'קיבוע הזכויות השמור נמחק. נתוני קיבוע לא ישמשו בחישובי המס עד שתשמור קיבוע חדש.'
      );
    } catch (err: any) {
      if (err.response?.status === 404) {
        alert('לא נמצא קיבוע זכויות שמור למחיקה עבור הלקוח.');
      } else {
        setError('שגיאה במחיקת קיבוע זכויות: ' + (err.message || ''));
      }
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    error,
    fixationData,
    grantsSummary,
    exemptionSummary,
    eligibilityDate,
    fixationAmount,
    hasGrants,
    clientData,
    commutations,
    futureGrantReserved,
    setFutureGrantReserved,
    retirementAge,
    savedEffectivePensionDate,
    currentPensionStartDate,
    isFixationStale,
    handleCalculateFixation,
    handleDeleteFixation
  };
};
