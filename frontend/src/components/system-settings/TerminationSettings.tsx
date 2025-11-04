import React from 'react';

const TerminationSettings: React.FC = () => {
  return (
    <div style={{ marginBottom: '40px' }}>
      <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '20px' }}>
        🚪 לוגיקת עזיבות עבודה ופריסת מס
      </h2>

      {/* חישוב שנות פריסה */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        backgroundColor: '#fff3cd', 
        borderRadius: '8px',
        border: '2px solid #ffc107'
      }}>
        <h3 style={{ color: '#856404', marginTop: 0 }}>📊 חישוב שנות פריסה לפי וותק</h3>
        <p style={{ fontSize: '16px', lineHeight: '1.6', marginBottom: '15px' }}>
          <strong>עיקרון החישוב:</strong> זכאות לשנת פריסה אחת על כל 4 שנות וותק אצל המעסיק (עד מקסימום 6 שנות פריסה).
          את הוותק מעגלים לנקודת הזכאות הקרובה.
        </p>
        
        <table className="modern-table" style={{ width: '100%', marginTop: '15px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #dee2e6' }}>וותק (שנים)</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '2px solid #dee2e6' }}>שנות פריסה</th>
              <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #dee2e6' }}>הערות</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ padding: '10px' }}>עד תום שנתיים</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold' }}>0</td>
              <td style={{ padding: '10px', color: '#6c757d' }}>אין זכאות לפריסה</td>
            </tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <td style={{ padding: '10px' }}>2 שנים ויום - 6 שנים</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>1</td>
              <td style={{ padding: '10px' }}>זכאות לשנת פריסה אחת</td>
            </tr>
            <tr>
              <td style={{ padding: '10px' }}>6 שנים ויום - 10 שנים</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>2</td>
              <td style={{ padding: '10px' }}>זכאות ל-2 שנות פריסה</td>
            </tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <td style={{ padding: '10px' }}>10 שנים ויום - 14 שנים</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>3</td>
              <td style={{ padding: '10px' }}>זכאות ל-3 שנות פריסה</td>
            </tr>
            <tr>
              <td style={{ padding: '10px' }}>14 שנים ויום - 18 שנים</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>4</td>
              <td style={{ padding: '10px' }}>זכאות ל-4 שנות פריסה</td>
            </tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <td style={{ padding: '10px' }}>18 שנים ויום - 22 שנים</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>5</td>
              <td style={{ padding: '10px' }}>זכאות ל-5 שנות פריסה</td>
            </tr>
            <tr>
              <td style={{ padding: '10px' }}>22 שנים ויום ומעלה</td>
              <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#dc3545' }}>6</td>
              <td style={{ padding: '10px' }}><strong>מקסימום - זכאות ל-6 שנות פריסה</strong></td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* דוגמאות חישוב */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        backgroundColor: '#d1ecf1', 
        borderRadius: '8px',
        border: '2px solid #bee5eb'
      }}>
        <h3 style={{ color: '#0c5460', marginTop: 0 }}>💡 דוגמאות חישוב</h3>
        
        <div style={{ marginBottom: '15px' }}>
          <strong>דוגמה 1:</strong> עובד עם וותק של 5 שנים ו-3 חודשים
          <div style={{ marginLeft: '20px', marginTop: '5px', color: '#0c5460' }}>
            → זכאות ל-<strong>1 שנת פריסה</strong> (נמצא בטווח 2-6 שנים)
          </div>
        </div>
        
        <div style={{ marginBottom: '15px' }}>
          <strong>דוגמה 2:</strong> עובד עם וותק של 10 שנים ויום אחד
          <div style={{ marginLeft: '20px', marginTop: '5px', color: '#0c5460' }}>
            → זכאות ל-<strong>3 שנות פריסה</strong> (עבר את סף 10 השנים)
          </div>
        </div>
        
        <div style={{ marginBottom: '15px' }}>
          <strong>דוגמה 3:</strong> עובד עם וותק של 25 שנים
          <div style={{ marginLeft: '20px', marginTop: '5px', color: '#0c5460' }}>
            → זכאות ל-<strong>6 שנות פריסה</strong> (מקסימום)
          </div>
        </div>
      </div>

      {/* סוגי פיצויים ואפשרויות */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '8px',
        border: '1px solid #dee2e6'
      }}>
        <h3 style={{ color: '#2c3e50', marginTop: 0 }}>📋 סוגי פיצויים ואפשרויות מימוש</h3>
        
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ color: '#495057', marginBottom: '10px' }}>1️⃣ פיצויים פטורים ממס</h4>
          <ul style={{ lineHeight: '1.8', color: '#495057' }}>
            <li><strong>פדיון עם פטור:</strong> מימוש מיידי עם פטור מלא ממס (עד תקרה חוקית)</li>
            <li><strong>פדיון ללא פטור:</strong> מימוש מיידי עם פריסת מס לפי שנות הוותק</li>
            <li><strong>המרה לקצבה:</strong> המרת הסכום לקצבה חודשית (ללא פריסת מס)</li>
          </ul>
        </div>
        
        <div>
          <h4 style={{ color: '#495057', marginBottom: '10px' }}>2️⃣ פיצויים חייבים במס</h4>
          <ul style={{ lineHeight: '1.8', color: '#495057' }}>
            <li><strong>פדיון ללא פטור:</strong> מימוש מיידי עם פריסת מס לפי שנות הוותק</li>
            <li><strong>המרה לקצבה:</strong> המרת הסכום לקצבה חודשית (ללא פריסת מס)</li>
          </ul>
        </div>
      </div>

      {/* פריסת מס - הסבר מפורט */}
      <div style={{ 
        marginBottom: '30px', 
        padding: '20px', 
        backgroundColor: '#e7f3ff', 
        borderRadius: '8px',
        border: '2px solid #b3d9ff'
      }}>
        <h3 style={{ color: '#004085', marginTop: 0 }}>🧮 איך עובדת פריסת מס?</h3>
        <p style={{ fontSize: '16px', lineHeight: '1.8', marginBottom: '15px' }}>
          פריסת מס היא הטבה מיסויית המאפשרת לחלק את הכנסת הפיצויים על פני מספר שנים,
          כך שבכל שנה מחושב המס רק על חלק מהסכום הכולל.
        </p>
        
        <div style={{ 
          padding: '15px', 
          backgroundColor: 'white', 
          borderRadius: '4px',
          marginBottom: '15px'
        }}>
          <strong style={{ color: '#004085' }}>דוגמה מספרית:</strong>
          <div style={{ marginTop: '10px', lineHeight: '1.8' }}>
            • סכום פיצויים: 600,000 ₪<br/>
            • וותק: 12 שנים → זכאות ל-3 שנות פריסה<br/>
            • חלוקה: 600,000 ÷ 3 = 200,000 ₪ לשנה<br/>
            • המס מחושב על 200,000 ₪ בשנה (במקום על 600,000 ₪ בבת אחת)<br/>
            • <strong style={{ color: '#28a745' }}>חיסכון משמעותי במס!</strong>
          </div>
        </div>
        
        <p style={{ fontSize: '14px', color: '#004085', margin: 0 }}>
          <strong>💡 טיפ:</strong> המערכת ממליצה תמיד על פריסה מלאה (מקסימום שנות הזכאות) 
          לחיסכון מרבי במס.
        </p>
      </div>

      {/* הערות חשובות */}
      <div style={{ 
        padding: '20px', 
        backgroundColor: '#fff3cd', 
        borderRadius: '8px',
        border: '2px solid #ffc107'
      }}>
        <h3 style={{ color: '#856404', marginTop: 0 }}>⚠️ הערות חשובות</h3>
        <ul style={{ lineHeight: '1.8', color: '#856404', marginBottom: 0 }}>
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
