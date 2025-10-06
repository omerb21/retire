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

        // Get client info
        const clientResponse = await axios.get(`/api/v1/clients/${id}`);
        const clientData = clientResponse.data;
        setClient(clientData);

        // Get financial data - pension funds, additional incomes, capital assets
        const [pensionFundsResponse, additionalIncomesResponse, capitalAssetsResponse] = await Promise.all([
          axios.get(`/api/v1/clients/${id}/pension-funds`),
          axios.get(`/api/v1/clients/${id}/additional-incomes`),
          axios.get(`/api/v1/clients/${id}/capital-assets`)
        ]);
        
        const pensionFundsData = pensionFundsResponse.data || [];
        const additionalIncomesData = additionalIncomesResponse.data || [];
        const capitalAssetsData = capitalAssetsResponse.data || [];
        
        // לוג לבדיקת מבנה הנתונים
        console.log('Additional Incomes Data:', JSON.stringify(additionalIncomesData, null, 2));
        console.log('First Additional Income:', additionalIncomesData[0]);
        
        // לוג לבדיקת קרנות פנסיה
        console.log('Pension Funds Data:', JSON.stringify(pensionFundsData, null, 2));
        pensionFundsData.forEach((fund: any, index: number) => {
          console.log(`Pension Fund ${index + 1} - start_date:`, fund.start_date);
          if (fund.start_date) {
            const parsedYear = parseInt(fund.start_date.split('-')[0]);
            const parsedMonth = parseInt(fund.start_date.split('-')[1]);
            const parsedDay = parseInt(fund.start_date.split('-')[2]);
            console.log(`  Parsed Date: Year=${parsedYear}, Month=${parsedMonth}, Day=${parsedDay}`);
            console.log(`  Full Date:`, new Date(fund.start_date));
          }
        });
        
        // Update state with fetched data
        setPensionFunds(pensionFundsData);
        setAdditionalIncomes(additionalIncomesData);
        setCapitalAssets(capitalAssetsData);
        
        // Calculate financial summary
        const totalPensionValue = pensionFundsData.reduce((sum: number, fund: any) => 
          sum + (fund.current_balance || fund.computed_monthly_amount * 12 * 20 || 0), 0);
        const totalAdditionalIncome = additionalIncomesData.reduce((sum: number, income: any) => 
          sum + (income.annual_amount || income.monthly_amount * 12 || 0), 0);
        const totalCapitalAssets = capitalAssetsData.reduce((sum: number, asset: any) => 
          sum + (asset.current_value || 0), 0);
        
        const totalWealth = totalPensionValue + totalAdditionalIncome + totalCapitalAssets;
        const estimatedTax = totalWealth * 0.15; // הערכת מס בסיסית

        // Get scenarios for cashflow
        const scenariosResponse = await axios.get(`/api/v1/clients/${id}/scenarios`);
        const scenarios = scenariosResponse.data || [];
        
        // Create realistic cashflow data based on actual financial data
        const currentDate = new Date();
        const pensionStartDate = clientData.pension_start_date ? new Date(clientData.pension_start_date) : new Date(currentDate.getFullYear() + 2, 0, 1);
        
        const cashflowData = Array.from({ length: 24 }, (_, i) => {
          const monthDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + i, 1);
          const isPensionActive = monthDate >= pensionStartDate;
          
          let monthlyGrossAmount = 0;
          let monthlyTax = 0;
          let monthlyNetAmount = 0;
          let source = 'ללא הכנסה';
          
          if (isPensionActive) {
            // חישוב הכנסה חודשית מקרנות פנסיה
            const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
              sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
            const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
              sum + (income.monthly_amount || income.annual_amount / 12 || 0), 0);
            
            monthlyGrossAmount = monthlyPension + monthlyAdditional;
            
            // חישוב מס על ההכנסה החודשית עם נקודות זיכוי
            if (monthlyGrossAmount > 0) {
              const annualGrossAmount = monthlyGrossAmount * 12;
              // חישוב מס בסיסי לפי מדרגות
              let baseTax = 0;
              let remainingIncome = annualGrossAmount;
              
              const taxBrackets = [
                { min: 0, max: 84120, rate: 0.10 },
                { min: 84120, max: 120720, rate: 0.14 },
                { min: 120720, max: 193800, rate: 0.20 },
                { min: 193800, max: 269280, rate: 0.31 },
                { min: 269280, max: 560280, rate: 0.35 },
                { min: 560280, max: 721560, rate: 0.47 },
                { min: 721560, max: Infinity, rate: 0.50 }
              ];
              
              for (const bracket of taxBrackets) {
                if (remainingIncome <= 0) break;
                const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
                baseTax += taxableInThisBracket * bracket.rate;
                remainingIncome -= taxableInThisBracket;
              }
              
              // הפחתת נקודות זיכוי אם קיימות
              if (clientData?.tax_credit_points) {
                baseTax = Math.max(0, baseTax - (clientData.tax_credit_points * 2640));
              }
              
              monthlyTax = baseTax / 12;
              monthlyNetAmount = monthlyGrossAmount - monthlyTax;
            }
            
            source = monthlyPension > 0 ? 'פנסיה' : 'הכנסות נוספות';
          }
          
          return {
            date: monthDate.toISOString().split('T')[0],
            amount: Math.round(monthlyNetAmount), // הצגת הכנסה נטו אחרי מס
            grossAmount: Math.round(monthlyGrossAmount), // הכנסה גולמית
            tax: Math.round(monthlyTax), // מס חודשי
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
            name: clientData ? `${clientData.first_name || ''} ${clientData.last_name || ''}`.trim() || 'לא צוין' : 'לא צוין',
            id_number: clientData?.id_number || 'לא צוין'
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
    
    // הכנסות מקרן פנסיה הן הכנסות עבודה רגילות - ללא הנחות מיוחדות
    // (ההנחה הוסרה - הכנסות פנסיה חייבות במס כמו הכנסות עבודה רגילות)
    
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

  /**
   * מייצר תחזית שנתית של תזרים מזומנים
   * הפונקציה מציגה רק שנים עתידיות בתזרים, החל מהשנה הנוכחית
   * קרנות פנסיה והכנסות נוספות שהתחילו בעבר יוצגו החל מהשנה הנוכחית
   * קרנות פנסיה והכנסות נוספות שמתחילות בעתיד יוצגו החל משנת ההתחלה שלהן
   */
  const generateYearlyProjection = (): YearlyProjection[] => {
    if (!reportData) return [];
    
    // קביעת שנת התחלה של התזרים - נתחיל משנה קודמת כדי לכלול קרנות שהתחילו בעבר
    const currentYear = 2025;
    
    // מציאת השנה המוקדמת ביותר שבה מתחילה קרן פנסיה או הכנסה נוספת
    let earliestStartYear = currentYear;
    
    // בדיקת קרנות פנסיה
    pensionFunds.forEach(fund => {
      if (fund.start_date) {
        const fundStartYear = parseInt(fund.start_date.split('-')[0]);
        earliestStartYear = Math.min(earliestStartYear, fundStartYear);
      }
    });
    
    // בדיקת הכנסות נוספות
    additionalIncomes.forEach(income => {
      if (income.start_date) {
        const incomeStartYear = parseInt(income.start_date.split('-')[0]);
        earliestStartYear = Math.min(earliestStartYear, incomeStartYear);
      }
    });
    
    // התזרים יתחיל מהשנה המוקדמת ביותר
    const projectionStartYear = earliestStartYear;
    const clientBirthYear = 1957; // Default birth year if not available
    const maxAge = 90;
    const maxYear = clientBirthYear + maxAge;
    const projectionYears = Math.min(maxYear - projectionStartYear + 1, 40); // Limit to 40 years max
    
    // Create array of years from projection start year to max age (or 40 years, whichever is less)
    const yearlyData: YearlyProjection[] = [];
    
    for (let i = 0; i < projectionYears; i++) {
      const year = projectionStartYear + i;
      const clientAge = year - clientBirthYear;
      
      // Initialize income breakdown array
      const incomeBreakdown: number[] = [];
      let totalMonthlyIncome = 0;
      
      // Add pension fund incomes
      pensionFunds.forEach(fund => {
        // תיקון חישוב שנת התחלה - השתמש בשנת ההתחלה המקורית של הקרן
        let fundStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (fund.start_date) {
          // השתמש בשנת ההתחלה המקורית של הקרן
          fundStartYear = parseInt(fund.start_date.split('-')[0]);
          
          // הדפסת מידע לבדיקה
          console.log(`Fund ${fund.fund_name || 'unnamed'} start date: ${fund.start_date}, parsed year: ${fundStartYear}`);
        }
        
        const monthlyAmount = fund.computed_monthly_amount || fund.monthly_amount || 0;
        
        // Apply annual increase (2% by default)
        const yearsActive = year >= fundStartYear ? year - fundStartYear : 0;
        const indexationRate = fund.indexation_rate || 0.02; // Default 2% annual increase
        const adjustedAmount = yearsActive > 0 ? 
          monthlyAmount * Math.pow(1 + indexationRate, yearsActive) : 0;
        
        // Only add income if pension has started
        const amount = year >= fundStartYear ? adjustedAmount : 0;
        
        incomeBreakdown.push(Math.round(amount));
        totalMonthlyIncome += amount;
      });
      
      // Add additional incomes
      additionalIncomes.forEach(income => {
        // תיקון חישוב שנת התחלה - השתמש בשנת ההתחלה המקורית של ההכנסה
        let incomeStartYear = currentYear; // ברירת מחדל היא השנה הנוכחית
        
        if (income.start_date) {
          // השתמש בשנת ההתחלה המקורית של ההכנסה
          incomeStartYear = parseInt(income.start_date.split('-')[0]);
          
          // הדפסת מידע לבדיקה
          console.log(`Income ${income.income_name || 'unnamed'} start date: ${income.start_date}, parsed year: ${incomeStartYear}`);
        }
        
        const incomeEndYear = income.end_date ? parseInt(income.end_date.split('-')[0]) : maxYear;
        // בדיקת כל השדות האפשריים להכנסה חודשית
        const monthlyAmount = income.monthly_amount || income.amount || (income.annual_amount ? income.annual_amount / 12 : 0);
        
        // Only add income if it's active in this year
        const amount = (year >= incomeStartYear && year <= incomeEndYear) ? monthlyAmount : 0;
        incomeBreakdown.push(Math.round(amount));
        
        // הוספה לסך ההכנסה החודשית
        totalMonthlyIncome += amount;
      });
      
      // חישוב מס על סך כל ההכנסות הדינמיות של השנה הנוכחית
      const taxBreakdown: number[] = [];
      let totalMonthlyTax = 0;
      
      // חישוב סך כל ההכנסות השנתיות בהתבסס על ההכנסות הדינמיות של השנה הנוכחית
      let totalTaxableAnnualIncome = 0;
      let totalExemptIncome = 0;
      
      // חישוב הכנסה חייבת במס מקרנות פנסיה (בהתבסס על ההכנסות הדינמיות)
      let monthlyTaxableIncome = 0;
      incomeBreakdown.slice(0, pensionFunds.length).forEach(income => {
        monthlyTaxableIncome += income;
      });
      
      // חישוב הכנסה פטורה וחייבת במס מהכנסות נוספות (בהתבסס על ההכנסות הדינמיות)
      let monthlyExemptIncome = 0;
      let monthlyTaxableAdditionalIncome = 0;
      
      incomeBreakdown.slice(pensionFunds.length).forEach((income, index) => {
        const additionalIncome = additionalIncomes[index];
        if (additionalIncome && additionalIncome.tax_treatment === 'exempt') {
          monthlyExemptIncome += income;
        } else {
          monthlyTaxableAdditionalIncome += income;
        }
      });
      
      totalTaxableAnnualIncome = (monthlyTaxableIncome + monthlyTaxableAdditionalIncome) * 12;
      totalExemptIncome = monthlyExemptIncome * 12;
      const totalAnnualIncome = totalTaxableAnnualIncome + totalExemptIncome;
      
      if (totalTaxableAnnualIncome > 0) {
        // חישוב מס כולל על סך ההכנסות החייבות במס
        let totalAnnualTax = 0;
        let remainingIncome = totalTaxableAnnualIncome;
        
        const taxBrackets = [
          { min: 0, max: 84120, rate: 0.10 },
          { min: 84120, max: 120720, rate: 0.14 },
          { min: 120720, max: 193800, rate: 0.20 },
          { min: 193800, max: 269280, rate: 0.31 },
          { min: 269280, max: 560280, rate: 0.35 },
          { min: 560280, max: 721560, rate: 0.47 },
          { min: 721560, max: Infinity, rate: 0.50 }
        ];
        
        for (const bracket of taxBrackets) {
          if (remainingIncome <= 0) break;
          const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
          totalAnnualTax += taxableInThisBracket * bracket.rate;
          remainingIncome -= taxableInThisBracket;
        }
        
        // הפחתת נקודות זיכוי אם קיימות
        if (client?.tax_credit_points) {
          totalAnnualTax = Math.max(0, totalAnnualTax - (client.tax_credit_points * 2640));
        }
        
        totalMonthlyTax = totalAnnualTax / 12;
        
        // חלוקת המס באופן יחסי לפי ההכנסות
        // חישוב סך ההכנסה החייבת במס
        const taxableTotalMonthlyIncome = monthlyTaxableIncome + monthlyTaxableAdditionalIncome;
        
        pensionFunds.forEach((fund, index) => {
          const incomeAmount = incomeBreakdown[index] || 0;
          // חלוקת המס רק על ההכנסות החייבות במס
          const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * totalMonthlyTax : 0;
          taxBreakdown.push(Math.round(taxPortion));
        });
        
        additionalIncomes.forEach((income, index) => {
          const incomeIndex = pensionFunds.length + index;
          const incomeAmount = incomeBreakdown[incomeIndex] || 0;
          
          // אם ההכנסה פטורה ממס, המס הוא אפס
          if (income.tax_treatment === 'exempt') {
            taxBreakdown.push(0);
          } else {
            // חלוקת המס רק על ההכנסות החייבות במס
            // משתמשים במשתנה שהוגדר למעלה
            const taxPortion = taxableTotalMonthlyIncome > 0 ? (incomeAmount / taxableTotalMonthlyIncome) * totalMonthlyTax : 0;
            taxBreakdown.push(Math.round(taxPortion));
          }
        });
      } else {
        // אין הכנסה - אין מס
        for (let i = 0; i < pensionFunds.length + additionalIncomes.length; i++) {
          taxBreakdown.push(0);
        }
      }

      yearlyData.push({
        year,
        totalMonthlyIncome: Math.round(totalMonthlyIncome),
        totalMonthlyTax: Math.round(totalMonthlyTax),
        netMonthlyIncome: Math.round(totalMonthlyIncome - totalMonthlyTax),
        incomeBreakdown,
        taxBreakdown
      });
    }
    
    return yearlyData;
  };

  // הוסר calculateTaxImpact - המס מחושב ישירות בטבלה

  const handleGeneratePdf = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Generate PDF report using the correct API endpoint
      // First create a scenario if none exists
      let scenarioId = 1; // Default scenario ID
      try {
        const scenarioResponse = await axios.get(`/api/v1/clients/${id}/scenarios`);
        const scenarios = Array.isArray(scenarioResponse.data) ? scenarioResponse.data : (scenarioResponse.data?.scenarios || []);
        if (scenarios.length === 0) {
          // Create a default scenario
          const newScenario = await axios.post(`/api/v1/clients/${id}/scenarios`, {
            name: "דוח ברירת מחדל",
            parameters: "{}",
            description: "תרחיש ברירת מחדל ליצירת דוח"
          });
          scenarioId = newScenario.data.id;
        } else {
          scenarioId = scenarios[0].id;
        }
      } catch (e) {
        console.warn('Could not get/create scenario, using default ID');
      }
      
      // Use the correct API endpoint for PDF generation
      const response = await axios.post(`/api/v1/reports/clients/${id}/reports/pdf`, {
        scenario_id: scenarioId,
        report_type: "comprehensive",
        include_charts: true,
        include_cashflow: true
      }, {
        responseType: 'blob'
      });

      // Create blob URL for PDF
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      setPdfUrl(url);

      // Also trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = `retirement_report_${id}_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      alert('דוח PDF נוצר בהצלחה');
    } catch (err: any) {
      setError('שגיאה ביצירת דוח PDF: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateExcel = async () => {
    if (!reportData) return;

    try {
      setLoading(true);
      setError(null);

      // Generate Excel report - use same endpoint as PDF but request Excel format
      const response = await axios.post(`/api/v1/reports/clients/${id}/reports/excel`, {
        scenario_id: 1, // Default scenario
        report_type: "excel",
        include_charts: false,
        include_cashflow: true
      }, {
        responseType: 'blob'
      });

      // Create blob URL for Excel
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const url = window.URL.createObjectURL(blob);

      // Trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = `retirement_report_${id}_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      alert('דוח Excel נוצר בהצלחה');
    } catch (err: any) {
      setError('שגיאה ביצירת דוח Excel: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !reportData) {
    return <div style={{ padding: '20px' }}>טוען נתוני דוח...</div>;
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <a href={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </a>
      </div>

      <h2>דוחות</h2>

      {error && (
        <div style={{ 
          color: 'red', 
          marginBottom: '20px', 
          padding: '10px', 
          backgroundColor: '#fee', 
          borderRadius: '4px' 
        }}>
          {error}
        </div>
      )}

      {/* Report Generation Controls */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        border: '1px solid #007bff', 
        borderRadius: '4px',
        backgroundColor: '#f8f9ff'
      }}>
        <h3>יצירת דוחות</h3>
        
        <div style={{ display: 'flex', gap: '15px', marginBottom: '15px' }}>
          <button
            onClick={handleGeneratePdf}
            disabled={loading || !reportData}
            style={{
              backgroundColor: loading ? '#6c757d' : '#dc3545',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {loading ? 'יוצר...' : 'יצירת דוח PDF'}
          </button>

          <button
            onClick={handleGenerateExcel}
            disabled={loading || !reportData}
            style={{
              backgroundColor: loading ? '#6c757d' : '#28a745',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {loading ? 'יוצר...' : 'יצירת דוח Excel'}
          </button>
        </div>

        {pdfUrl && (
          <div style={{ marginTop: '15px' }}>
            <a 
              href={pdfUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: '#007bff', textDecoration: 'none' }}
            >
              📄 צפה בדוח PDF שנוצר
            </a>
          </div>
        )}
      </div>

      {/* Report Preview */}
      {reportData && (
        <div>
          <h3>תצוגה מקדימה של הדוח</h3>
          
          {/* Client Info */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>פרטי לקוח</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div><strong>שם:</strong> {reportData.client_info.name}</div>
              <div><strong>ת.ז.:</strong> {reportData.client_info.id_number}</div>
            </div>
          </div>

          {/* Detailed Financial Breakdown */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>פירוט פיננסי</h4>
            
            {/* Pension Funds */}
            <div style={{ marginBottom: '15px' }}>
              <h5 style={{ 
                borderBottom: '1px solid #ddd', 
                paddingBottom: '5px', 
                marginBottom: '10px',
                color: '#0056b3'
              }}>קרנות פנסיה</h5>
              
              {pensionFunds && pensionFunds.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  {pensionFunds.map((fund: any) => (
                    <div key={fund.id} style={{ 
                      padding: '10px', 
                      backgroundColor: '#f0f8ff', 
                      borderRadius: '4px',
                      border: '1px solid #cce5ff'
                    }}>
                      <div><strong>{fund.fund_name}</strong></div>
                      <div>קצבה חודשית: ₪{(fund.computed_monthly_amount || fund.monthly_amount || 0).toLocaleString()}</div>
                      <div>יתרה נוכחית: ₪{(fund.current_balance || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {fund.start_date || 'לא צוין'}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין קרנות פנסיה</div>
              )}
            </div>
            
            {/* Additional Incomes */}
            <div style={{ marginBottom: '15px' }}>
              <h5 style={{ 
                borderBottom: '1px solid #ddd', 
                paddingBottom: '5px', 
                marginBottom: '10px',
                color: '#0056b3'
              }}>הכנסות נוספות</h5>
              
              {additionalIncomes && additionalIncomes.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  {additionalIncomes.map((income: any) => (
                    <div key={income.id} style={{ 
                      padding: '10px', 
                      backgroundColor: '#f0fff0', 
                      borderRadius: '4px',
                      border: '1px solid #d4edda'
                    }}>
                      <div><strong>{income.income_name || income.description || income.income_type || income.source_type || 'הכנסה נוספת'}</strong></div>
                      <div>הכנסה חודשית: ₪{(income.monthly_amount || income.amount || 0).toLocaleString()}</div>
                      <div>הכנסה שנתית: ₪{(income.annual_amount || (income.monthly_amount || income.amount) * 12 || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {income.start_date || 'לא צוין'}</div>
                      {income.tax_treatment && <div>יחס מס: {income.tax_treatment === 'exempt' ? 'פטור ממס' : income.tax_treatment === 'taxable' ? 'חייב במס' : 'שיעור קבוע'}</div>}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין הכנסות נוספות</div>
              )}
            </div>
            
            {/* Capital Assets */}
            <div style={{ marginBottom: '15px' }}>
              <h5 style={{ 
                borderBottom: '1px solid #ddd', 
                paddingBottom: '5px', 
                marginBottom: '10px',
                color: '#0056b3'
              }}>נכסי הון</h5>
              
              {capitalAssets && capitalAssets.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  {capitalAssets.map((asset: any) => (
                    <div key={asset.id} style={{ 
                      padding: '10px', 
                      backgroundColor: '#fff8f0', 
                      borderRadius: '4px',
                      border: '1px solid #ffeeba'
                    }}>
                      <div><strong>{asset.description || asset.asset_type}</strong></div>
                      <div>ערך נוכחי: ₪{(asset.current_value || 0).toLocaleString()}</div>
                      <div>מחיר רכישה: ₪{(asset.purchase_price || 0).toLocaleString()}</div>
                      <div>תאריך רכישה: {asset.purchase_date || 'לא צוין'}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: '#6c757d' }}>אין נכסי הון</div>
              )}
            </div>
            
            {/* Summary */}
            <div style={{ 
              marginTop: '15px', 
              padding: '10px', 
              backgroundColor: '#e9ecef', 
              borderRadius: '4px',
              border: '1px solid #dee2e6'
            }}>
              <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>סיכום</h5>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div><strong>סך הכנסה חודשית:</strong> ₪{(() => {
                  const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                    sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
                  const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
                    sum + (income.monthly_amount || (income.annual_amount ? income.annual_amount / 12 : 0)), 0);
                  return (monthlyPension + monthlyAdditional).toLocaleString();
                })()}</div>
                <div><strong>סך נכסים:</strong> ₪{(() => {
                  const totalPensionBalance = pensionFunds.reduce((sum: number, fund: any) => 
                    sum + (fund.current_balance || 0), 0);
                  const totalCapitalAssets = capitalAssets.reduce((sum: number, asset: any) => 
                    sum + (asset.current_value || 0), 0);
                  return (totalPensionBalance + totalCapitalAssets).toLocaleString();
                })()}</div>
                <div><strong>תאריך התחלת תזרים:</strong> {(() => {
                  // מציאת השנה הראשונה עם הכנסה
                  const firstIncomeYear = Math.min(
                    ...pensionFunds.map((fund: any) => 
                      fund.start_date ? parseInt(fund.start_date.split('-')[0]) : new Date().getFullYear() + 10
                    ),
                    ...additionalIncomes.map((income: any) => 
                      income.start_date ? parseInt(income.start_date.split('-')[0]) : new Date().getFullYear() + 10
                    )
                  );
                  return firstIncomeYear < new Date().getFullYear() + 10 ? `01/01/${firstIncomeYear}` : 'לא צוין';
                })()}</div>
                <div style={{ color: '#dc3545' }}><strong>מס משוער:</strong> ₪{(() => {
                  const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                    sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
                  const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
                    sum + (income.monthly_amount || (income.annual_amount ? income.annual_amount / 12 : 0)), 0);
                  const totalAnnualIncome = (monthlyPension + monthlyAdditional) * 12;
                  
                  // חישוב מס בסיסי לפי מדרגות
                  let tax = 0;
                  let remaining = totalAnnualIncome;
                  const brackets = [
                    { max: 84120, rate: 0.10 },
                    { max: 120720, rate: 0.14 },
                    { max: 193800, rate: 0.20 },
                    { max: 269280, rate: 0.31 },
                    { max: 560280, rate: 0.35 },
                    { max: 721560, rate: 0.47 },
                    { max: Infinity, rate: 0.50 }
                  ];
                  
                  let prevMax = 0;
                  for (const bracket of brackets) {
                    if (remaining <= 0) break;
                    const taxableInBracket = Math.min(remaining, bracket.max - prevMax);
                    tax += taxableInBracket * bracket.rate;
                    remaining -= taxableInBracket;
                    prevMax = bracket.max;
                  }
                  
                  // הפחתת נקודות זיכוי אם קיימות
                  if (client?.tax_credit_points) {
                    tax = Math.max(0, tax - (client.tax_credit_points * 2640));
                  }
                  
                  return tax.toLocaleString();
                })()}</div>
              </div>
            </div>
          </div>

          {/* Tax Calculation Results */}
          {taxCalculation && (
            <div style={{ 
              marginBottom: '20px', 
              padding: '15px', 
              border: '1px solid #dc3545', 
              borderRadius: '4px',
              backgroundColor: '#fff5f5'
            }}>
              <h4>חישוב מס הכנסה</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <div>
                  <div><strong>סך הכנסה שנתית:</strong> ₪{taxCalculation.total_income.toLocaleString()}</div>
                  <div><strong>הכנסה חייבת במס:</strong> ₪{taxCalculation.taxable_income.toLocaleString()}</div>
                  <div><strong>הכנסה פטורה ממס:</strong> ₪{taxCalculation.exempt_income.toLocaleString()}</div>
                  <div style={{ color: '#dc3545' }}><strong>מס נטו לתשלום:</strong> ₪{taxCalculation.net_tax.toLocaleString()}</div>
                </div>
                <div>
                  <div><strong>מס הכנסה:</strong> ₪{taxCalculation.income_tax.toLocaleString()}</div>
                  <div><strong>ביטוח לאומי:</strong> ₪{taxCalculation.national_insurance.toLocaleString()}</div>
                  <div><strong>מס בריאות:</strong> ₪{taxCalculation.health_tax.toLocaleString()}</div>
                  <div><strong>שיעור מס אפקטיבי:</strong> {taxCalculation.effective_tax_rate.toFixed(2)}%</div>
                </div>
              </div>
              
              {taxCalculation.applied_credits && taxCalculation.applied_credits.length > 0 && (
                <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #ddd' }}>
                  <strong>נקודות זיכוי:</strong>
                  <div style={{ marginTop: '5px' }}>
                    {taxCalculation.applied_credits.map((credit: any, index: number) => (
                      <div key={index} style={{ fontSize: '14px' }}>
                        • {credit.description}: ₪{credit.amount.toLocaleString()}
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: '10px', color: '#28a745' }}>
                    <strong>סך זיכויים: ₪{taxCalculation.tax_credits_amount.toLocaleString()}</strong>
                  </div>
                </div>
              )}
              
              <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #ddd' }}>
                <div style={{ color: '#28a745', fontSize: '18px' }}>
                  <strong>הכנסה נטו לאחר מס: ₪{taxCalculation.net_income.toLocaleString()}</strong>
                </div>
                <div style={{ fontSize: '14px', color: '#666', marginTop: '5px' }}>
                  הכנסה חודשית נטו: ₪{(taxCalculation.net_income / 12).toLocaleString()}
                </div>
              </div>
            </div>
          )}

          {/* Tax Calculation Report */}
          {client && (
            <div style={{ 
              marginBottom: '20px', 
              padding: '15px', 
              border: '1px solid #ddd', 
              borderRadius: '4px',
              backgroundColor: '#f0f8ff'
            }}>
              <h4>דוח חישוב מס מפורט</h4>
              <div style={{ fontSize: '14px', color: '#666', marginBottom: '15px' }}>
                חישוב מס הכנסה כולל נקודות זיכוי לפי הפרטים האישיים
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                {/* Personal Tax Details - רק נתונים קיימים */}
                <div>
                  <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>פרטים אישיים למיסוי</h5>
                  <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                    {/* הצגת פרטים בסיסיים בלבד */}
                    {client.birth_date && (
                      <div><strong>גיל:</strong> {new Date().getFullYear() - new Date(client.birth_date).getFullYear()}</div>
                    )}
                    {client.gender && (
                      <div><strong>מין:</strong> {client.gender === 'male' ? 'זכר' : client.gender === 'female' ? 'נקבה' : client.gender}</div>
                    )}
                    
                    {/* הצגת נקודות זיכוי רק אם קיימות */}
                    {client.tax_credit_points && client.tax_credit_points > 0 && (
                      <div><strong>נקודות זיכוי (ידני):</strong> {client.tax_credit_points}</div>
                    )}
                    
                    {/* הצגת שדות נוספים רק אם קיימים ומוגדרים */}
                    {client.marital_status && (
                      <div><strong>מצב משפחתי:</strong> {client.marital_status}</div>
                    )}
                    {client.num_children && client.num_children > 0 && (
                      <div><strong>מספר ילדים:</strong> {client.num_children}</div>
                    )}
                    {client.is_disabled && client.disability_percentage && (
                      <div><strong>אחוז נכות:</strong> {client.disability_percentage}%</div>
                    )}
                    {client.is_new_immigrant && (
                      <div><strong>עולה חדש:</strong> כן {client.immigration_date && `(מ-${new Date(client.immigration_date).getFullYear()})`}</div>
                    )}
                    {client.is_veteran && (
                      <div><strong>חייל משוחרר:</strong> כן {client.military_discharge_date && `(${new Date(client.military_discharge_date).getFullYear()})`}</div>
                    )}
                    {client.reserve_duty_days && client.reserve_duty_days > 0 && (
                      <div><strong>ימי מילואים:</strong> {client.reserve_duty_days} ימים בשנה</div>
                    )}
                    
                    {/* אם אין נתונים מיוחדים */}
                    {!client.marital_status && !client.num_children && !client.is_disabled && 
                     !client.is_new_immigrant && !client.is_veteran && !client.reserve_duty_days && 
                     (!client.tax_credit_points || client.tax_credit_points === 0) && (
                      <div style={{ color: '#6c757d', fontStyle: 'italic' }}>לא הוזנו פרטים מיוחדים למיסוי</div>
                    )}
                  </div>
                </div>

                {/* Tax Credits Display - רק הצגה ללא חישובים */}
                <div>
                  <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>נקודות זיכוי</h5>
                  <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                    {client.tax_credit_points && client.tax_credit_points > 0 ? (
                      <div>
                        <div><strong>נקודות זיכוי (ידני):</strong> {client.tax_credit_points}</div>
                        <div><strong>סכום זיכוי שנתי:</strong> ₪{(client.tax_credit_points * 2640).toLocaleString()}</div>
                      </div>
                    ) : (
                      <div style={{ color: '#6c757d', fontStyle: 'italic' }}>
                        לא הוזנו נקודות זיכוי
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Current Case Tax Calculation - חישוב מס למקרה הנוכחי */}
              <div style={{ marginTop: '15px' }}>
                <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>חישוב מס למקרה הנוכחי</h5>
                <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                  {(() => {
                    // חישוב הכנסה שנתית נוכחית
                    const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
                      sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
                    const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
                      sum + (income.monthly_amount || (income.annual_amount ? income.annual_amount / 12 : 0)), 0);
                    const totalAnnualIncome = (monthlyPension + monthlyAdditional) * 12;
                    
                    if (totalAnnualIncome === 0) {
                      return (
                        <div style={{ textAlign: 'center', color: '#6c757d', fontStyle: 'italic' }}>
                          אין הכנסות מוגדרות לחישוב מס
                        </div>
                      );
                    }
                    
                    // חישוב מס בסיסי לפי מדרגות
                    let baseTax = 0;
                    let remaining = totalAnnualIncome;
                    const brackets = [
                      { min: 0, max: 84120, rate: 0.10 },
                      { min: 84120, max: 120720, rate: 0.14 },
                      { min: 120720, max: 193800, rate: 0.20 },
                      { min: 193800, max: 269280, rate: 0.31 },
                      { min: 269280, max: 560280, rate: 0.35 },
                      { min: 560280, max: 721560, rate: 0.47 },
                      { min: 721560, max: Infinity, rate: 0.50 }
                    ];
                    
                    const taxBreakdown = [];
                    for (const bracket of brackets) {
                      if (remaining <= 0) break;
                      const taxableInBracket = Math.min(remaining, bracket.max - bracket.min);
                      const taxInBracket = taxableInBracket * bracket.rate;
                      if (taxableInBracket > 0) {
                        baseTax += taxInBracket;
                        taxBreakdown.push({
                          range: bracket.max === Infinity ? `₪${bracket.min.toLocaleString()}+` : `₪${bracket.min.toLocaleString()}-${bracket.max.toLocaleString()}`,
                          amount: taxableInBracket,
                          rate: (bracket.rate * 100).toFixed(0),
                          tax: taxInBracket
                        });
                      }
                      remaining -= taxableInBracket;
                    }
                    
                    // חישוב נקודות זיכוי
                    const taxCredits = client?.tax_credit_points ? client.tax_credit_points * 2640 : 0;
                    const finalTax = Math.max(0, baseTax - taxCredits);
                    
                    return (
                      <div>
                        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                          <strong>סך הכנסה שנתית: ₪{totalAnnualIncome.toLocaleString()}</strong>
                          <div>הכנסה חודשית: ₪{(totalAnnualIncome / 12).toLocaleString()}</div>
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                          <div>
                            <strong>חישוב מס לפי מדרגות:</strong>
                            {taxBreakdown.map((item, index) => (
                              <div key={index}>
                                {item.range}: ₪{item.tax.toLocaleString()} ({item.rate}%)
                              </div>
                            ))}
                            <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px' }}>
                              <strong>סה"כ מס בסיסי: ₪{baseTax.toLocaleString()}</strong>
                            </div>
                          </div>
                          
                          <div>
                            <strong>נקודות זיכוי:</strong>
                            {client?.tax_credit_points && client.tax_credit_points > 0 ? (
                              <div>
                                <div>נקודות: {client.tax_credit_points}</div>
                                <div>זיכוי שנתי: ₪{taxCredits.toLocaleString()}</div>
                              </div>
                            ) : (
                              <div style={{ color: '#6c757d' }}>ללא נקודות זיכוי</div>
                            )}
                          </div>
                          
                          <div>
                            <strong>מס סופי:</strong>
                            <div>מס בסיסי: ₪{baseTax.toLocaleString()}</div>
                            {taxCredits > 0 && (
                              <div>פחות זיכוי: ₪{taxCredits.toLocaleString()}</div>
                            )}
                            <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px', fontWeight: 'bold', color: '#28a745' }}>
                              <strong>מס לתשלום: ₪{finalTax.toLocaleString()}</strong>
                            </div>
                            <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                              מס חודשי: ₪{(finalTax / 12).toLocaleString()}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()} 
                </div>
              </div>
            </div>
          )}

          {/* Annual Cashflow Projection */}
          <div style={{ 
            marginBottom: '20px', 
            padding: '15px', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: '#f9f9f9'
          }}>
            <h4>תזרים מזומנים עתידי</h4>
            <div style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
              הטבלה מציגה הכנסות חודשיות, מס חודשי והכנסה נטו לכל שנה. עמודות המס מוצגות בצבע אדום בהיר.
            </div>
            <div style={{ maxHeight: '400px', overflowY: 'auto', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1200px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#e9ecef' }}>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', position: 'sticky', left: 0, backgroundColor: '#e9ecef' }}>שנה</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#f0f8ff' }}>הכנסה נטו</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold' }}>סה"כ הכנסה</th>
                    <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', fontWeight: 'bold', backgroundColor: '#ffe4e1' }}>סה"כ מס</th>
                    {pensionFunds.map(fund => (
                      <React.Fragment key={`fund-${fund.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>
                          {fund.fund_name} {fund.fund_number ? `(${fund.fund_number})` : ''}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {fund.fund_name}
                        </th>
                      </React.Fragment>
                    ))}
                    {additionalIncomes.map(income => (
                      <React.Fragment key={`income-${income.id}`}>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right' }}>
                          {income.income_name || income.description || income.income_type || income.source_type || 'הכנסה נוספת'}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {income.income_name || income.description || income.income_type || income.source_type || 'הכנסה נוספת'}
                        </th>
                      </React.Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {generateYearlyProjection().map((yearData, index) => (
                    <tr key={index} style={{ backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                      <td style={{ padding: '8px', border: '1px solid #ddd', position: 'sticky', left: 0, backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                        {yearData.year}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold', backgroundColor: '#f0f8ff' }}>
                        ₪{yearData.netMonthlyIncome.toLocaleString()}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold' }}>
                        ₪{yearData.totalMonthlyIncome.toLocaleString()}
                      </td>
                      <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', fontWeight: 'bold', backgroundColor: '#ffe4e1' }}>
                        ₪{yearData.totalMonthlyTax.toLocaleString()}
                      </td>
                      {yearData.incomeBreakdown.map((income, i) => (
                        <React.Fragment key={i}>
                          <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left' }}>
                            ₪{income.toLocaleString()}
                          </td>
                          <td style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left', backgroundColor: '#ffe4e1' }}>
                            ₪{(yearData.taxBreakdown[i] || 0).toLocaleString()}
                          </td>
                        </React.Fragment>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {!reportData && !loading && pensionFunds.length === 0 && additionalIncomes.length === 0 && capitalAssets.length === 0 && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fff3cd', 
          borderRadius: '4px',
          textAlign: 'center',
          color: '#856404'
        }}>
          אין מספיק נתונים ליצירת דוח. יש להוסיף קרנות פנסיה, הכנסות נוספות או נכסי הון תחילה.
          <div style={{ marginTop: '10px' }}>
            <a href={`/clients/${id}/pension-funds`} style={{ color: '#007bff', textDecoration: 'none', marginRight: '15px' }}>
              הוסף קרנות פנסיה ←
            </a>
            <a href={`/clients/${id}/additional-incomes`} style={{ color: '#007bff', textDecoration: 'none', marginRight: '15px' }}>
              הוסף הכנסות נוספות ←
            </a>
            <a href={`/clients/${id}/capital-assets`} style={{ color: '#007bff', textDecoration: 'none' }}>
              הוסף נכסי הון ←
            </a>
          </div>
        </div>
      )}

      <div style={{ 
        marginTop: '30px', 
        padding: '15px', 
        backgroundColor: '#e9ecef', 
        borderRadius: '4px',
        fontSize: '14px'
      }}>
        <strong>הסבר:</strong> הדוחות מבוססים על כלל הנתונים שהוזנו במערכת - מענקים, תרחישים, וחישובי מס. 
        דוח ה-PDF מכיל את כל הפרטים כולל גרפים וטבלאות מפורטות. 
        דוח ה-Excel מאפשר עיבוד נוסף של הנתונים.
      </div>
    </div>
  );
};

export default SimpleReports;
