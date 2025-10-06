import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface YearlyProjection {
  year: number;
  totalMonthlyIncome: number;
  totalMonthlyTax: number;
  netMonthlyIncome: number;
  incomeBreakdown: number[];
  taxBreakdown: number[];
}

interface ReportData {
  client_info: {
    name: string;
    id_number: string;
    birth_year?: number;
  };
  financial_summary: {
    total_pension_value: number;
    total_additional_income: number;
    total_capital_assets: number;
    total_wealth: number;
    estimated_tax: number;
  };
  cashflow_projection: Array<{
    date: string;
    amount: number;
    source: string;
  }>;
  yearly_totals: {
    total_income: number;
    total_tax: number;
    net_income: number;
  };
}

const SimpleReports: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pensionFunds, setPensionFunds] = useState<any[]>([]);
  const [additionalIncomes, setAdditionalIncomes] = useState<any[]>([]);
  const [capitalAssets, setCapitalAssets] = useState<any[]>([]);
  const [taxCalculation, setTaxCalculation] = useState<any>(null);
  const [client, setClient] = useState<any>(null);

  // Load report data
  useEffect(() => {
    const fetchReportData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get client info with full URL
        const clientResponse = await axios.get(`http://localhost:8005/api/v1/clients/${id}`);
        const clientData = clientResponse.data;
        setClient(clientData);

        // Get financial data - pension funds, additional incomes, capital assets
        const [pensionFundsResponse, additionalIncomesResponse, capitalAssetsResponse] = await Promise.all([
          axios.get(`http://localhost:8005/api/v1/clients/${id}/pension-funds`),
          axios.get(`http://localhost:8005/api/v1/clients/${id}/additional-incomes`),
          axios.get(`http://localhost:8005/api/v1/clients/${id}/capital-assets`)
        ]);
        
        const pensionFundsData = pensionFundsResponse.data || [];
        const additionalIncomesData = additionalIncomesResponse.data || [];
        const capitalAssetsData = capitalAssetsResponse.data || [];
        
        // Update state with fetched data
        setPensionFunds(pensionFundsData);
        setAdditionalIncomes(additionalIncomesData);
        setCapitalAssets(capitalAssetsData);
        
        // Calculate financial summary
        const totalPensionValue = pensionFundsData.reduce((sum: number, fund: any) => 
          sum + (fund.current_balance || fund.computed_monthly_amount * 12 * 20 || 0), 0);
        
        // תיקון חישוב הכנסות נוספות - תמיכה בשני פורמטים
        const totalAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => {
          if (income.amount && income.frequency) {
            // פורמט חדש
            return sum + (income.frequency === 'monthly' ? income.amount * 12 : income.amount);
          } else {
            // פורמט ישן
            return sum + (income.annual_amount || income.monthly_amount * 12 || 0);
          }
        }, 0);
        
        const totalCapitalAssets = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (asset.current_value || 0), 0);
        
        const totalWealth = totalPensionValue + totalAdditionalIncome + totalCapitalAssets;
        const estimatedTax = totalWealth * 0.15; // הערכת מס בסיסית

        // Get integrated cashflow data from the new API
        let cashflowData = [];
        try {
          const cashflowResponse = await axios.post(`http://localhost:8005/api/v1/clients/${id}/cashflow/integrate-all`, []);
          cashflowData = cashflowResponse.data || [];
        } catch (cashflowError) {
          console.warn('Could not get integrated cashflow, using fallback');
          // Fallback to old method if API fails
          const currentDate = new Date();
          const pensionStartDate = clientData.pension_start_date ? new Date(clientData.pension_start_date) : new Date(currentDate.getFullYear() + 2, 0, 1);
          
          cashflowData = Array.from({ length: 24 }, (_, i) => {
            const monthDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + i, 1);
            const isPensionActive = monthDate >= pensionStartDate;
            
            let monthlyAmount = 0;
            let source = 'ללא הכנסה';
            
            if (isPensionActive) {
              // חישוב הכנסה חודשית מקרנות פנסיה
              const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
              const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => {
                if (income.amount && income.frequency === 'monthly') {
                  return sum + income.amount;
                } else {
                  return sum + (income.monthly_amount || income.annual_amount / 12 || 0);
                }
              }, 0);
              
              monthlyAmount = monthlyPension + monthlyAdditional;
              source = monthlyPension > 0 ? 'פנסיה' : 'הכנסות נוספות';
            }
            
            return {
              date: monthDate.toISOString().split('T')[0],
              amount: Math.round(monthlyAmount),
              source: source
            };
          });
        }

        const yearlyTotals = {
          total_income: totalWealth,
          total_tax: estimatedTax,
          net_income: totalWealth - estimatedTax
        };

        setReportData({
          client_info: {
            name: clientData ? `${clientData.first_name || ''} ${clientData.last_name || ''}`.trim() || 'לא צוין' : 'לא צוין',
            id_number: clientData?.id_number || 'לא צוין',
            birth_year: clientData?.birth_date ? new Date(clientData.birth_date).getFullYear() : undefined
          },
          financial_summary: {
            total_pension_value: totalPensionValue,
            total_additional_income: totalAdditionalIncome,
            total_capital_assets: totalCapitalAssets,
            total_wealth: totalWealth,
            estimated_tax: estimatedTax
          },
          cashflow_projection: cashflowData,
          yearly_totals: yearlyTotals
        });

        setLoading(false);
      } catch (err: any) {
        setError('שגיאה בטעינת נתוני דוח: ' + err.message);
        setLoading(false);
      }
    };
    if (id) {
      fetchReportData();
    }
  }, [id]);

  // פונקציה לחישוב מס על הכנסה ספציפית עם נקודות זיכוי
  const calculateTaxForIncome = (annualIncome: number, incomeType: string): number => {
    if (annualIncome <= 0) return 0;
    
    // חישוב מס בסיסי לפי מדרגות
    let baseTax = 0;
    let remainingIncome = annualIncome;
    
    // מדרגות מס 2024
    const taxBrackets = [
      { min: 0, max: 84000, rate: 0.10 },
      { min: 84000, max: 121000, rate: 0.14 },
      { min: 121000, max: 202000, rate: 0.20 },
      { min: 202000, max: 420000, rate: 0.31 },
      { min: 420000, max: 672000, rate: 0.35 },
      { min: 672000, max: Infinity, rate: 0.47 }
    ];
    
    // חישוב מס לפי מדרגות
    for (const bracket of taxBrackets) {
      if (remainingIncome <= 0) break;
      
      const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
      baseTax += taxableInThisBracket * bracket.rate;
      remainingIncome -= taxableInThisBracket;
    }
    
    // הקלות למס לפנסיונרים
    if (incomeType === 'pension') {
      baseTax *= 0.85; // הנחה של 15% לפנסיונרים
    }
    
    // חישוב נקודות זיכוי
    let totalTaxCredits = 0;
    const creditPointValue = 2640; // ערך נקודת זיכוי 2024 בשקלים
    
    if (client) {
      // נקודות זיכוי מקלט המשתמש בלבד
      if (client.tax_credit_points && client.tax_credit_points > 0) {
        totalTaxCredits = client.tax_credit_points * creditPointValue;
      }
    }
    
    // הפחתת נקודות הזיכוי מהמס
    const finalTax = Math.max(0, baseTax - totalTaxCredits);
    
    return finalTax;
  };
