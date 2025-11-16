import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../../../lib/api';
import { getPensionCeiling } from '../calculations/pensionCalculations';
import { calculateTaxByBrackets } from '../calculations/taxCalculations';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';

interface ReportData {
  client_info: {
    name: string;
    id_number: string;
  };
  financial_summary: {
    total_pension_value: number;
    total_additional_income: number;
    total_capital_assets: number;
    total_wealth: number;
    estimated_tax: number;
    total_monthly_income: number;
  };
  cashflow_projection: Array<{
    date: string;
    amount: number;
    grossAmount: number;
    tax: number;
    source: string;
  }>;
  yearly_totals: {
    total_income: number;
    total_tax: number;
    net_income: number;
  };
}

export function useReportData(clientId: string | undefined) {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [pensionFunds, setPensionFunds] = useState<any[]>([]);
  const [additionalIncomes, setAdditionalIncomes] = useState<any[]>([]);
  const [capitalAssets, setCapitalAssets] = useState<any[]>([]);
  const [client, setClient] = useState<any>(null);
  const [fixationData, setFixationData] = useState<any>(null);

  useEffect(() => {
    if (!clientId) return;

    const fetchReportData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get client info
        const clientResponse = await axios.get(`${API_BASE}/clients/${clientId}`);
        const clientData = clientResponse.data;
        setClient(clientData);

        // Get financial data
        const [pensionFundsResponse, additionalIncomesResponse, capitalAssetsResponse, fixationResponse] = await Promise.all([
          axios.get(`${API_BASE}/clients/${clientId}/pension-funds`),
          axios.get(`${API_BASE}/clients/${clientId}/additional-incomes`),
          axios.get(`${API_BASE}/clients/${clientId}/capital-assets`),
          axios.get(`${API_BASE}/rights-fixation/client/${clientId}`).catch(() => ({ data: null }))
        ]);
        
        const pensionFundsData = pensionFundsResponse.data || [];
        const additionalIncomesData = additionalIncomesResponse.data || [];
        const capitalAssetsData = capitalAssetsResponse.data || [];
        
        // Extract raw_result from the fixation response
        let fixationDataResponse = fixationResponse?.data?.raw_result || null;
        
        // עדכון remaining_exempt_capital עם הערך הסופי ששמרנו ב-DB
        // הערכים הסופיים (אחרי כל הקיזוזים) נשמרים ב-raw_result.exemption_summary
        // ולא צריך לעדכן אותם כאן - הם כבר נכונים!
        
        // Update state
        setPensionFunds(pensionFundsData);
        setAdditionalIncomes(additionalIncomesData);
        setCapitalAssets(capitalAssetsData);
        setFixationData(fixationDataResponse);
        
        // Calculate financial summary
        const totalPensionValue = 0;
        const totalAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (income.annual_amount || income.monthly_amount * 12 || 0), 0);
        
        const totalCapitalAssetsValue = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.current_value) || 0), 0);
        
        const totalCapitalAssetsPayments = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.monthly_income) || 0), 0);
        
        // חישוב הכנסה חודשית
        const monthlyPensionIncome = pensionFundsData.reduce((sum: number, fund: any) => 
          sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0);
        const monthlyAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (parseFloat(income.monthly_amount) || (income.annual_amount ? parseFloat(income.annual_amount) / 12 : 0)), 0);
        const monthlyCapitalIncome = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (parseFloat(asset.monthly_income) || 0), 0);
        const totalMonthlyIncome = monthlyPensionIncome + monthlyAdditionalIncome + monthlyCapitalIncome;
        
        const totalWealth = totalPensionValue + totalAdditionalIncome + totalCapitalAssetsValue;
        const estimatedTax = totalWealth * 0.15;

        // Create cashflow data
        const currentDate = new Date();
        const pensionStartDate = clientData.pension_start_date ? new Date(clientData.pension_start_date) : new Date(currentDate.getFullYear() + 2, 0, 1);
        
        const cashflowData = Array.from({ length: 24 }, (_, i) => {
          const monthDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + i, 1);
          const isPensionActive = monthDate >= pensionStartDate;
          
          let monthlyGrossAmount = 0;
          let monthlyTax = 0;
          let monthlyNetAmount = 0;
          let source = 'ללא הכנסה';

          // הכנסה נוספת קיימת גם לפני תחילת הפנסיה
          const monthlyAdditional = additionalIncomesData.reduce((sum: number, income: any) => 
            sum + (income.monthly_amount || income.annual_amount / 12 || 0), 0);

          // פנסיה פעילה רק אחרי תאריך תחילת הפנסיה
          let monthlyPensionTaxable = 0;
          let monthlyPensionExempt = 0;
          if (isPensionActive) {
            monthlyPensionTaxable = pensionFundsData.reduce((sum: number, fund: any) => {
              if (fund.tax_treatment === 'exempt') return sum;
              return sum + (fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0);
            }, 0);
            
            monthlyPensionExempt = pensionFundsData.reduce((sum: number, fund: any) => {
              if (fund.tax_treatment !== 'exempt') return sum;
              return sum + (fund.pension_amount || fund.computed_monthly_amount || fund.monthly_amount || 0);
            }, 0);
          }

          const monthlyPension = monthlyPensionTaxable + monthlyPensionExempt;
          monthlyGrossAmount = monthlyPension + monthlyAdditional;

          if (monthlyGrossAmount > 0) {
            let monthlyExemptPension = monthlyPensionExempt;
            if (fixationDataResponse && fixationDataResponse.exemption_summary) {
              const eligibilityYear = fixationDataResponse.eligibility_year || fixationDataResponse.exemption_summary.eligibility_year;
              const currentYear = monthDate.getFullYear();
              
              if (currentYear >= eligibilityYear) {
                const exemptionPercentage = fixationDataResponse.exemption_summary.exemption_percentage || 0;
                const remainingExemptCapital = fixationDataResponse.exemption_summary.remaining_exempt_capital || 0;
                
                if (currentYear === eligibilityYear) {
                  monthlyExemptPension += remainingExemptCapital / 180;
                } else {
                  const pensionCeiling = getPensionCeiling(currentYear);
                  monthlyExemptPension += exemptionPercentage * pensionCeiling;
                }
              }
            }
            
            const monthlyTaxableIncome = monthlyPensionTaxable + monthlyAdditional;
            const annualTaxableIncome = monthlyTaxableIncome * 12;
            
            let baseTax = calculateTaxByBrackets(annualTaxableIncome, monthDate.getFullYear());
            
            if (clientData?.tax_credit_points) {
              baseTax = Math.max(0, baseTax - (clientData.tax_credit_points * 2904));
            }
            
            monthlyTax = baseTax / 12;
            monthlyNetAmount = monthlyGrossAmount - monthlyTax;
            source = monthlyPension > 0 ? 'פנסיה' : 'הכנסות נוספות';
          }
          
          return {
            date: formatDateToDDMMYY(monthDate),
            amount: Math.round(monthlyNetAmount),
            grossAmount: Math.round(monthlyGrossAmount),
            tax: Math.round(monthlyTax),
            source: source
          };
        });

        const yearlyTotals = {
          total_income: totalWealth,
          total_tax: estimatedTax,
          net_income: totalWealth - estimatedTax
        };

        setReportData({
          client_info: {
            name: clientData && clientData.first_name && clientData.last_name ? `${clientData.first_name} ${clientData.last_name}` : 'לא צוין',
            id_number: clientData?.id_number || 'לא צוין'
          },
          financial_summary: {
            total_pension_value: totalPensionValue,
            total_additional_income: totalAdditionalIncome,
            total_capital_assets: totalCapitalAssetsValue,
            total_wealth: totalWealth,
            estimated_tax: estimatedTax,
            total_monthly_income: totalMonthlyIncome
          },
          cashflow_projection: cashflowData,
          yearly_totals: yearlyTotals
        });

        setLoading(false);
      } catch (err: any) {
        console.error('Error fetching report data:', err);
        setError(err.response?.data?.detail || err.message || 'שגיאה בטעינת נתוני הדוח');
        setLoading(false);
      }
    };

    fetchReportData();
  }, [clientId]);

  return {
    loading,
    error,
    reportData,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    client,
    fixationData
  };
}
