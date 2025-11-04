import React from 'react';

interface RetirementSettingsProps {
  maleRetirementAge: number;
  retirementSaved: boolean;
  onMaleRetirementAgeChange: (age: number) => void;
  onSave: () => void;
}

const RetirementSettings: React.FC<RetirementSettingsProps> = ({
  maleRetirementAge,
  retirementSaved,
  onMaleRetirementAgeChange,
  onSave,
}) => {
  return (
    <div style={{ marginBottom: '40px' }}>
      <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '20px' }}>
        הגדרות גיל פרישה
      </h2>
      
      <div style={{ 
        backgroundColor: 'white', 
        padding: '20px', 
        borderRadius: '8px', 
        border: '1px solid #dee2e6',
        marginBottom: '20px'
      }}>
        <h3 style={{ marginTop: 0 }}>גיל פרישה לגברים</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label>גיל פרישה:</label>
          <input
            type="number"
            value={maleRetirementAge}
            onChange={(e) => onMaleRetirementAgeChange(parseInt(e.target.value))}
            style={{
              width: '80px',
              padding: '8px',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
          />
          <span>שנים</span>
        </div>
        <p style={{ color: '#666', fontSize: '14px', marginTop: '10px' }}>
          גיל פרישה לגברים הוא תמיד קבוע: <strong>67 שנים</strong>
        </p>
      </div>
      
      <div style={{ 
        backgroundColor: 'white', 
        padding: '20px', 
        borderRadius: '8px', 
        border: '1px solid #dee2e6',
        marginBottom: '20px'
      }}>
        <h3 style={{ marginTop: 0 }}>גיל פרישה לנשים - טבלה חוקית</h3>
        <p style={{ marginBottom: '15px' }}>גיל הפרישה לנשים מחושב אוטומטית לפי תאריך הלידה:</p>
        
        <table className="modern-table" style={{ fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #dee2e6' }}>תאריך לידה</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '2px solid #dee2e6' }}>גיל פרישה</th>
            </tr>
          </thead>
          <tbody>
            <tr><td style={{ padding: '10px' }}>עד מרץ 1944</td><td style={{ padding: '10px', textAlign: 'center' }}>60</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>אפריל - אוגוסט 1944</td><td style={{ padding: '10px', textAlign: 'center' }}>60 + 4 חודשים</td></tr>
            <tr><td style={{ padding: '10px' }}>ספטמבר 1944 - אפריל 1945</td><td style={{ padding: '10px', textAlign: 'center' }}>60 + 8 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>מאי - דצמבר 1945</td><td style={{ padding: '10px', textAlign: 'center' }}>61</td></tr>
            <tr><td style={{ padding: '10px' }}>ינואר - אוגוסט 1946</td><td style={{ padding: '10px', textAlign: 'center' }}>61 + 4 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>ספטמבר 1946 - אפריל 1947</td><td style={{ padding: '10px', textAlign: 'center' }}>61 + 8 חודשים</td></tr>
            <tr><td style={{ padding: '10px' }}>מאי 1947 - דצמבר 1959</td><td style={{ padding: '10px', textAlign: 'center' }}>62</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>ינואר - דצמבר 1960</td><td style={{ padding: '10px', textAlign: 'center' }}>62 + 4 חודשים</td></tr>
            <tr><td style={{ padding: '10px' }}>ינואר - דצמבר 1961</td><td style={{ padding: '10px', textAlign: 'center' }}>62 + 8 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>ינואר - דצמבר 1962</td><td style={{ padding: '10px', textAlign: 'center' }}>63</td></tr>
            <tr><td style={{ padding: '10px' }}>ינואר - דצמבר 1963</td><td style={{ padding: '10px', textAlign: 'center' }}>63 + 3 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>ינואר - דצמבר 1964</td><td style={{ padding: '10px', textAlign: 'center' }}>63 + 6 חודשים</td></tr>
            <tr><td style={{ padding: '10px' }}>ינואר - דצמבר 1965</td><td style={{ padding: '10px', textAlign: 'center' }}>63 + 9 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>ינואר - דצמבר 1966</td><td style={{ padding: '10px', textAlign: 'center' }}>64</td></tr>
            <tr><td style={{ padding: '10px' }}>ינואר - דצמבר 1967</td><td style={{ padding: '10px', textAlign: 'center' }}>64 + 3 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>ינואר - דצמבר 1968</td><td style={{ padding: '10px', textAlign: 'center' }}>64 + 6 חודשים</td></tr>
            <tr><td style={{ padding: '10px' }}>ינואר - דצמבר 1969</td><td style={{ padding: '10px', textAlign: 'center' }}>64 + 9 חודשים</td></tr>
            <tr style={{ backgroundColor: '#f8f9fa' }}><td style={{ padding: '10px' }}>1970 ואילך</td><td style={{ padding: '10px', textAlign: 'center' }}>65</td></tr>
          </tbody>
        </table>
      </div>
      
      <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
        <button
          onClick={onSave}
          className="btn btn-success"
        >
          💾 שמור הגדרות
        </button>
        {retirementSaved && (
          <span style={{ color: '#28a745', alignSelf: 'center' }}>✅ נשמר בהצלחה</span>
        )}
      </div>
      
      <div style={{ 
        marginTop: '20px', 
        padding: '15px', 
        backgroundColor: '#e7f3ff', 
        borderRadius: '4px',
        border: '1px solid #b3d9ff'
      }}>
        <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
          <strong>הערה:</strong> גיל הפרישה לנשים מחושב אוטומטית על פי הטבלה החוקית לעיל.
          המערכת משתמשת בתאריך הלידה של הלקוח לחישוב מדויק.
        </p>
      </div>
    </div>
  );
};

export default RetirementSettings;
