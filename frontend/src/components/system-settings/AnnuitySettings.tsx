import React from 'react';

const AnnuitySettings: React.FC = () => {
  return (
    <div style={{ marginBottom: '40px' }}>
      <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '30px' }}>
        מקדמי קצבה
      </h2>
      
      <div style={{ 
        padding: '20px', 
        backgroundColor: '#e7f3ff', 
        borderRadius: '8px',
        border: '2px solid #007bff',
        marginBottom: '30px'
      }}>
        <h3 style={{ color: '#004085', marginTop: 0 }}>💡 מהם מקדמי קצבה?</h3>
        <p style={{ lineHeight: '1.8', marginBottom: '15px' }}>
          <strong>מקדם קצבה</strong> הוא המספר שבו מחלקים את יתרת החיסכון כדי לחשב את הקצבה החודשית.<br/>
          לדוגמה: יתרה של 200,000 ₪ עם מקדם 200 = קצבה חודשית של 1,000 ₪
        </p>
        <p style={{ lineHeight: '1.8', marginBottom: 0 }}>
          המקדמים משתנים לפי: <strong>סוג המוצר</strong>, <strong>גיל הפרישה</strong>, <strong>מגדר</strong>, 
          <strong>חברת הביטוח</strong>, <strong>תאריך התחלת הפוליסה</strong> ו<strong>מסלול שארים</strong>.
        </p>
      </div>

      <div style={{ 
        padding: '20px', 
        backgroundColor: '#d4edda', 
        borderRadius: '8px',
        border: '2px solid #28a745',
        marginBottom: '30px'
      }}>
        <h3 style={{ color: '#155724', marginTop: 0 }}>✅ המערכת פועלת אוטומטית</h3>
        <p style={{ lineHeight: '1.8', marginBottom: '15px' }}>
          כאשר ממירים כספים לקצבה מתיק פנסיוני, המערכת:
        </p>
        <ol style={{ lineHeight: '1.8', marginBottom: '15px' }}>
          <li>מזהה את סוג המוצר מה-XML</li>
          <li>שולפת את נתוני הלקוח (מגדר, גיל פרישה)</li>
          <li>בוחרת את הטבלה המתאימה:
            <ul style={{ marginTop: '8px' }}>
              <li><strong>קרן פנסיה / קופת גמל / קרן השתלמות</strong> → טבלת קרנות פנסיה</li>
              <li><strong>כל סוג אחר</strong> (ביטוח מנהלים, פוליסות) → טבלת דורות ביטוח</li>
            </ul>
          </li>
          <li>מחפשת את המקדם המדויק לפי <strong>גיל</strong> ו<strong>מין</strong></li>
          <li>מחשבת את הקצבה החודשית: <code>יתרה ÷ מקדם</code></li>
          <li>שומרת את פרטי המקדם בהערות הקצבה</li>
        </ol>
        <div style={{ 
          padding: '12px', 
          backgroundColor: '#fff', 
          borderRadius: '4px',
          fontSize: '14px',
          border: '1px solid #28a745'
        }}>
          <strong>💡 חשוב - לוגיקת חישוב מקדם:</strong>
          <ol style={{ marginTop: '8px', marginBottom: 0, paddingRight: '20px' }}>
            <li><strong>זיהוי דור:</strong> המערכת בודקת את תאריך התחלת התכנית ומשייכת אותה לדור המתאים לפי טווחי התאריכים (valid_from, valid_to)</li>
            <li><strong>חישוב גיל בפועל:</strong> המערכת מחשבת את גיל הלקוח <strong>בתאריך תחילת הקצבה</strong> (תאריך מימוש), לא בגיל פרישה</li>
            <li><strong>בחירת מקדם:</strong> לפי הדור, הגיל בפועל והמין - המערכת שולפת את המקדם המדויק מהטבלה</li>
          </ol>
          <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#e7f3ff', borderRadius: '4px' }}>
            <strong>דוגמה:</strong> לקוח נולד ב-1958, תכנית התחילה ב-2005, תאריך מימוש 2026:<br/>
            • דור: Y2004_TO_2008 (לפי 2005)<br/>
            • גיל בפועל: 68 (2026 - 1958)<br/>
            • מקדם: לפי דור Y2004_TO_2008, גיל 68, מין הלקוח
          </div>
        </div>
      </div>

      <div style={{ 
        padding: '20px', 
        backgroundColor: '#fff', 
        borderRadius: '8px',
        border: '1px solid #dee2e6',
        marginBottom: '20px'
      }}>
        <h3 style={{ marginTop: 0 }}>📋 טבלאות המקדמים במערכת</h3>
        
        <div style={{ marginBottom: '25px' }}>
          <h4 style={{ color: '#007bff' }}>1️⃣ דורות פוליסות ביטוח מנהלים</h4>
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
            מקדמים לפי תקופת הפוליסה, גיל ומין (7 דורות, 21 גילאים לכל דור, 147 שורות)
          </p>
          <div style={{ 
            padding: '10px', 
            backgroundColor: '#fff3cd', 
            borderRadius: '4px',
            marginBottom: '10px',
            fontSize: '13px',
            border: '1px solid #ffc107'
          }}>
            <strong>⚠️ חשוב:</strong> הדור נקבע לפי <strong>תאריך התחלת התכנית</strong> (start_date), לא לפי תאריך המימוש!<br/>
            המערכת בודקת את טווחי התאריכים (valid_from - valid_to) ומשייכת כל תכנית לדור המתאים.
          </div>
          <table className="modern-table" style={{ fontSize: '13px', width: '100%' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '10px', textAlign: 'right' }}>תקופה</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>גיל</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מקדם זכר</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מקדם נקבה</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>הבטחה</th>
              </tr>
            </thead>
            <tbody>
              <tr><td style={{ padding: '8px' }}>עד 31.12.1989</td><td style={{ padding: '8px', textAlign: 'center' }}>60</td><td style={{ padding: '8px', textAlign: 'center' }}>169.2</td><td style={{ padding: '8px', textAlign: 'center' }}>189.2</td><td style={{ padding: '8px', textAlign: 'center' }}>120</td></tr>
              <tr><td style={{ padding: '8px' }}>עד 31.12.1989</td><td style={{ padding: '8px', textAlign: 'center' }}>65</td><td style={{ padding: '8px', textAlign: 'center' }}>144.2</td><td style={{ padding: '8px', textAlign: 'center' }}>164.2</td><td style={{ padding: '8px', textAlign: 'center' }}>120</td></tr>
              <tr><td style={{ padding: '8px' }}>עד 31.12.1989</td><td style={{ padding: '8px', textAlign: 'center' }}>68</td><td style={{ padding: '8px', textAlign: 'center' }}>129.2</td><td style={{ padding: '8px', textAlign: 'center' }}>149.2</td><td style={{ padding: '8px', textAlign: 'center' }}>120</td></tr>
              <tr><td style={{ padding: '8px' }}>2004-2008</td><td style={{ padding: '8px', textAlign: 'center' }}>60</td><td style={{ padding: '8px', textAlign: 'center' }}>224.37</td><td style={{ padding: '8px', textAlign: 'center' }}>244.37</td><td style={{ padding: '8px', textAlign: 'center' }}>240</td></tr>
              <tr><td style={{ padding: '8px' }}>2004-2008</td><td style={{ padding: '8px', textAlign: 'center' }}>67</td><td style={{ padding: '8px', textAlign: 'center' }}>206.87</td><td style={{ padding: '8px', textAlign: 'center' }}>226.87</td><td style={{ padding: '8px', textAlign: 'center' }}>240</td></tr>
              <tr><td style={{ padding: '8px' }}>2013 ואילך</td><td style={{ padding: '8px', textAlign: 'center' }}>65</td><td style={{ padding: '8px', textAlign: 'center' }}>214.35</td><td style={{ padding: '8px', textAlign: 'center' }}>234.35</td><td style={{ padding: '8px', textAlign: 'center' }}>240</td></tr>
              <tr><td colSpan={5} style={{ padding: '8px', textAlign: 'center', fontStyle: 'italic', color: '#666' }}>+ 141 שורות נוספות לכל שילוב של דור וגיל</td></tr>
            </tbody>
          </table>
        </div>

        <div style={{ marginBottom: '25px' }}>
          <h4 style={{ color: '#007bff' }}>2️⃣ מקדמים ספציפיים לחברות</h4>
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
            מקדמים מדויקים לפי חברה, מסלול, מגדר וגיל (כלל, הראל)
          </p>
          <table className="modern-table" style={{ fontSize: '13px', width: '100%' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '10px', textAlign: 'right' }}>חברה</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מסלול</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מגדר</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>גיל</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מקדם בסיס</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>שיעור עליה שנתי</th>
              </tr>
            </thead>
            <tbody>
              <tr><td style={{ padding: '8px' }}>כלל</td><td style={{ padding: '8px', textAlign: 'center' }}>מינימום 180</td><td style={{ padding: '8px', textAlign: 'center' }}>זכר</td><td style={{ padding: '8px', textAlign: 'center' }}>60</td><td style={{ padding: '8px', textAlign: 'center' }}>228.41</td><td style={{ padding: '8px', textAlign: 'center' }}>0.353%</td></tr>
              <tr><td style={{ padding: '8px' }}>כלל</td><td style={{ padding: '8px', textAlign: 'center' }}>מינימום 180</td><td style={{ padding: '8px', textAlign: 'center' }}>נקבה</td><td style={{ padding: '8px', textAlign: 'center' }}>60</td><td style={{ padding: '8px', textAlign: 'center' }}>238.51</td><td style={{ padding: '8px', textAlign: 'center' }}>0.316%</td></tr>
              <tr><td style={{ padding: '8px' }}>הראל</td><td style={{ padding: '8px', textAlign: 'center' }}>מינימום 240</td><td style={{ padding: '8px', textAlign: 'center' }}>זכר</td><td style={{ padding: '8px', textAlign: 'center' }}>67</td><td style={{ padding: '8px', textAlign: 'center' }}>201.81</td><td style={{ padding: '8px', textAlign: 'center' }}>0.149%</td></tr>
              <tr><td style={{ padding: '8px' }}>הראל</td><td style={{ padding: '8px', textAlign: 'center' }}>מינימום 240</td><td style={{ padding: '8px', textAlign: 'center' }}>נקבה</td><td style={{ padding: '8px', textAlign: 'center' }}>67</td><td style={{ padding: '8px', textAlign: 'center' }}>207.22</td><td style={{ padding: '8px', textAlign: 'center' }}>0.195%</td></tr>
            </tbody>
          </table>
        </div>

        <div style={{ marginBottom: '25px' }}>
          <h4 style={{ color: '#007bff' }}>3️⃣ מקדמים לקרנות פנסיה</h4>
          <p style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
            מקדמים לפי גיל פרישה (60-80), מגדר, מסלול שארים והפרש גיל בן זוג (-20 עד +20)
            <br/>
            <strong>75,440 שורות</strong> עם כל השילובים האפשריים לתקופות הבטחה: 0, 60, 120, 180, 240 חודשים
          </p>
          <table className="modern-table" style={{ fontSize: '13px', width: '100%' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa' }}>
                <th style={{ padding: '10px', textAlign: 'right' }}>מסלול</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מגדר</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>גיל</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>הפרש גיל</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>מקדם</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>הבטחה</th>
              </tr>
            </thead>
            <tbody>
              <tr><td style={{ padding: '8px' }}>תקנוני</td><td style={{ padding: '8px', textAlign: 'center' }}>זכר</td><td style={{ padding: '8px', textAlign: 'center' }}>60</td><td style={{ padding: '8px', textAlign: 'center' }}>0</td><td style={{ padding: '8px', textAlign: 'center' }}>201.67</td><td style={{ padding: '8px', textAlign: 'center' }}>0</td></tr>
              <tr><td style={{ padding: '8px' }}>תקנוני</td><td style={{ padding: '8px', textAlign: 'center' }}>זכר</td><td style={{ padding: '8px', textAlign: 'center' }}>67</td><td style={{ padding: '8px', textAlign: 'center' }}>0</td><td style={{ padding: '8px', textAlign: 'center' }}>177.8</td><td style={{ padding: '8px', textAlign: 'center' }}>120</td></tr>
              <tr><td style={{ padding: '8px' }}>תקנוני</td><td style={{ padding: '8px', textAlign: 'center' }}>זכר</td><td style={{ padding: '8px', textAlign: 'center' }}>67</td><td style={{ padding: '8px', textAlign: 'center' }}>-5</td><td style={{ padding: '8px', textAlign: 'center' }}>180.6</td><td style={{ padding: '8px', textAlign: 'center' }}>120</td></tr>
              <tr><td style={{ padding: '8px' }}>תקנוני</td><td style={{ padding: '8px', textAlign: 'center' }}>נקבה</td><td style={{ padding: '8px', textAlign: 'center' }}>64</td><td style={{ padding: '8px', textAlign: 'center' }}>0</td><td style={{ padding: '8px', textAlign: 'center' }}>207.22</td><td style={{ padding: '8px', textAlign: 'center' }}>240</td></tr>
              <tr><td colSpan={6} style={{ padding: '8px', textAlign: 'center', fontStyle: 'italic', color: '#666' }}>+ 75,436 שורות נוספות לכל שילוב אפשרי</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ 
        padding: '20px', 
        backgroundColor: '#fff3cd', 
        borderRadius: '8px',
        border: '2px solid #ffc107'
      }}>
        <h3 style={{ color: '#856404', marginTop: 0 }}>⚙️ איך לעדכן את הטבלאות?</h3>
        <p style={{ lineHeight: '1.8', marginBottom: '15px' }}>
          הטבלאות נטענות מקבצי CSV בתיקייה <code>MEKEDMIM</code>. 
          כדי לעדכן או להוסיף מקדמים:
        </p>
        <ol style={{ lineHeight: '1.8' }}>
          <li>ערוך את קבצי ה-CSV המתאימים בתיקייה</li>
          <li>הרץ את הסקריפט: <code>python load_annuity_coefficients.py</code></li>
          <li>אתחל את השרת מחדש</li>
        </ol>
        <p style={{ fontSize: '14px', color: '#856404', marginTop: '15px', marginBottom: 0 }}>
          <strong>💡 טיפ:</strong> המערכת שומרת את מקור המקדם בהערות הקצבה לשקיפות מלאה.
        </p>
      </div>
    </div>
  );
};

export default AnnuitySettings;
