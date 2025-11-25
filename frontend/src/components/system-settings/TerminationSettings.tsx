import React from 'react';
import './TerminationSettings.css';

const TerminationSettings: React.FC = () => {
  return (
    <div className="termination-settings-container">
      <h2 className="termination-settings-title">
        🚪 לוגיקת עזיבות עבודה ופריסת מס
      </h2>

      {/* חישוב שנות פריסה */}
      <div className="termination-card-warning">
        <h3 className="termination-card-warning-title">📊 חישוב שנות פריסה לפי וותק</h3>
        <p className="termination-card-warning-text">
          <strong>עיקרון החישוב:</strong> זכאות לשנת פריסה אחת על כל 4 שנות וותק אצל המעסיק (עד מקסימום 6 שנות פריסה).
          את הוותק מעגלים לנקודת הזכאות הקרובה.
        </p>
        
        <table className="modern-table termination-tenure-table">
          <thead>
            <tr className="termination-tenure-header-row">
              <th className="termination-tenure-header-cell termination-tenure-header-cell-right">וותק (שנים)</th>
              <th className="termination-tenure-header-cell termination-tenure-header-cell-center">שנות פריסה</th>
              <th className="termination-tenure-header-cell termination-tenure-header-cell-right">הערות</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="termination-tenure-cell">עד תום שנתיים</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-bold">0</td>
              <td className="termination-tenure-cell termination-tenure-note">אין זכאות לפריסה</td>
            </tr>
            <tr className="termination-tenure-body-row-alt">
              <td className="termination-tenure-cell">2 שנים ויום - 6 שנים</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-green">1</td>
              <td className="termination-tenure-cell">זכאות לשנת פריסה אחת</td>
            </tr>
            <tr>
              <td className="termination-tenure-cell">6 שנים ויום - 10 שנים</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-green">2</td>
              <td className="termination-tenure-cell">זכאות ל-2 שנות פריסה</td>
            </tr>
            <tr className="termination-tenure-body-row-alt">
              <td className="termination-tenure-cell">10 שנים ויום - 14 שנים</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-green">3</td>
              <td className="termination-tenure-cell">זכאות ל-3 שנות פריסה</td>
            </tr>
            <tr>
              <td className="termination-tenure-cell">14 שנים ויום - 18 שנים</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-green">4</td>
              <td className="termination-tenure-cell">זכאות ל-4 שנות פריסה</td>
            </tr>
            <tr className="termination-tenure-body-row-alt">
              <td className="termination-tenure-cell">18 שנים ויום - 22 שנים</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-green">5</td>
              <td className="termination-tenure-cell">זכאות ל-5 שנות פריסה</td>
            </tr>
            <tr>
              <td className="termination-tenure-cell">22 שנים ויום ומעלה</td>
              <td className="termination-tenure-cell termination-tenure-cell-center termination-tenure-cell-red">6</td>
              <td className="termination-tenure-cell"><strong>מקסימום - זכאות ל-6 שנות פריסה</strong></td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* דוגמאות חישוב */}
      <div className="termination-examples-card">
        <h3 className="termination-examples-title">💡 דוגמאות חישוב</h3>
        
        <div className="termination-example-block">
          <strong>דוגמה 1:</strong> עובד עם וותק של 5 שנים ו-3 חודשים
          <div className="termination-example-detail">
            → זכאות ל-<strong>1 שנת פריסה</strong> (נמצא בטווח 2-6 שנים)
          </div>
        </div>
        
        <div className="termination-example-block">
          <strong>דוגמה 2:</strong> עובד עם וותק של 10 שנים ויום אחד
          <div className="termination-example-detail">
            → זכאות ל-<strong>3 שנות פריסה</strong> (עבר את סף 10 השנים)
          </div>
        </div>
        
        <div className="termination-example-block">
          <strong>דוגמה 3:</strong> עובד עם וותק של 25 שנים
          <div className="termination-example-detail">
            → זכאות ל-<strong>6 שנות פריסה</strong> (מקסימום)
          </div>
        </div>
      </div>

      {/* סוגי פיצויים ואפשרויות */}
      <div className="termination-types-card">
        <h3 className="termination-types-title">📋 סוגי פיצויים ואפשרויות מימוש</h3>
        
        <div className="termination-types-section">
          <h4 className="termination-types-section-title">1️⃣ פיצויים פטורים ממס</h4>
          <ul className="termination-types-list">
            <li><strong>פדיון עם פטור:</strong> מימוש מיידי עם פטור מלא ממס (עד תקרה חוקית)</li>
            <li><strong>פדיון ללא פטור:</strong> מימוש מיידי עם פריסת מס לפי שנות הוותק</li>
            <li><strong>המרה לקצבה:</strong> המרת הסכום לקצבה חודשית (ללא פריסת מס)</li>
          </ul>
        </div>
        
        <div>
          <h4 className="termination-types-section-title">2️⃣ פיצויים חייבים במס</h4>
          <ul className="termination-types-list">
            <li><strong>פדיון ללא פטור:</strong> מימוש מיידי עם פריסת מס לפי שנות הוותק</li>
            <li><strong>המרה לקצבה:</strong> המרת הסכום לקצבה חודשית (ללא פריסת מס)</li>
          </ul>
        </div>
      </div>

      {/* פריסת מס - הסבר מפורט */}
      <div className="termination-spread-card">
        <h3 className="termination-spread-title">🧮 איך עובדת פריסת מס?</h3>
        <p className="termination-spread-text">
          פריסת מס היא הטבה מיסויית המאפשרת לחלק את הכנסת הפיצויים על פני מספר שנים,
          כך שבכל שנה מחושב המס רק על חלק מהסכום הכולל.
        </p>
        
        <div className="termination-spread-example">
          <strong className="termination-spread-example-title">דוגמה מספרית:</strong>
          <div className="termination-spread-example-list">
            • סכום פיצויים: 600,000 ₪<br/>
            • וותק: 12 שנים → זכאות ל-3 שנות פריסה<br/>
            • חלוקה: 600,000 ÷ 3 = 200,000 ₪ לשנה<br/>
            • המס מחושב על 200,000 ₪ בשנה (במקום על 600,000 ₪ בבת אחת)<br/>
            • <strong className="termination-spread-highlight">חיסכון משמעותי במס!</strong>
          </div>
        </div>
        
        <p className="termination-spread-tip">
          <strong>💡 טיפ:</strong> המערכת ממליצה תמיד על פריסה מלאה (מקסימום שנות הזכאות) 
          לחיסכון מרבי במס.
        </p>
      </div>

      {/* הערות חשובות */}
      <div className="termination-notes-card">
        <h3 className="termination-notes-title">⚠️ הערות חשובות</h3>
        <ul className="termination-notes-list">
          <li>חישוב שנות הפריסה מתבצע אוטומטית על פי שנות הוותק בפועל</li>
          <li>המשתמש יכול לבחור מספר שנות פריסה נמוך יותר מהמקסימום (לא מומלץ)</li>
          <li>פריסת מס חלה רק על פדיון מיידי, לא על המרה לקצבה</li>
          <li>התקרה החוקית לפטור ממס מתעדכנת מדי שנה (ראה לשונית "תקרות פיצויים")</li>
          <li>המערכת יוצרת אוטומטית נכס הון עם פריסת מס מתאימה</li>
        </ul>
      </div>
    </div>
  );
};

export default TerminationSettings;
