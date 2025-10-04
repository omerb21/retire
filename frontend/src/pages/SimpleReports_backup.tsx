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
          
          let monthlyAmount = 0;
          let source = 'ללא הכנסה';
          
          if (isPensionActive) {
            // חישוב הכנסה חודשית מקרנות פנסיה
            const monthlyPension = pensionFunds.reduce((sum: number, fund: any) => 
              sum + (fund.computed_monthly_amount || fund.monthly_amount || 0), 0);
            const monthlyAdditional = additionalIncomes.reduce((sum: number, income: any) => 
              sum + (income.monthly_amount || income.annual_amount / 12 || 0), 0);
            
            monthlyAmount = monthlyPension + monthlyAdditional;
            source = monthlyPension > 0 ? 'פנסיה' : 'הכנסות נוספות';
          }
          
          return {
            date: monthDate.toISOString().split('T')[0],
            amount: Math.round(monthlyAmount),
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
            name: client ? `${client.first_name || ''} ${client.last_name || ''}`.trim() || 'לא צוין' : 'לא צוין',
            id_number: client?.id_number || 'לא צוין'
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
      // נקודות זיכוי ידניות (אם הוזנו)
      if (client.tax_credit_points && client.tax_credit_points > 0) {
        totalTaxCredits = client.tax_credit_points * creditPointValue;
      } else {
        // חישוב אוטומטי של נקודות זיכוי
        let creditPoints = 1; // נקודה בסיסית
        
        // נקודות זיכוי לילדים
        if (client.num_children) {
          creditPoints += client.num_children * 0.5;
        }
        
        // נקודות זיכוי לנכות
        if (client.is_disabled && client.disability_percentage) {
          if (client.disability_percentage >= 75) {
            creditPoints += 3;
          } else if (client.disability_percentage >= 40) {
            creditPoints += 1.5;
          }
        }
        
        // נקודות זיכוי לעולים חדשים
        if (client.is_new_immigrant && client.immigration_date) {
          const immigrationYear = new Date(client.immigration_date).getFullYear();
          const currentYear = new Date().getFullYear();
          const yearsInIsrael = currentYear - immigrationYear;
          
          if (yearsInIsrael <= 3.5) {
            creditPoints += 1;
          }
        }
        
        // נקודות זיכוי למילואים
        if (client.reserve_duty_days && client.reserve_duty_days > 0) {
          const reservePoints = Math.min(client.reserve_duty_days / 30, 1);
          creditPoints += reservePoints;
        }
        
        // נקודות זיכוי לזקנה (לפנסיונרים)
        if (incomeType === 'pension' && client.birth_date) {
          const age = new Date().getFullYear() - new Date(client.birth_date).getFullYear();
          const retirementAge = client.gender === 'male' ? 67 : 62;
          
          if (age >= retirementAge) {
            creditPoints += 1;
          }
        }
        
        totalTaxCredits = creditPoints * creditPointValue;
      }
    }
    
    // הפחתת נקודות הזיכוי מהמס
    const finalTax = Math.max(0, baseTax - totalTaxCredits);
    
    return finalTax;
  };

  // Generate yearly projection data based on pension funds and additional incomes
  const generateYearlyProjection = (): YearlyProjection[] => {
    if (!reportData) return [];
    
    const currentYear = new Date().getFullYear();
    const clientBirthYear = 1957; // Default birth year if not available
    const maxAge = 90;
    const maxYear = clientBirthYear + maxAge;
    const projectionYears = Math.min(maxYear - currentYear + 1, 40); // Limit to 40 years max
    
    // Create array of years from current year to max age (or 40 years, whichever is less)
    const yearlyData: YearlyProjection[] = [];
    
    for (let i = 0; i < projectionYears; i++) {
      const year = currentYear + i;
      const clientAge = year - clientBirthYear;
      
      // Initialize income breakdown array
      const incomeBreakdown: number[] = [];
      let totalMonthlyIncome = 0;
      
      // Add pension fund incomes
      pensionFunds.forEach(fund => {
        const fundStartYear = fund.start_date ? parseInt(fund.start_date.split('-')[0]) : 2025;
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
        const incomeStartYear = income.start_date ? parseInt(income.start_date.split('-')[0]) : currentYear;
        const incomeEndYear = income.end_date ? parseInt(income.end_date.split('-')[0]) : maxYear;
        const monthlyAmount = income.monthly_amount || (income.annual_amount ? income.annual_amount / 12 : 0);
        
        // Only add income if it's active in this year
        const amount = (year >= incomeStartYear && year <= incomeEndYear) ? monthlyAmount : 0;
        incomeBreakdown.push(Math.round(amount));
        totalMonthlyIncome += amount;
      });
      
      // חישוב מס לכל הכנסה
      const taxBreakdown: number[] = [];
      let totalMonthlyTax = 0;
      
      // מס על קרנות פנסיה
      pensionFunds.forEach((fund, index) => {
        const incomeAmount = incomeBreakdown[index] || 0;
        const annualIncome = incomeAmount * 12;
        const monthlyTax = calculateTaxForIncome(annualIncome, 'pension') / 12;
        taxBreakdown.push(Math.round(monthlyTax));
        totalMonthlyTax += monthlyTax;
      });
      
      // מס על הכנסות נוספות
      additionalIncomes.forEach((income, index) => {
        const incomeIndex = pensionFunds.length + index;
        const incomeAmount = incomeBreakdown[incomeIndex] || 0;
        const annualIncome = incomeAmount * 12;
        const monthlyTax = calculateTaxForIncome(annualIncome, 'additional') / 12;
        taxBreakdown.push(Math.round(monthlyTax));
        totalMonthlyTax += monthlyTax;
      });

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

  const calculateTaxImpact = async () => {
    if (!reportData) return;

    try {
      // חישוב סך ההכנסות השנתיות
      const totalPensionIncome = pensionFunds.reduce((sum, fund) => {
        return sum + ((fund.computed_monthly_amount || fund.monthly_amount || 0) * 12);
      }, 0);

      const totalAdditionalIncome = additionalIncomes.reduce((sum, income) => {
        return sum + (income.annual_amount || (income.monthly_amount * 12) || 0);
      }, 0);

      // יצירת נתוני קלט לחישוב מס
      const taxInput = {
        tax_year: new Date().getFullYear(),
        personal_details: {
          birth_date: reportData.client_info.birth_year ? `${reportData.client_info.birth_year}-01-01` : null,
          marital_status: 'single', // ברירת מחדל
          num_children: 0,
          is_new_immigrant: false,
          is_veteran: false,
          is_disabled: false,
          is_student: false,
          reserve_duty_days: 0
        },
        salary_income: 0, // אין שכר בפרישה
        pension_income: totalPensionIncome,
        rental_income: totalAdditionalIncome, // מניחים שזה הכנסה משכירות
        capital_gains: 0,
        business_income: 0,
        interest_income: 0,
        dividend_income: 0,
        other_income: 0,
        pension_contributions: 0, // אין הפרשות בפרישה
        study_fund_contributions: 0,
        insurance_premiums: 0,
        charitable_donations: 0
      };

      const response = await axios.post('/api/v1/tax/calculate', taxInput);
      setTaxCalculation(response.data);

    } catch (err) {
      console.error('שגיאה בחישוב מס:', err);
    }
  };

  // חישוב מס אוטומטי כשהנתונים מוכנים
  useEffect(() => {
    if (reportData && pensionFunds.length > 0) {
      calculateTaxImpact();
    }
  }, [reportData, pensionFunds, additionalIncomes]);

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

      // Generate Excel report
      const response = await axios.post(`/api/v1/reports/clients/${id}/reports/excel`, {
        report_data: reportData
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
                      <div><strong>{income.description || income.income_type}</strong></div>
                      <div>הכנסה חודשית: ₪{(income.monthly_amount || 0).toLocaleString()}</div>
                      <div>הכנסה שנתית: ₪{(income.annual_amount || income.monthly_amount * 12 || 0).toLocaleString()}</div>
                      <div>תאריך התחלה: {income.start_date || 'לא צוין'}</div>
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
                <div><strong>סך הכנסה חודשית:</strong> ₪{((reportData.financial_summary.total_pension_value / 240) + (reportData.financial_summary.total_additional_income / 12)).toLocaleString()}</div>
                <div><strong>סך נכסים:</strong> ₪{reportData.financial_summary.total_wealth.toLocaleString()}</div>
                <div><strong>תאריך התחלת תזרים:</strong> {reportData.cashflow_projection[0]?.date ? new Date(reportData.cashflow_projection[0].date).toLocaleDateString('he-IL') : 'לא צוין'}</div>
                <div style={{ color: '#dc3545' }}><strong>מס משוער:</strong> ₪{reportData.financial_summary.estimated_tax.toLocaleString()}</div>
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
                {/* Personal Tax Details */}
                <div>
                  <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>פרטים אישיים למיסוי</h5>
                  <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                    <div><strong>גיל:</strong> {client.birth_date ? new Date().getFullYear() - new Date(client.birth_date).getFullYear() : 'לא צוין'}</div>
                    <div><strong>מין:</strong> {client.gender === 'male' ? 'זכר' : client.gender === 'female' ? 'נקבה' : 'לא צוין'}</div>
                    <div><strong>מצב משפחתי:</strong> {client.marital_status || 'לא צוין'}</div>
                    <div><strong>מספר ילדים:</strong> {client.num_children || 0}</div>
                    {client.is_disabled && (
                      <div><strong>אחוז נכות:</strong> {client.disability_percentage || 0}%</div>
                    )}
                    {client.is_new_immigrant && (
                      <div><strong>עולה חדש:</strong> כן {client.immigration_date && `(מ-${new Date(client.immigration_date).getFullYear()})`}</div>
                    )}
                    {client.is_veteran && (
                      <div><strong>חייל משוחרר:</strong> כן {client.military_discharge_date && `(${new Date(client.military_discharge_date).getFullYear()})`}</div>
                    )}
                    {client.reserve_duty_days > 0 && (
                      <div><strong>ימי מילואים:</strong> {client.reserve_duty_days} ימים בשנה</div>
                    )}
                  </div>
                </div>

                {/* Tax Credits Calculation */}
                <div>
                  <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>חישוב נקודות זיכוי</h5>
                  <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                    {client.tax_credit_points && client.tax_credit_points > 0 ? (
                      <div>
                        <div><strong>נקודות זיכוי (ידני):</strong> {client.tax_credit_points}</div>
                        <div><strong>סכום זיכוי שנתי:</strong> ₪{(client.tax_credit_points * 2640).toLocaleString()}</div>
                      </div>
                    ) : (
                      <div>
                        <div><strong>נקודת זיכוי בסיסית:</strong> 1.0 נקודה</div>
                        {client.num_children > 0 && (
                          <div><strong>זיכוי לילדים:</strong> {client.num_children * 0.5} נקודות</div>
                        )}
                        {client.is_disabled && client.disability_percentage >= 40 && (
                          <div><strong>זיכוי נכות:</strong> {client.disability_percentage >= 75 ? '3.0' : '1.5'} נקודות</div>
                        )}
                        {client.is_new_immigrant && client.immigration_date && 
                         (new Date().getFullYear() - new Date(client.immigration_date).getFullYear() <= 3.5) && (
                          <div><strong>זיכוי עולה חדש:</strong> 1.0 נקודה</div>
                        )}
                        {client.reserve_duty_days > 0 && (
                          <div><strong>זיכוי מילואים:</strong> {Math.min(client.reserve_duty_days / 30, 1).toFixed(1)} נקודות</div>
                        )}
                        <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px', fontWeight: 'bold' }}>
                          <div><strong>סה"כ נקודות זיכוי:</strong> {(() => {
                            let total = 1; // בסיסי
                            if (client.num_children) total += client.num_children * 0.5;
                            if (client.is_disabled && client.disability_percentage >= 75) total += 3;
                            else if (client.is_disabled && client.disability_percentage >= 40) total += 1.5;
                            if (client.is_new_immigrant && client.immigration_date && 
                                (new Date().getFullYear() - new Date(client.immigration_date).getFullYear() <= 3.5)) total += 1;
                            if (client.reserve_duty_days > 0) total += Math.min(client.reserve_duty_days / 30, 1);
                            return total.toFixed(1);
                          })()} נקודות</div>
                          <div><strong>סכום זיכוי שנתי:</strong> ₪{(() => {
                            let total = 1;
                            if (client.num_children) total += client.num_children * 0.5;
                            if (client.is_disabled && client.disability_percentage >= 75) total += 3;
                            else if (client.is_disabled && client.disability_percentage >= 40) total += 1.5;
                            if (client.is_new_immigrant && client.immigration_date && 
                                (new Date().getFullYear() - new Date(client.immigration_date).getFullYear() <= 3.5)) total += 1;
                            if (client.reserve_duty_days > 0) total += Math.min(client.reserve_duty_days / 30, 1);
                            return (total * 2640).toLocaleString();
                          })()}</div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Sample Tax Calculation */}
              <div style={{ marginTop: '15px' }}>
                <h5 style={{ color: '#0056b3', marginBottom: '10px' }}>דוגמה לחישוב מס (על הכנסה שנתית של ₪200,000)</h5>
                <div style={{ backgroundColor: 'white', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                    <div>
                      <strong>מס בסיסי:</strong>
                      <div>₪0-84,000: ₪8,400 (10%)</div>
                      <div>₪84,001-121,000: ₪5,180 (14%)</div>
                      <div>₪121,001-200,000: ₪15,800 (20%)</div>
                      <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px' }}>
                        <strong>סה"כ מס בסיסי: ₪29,380</strong>
                      </div>
                    </div>
                    <div>
                      <strong>נקודות זיכוי:</strong>
                      <div>זיכוי שנתי: ₪{(() => {
                        let total = 1;
                        if (client.num_children) total += client.num_children * 0.5;
                        if (client.is_disabled && client.disability_percentage >= 75) total += 3;
                        else if (client.is_disabled && client.disability_percentage >= 40) total += 1.5;
                        if (client.is_new_immigrant && client.immigration_date && 
                            (new Date().getFullYear() - new Date(client.immigration_date).getFullYear() <= 3.5)) total += 1;
                        if (client.reserve_duty_days > 0) total += Math.min(client.reserve_duty_days / 30, 1);
                        return (total * 2640).toLocaleString();
                      })()}</div>
                    </div>
                    <div>
                      <strong>מס סופי:</strong>
                      <div>מס בסיסי: ₪29,380</div>
                      <div>פחות זיכוי: ₪{(() => {
                        let total = 1;
                        if (client.num_children) total += client.num_children * 0.5;
                        if (client.is_disabled && client.disability_percentage >= 75) total += 3;
                        else if (client.is_disabled && client.disability_percentage >= 40) total += 1.5;
                        if (client.is_new_immigrant && client.immigration_date && 
                            (new Date().getFullYear() - new Date(client.immigration_date).getFullYear() <= 3.5)) total += 1;
                        if (client.reserve_duty_days > 0) total += Math.min(client.reserve_duty_days / 30, 1);
                        return (total * 2640).toLocaleString();
                      })()}</div>
                      <div style={{ borderTop: '1px solid #eee', paddingTop: '5px', marginTop: '5px', fontWeight: 'bold', color: '#28a745' }}>
                        <strong>מס לתשלום: ₪{Math.max(0, 29380 - (() => {
                          let total = 1;
                          if (client.num_children) total += client.num_children * 0.5;
                          if (client.is_disabled && client.disability_percentage >= 75) total += 3;
                          else if (client.is_disabled && client.disability_percentage >= 40) total += 1.5;
                          if (client.is_new_immigrant && client.immigration_date && 
                              (new Date().getFullYear() - new Date(client.immigration_date).getFullYear() <= 3.5)) total += 1;
                          if (client.reserve_duty_days > 0) total += Math.min(client.reserve_duty_days / 30, 1);
                          return total * 2640;
                        })()).toLocaleString()}</strong>
                      </div>
                    </div>
                  </div>
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
                          {income.description || income.income_type}
                        </th>
                        <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'right', backgroundColor: '#ffe4e1', fontSize: '12px' }}>
                          מס {income.description || income.income_type}
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
