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
    <section style={{ marginBottom: 32, padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
      <h3>קליטת נתוני מסלקה</h3>
      
      {/* הוראות שימוש */}
      <div style={{ marginBottom: 16, padding: 12, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
        <h4 style={{ margin: "0 0 8px 0", color: "#495057" }}>אפשרויות עיבוד:</h4>
        <ul style={{ margin: 0, paddingRight: 20, fontSize: "14px", color: "#666" }}>
          <li><strong>עיבוד ידני:</strong> בחר קבצי XML או DAT ולחץ "עבד קבצי מסלקה"</li>
          <li><strong>תמיכה בפורמטים:</strong> המערכת תומכת בקבצי XML ו-DAT (קבצי מסלקה לאחר מניפולציה)</li>
        </ul>
      </div>

      <div style={{ marginBottom: 16 }}>
        <input
          type="file"
          multiple
          accept=".xml,.dat"
          onChange={(e) => setSelectedFiles(e.target.files)}
          style={{ marginBottom: 10 }}
        />
        <div style={{ fontSize: "14px", color: "#666" }}>
          בחר קבצי XML או DAT של המסלקה לעיבוד ידני (תמיכה בשני הפורמטים)
        </div>
      </div>
      
      <div style={{ display: "flex", gap: 10 }}>
        <button
          onClick={onProcessFiles}
          disabled={!selectedFiles || loading}
          style={{
            padding: "10px 16px",
            backgroundColor: selectedFiles && !loading ? "#007bff" : "#ccc",
            color: "white",
            border: "none",
            borderRadius: 4,
            cursor: selectedFiles && !loading ? "pointer" : "not-allowed"
          }}
        >
          {loading ? "מעבד..." : "עבד קבצי מסלקה"}
        </button>
        
        <button
          onClick={onGenerateExcel}
          disabled={pensionDataLength === 0}
          style={{
            padding: "10px 16px",
            backgroundColor: pensionDataLength > 0 ? "#28a745" : "#ccc",
            color: "white",
            border: "none",
            borderRadius: 4,
            cursor: pensionDataLength > 0 ? "pointer" : "not-allowed"
          }}
        >
          יצא דוח Excel
        </button>
      </div>
    </section>
  );
};
