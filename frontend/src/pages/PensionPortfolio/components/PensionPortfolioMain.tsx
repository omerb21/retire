import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { getConversionRulesExplanation } from '../../../config/conversionRules';
import { formatDateInput } from '../../../utils/dateUtils';
import { usePensionData } from '../hooks/usePensionData';
import { usePensionConversion } from '../hooks/usePensionConversion';
import { FileUploadSection } from './FileUploadSection';
import { PensionTable } from './PensionTable';
import { generateExcelReport } from '../utils/exportUtils';

/**
 * קומפוננטה ראשית לניהול תיק פנסיוני
 * מפוצלת לקומפוננטות ו-hooks נפרדים לשיפור תחזוקה וקריאות
 */
export default function PensionPortfolioMain() {
  const { id: clientId } = useParams<{ id: string }>();
  
  // שימוש ב-hooks מפוצלים
  const pensionDataHook = usePensionData(clientId);
  const conversionHook = usePensionConversion(
    clientId,
    pensionDataHook.pensionData,
    pensionDataHook.setPensionData,
    pensionDataHook.conversionTypes,
    pensionDataHook.setConversionTypes,
    pensionDataHook.convertedAccounts,
    pensionDataHook.setConvertedAccounts,
    pensionDataHook.setLoading,
    pensionDataHook.setError,
    pensionDataHook.setProcessingStatus,
    pensionDataHook.redemptionDate,
    pensionDataHook.clientData
  );

  // פונקציה לטיפול בייצוא Excel
  const handleGenerateExcel = () => {
    try {
      generateExcelReport(pensionDataHook.pensionData, clientId || '');
      pensionDataHook.setProcessingStatus(`יוצא דוח Excel עם ${pensionDataHook.pensionData.length} תכניות פנסיוניות`);
    } catch (error: any) {
      pensionDataHook.setError(error.message);
    }
  };

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💼 תיק פנסיוני</h1>
            <p className="card-subtitle">
              ניהול יתרות קרנות פנסיה וקופות גמל
              {pensionDataHook.clientData && ` - ${pensionDataHook.clientData.first_name} ${pensionDataHook.clientData.last_name}`}
            </p>
          </div>
          <Link to={`/clients/${clientId}`} className="btn btn-secondary">
            ← חזרה
          </Link>
        </div>

        {pensionDataHook.error && (
          <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
            {pensionDataHook.error}
          </div>
        )}

        {pensionDataHook.processingStatus && (
          <div style={{ color: "blue", marginBottom: 16, padding: 8, backgroundColor: "#e7f3ff" }}>
            {pensionDataHook.processingStatus}
          </div>
        )}

        {/* קליטת קבצים */}
        <FileUploadSection
          selectedFiles={pensionDataHook.selectedFiles}
          setSelectedFiles={pensionDataHook.setSelectedFiles}
          loading={pensionDataHook.loading}
          pensionDataLength={pensionDataHook.pensionData.length}
          onProcessFiles={() => pensionDataHook.selectedFiles && pensionDataHook.processXMLFiles(pensionDataHook.selectedFiles)}
          onGenerateExcel={handleGenerateExcel}
        />

        {/* טבלת נתונים */}
        {pensionDataHook.pensionData.length > 0 && (
          <section style={{ marginBottom: 32 }}>
            <h3>נתוני התיק הפנסיוני ({pensionDataHook.pensionData.length} חשבונות)</h3>
            
            {/* הוראות שימוש */}
            <div style={{ marginBottom: 16, padding: 12, backgroundColor: "#fff3cd", borderRadius: 4, border: "1px solid #ffeaa7" }}>
              <h4 style={{ margin: "0 0 8px 0", color: "#856404" }}>הוראות שימוש:</h4>
              <ol style={{ margin: 0, paddingRight: 20, fontSize: "14px", color: "#856404" }}>
                <li><strong>שמירת תכניות:</strong> סמן תכניות בעמודה "בחר" ולחץ "שמור תכניות נבחרות" לשמירה בטבלת התכניות הפנסיוניות</li>
                <li><strong>מחיקת תכנית:</strong> לחץ "מחק" בעמודת הפעולות להסרת תכנית מהרשימה</li>
                <li><strong>המרה לקצבאות/נכסים:</strong> סמן חשבונות או סכומים ספציפיים, בחר סוג המרה ולחץ "המר חשבונות/סכומים נבחרים"</li>
                <li><strong>חוקי המרה:</strong> לחץ על הכפתור "חוקי המרה לפי חוק" כדי לצפות במגבלות המרת יתרות</li>
              </ol>
            </div>
            
            {/* כפתור חוקי המרה */}
            {/* הצגת חוקי המרה */}
            {pensionDataHook.showConversionRules && (
              <div style={{ 
                marginBottom: 16, 
                padding: 16, 
                backgroundColor: "#e7f3ff", 
                borderRadius: 4, 
                border: "2px solid #007bff",
                whiteSpace: "pre-wrap",
                fontSize: "13px",
                lineHeight: "1.6"
              }}>
                <h4 style={{ marginTop: 0, color: "#007bff" }}>חוקי המרת יתרות מתיק פנסיוני</h4>
                {getConversionRulesExplanation()}
              </div>
            )}
            
            {/* כפתור הוספה ידנית */}
            {/* שדה תאריך מימוש */}
            <div style={{ marginBottom: 16, padding: '15px', backgroundColor: '#e7f3ff', borderRadius: '4px', border: '1px solid #007bff' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', color: '#004085' }}>
                תאריך מימוש (אופציונלי):
              </label>
              <input
                type="text"
                placeholder="DD/MM/YYYY"
                value={pensionDataHook.redemptionDate}
                onChange={(e) => {
                  const formatted = formatDateInput(e.target.value);
                  pensionDataHook.setRedemptionDate(formatted);
                }}
                maxLength={10}
                style={{
                  width: '200px',
                  padding: '8px',
                  border: '1px solid #007bff',
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
              />
              <div style={{ marginTop: '8px', fontSize: '13px', color: '#004085' }}>
                💡 <strong>הסבר:</strong> אם תזין תאריך מימוש, כל ההמרות ייווצרו עם תאריך תשלום = תאריך המימוש.<br/>
                אם השדה ריק, ההמרות ייווצרו עם תאריך תשלום = תאריך גיל הפרישה של הלקוח.
              </div>
            </div>

            {/* כפתורי פעולה */}
            <div style={{ marginBottom: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
              {/* כפתור חוקי המרה */}
              <button
                onClick={() => pensionDataHook.setShowConversionRules(!pensionDataHook.showConversionRules)}
                style={{
                  padding: "10px 20px",
                  backgroundColor: "#17a2b8",
                  color: "white",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: "bold"
                }}
                title="הצג/הסתר חוקי המרה לפי חוק"
              >
                📋 {pensionDataHook.showConversionRules ? 'הסתר חוקי המרה' : 'חוקי המרה לפי חוק'}
              </button>

              {/* כפתור הוספה ידנית */}
              <button
                onClick={pensionDataHook.addManualAccount}
                style={{
                  padding: "10px 20px",
                  backgroundColor: "#28a745",
                  color: "white",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: "bold"
                }}
                title="הוסף תכנית פנסיונית חדשה ידנית"
              >
                + הוסף תכנית חדשה
              </button>

              <button
                onClick={pensionDataHook.toggleAllAccountsSelection}
                style={{
                  padding: "8px 12px",
                  backgroundColor: "#6c757d",
                  color: "white",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                  fontSize: "14px"
                }}
              >
                {pensionDataHook.pensionData.every(a => a.selected) ? "בטל בחירת הכל" : "בחר הכל"}
              </button>
              
              <button
                onClick={pensionDataHook.saveSelectedAccounts}
                disabled={pensionDataHook.saving || !pensionDataHook.pensionData.some(a => a.selected)}
                style={{
                  padding: "10px 16px",
                  backgroundColor: !pensionDataHook.saving && pensionDataHook.pensionData.some(a => a.selected) ? "#007bff" : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: 4,
                  cursor: !pensionDataHook.saving && pensionDataHook.pensionData.some(a => a.selected) ? "pointer" : "not-allowed"
                }}
              >
                {pensionDataHook.saving ? "שומר..." : "שמור תכניות נבחרות"}
              </button>
              
              <button
                onClick={conversionHook.convertSelectedAccounts}
                disabled={pensionDataHook.loading || !pensionDataHook.pensionData.some(a => 
                  a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
                )}
                style={{
                  padding: "10px 16px",
                  backgroundColor: !pensionDataHook.loading && pensionDataHook.pensionData.some(a => 
                    a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
                  ) ? "#28a745" : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: 4,
                  cursor: !pensionDataHook.loading && pensionDataHook.pensionData.some(a => 
                    a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
                  ) ? "pointer" : "not-allowed"
                }}
              >
                המר חשבונות/סכומים נבחרים
              </button>
            </div>

            {/* טבלה מורחבת */}
            <div style={{ marginBottom: 8, padding: 8, backgroundColor: "#e7f3ff", borderRadius: 4, fontSize: "13px" }}>
              💡 <strong>טיפ:</strong> לחץ על כל תא בטבלה כדי לערוך את הערך ישירות. לחץ Enter או לחץ מחוץ לתא לשמור.
            </div>
            
            <PensionTable
              pensionData={pensionDataHook.pensionData}
              editingCell={pensionDataHook.editingCell}
              setEditingCell={pensionDataHook.setEditingCell}
              conversionTypes={pensionDataHook.conversionTypes}
              toggleAccountSelection={pensionDataHook.toggleAccountSelection}
              toggleAllAccountsSelection={pensionDataHook.toggleAllAccountsSelection}
              updateCellValue={pensionDataHook.updateCellValue}
              toggleAmountSelection={pensionDataHook.toggleAmountSelection}
              setConversionType={pensionDataHook.setConversionType}
              deleteAccount={pensionDataHook.deleteAccount}
            />
          </section>
        )}

        {pensionDataHook.pensionData.length === 0 && !pensionDataHook.loading && (
          <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4, textAlign: "center" }}>
            אין נתוני תיק פנסיוני. אנא טען קבצי מסלקה לעיבוד.
          </div>
        )}
      </div>
    </div>
  );
}
