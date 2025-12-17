import React from 'react';
import { YearlyProjection } from '../../../../components/reports/types/reportTypes';

interface ExportControlsProps {
  yearlyProjection: YearlyProjection[];
  pensionFunds: any[];
  additionalIncomes: any[];
  capitalAssets: any[];
  client: any;
  fixationData?: any;
  onGenerateHTML: () => void;
  onGenerateFixationDocuments?: () => void;
}

export const ExportControls: React.FC<ExportControlsProps> = ({
  yearlyProjection,
  pensionFunds,
  additionalIncomes,
  capitalAssets,
  client,
  fixationData,
  onGenerateHTML,
  onGenerateFixationDocuments
}) => {
  const handleGeneratePDF = async () => {
    try {
      const { generatePDFReport } = await import(
        '../../../../components/reports/generators/PDFGenerator'
      );
      await generatePDFReport(
        yearlyProjection,
        pensionFunds,
        additionalIncomes,
        capitalAssets,
        client
      );
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('שגיאה ביצירת דוח PDF');
    }
  };

  const handleGenerateExcel = async () => {
    try {
      const { generateExcelReport } = await import(
        '../../../../components/reports/generators/ExcelGenerator'
      );
      await generateExcelReport(
        yearlyProjection,
        pensionFunds,
        additionalIncomes,
        capitalAssets,
        client
      );
    } catch (error) {
      console.error('Error generating Excel:', error);
      alert('שגיאה ביצירת דוח Excel');
    }
  };

  return (
    <div className="report-export-controls">
      <button 
        onClick={handleGenerateExcel}
        className="report-export-button report-export-button--excel"
      >
        📊 דוח Excel
      </button>
      <button 
        onClick={onGenerateHTML}
        className="report-export-button report-export-button--pdf"
      >
        🌐 דוח HTML מלא
      </button>
      {fixationData && onGenerateFixationDocuments && (
        <button 
          onClick={onGenerateFixationDocuments}
          className="report-export-button report-export-button--fixation"
        >
          📋 מסמכי קיבוע
        </button>
      )}
    </div>
  );
}
;
