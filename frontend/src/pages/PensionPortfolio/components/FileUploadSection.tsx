import React from 'react';

interface FileUploadSectionProps {
  selectedFiles: FileList | null;
  setSelectedFiles: (files: FileList | null) => void;
  loading: boolean;
  pensionDataLength: number;
  onProcessFiles: () => void;
  onGenerateExcel: () => void;
}

/**
 * קומפוננטת קליטת קבצים וייצוא
 */
export const FileUploadSection: React.FC<FileUploadSectionProps> = ({
  selectedFiles,
  setSelectedFiles,
  loading,
  pensionDataLength,
  onProcessFiles,
  onGenerateExcel
}) => {
  return (
    <section className="pension-portfolio-upload-section">
      <h3>קליטת נתוני מסלקה</h3>
      
      {/* הוראות שימוש */}
      <div className="pension-portfolio-upload-instructions">
        <h4 className="pension-portfolio-upload-instructions-title">אפשרויות עיבוד:</h4>
        <ul className="pension-portfolio-upload-instructions-list">
          <li><strong>עיבוד ידני:</strong> בחר קבצי XML או DAT ולחץ "עבד קבצי מסלקה"</li>
          <li><strong>תמיכה בפורמטים:</strong> המערכת תומכת בקבצי XML ו-DAT (קבצי מסלקה לאחר מניפולציה)</li>
        </ul>
      </div>

      <div className="pension-portfolio-upload-input-group">
        <input
          type="file"
          multiple
          accept=".xml,.dat"
          onChange={(e) => setSelectedFiles(e.target.files)}
          className="pension-portfolio-upload-input"
        />
        <div className="pension-portfolio-upload-help">
          בחר קבצי XML או DAT של המסלקה לעיבוד ידני (תמיכה בשני הפורמטים)
        </div>
      </div>
      
      <div className="pension-portfolio-upload-actions">
        <button
          onClick={onProcessFiles}
          disabled={!selectedFiles || loading}
          className={`pension-portfolio-btn ${
            selectedFiles && !loading
              ? 'pension-portfolio-btn--upload-process'
              : 'pension-portfolio-btn--upload-process-disabled'
          }`}
        >
          {loading ? "מעבד..." : "עבד קבצי מסלקה"}
        </button>
        
        <button
          onClick={onGenerateExcel}
          disabled={pensionDataLength === 0}
          className={`pension-portfolio-btn ${
            pensionDataLength > 0
              ? 'pension-portfolio-btn--upload-export'
              : 'pension-portfolio-btn--upload-export-disabled'
          }`}
        >
          יצא דוח Excel
        </button>
      </div>
    </section>
  );
};
