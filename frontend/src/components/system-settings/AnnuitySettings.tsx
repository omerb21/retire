import React from 'react';
import './AnnuitySettings.css';

const AnnuitySettings: React.FC = () => {
  return (
    <div className="annuity-settings-container">
      <h2 className="annuity-settings-title">
        מקדמי קצבה
      </h2>
      
      <div className="annuity-card annuity-card-info">
        <h3 className="annuity-subtitle annuity-subtitle-info">💡 מהם מקדמי קצבה?</h3>
        <p className="annuity-text">
          <strong>מקדם קצבה</strong> הוא המספר שבו מחלקים את יתרת החיסכון כדי לחשב את הקצבה החודשית.<br/>
          לדוגמה: יתרה של 200,000 ₪ עם מקדם 200 = קצבה חודשית של 1,000 ₪
        </p>
        <p className="annuity-text annuity-text-last">
          המקדמים משתנים לפי: <strong>סוג המוצר</strong>, <strong>גיל הפרישה</strong>, <strong>מגדר</strong>, 
          <strong>חברת הביטוח</strong>, <strong>תאריך התחלת הפוליסה</strong> ו<strong>מסלול שארים</strong>.
        </p>
      </div>

      <div className="annuity-card annuity-card-success">
        <h3 className="annuity-subtitle annuity-subtitle-success">✅ המערכת פועלת אוטומטית</h3>
        <p className="annuity-text">
          כאשר ממירים כספים לקצבה מתיק פנסיוני, המערכת:
        </p>
        <ol className="annuity-list">
          <li>מזהה את סוג המוצר מה-XML</li>
          <li>שולפת את נתוני הלקוח (מגדר, גיל פרישה)</li>
          <li>בוחרת את הטבלה המתאימה:
            <ul>
              <li><strong>קרן פנסיה / קופת גמל / קרן השתלמות</strong> → טבלת קרנות פנסיה</li>
              <li><strong>כל סוג אחר</strong> (ביטוח מנהלים, פוליסות) → טבלת דורות ביטוח</li>
            </ul>
          </li>
          <li>מחפשת את המקדם המדויק לפי <strong>גיל</strong> ו<strong>מין</strong></li>
          <li>מחשבת את הקצבה החודשית: <code>יתרה ÷ מקדם</code></li>
          <li>שומרת את פרטי המקדם בהערות הקצבה</li>
        </ol>
        <div className="annuity-helper-box">
          <strong>💡 חשוב - לוגיקת חישוב מקדם:</strong>
          <ol className="annuity-list-tight">
            <li><strong>זיהוי דור:</strong> המערכת בודקת את תאריך התחלת התכנית ומשייכת אותה לדור המתאים לפי טווחי התאריכים (valid_from, valid_to)</li>
            <li><strong>חישוב גיל בפועל:</strong> המערכת מחשבת את גיל הלקוח <strong>בתאריך תחילת הקצבה</strong> (תאריך מימוש), לא בגיל פרישה</li>
            <li><strong>בחירת מקדם:</strong> לפי הדור, הגיל בפועל והמין - המערכת שולפת את המקדם המדויק מהטבלה</li>
          </ol>
          <div className="annuity-example-box">
            <strong>דוגמה:</strong> לקוח נולד ב-1958, תכנית התחילה ב-2005, תאריך מימוש 2026:<br/>
            • דור: Y2004_TO_2008 (לפי 2005)<br/>
            • גיל בפועל: 68 (2026 - 1958)<br/>
            • מקדם: לפי דור Y2004_TO_2008, גיל 68, מין הלקוח
          </div>
        </div>
      </div>

      <div className="annuity-card annuity-card-outline">
        <h3 className="annuity-subtitle">📋 טבלאות המקדמים במערכת</h3>
        
        <div className="annuity-table-wrapper">
          <h4 className="annuity-table-title">1️⃣ דורות פוליסות ביטוח מנהלים</h4>
          <p className="annuity-table-description">
            מקדמים לפי תקופת הפוליסה, גיל ומין (7 דורות, 21 גילאים לכל דור, 147 שורות)
          </p>
          <div className="annuity-table-note">
            <strong>⚠️ חשוב:</strong> הדור נקבע לפי <strong>תאריך התחלת התכנית</strong> (start_date), לא לפי תאריך המימוש!<br/>
            המערכת בודקת את טווחי התאריכים (valid_from - valid_to) ומשייכת כל תכנית לדור המתאים.
          </div>
          <table className="modern-table annuity-table">
            <thead>
              <tr>
                <th className="annuity-table-header-right">תקופה</th>
                <th className="annuity-table-header-center">גיל</th>
                <th className="annuity-table-header-center">מקדם זכר</th>
                <th className="annuity-table-header-center">מקדם נקבה</th>
                <th className="annuity-table-header-center">הבטחה</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="annuity-table-cell">עד 31.12.1989</td><td className="annuity-table-cell annuity-table-cell-center">60</td><td className="annuity-table-cell annuity-table-cell-center">169.2</td><td className="annuity-table-cell annuity-table-cell-center">189.2</td><td className="annuity-table-cell annuity-table-cell-center">120</td></tr>
              <tr><td className="annuity-table-cell">עד 31.12.1989</td><td className="annuity-table-cell annuity-table-cell-center">65</td><td className="annuity-table-cell annuity-table-cell-center">144.2</td><td className="annuity-table-cell annuity-table-cell-center">164.2</td><td className="annuity-table-cell annuity-table-cell-center">120</td></tr>
              <tr><td className="annuity-table-cell">עד 31.12.1989</td><td className="annuity-table-cell annuity-table-cell-center">68</td><td className="annuity-table-cell annuity-table-cell-center">129.2</td><td className="annuity-table-cell annuity-table-cell-center">149.2</td><td className="annuity-table-cell annuity-table-cell-center">120</td></tr>
              <tr><td className="annuity-table-cell">2004-2008</td><td className="annuity-table-cell annuity-table-cell-center">60</td><td className="annuity-table-cell annuity-table-cell-center">224.37</td><td className="annuity-table-cell annuity-table-cell-center">244.37</td><td className="annuity-table-cell annuity-table-cell-center">240</td></tr>
              <tr><td className="annuity-table-cell">2004-2008</td><td className="annuity-table-cell annuity-table-cell-center">67</td><td className="annuity-table-cell annuity-table-cell-center">206.87</td><td className="annuity-table-cell annuity-table-cell-center">226.87</td><td className="annuity-table-cell annuity-table-cell-center">240</td></tr>
              <tr><td className="annuity-table-cell">2013 ואילך</td><td className="annuity-table-cell annuity-table-cell-center">65</td><td className="annuity-table-cell annuity-table-cell-center">214.35</td><td className="annuity-table-cell annuity-table-cell-center">234.35</td><td className="annuity-table-cell annuity-table-cell-center">240</td></tr>
              <tr><td colSpan={5} className="annuity-table-cell-note">+ 141 שורות נוספות לכל שילוב של דור וגיל</td></tr>
            </tbody>
          </table>
        </div>

        <div className="annuity-table-wrapper">
          <h4 className="annuity-table-title">2️⃣ מקדמים ספציפיים לחברות</h4>
          <p className="annuity-table-description">
            מקדמים מדויקים לפי חברה, מסלול, מגדר וגיל (כלל, הראל)
          </p>
          <table className="modern-table annuity-table">
            <thead>
              <tr>
                <th className="annuity-table-header-right">חברה</th>
                <th className="annuity-table-header-center">מסלול</th>
                <th className="annuity-table-header-center">מגדר</th>
                <th className="annuity-table-header-center">גיל</th>
                <th className="annuity-table-header-center">מקדם בסיס</th>
                <th className="annuity-table-header-center">שיעור עליה שנתי</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="annuity-table-cell">כלל</td><td className="annuity-table-cell annuity-table-cell-center">מינימום 180</td><td className="annuity-table-cell annuity-table-cell-center">זכר</td><td className="annuity-table-cell annuity-table-cell-center">60</td><td className="annuity-table-cell annuity-table-cell-center">228.41</td><td className="annuity-table-cell annuity-table-cell-center">0.353%</td></tr>
              <tr><td className="annuity-table-cell">כלל</td><td className="annuity-table-cell annuity-table-cell-center">מינימום 180</td><td className="annuity-table-cell annuity-table-cell-center">נקבה</td><td className="annuity-table-cell annuity-table-cell-center">60</td><td className="annuity-table-cell annuity-table-cell-center">238.51</td><td className="annuity-table-cell annuity-table-cell-center">0.316%</td></tr>
              <tr><td className="annuity-table-cell">הראל</td><td className="annuity-table-cell annuity-table-cell-center">מינימום 240</td><td className="annuity-table-cell annuity-table-cell-center">זכר</td><td className="annuity-table-cell annuity-table-cell-center">67</td><td className="annuity-table-cell annuity-table-cell-center">201.81</td><td className="annuity-table-cell annuity-table-cell-center">0.149%</td></tr>
              <tr><td className="annuity-table-cell">הראל</td><td className="annuity-table-cell annuity-table-cell-center">מינימום 240</td><td className="annuity-table-cell annuity-table-cell-center">נקבה</td><td className="annuity-table-cell annuity-table-cell-center">67</td><td className="annuity-table-cell annuity-table-cell-center">207.22</td><td className="annuity-table-cell annuity-table-cell-center">0.195%</td></tr>
            </tbody>
          </table>
        </div>

        <div className="annuity-table-wrapper">
          <h4 className="annuity-table-title">3️⃣ מקדמים לקרנות פנסיה</h4>
          <p className="annuity-table-description">
            מקדמים לפי גיל פרישה (60-80), מגדר, מסלול שארים והפרש גיל בן זוג (-20 עד +20)
            <br/>
            <strong>75,440 שורות</strong> עם כל השילובים האפשריים לתקופות הבטחה: 0, 60, 120, 180, 240 חודשים
          </p>
          <table className="modern-table annuity-table">
            <thead>
              <tr>
                <th className="annuity-table-header-right">מסלול</th>
                <th className="annuity-table-header-center">מגדר</th>
                <th className="annuity-table-header-center">גיל</th>
                <th className="annuity-table-header-center">הפרש גיל</th>
                <th className="annuity-table-header-center">מקדם</th>
                <th className="annuity-table-header-center">הבטחה</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="annuity-table-cell">תקנוני</td><td className="annuity-table-cell annuity-table-cell-center">זכר</td><td className="annuity-table-cell annuity-table-cell-center">60</td><td className="annuity-table-cell annuity-table-cell-center">0</td><td className="annuity-table-cell annuity-table-cell-center">201.67</td><td className="annuity-table-cell annuity-table-cell-center">0</td></tr>
              <tr><td className="annuity-table-cell">תקנוני</td><td className="annuity-table-cell annuity-table-cell-center">זכר</td><td className="annuity-table-cell annuity-table-cell-center">67</td><td className="annuity-table-cell annuity-table-cell-center">0</td><td className="annuity-table-cell annuity-table-cell-center">177.8</td><td className="annuity-table-cell annuity-table-cell-center">120</td></tr>
              <tr><td className="annuity-table-cell">תקנוני</td><td className="annuity-table-cell annuity-table-cell-center">זכר</td><td className="annuity-table-cell annuity-table-cell-center">67</td><td className="annuity-table-cell annuity-table-cell-center">-5</td><td className="annuity-table-cell annuity-table-cell-center">180.6</td><td className="annuity-table-cell annuity-table-cell-center">120</td></tr>
              <tr><td className="annuity-table-cell">תקנוני</td><td className="annuity-table-cell annuity-table-cell-center">נקבה</td><td className="annuity-table-cell annuity-table-cell-center">64</td><td className="annuity-table-cell annuity-table-cell-center">0</td><td className="annuity-table-cell annuity-table-cell-center">207.22</td><td className="annuity-table-cell annuity-table-cell-center">240</td></tr>
              <tr><td colSpan={6} className="annuity-table-cell-note">+ 75,436 שורות נוספות לכל שילוב אפשרי</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="annuity-card-warning">
        <h3 className="annuity-subtitle annuity-subtitle-warning">⚙️ איך לעדכן את הטבלאות?</h3>
        <p className="annuity-text">
          הטבלאות נטענות מקבצי CSV בתיקייה <code>MEKEDMIM</code>. 
          כדי לעדכן או להוסיף מקדמים:
        </p>
        <ol className="annuity-warning-list">
          <li>ערוך את קבצי ה-CSV המתאימים בתיקייה</li>
          <li>הרץ את הסקריפט: <code>python load_annuity_coefficients.py</code></li>
          <li>אתחל את השרת מחדש</li>
        </ol>
        <p className="annuity-warning-footer">
          <strong>💡 טיפ:</strong> המערכת שומרת את מקור המקדם בהערות הקצבה לשקיפות מלאה.
        </p>
      </div>
    </div>
  );
};

export default AnnuitySettings;
