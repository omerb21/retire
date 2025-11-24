import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { getConversionRulesExplanation } from '../../../config/conversionRules';
import { formatDateInput } from '../../../utils/dateUtils';
import { usePensionData } from '../hooks/usePensionData';
import { usePensionConversion } from '../hooks/usePensionConversion';
import { FileUploadSection } from './FileUploadSection';
import { PensionTable } from './PensionTable';
import { generateExcelReport } from '../utils/exportUtils';
import '../PensionPortfolio.css';

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

  const canSave = !pensionDataHook.saving && pensionDataHook.pensionData.some(a => a.selected);
  const canConvert = !pensionDataHook.loading && pensionDataHook.pensionData.some(a => 
    a.selected || Object.values(a.selected_amounts || {}).some(Boolean)
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
          <div className="pension-portfolio-error-banner">
            {pensionDataHook.error}
          </div>
        )}

        {pensionDataHook.processingStatus && (
          <div className="pension-portfolio-status-banner">
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
          <section className="pension-portfolio-section">
            <h3>נתוני התיק הפנסיוני ({pensionDataHook.pensionData.length} חשבונות)</h3>
            
            {/* הוראות שימוש */}
            <div className="pension-portfolio-instructions">
              <h4 className="pension-portfolio-instructions-title">הוראות שימוש:</h4>
              <ol className="pension-portfolio-instructions-list">
                <li><strong>שמירת תכניות:</strong> סמן תכניות בעמודה "בחר" ולחץ "שמור תכניות נבחרות" לשמירה בטבלת התכניות הפנסיוניות</li>
                <li><strong>מחיקת תכנית:</strong> לחץ "מחק" בעמודת הפעולות להסרת תכנית מהרשימה</li>
                <li><strong>המרה לקצבאות/נכסים:</strong> סמן חשבונות או סכומים ספציפיים, בחר סוג המרה ולחץ "המר חשבונות/סכומים נבחרים"</li>
                <li><strong>חוקי המרה:</strong> לחץ על הכפתור "חוקי המרה לפי חוק" כדי לצפות במגבלות המרת יתרות</li>
              </ol>
            </div>
            
            {/* כפתור חוקי המרה */}
            {/* הצגת חוקי המרה */}
            {pensionDataHook.showConversionRules && (
              <div className="pension-portfolio-rules">
                <h4 className="pension-portfolio-rules-title">חוקי המרת יתרות מתיק פנסיוני</h4>
                {getConversionRulesExplanation()}
              </div>
            )}
            
            {/* כפתור הוספה ידנית */}
            {/* שדה תאריך מימוש */}
            <div className="pension-portfolio-redemption-box">
              <label className="pension-portfolio-redemption-label">
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
                className="pension-portfolio-redemption-input"
              />
              <div className="pension-portfolio-redemption-help">
                💡 <strong>הסבר:</strong> אם תזין תאריך מימוש, כל ההמרות ייווצרו עם תאריך תשלום = תאריך המימוש.<br/>
                אם השדה ריק, ההמרות ייווצרו עם תאריך תשלום = תאריך גיל הפרישה של הלקוח.
              </div>
            </div>

            {/* כפתורי פעולה */}
            <div className="pension-portfolio-actions">
              {/* כפתור חוקי המרה */}
              <button
                onClick={() => pensionDataHook.setShowConversionRules(!pensionDataHook.showConversionRules)}
                className="pension-portfolio-btn pension-portfolio-btn--rules"
                title="הצג/הסתר חוקי המרה לפי חוק"
              >
                📋 {pensionDataHook.showConversionRules ? 'הסתר חוקי המרה' : 'חוקי המרה לפי חוק'}
              </button>

              {/* כפתור הוספה ידנית */}
              <button
                onClick={pensionDataHook.addManualAccount}
                className="pension-portfolio-btn pension-portfolio-btn--add"
                title="הוסף תכנית פנסיונית חדשה ידנית"
              >
                + הוסף תכנית חדשה
              </button>

              <button
                onClick={pensionDataHook.toggleAllAccountsSelection}
                className="pension-portfolio-btn pension-portfolio-btn--toggle"
              >
                {pensionDataHook.pensionData.every(a => a.selected) ? "בטל בחירת הכל" : "בחר הכל"}
              </button>
              
              <button
                onClick={pensionDataHook.saveSelectedAccounts}
                disabled={!canSave}
                className={`pension-portfolio-btn ${canSave ? 'pension-portfolio-btn--save' : 'pension-portfolio-btn--save-disabled'}`}
              >
                {pensionDataHook.saving ? "שומר..." : "שמור תכניות נבחרות"}
              </button>
              
              <button
                onClick={conversionHook.convertSelectedAccounts}
                disabled={!canConvert}
                className={`pension-portfolio-btn ${canConvert ? 'pension-portfolio-btn--convert' : 'pension-portfolio-btn--convert-disabled'}`}
              >
                המר חשבונות/סכומים נבחרים
              </button>
            </div>

            {/* טבלה מורחבת */}
            <div className="pension-portfolio-tip">
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
          <div className="pension-portfolio-empty">
            אין נתוני תיק פנסיוני. אנא טען קבצי מסלקה לעיבוד.
          </div>
        )}
      </div>
    </div>
  );
}
