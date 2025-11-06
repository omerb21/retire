import React, { useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useReportData } from '../../components/reports/hooks/useReportData';
import { generateYearlyProjection } from '../../components/reports/calculations/cashflowCalculations';
import { calculateNPVComparison } from '../../components/reports/calculations/npvCalculations';
import { ReportHeader } from './components/ReportHeader';
import { ExportControls } from './components/ExportControls';
import { YearlyBreakdown } from './components/YearlyBreakdown';
import { NPVAnalysis } from './components/NPVAnalysis';
import { IncomeDetails } from './components/IncomeDetails';
import { generateHTMLReport } from './utils/htmlReportGenerator';

const ReportsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  
  // שימוש ב-hook המפוצל לטעינת נתונים
  const {
    loading,
    error,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    client,
    fixationData
  } = useReportData(id);

  // חישוב תחזית שנתית באמצעות הפונקציה המפוצלת
  const yearlyProjection = useMemo(() => {
    if (!client || pensionFunds.length === 0) {
      return [];
    }
    return generateYearlyProjection(pensionFunds, additionalIncomes, capitalAssets, client, fixationData);
  }, [pensionFunds, additionalIncomes, capitalAssets, client, fixationData]);

  // חישוב NPV
  const npvComparison = useMemo(() => {
    if (yearlyProjection.length === 0) return null;
    return calculateNPVComparison(yearlyProjection, 0.03);
  }, [yearlyProjection]);

  // חישוב סיכומים
  const totalPensionBalance = useMemo(() => 
    pensionFunds.reduce((sum, fund) => sum + (parseFloat(fund.balance) || 0), 0),
    [pensionFunds]
  );

  const totalMonthlyPension = useMemo(() => 
    pensionFunds.reduce((sum, fund) => 
      sum + (parseFloat(fund.pension_amount) || parseFloat(fund.computed_monthly_amount) || parseFloat(fund.monthly_amount) || 0), 0),
    [pensionFunds]
  );

  const totalAdditionalIncome = useMemo(() => 
    additionalIncomes.reduce((sum, income) => {
      const amount = parseFloat(income.amount) || 0;
      let monthlyAmount = amount;
      if (income.frequency === 'quarterly') monthlyAmount = amount / 3;
      else if (income.frequency === 'annually') monthlyAmount = amount / 12;
      return sum + monthlyAmount;
    }, 0),
    [additionalIncomes]
  );

  const totalCapitalValue = useMemo(() => 
    capitalAssets.reduce((sum, asset) => sum + (parseFloat(asset.current_value) || 0), 0),
    [capitalAssets]
  );

  const totalMonthlyIncome = totalMonthlyPension + totalAdditionalIncome;

  // פונקציות ייצוא
  const handleGenerateHTML = () => {
    const htmlContent = generateHTMLReport(
      client,
      fixationData,
      yearlyProjection,
      pensionFunds,
      additionalIncomes,
      capitalAssets,
      npvComparison,
      totalPensionBalance,
      totalCapitalValue,
      totalMonthlyIncome
    );
    
    const reportWindow = window.open('', '_blank');

    if (!reportWindow) {
      alert('יש לאפשר פתיחת חלונות קופצים להצגת הדוח');
      return;
    }

    reportWindow.document.open();
    reportWindow.document.write(htmlContent);
    reportWindow.document.close();
    reportWindow.focus();
  };

  const handleGenerateFixationDocuments = async () => {
    if (!fixationData || !client) {
      alert('אין נתוני קיבוע זכויות');
      return;
    }
    try {
      const response = await fetch(`/api/v1/fixation/${client.id}/package`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `מסמכי_קיבוע_${client?.name || 'לקוח'}.zip`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const errorText = await response.text();
        console.error('Server error:', errorText);
        alert('שגיאה בהפקת מסמכי קיבוע: ' + errorText);
      }
    } catch (error) {
      console.error('Error generating fixation documents:', error);
      alert('שגיאה בהפקת מסמכי קיבוע');
    }
  };

  // טעינה
  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <div>טוען נתונים...</div>
      </div>
    );
  }

  // שגיאה
  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <div style={{ color: 'red', marginBottom: '20px' }}>שגיאה: {error}</div>
        <Link to={`/clients/${id}`}>חזרה לפרטי לקוח</Link>
      </div>
    );
  }

  // אם אין נתונים
  if (!pensionFunds.length && !additionalIncomes.length && !capitalAssets.length) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h3>אין מספיק נתונים ליצירת דוח</h3>
        <p>אנא הוסף קצבאות, הכנסות נוספות או נכסי הון</p>
        <div style={{ marginTop: '10px' }}>
          <Link to={`/clients/${id}/pension-funds`} style={{ color: '#007bff', marginRight: '15px' }}>
            הוסף קצבאות ←
          </Link>
          <Link to={`/clients/${id}/additional-incomes`} style={{ color: '#007bff', marginRight: '15px' }}>
            הוסף הכנסות נוספות ←
          </Link>
          <Link to={`/clients/${id}/capital-assets`} style={{ color: '#007bff' }}>
            הוסף נכסי הון ←
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', direction: 'rtl' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>דוחות פנסיה - {client?.name}</h2>
        <ExportControls
          yearlyProjection={yearlyProjection}
          pensionFunds={pensionFunds}
          additionalIncomes={additionalIncomes}
          capitalAssets={capitalAssets}
          client={client}
          fixationData={fixationData}
          onGenerateHTML={handleGenerateHTML}
          onGenerateFixationDocuments={fixationData ? handleGenerateFixationDocuments : undefined}
        />
      </div>

      <ReportHeader client={client} fixationData={fixationData} />

      <YearlyBreakdown
        yearlyProjection={yearlyProjection}
        pensionFunds={pensionFunds}
        additionalIncomes={additionalIncomes}
        capitalAssets={capitalAssets}
      />

      <NPVAnalysis
        npvComparison={npvComparison}
        totalCapitalValue={totalCapitalValue}
      />

      <IncomeDetails
        pensionFunds={pensionFunds}
        additionalIncomes={additionalIncomes}
        capitalAssets={capitalAssets}
      />

      <div style={{ marginTop: '30px', textAlign: 'center' }}>
        <Link to={`/clients/${id}`} style={{ 
          padding: '10px 20px', 
          backgroundColor: '#6c757d', 
          color: 'white', 
          textDecoration: 'none',
          borderRadius: '4px',
          display: 'inline-block'
        }}>
          חזרה לפרטי לקוח
        </Link>
      </div>
    </div>
  );
};

export default ReportsPage;
