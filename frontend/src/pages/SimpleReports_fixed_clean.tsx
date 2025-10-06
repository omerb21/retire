import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const SimpleReportsFixed: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // פונקציה לחישוב מס על הכנסה ספציפית עם נקודות זיכוי
  const calculateTaxForIncome = (annualIncome: number, incomeType: string): number => {
    if (annualIncome <= 0) return 0;
    
    // חישוב מס בסיסי לפי מדרגות
    let baseTax = 0;
    let remainingIncome = annualIncome;
    
    // מדרגות מס 2024
    const taxBrackets = [
      { min: 0, max: 84000, rate: 0.10 },
      { min: 84000, max: 121000, rate: 0.14 },
      { min: 121000, max: 202000, rate: 0.20 },
      { min: 202000, max: 420000, rate: 0.31 },
      { min: 420000, max: 672000, rate: 0.35 },
      { min: 672000, max: Infinity, rate: 0.47 }
    ];
    
    // חישוב מס לפי מדרגות
    for (const bracket of taxBrackets) {
      if (remainingIncome <= 0) break;
      
      const taxableInThisBracket = Math.min(remainingIncome, bracket.max - bracket.min);
      baseTax += taxableInThisBracket * bracket.rate;
      remainingIncome -= taxableInThisBracket;
    }
    
    // הקלות למס לפנסיונרים
    if (incomeType === 'pension') {
      baseTax *= 0.85; // הנחה של 15% לפנסיונרים
    }
    
    // חישוב נקודות זיכוי - רק מקלט המשתמש
    let totalTaxCredits = 0;
    const creditPointValue = 2640; // ערך נקודת זיכוי 2024 בשקלים
    
    if (client && client.tax_credit_points && client.tax_credit_points > 0) {
      totalTaxCredits = client.tax_credit_points * creditPointValue;
    }
    
    // הפחתת נקודות הזיכוי מהמס
    const finalTax = Math.max(0, baseTax - totalTaxCredits);
    
    return finalTax;
  };

  useEffect(() => {
    const fetchClient = async () => {
      if (!id) return;
      
      try {
        setLoading(true);
        const response = await axios.get(`http://localhost:8005/api/v1/clients/${id}`);
        setClient(response.data);
      } catch (err: any) {
        setError('שגיאה בטעינת נתוני לקוח: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchClient();
  }, [id]);

  if (loading) return <div>טוען נתונים...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;
  if (!client) return <div>לא נמצא לקוח</div>;

  return (
    <div>
      <h2>דוח פרישה מתוקן</h2>
      <h3>פרטי לקוח: {client.full_name}</h3>
      <p>מספר זהות: {client.id_number}</p>
      
      {client.tax_credit_points && (
        <div>
          <h4>נקודות זיכוי</h4>
          <p>נקודות זיכוי (מקלט המשתמש): {client.tax_credit_points}</p>
          <p>סכום זיכוי שנתי: ₪{(client.tax_credit_points * 2640).toLocaleString()}</p>
        </div>
      )}
      
      <div>
        <h4>דוגמת חישוב מס</h4>
        <p>מס על הכנסה של ₪200,000: ₪{calculateTaxForIncome(200000, 'salary').toLocaleString()}</p>
        <p>מס על פנסיה של ₪200,000: ₪{calculateTaxForIncome(200000, 'pension').toLocaleString()}</p>
      </div>
    </div>
  );
};

export default SimpleReportsFixed;
