import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { ReportHeader } from './Reports/components/ReportHeader';
import { ExportControls } from './Reports/components/ExportControls';
import { YearlyBreakdown } from './Reports/components/YearlyBreakdown';
import { NPVAnalysis } from './Reports/components/NPVAnalysis';
import { IncomeDetails } from './Reports/components/IncomeDetails';
import { useReportsPage } from './Reports/hooks/useReportsPage';
import './Reports/Reports.css';

const ReportsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const {
    loading,
    error,
    pensionFunds,
    additionalIncomes,
    capitalAssets,
    client,
    fixationData,
    yearlyProjectionWithExemption,
    npvComparison,
    totalCapitalValue,
    handleGenerateHTML,
    handleGenerateFixationDocuments,
  } = useReportsPage(id);

  // טעינה
  if (loading) {
    return (
      <div className="reports-loading">
        <div>טוען נתונים...</div>
      </div>
    );
  }

  // שגיאה
  if (error) {
    return (
      <div className="reports-error">
        <div className="reports-error-message">שגיאה: {error}</div>
        <Link to={`/clients/${id}`}>חזרה לפרטי לקוח</Link>
      </div>
    );
  }

  // אם אין נתונים
  if (!pensionFunds.length && !additionalIncomes.length && !capitalAssets.length) {
    return (
      <div className="reports-no-data">
        <h3>אין מספיק נתונים ליצירת דוח</h3>
        <p>אנא הוסף קצבאות, הכנסות נוספות או נכסי הון</p>
        <div className="reports-no-data-links">
          <Link to={`/clients/${id}/pension-funds`} className="reports-no-data-link">
            הוסף קצבאות ←
          </Link>
          <Link to={`/clients/${id}/additional-incomes`} className="reports-no-data-link">
            הוסף הכנסות נוספות ←
          </Link>
          <Link to={`/clients/${id}/capital-assets`} className="reports-no-data-link">
            הוסף נכסי הון ←
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="reports-page-container">
      <div className="reports-page-header">
        <h2>תיק פרישה - {client?.name}</h2>
        <ExportControls
          yearlyProjection={yearlyProjectionWithExemption}
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
        yearlyProjection={yearlyProjectionWithExemption}
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

      <div className="reports-back-wrapper">
        <Link to={`/clients/${id}`} className="reports-back-link">
          חזרה לפרטי לקוח
        </Link>
      </div>
    </div>
  );
};

export default ReportsPage;
