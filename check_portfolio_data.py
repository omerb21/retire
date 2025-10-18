"""
בדיקה - האם יש נתוני תיק פנסיוני ב-localStorage
"""

# זה סקריפט להדרכה - צריך לבדוק ב-DevTools של הדפדפן:
# 1. פתח DevTools (F12)
# 2. לך ל-Console
# 3. הרץ:
print("""
להדפסת נתוני התיק הפנסיוני:

JavaScript להרצה ב-Console:
================================
const pensionData = localStorage.getItem('pensionData_4');
if (pensionData) {
    const data = JSON.parse(pensionData);
    console.log('מספר חשבונות בתיק:', data.length);
    console.log('נתונים:', data);
} else {
    console.log('אין נתוני תיק פנסיוני ב-localStorage');
}
================================

או בדוק ישירות ב-Application > Local Storage > localhost
""")
