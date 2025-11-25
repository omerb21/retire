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
    <div className="system-settings-section">
      <h2 className="system-settings-section-title">
        הגדרות גיל פרישה
      </h2>
      
      <div className="system-settings-card">
        <h3 className="system-settings-card-title">גיל פרישה לגברים</h3>
        <div className="system-settings-flex-row">
          <label>גיל פרישה:</label>
          <input
            type="number"
            value={maleRetirementAge}
            onChange={(e) => onMaleRetirementAgeChange(parseInt(e.target.value))}
            className="system-settings-input-small"
          />
          <span>שנים</span>
        </div>
        <p className="system-settings-muted-text">
          גיל פרישה לגברים הוא תמיד קבוע: <strong>67 שנים</strong>
        </p>
      </div>
      
      <div className="system-settings-card">
        <h3 className="system-settings-card-title">גיל פרישה לנשים - טבלה חוקית</h3>
        <p>גיל הפרישה לנשים מחושב אוטומטית לפי תאריך הלידה:</p>
        
        <table className="modern-table system-settings-retirement-table">
          <thead>
            <tr className="system-settings-retirement-header-row">
              <th className="system-settings-retirement-header-cell">תאריך לידה</th>
              <th className="system-settings-retirement-header-cell system-settings-retirement-header-cell-center">גיל פרישה</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="system-settings-retirement-cell">עד מרץ 1944</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">60</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">אפריל - אוגוסט 1944</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">60 + 4 חודשים</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ספטמבר 1944 - אפריל 1945</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">60 + 8 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">מאי - דצמבר 1945</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">61</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ינואר - אוגוסט 1946</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">61 + 4 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">ספטמבר 1946 - אפריל 1947</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">61 + 8 חודשים</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">מאי 1947 - דצמבר 1959</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">62</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1960</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">62 + 4 חודשים</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1961</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">62 + 8 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1962</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">63</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1963</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">63 + 3 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1964</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">63 + 6 חודשים</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1965</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">63 + 9 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1966</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">64</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1967</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">64 + 3 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1968</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">64 + 6 חודשים</td>
            </tr>
            <tr>
              <td className="system-settings-retirement-cell">ינואר - דצמבר 1969</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">64 + 9 חודשים</td>
            </tr>
            <tr className="system-settings-retirement-row-alt">
              <td className="system-settings-retirement-cell">1970 ואילך</td>
              <td className="system-settings-retirement-cell system-settings-retirement-cell-center">65</td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div className="system-settings-actions-row">
        <button
          onClick={onSave}
          className="btn btn-success"
        >
          💾 שמור הגדרות
        </button>
        {retirementSaved && (
          <span className="system-settings-success-text">✅ נשמר בהצלחה</span>
        )}
      </div>
      
      <div className="system-settings-note-box">
        <p className="system-settings-note-text">
          <strong>הערה:</strong> גיל הפרישה לנשים מחושב אוטומטית על פי הטבלה החוקית לעיל.
          המערכת משתמשת בתאריך הלידה של הלקוח לחישוב מדויק.
        </p>
      </div>
    </div>
  );
};

export default RetirementSettings;
