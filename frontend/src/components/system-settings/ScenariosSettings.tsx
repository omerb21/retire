import React from 'react';

const ScenariosSettings: React.FC = () => {
  return (
    <div className="system-settings-section">
      <h2 className="system-settings-section-title">
        לוגיקת תרחישי פרישה
      </h2>
      
      <div className="system-settings-card system-settings-card-neutral">
        <h3 className="system-settings-card-title-muted">🎯 עקרונות כלליים</h3>
        <ul className="system-settings-list-spaced">
          <li><strong>בסיס הלוגיקה:</strong> כל ההמרות בתרחישי הפרישה חייבות לפעול לפי חוקי ההמרה המוגדרים במערכת</li>
          <li><strong>מחיקת יתרות:</strong> כל יתרה שעוברת המרה חייבת להימחק מהטבלה המקורית</li>
          <li><strong>שימור נתונים מקוריים:</strong> כל תרחיש רץ על snapshot של הנתונים המקוריים</li>
        </ul>
      </div>
      
      <div className="system-settings-card system-settings-card-warning">
        <h3 className="system-settings-card-title-warning">🎁 קרן השתלמות - יוצאת מן הכלל</h3>
        <p><strong>מיקום יתרה:</strong> טור "תגמולים"</p>
        <p><strong>מצב מס:</strong> פטור ממס (tax_treatment="exempt")</p>
        <p><strong>ייחודיות:</strong> טור תגמולים בדרך כלל לא ניתן להמרה להון, אבל קרן השתלמות היא יוצאת מן הכלל</p>
        
        <h4>אפשרויות המרה:</h4>
        <ol className="system-settings-list-spaced">
          <li><strong>המרה לקצבה פטורה:</strong> יוצר PensionFund עם tax_treatment="exempt" (לא להכנסה נוספת!)</li>
          <li><strong>המרה לנכס הוני פטור:</strong> יוצר CapitalAsset עם tax_treatment="exempt"</li>
          <li><strong>לא הגיוני:</strong> להמיר לקצבה ואז להוון (זה שווה להמרה ישירה להון)</li>
        </ol>
      </div>
      
      <div className="system-settings-card system-settings-card-success">
        <h3 className="system-settings-card-title-success">📋 מוצרים פנסיוניים רגילים</h3>
        
        <h4>טור "פיצויים מעסיק נוכחי":</h4>
        <p className="system-settings-inline-note system-settings-inline-note-success">
          ⛔ <strong>אין לגעת בו בתרחישים!</strong> ההמרות שלו מתבצעות במסך "עזיבת עבודה"
        </p>
        
        <h4>יתרות אחרות - ליצירת נכסים הוניים:</h4>
        <ol className="system-settings-list-spaced">
          <li>
            <strong>יתרות הניתנות להמרה ישירה להון</strong> (פיצויים לאחר התחשבנות, תגמולי עובד/מעביד עד 2000):
            <br/>→ המרה ישירה לנכס הוני (לא להמיר לקצבה ואז להוון!)
          </li>
          <li>
            <strong>יתרות שאינן ניתנות להמרה ישירה להון:</strong>
            <br/>→ המרה לקצבה ← היוון מלא (יחס מס נשמר)
          </li>
        </ol>
        
        <h4>ליצירת קצבאות:</h4>
        <p>המרה לקצבה לפי חוקי ההמרה (יחס מס נשמר מהטור המקורי)</p>
      </div>
      
      <div className="system-settings-card system-settings-card-info">
        <h3 className="system-settings-card-title-info">🔄 המרות רכיבים אחרים</h3>
        
        <h4>קצבאות (PensionFund):</h4>
        <ul>
          <li><strong>המרה להון (היוון):</strong> pension_amount × annuity_factor</li>
          <li><strong>יחס מס:</strong> נשמר מהקצבה המקורית</li>
          <li><strong>מחיקה:</strong> ✅ מחיקת הקצבה המקורית</li>
        </ul>
        
        <h4>הכנסות נוספות (AdditionalIncome):</h4>
        <p className="system-settings-inline-note system-settings-inline-note-info">
          ⛔ <strong>אין לגעת בהן!</strong> לא ניתנות להמרה, נשארות תמיד כמו שהן
        </p>
        
        <h4>שגיאות נפוצות לתיקון:</h4>
        <ul>
          <li>❌ יצירת AdditionalIncome מכספי היוון → צריך CapitalAsset</li>
          <li>❌ יצירת AdditionalIncome מנכס פטור → צריך PensionFund עם tax_treatment="exempt"</li>
        </ul>
        
        <h4>נכסי הון (CapitalAsset):</h4>
        <ul>
          <li><strong>המרה לקצבה:</strong> current_value ÷ 200</li>
          <li><strong>יחס מס:</strong> זהה לנכס המקורי</li>
          <li><strong>מחיקה:</strong> ✅ מחיקת הנכס ההוני</li>
        </ul>
      </div>
      
      <div className="system-settings-card system-settings-card-danger">
        <h3 className="system-settings-card-title-danger">⚠️ מעסיק נוכחי ועזיבת עבודה</h3>
        
        <p><strong>אם אין עזיבת עבודה:</strong> אין צורך בטיפול - המערכת עובדת נכון</p>
        
        <p><strong>אם קיימת עזיבת עבודה:</strong></p>
        <ul className="system-settings-list-spaced">
          <li><strong>תרחיש 1 (מקסימום קצבה):</strong> סימון "קצבה" על הסכום הפטור והחייב</li>
          <li><strong>תרחיש 2 (מקסימום הון):</strong> פדיון + בדיקה האם שימוש בפטור (פריסת מס) נותן ערך נוכחי גבוה יותר</li>
          <li><strong>תרחיש 3 (מאוזן):</strong> שילוב של קצבה והון (50/50 או אופטימיזציה)</li>
        </ul>
      </div>
      
      <div className="system-settings-note-box">
        <p className="system-settings-note-text">
          <strong>📚 לתיעוד מלא:</strong> ראה קובץ SCENARIOS_LOGIC.md בתיקיית המערכת
        </p>
        <p className="system-settings-note-subtext">
          <strong>תאריך עדכון אחרון:</strong> 18/10/2025
        </p>
      </div>
    </div>
  );
};

export default ScenariosSettings;
