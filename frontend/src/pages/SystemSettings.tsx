import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from "../lib/api";
import { DEFAULT_RULES, ComponentConversionRule, loadConversionRules } from '../config/conversionRules';

interface TaxBracket {
  id: number;
  minMonthly: number;
  maxMonthly: number;
  minAnnual: number;
  maxAnnual: number;
  rate: number;
}

interface SeveranceCap {
  year: number;
  monthly_cap: number;
  annual_cap: number;
  description: string;
}

interface PensionCeiling {
  year: number;
  monthly_ceiling: number;
  description: string;
}

interface ExemptCapitalPercentage {
  year: number;
  percentage: number;
  description: string;
}

const SystemSettings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'tax' | 'severance' | 'conversion' | 'fixation'>('tax');
  
  const [taxBrackets, setTaxBrackets] = useState<TaxBracket[]>([
    { id: 1, minMonthly: 0, maxMonthly: 7010, minAnnual: 0, maxAnnual: 84120, rate: 10 },
    { id: 2, minMonthly: 7011, maxMonthly: 10060, minAnnual: 84121, maxAnnual: 120720, rate: 14 },
    { id: 3, minMonthly: 10061, maxMonthly: 16150, minAnnual: 120721, maxAnnual: 193800, rate: 20 },
    { id: 4, minMonthly: 16151, maxMonthly: 22440, minAnnual: 193801, maxAnnual: 269280, rate: 31 },
    { id: 5, minMonthly: 22441, maxMonthly: 46690, minAnnual: 269281, maxAnnual: 560280, rate: 35 },
    { id: 6, minMonthly: 46691, maxMonthly: 60130, minAnnual: 560281, maxAnnual: 721560, rate: 47 },
    { id: 7, minMonthly: 60131, maxMonthly: Infinity, minAnnual: 721561, maxAnnual: Infinity, rate: 50 }
  ]);

  const [isEditing, setIsEditing] = useState(false);
  const [editedBrackets, setEditedBrackets] = useState<TaxBracket[]>([]);
  
  // Conversion rules state
  const [conversionRules, setConversionRules] = useState<ComponentConversionRule[]>(loadConversionRules());
  const [conversionSaved, setConversionSaved] = useState(false);
  
  // Fixation data state - תקרות קצבה מזכה
  const [pensionCeilings, setPensionCeilings] = useState<PensionCeiling[]>([]);
  const [isEditingCeilings, setIsEditingCeilings] = useState(false);
  const [editedCeilings, setEditedCeilings] = useState<PensionCeiling[]>([]);
  
  // Fixation data state - אחוזי הון פטור
  const [exemptCapitalPercentages, setExemptCapitalPercentages] = useState<ExemptCapitalPercentage[]>([]);
  const [isEditingPercentages, setIsEditingPercentages] = useState(false);
  const [editedPercentages, setEditedPercentages] = useState<ExemptCapitalPercentage[]>([]);
  
  // תקרות פיצויים
  const [severanceCaps, setSeveranceCaps] = useState<SeveranceCap[]>([]);
  const [isEditingCaps, setIsEditingCaps] = useState(false);
  const [editedCaps, setEditedCaps] = useState<SeveranceCap[]>([]);
  const [capsLoading, setCapsLoading] = useState(false);
  const [capsError, setCapsError] = useState<string>("");

  useEffect(() => {
    // טעינת מדרגות המס מ-localStorage אם קיימות
    const savedBrackets = localStorage.getItem('taxBrackets');
    if (savedBrackets) {
      setTaxBrackets(JSON.parse(savedBrackets));
    }
    
    // טעינת תקרות פיצויים
    loadSeveranceCaps();
    
    // טעינת תקרות קצבה מזכה
    loadPensionCeilings();
    
    // טעינת אחוזי הון פטור
    loadExemptCapitalPercentages();
  }, []);
  
  // פונקציה לטעינת תקרות פיצויים מהשרת
  const loadSeveranceCaps = async () => {
    setCapsLoading(true);
    setCapsError("");
    
    try {
      // ניסיון לטעון מהשרת
      try {
        const response = await apiFetch<{caps: SeveranceCap[]}>('/api/v1/tax-data/severance-caps');
        
        if (response && response.caps) {
          setSeveranceCaps(response.caps);
          
          // שמירה גם ב-localStorage לגיבוי
          localStorage.setItem('severanceCaps', JSON.stringify(response.caps));
          return;
        }
      } catch (apiError) {
        console.log("API error, falling back to local data:", apiError);
        // המשך לשימוש בנתונים מקומיים
      }
      
      // אם אין תגובה מהשרת, נסה לטעון מ-localStorage
      const savedCaps = localStorage.getItem('severanceCaps');
      if (savedCaps) {
        setSeveranceCaps(JSON.parse(savedCaps));
      } else {
        // אם אין גם ב-localStorage, השתמש בערכי ברירת מחדל המעודכנים
        const defaultCaps = [
          {year: 2025, monthly_cap: 13750, annual_cap: 13750 * 12, description: 'תקרה חודשית לשנת 2025'},
          {year: 2024, monthly_cap: 13750, annual_cap: 13750 * 12, description: 'תקרה חודשית לשנת 2024'},
          {year: 2023, monthly_cap: 13310, annual_cap: 13310 * 12, description: 'תקרה חודשית לשנת 2023'},
          {year: 2022, monthly_cap: 12640, annual_cap: 12640 * 12, description: 'תקרה חודשית לשנת 2022'},
          {year: 2021, monthly_cap: 12340, annual_cap: 12340 * 12, description: 'תקרה חודשית לשנת 2021'},
          {year: 2020, monthly_cap: 12420, annual_cap: 12420 * 12, description: 'תקרה חודשית לשנת 2020'},
          {year: 2019, monthly_cap: 12380, annual_cap: 12380 * 12, description: 'תקרה חודשית לשנת 2019'},
          {year: 2018, monthly_cap: 12230, annual_cap: 12230 * 12, description: 'תקרה חודשית לשנת 2018'},
          {year: 2017, monthly_cap: 12200, annual_cap: 12200 * 12, description: 'תקרה חודשית לשנת 2017'},
          {year: 2016, monthly_cap: 12230, annual_cap: 12230 * 12, description: 'תקרה חודשית לשנת 2016'},
          {year: 2015, monthly_cap: 12340, annual_cap: 12340 * 12, description: 'תקרה חודשית לשנת 2015'},
          {year: 2014, monthly_cap: 12360, annual_cap: 12360 * 12, description: 'תקרה חודשית לשנת 2014'},
          {year: 2013, monthly_cap: 12120, annual_cap: 12120 * 12, description: 'תקרה חודשית לשנת 2013'},
          {year: 2012, monthly_cap: 11950, annual_cap: 11950 * 12, description: 'תקרה חודשית לשנת 2012'},
          {year: 2011, monthly_cap: 11650, annual_cap: 11650 * 12, description: 'תקרה חודשית לשנת 2011'},
          {year: 2010, monthly_cap: 11390, annual_cap: 11390 * 12, description: 'תקרה חודשית לשנת 2010'},
        ];
        
        setSeveranceCaps(defaultCaps);
        
        // שמירה ב-localStorage לשימוש עתידי
        localStorage.setItem('severanceCaps', JSON.stringify(defaultCaps));
      }
    } catch (e: any) {
      console.error("Error loading severance caps:", e);
      setCapsError(`שגיאה בטעינת תקרות פיצויים: ${e?.message || e}`);
      
      // ניסיון לטעון מ-localStorage במקרה של שגיאה
      const savedCaps = localStorage.getItem('severanceCaps');
      if (savedCaps) {
        setSeveranceCaps(JSON.parse(savedCaps));
      }
    } finally {
      setCapsLoading(false);
    }
  };
  
  // פונקציה לעריכת תקרות פיצויים
  const handleEditCaps = () => {
    setEditedCaps([...severanceCaps]);
    setIsEditingCaps(true);
  };
  
  // פונקציה לשמירת תקרות פיצויים
  const handleSaveCaps = async () => {
    try {
      // ניסיון לשמור בשרת
      await apiFetch('/tax-data/severance-caps', {
        method: 'POST',
        body: JSON.stringify(editedCaps),
      });
      
      // עדכון ה-state ושמירה ב-localStorage
      setSeveranceCaps([...editedCaps]);
      localStorage.setItem('severanceCaps', JSON.stringify(editedCaps));
      
      setIsEditingCaps(false);
      alert('תקרות הפיצויים נשמרו בהצלחה!');
    } catch (e: any) {
      console.error("Error saving severance caps:", e);
      alert(`שגיאה בשמירת תקרות פיצויים: ${e?.message || e}`);
    }
  };
  
  // פונקציה לביטול עריכת תקרות פיצויים
  const handleCancelCaps = () => {
    setEditedCaps([]);
    setIsEditingCaps(false);
  };
  
  // פונקציה לשינוי תקרת פיצויים
  const handleCapChange = (index: number, field: keyof SeveranceCap, value: any) => {
    const updated = [...editedCaps];
    updated[index] = { ...updated[index], [field]: field === 'year' ? parseInt(value) : parseFloat(value) };
    
    // עדכון אוטומטי של התקרה השנתית לפי התקרה החודשית
    if (field === 'monthly_cap') {
      updated[index].annual_cap = parseFloat(value) * 12;
    }
    
    // עדכון התיאור אם השנה השתנתה
    if (field === 'year') {
      updated[index].description = `תקרה חודשית לשנת ${value}`;
    }
    
    setEditedCaps(updated);
  };
  
  // פונקציה להוספת תקרת פיצויים חדשה
  const handleAddCap = () => {
    const currentYear = new Date().getFullYear();
    const newCap: SeveranceCap = {
      year: currentYear + 1,
      monthly_cap: 41667, // ערך ברירת מחדל
      annual_cap: 41667 * 12,
      description: `תקרה חודשית לשנת ${currentYear + 1}`
    };
    
    setEditedCaps([...editedCaps, newCap]);
  };

  const handleEdit = () => {
    setEditedBrackets([...taxBrackets]);
    setIsEditing(true);
  };

  const handleSave = () => {
    setTaxBrackets([...editedBrackets]);
    localStorage.setItem('taxBrackets', JSON.stringify(editedBrackets));
    setIsEditing(false);
    alert('מדרגות המס נשמרו בהצלחה!');
  };

  const handleCancel = () => {
    setEditedBrackets([]);
    setIsEditing(false);
  };

  const handleBracketChange = (index: number, field: keyof TaxBracket, value: number) => {
    const updated = [...editedBrackets];
    updated[index] = { ...updated[index], [field]: value };
    setEditedBrackets(updated);
  };

  const formatCurrency = (amount: number) => {
    if (amount === Infinity) return 'ומעלה';
    return amount.toLocaleString('he-IL') + ' ₪';
  };

  const currentBrackets = isEditing ? editedBrackets : taxBrackets;
  
  // Conversion rules handlers
  const handleSaveConversionRules = () => {
    localStorage.setItem('conversion_rules', JSON.stringify(conversionRules));
    setConversionSaved(true);
    setTimeout(() => setConversionSaved(false), 3000);
    alert('חוקי ההמרה נשמרו בהצלחה!\nהשינויים ייכנסו לתוקף בהמרות הבאות.');
  };

  const handleResetConversionRules = () => {
    if (confirm('האם אתה בטוח שברצונך לאפס את כל החוקים לברירת המחדל?')) {
      setConversionRules([...DEFAULT_RULES]);
      localStorage.removeItem('conversion_rules');
      alert('החוקים אופסו לברירת המחדל');
    }
  };

  const updateConversionRule = (index: number, field: keyof ComponentConversionRule, value: any) => {
    const newRules = [...conversionRules];
    (newRules[index] as any)[field] = value;
    setConversionRules(newRules);
  };
  
  // Pension Ceilings handlers
  const loadPensionCeilings = () => {
    const saved = localStorage.getItem('pensionCeilings');
    if (saved) {
      setPensionCeilings(JSON.parse(saved));
    } else {
      const defaultCeilings: PensionCeiling[] = [
        { year: 2025, monthly_ceiling: 9430, description: 'תקרת קצבה מזכה לשנת 2025' },
        { year: 2024, monthly_ceiling: 9430, description: 'תקרת קצבה מזכה לשנת 2024' },
        { year: 2023, monthly_ceiling: 9120, description: 'תקרת קצבה מזכה לשנת 2023' },
        { year: 2022, monthly_ceiling: 8660, description: 'תקרת קצבה מזכה לשנת 2022' },
        { year: 2021, monthly_ceiling: 8460, description: 'תקרת קצבה מזכה לשנת 2021' },
        { year: 2020, monthly_ceiling: 8510, description: 'תקרת קצבה מזכה לשנת 2020' },
        { year: 2019, monthly_ceiling: 8480, description: 'תקרת קצבה מזכה לשנת 2019' },
        { year: 2018, monthly_ceiling: 8380, description: 'תקרת קצבה מזכה לשנת 2018' },
        { year: 2017, monthly_ceiling: 8330, description: 'תקרת קצבה מזכה לשנת 2017' },
        { year: 2016, monthly_ceiling: 8370, description: 'תקרת קצבה מזכה לשנת 2016' },
        { year: 2015, monthly_ceiling: 8480, description: 'תקרת קצבה מזכה לשנת 2015' },
        { year: 2014, monthly_ceiling: 8500, description: 'תקרת קצבה מזכה לשנת 2014' },
        { year: 2013, monthly_ceiling: 8320, description: 'תקרת קצבה מזכה לשנת 2013' },
        { year: 2012, monthly_ceiling: 8210, description: 'תקרת קצבה מזכה לשנת 2012' },
      ];
      setPensionCeilings(defaultCeilings);
      localStorage.setItem('pensionCeilings', JSON.stringify(defaultCeilings));
    }
  };
  
  const handleEditCeilings = () => {
    setEditedCeilings([...pensionCeilings]);
    setIsEditingCeilings(true);
  };
  
  const handleSaveCeilings = () => {
    setPensionCeilings([...editedCeilings]);
    localStorage.setItem('pensionCeilings', JSON.stringify(editedCeilings));
    setIsEditingCeilings(false);
    alert('תקרות הקצבה המזכה נשמרו בהצלחה!');
  };
  
  const handleCancelCeilings = () => {
    setEditedCeilings([]);
    setIsEditingCeilings(false);
  };
  
  const handleCeilingChange = (index: number, field: keyof PensionCeiling, value: any) => {
    const updated = [...editedCeilings];
    updated[index] = { ...updated[index], [field]: field === 'year' ? parseInt(value) : (field === 'monthly_ceiling' ? parseFloat(value) : value) };
    setEditedCeilings(updated);
  };
  
  const handleAddCeiling = () => {
    const currentYear = new Date().getFullYear();
    const newCeiling: PensionCeiling = {
      year: currentYear + 1,
      monthly_ceiling: 9430,
      description: `תקרת קצבה מזכה לשנת ${currentYear + 1}`
    };
    setEditedCeilings([newCeiling, ...editedCeilings]);
  };
  
  // Exempt Capital Percentages handlers
  const loadExemptCapitalPercentages = () => {
    // הגדרת הערכים הנכונים
    const defaultPercentages: ExemptCapitalPercentage[] = [
      { year: 2028, percentage: 67, description: 'אחוז הון פטור לשנת 2028 ואילך' },
      { year: 2027, percentage: 62.5, description: 'אחוז הון פטור לשנת 2027' },
      { year: 2026, percentage: 57.5, description: 'אחוז הון פטור לשנת 2026' },
      { year: 2025, percentage: 57, description: 'אחוז הון פטור לשנת 2025' },
      { year: 2024, percentage: 52, description: 'אחוז הון פטור לשנת 2024' },
      { year: 2023, percentage: 52, description: 'אחוז הון פטור לשנת 2023' },
      { year: 2022, percentage: 52, description: 'אחוז הון פטור לשנת 2022' },
      { year: 2021, percentage: 52, description: 'אחוז הון פטור לשנת 2021' },
      { year: 2020, percentage: 52, description: 'אחוז הון פטור לשנת 2020' },
      { year: 2019, percentage: 49, description: 'אחוז הון פטור לשנת 2019' },
      { year: 2018, percentage: 49, description: 'אחוז הון פטור לשנת 2018' },
      { year: 2017, percentage: 49, description: 'אחוז הון פטור לשנת 2017' },
      { year: 2016, percentage: 49, description: 'אחוז הון פטור לשנת 2016' },
      { year: 2015, percentage: 43.5, description: 'אחוז הון פטור לשנת 2015' },
      { year: 2014, percentage: 43.5, description: 'אחוז הון פטור לשנת 2014' },
      { year: 2013, percentage: 43.5, description: 'אחוז הון פטור לשנת 2013' },
      { year: 2012, percentage: 43.5, description: 'אחוז הון פטור לשנת 2012' },
    ];
    
    // בדיקה אם יש נתונים שמורים
    const saved = localStorage.getItem('exemptCapitalPercentages');
    
    // אם יש נתונים שמורים, בדוק אם הם מעודכנים
    if (saved) {
      try {
        const savedData = JSON.parse(saved);
        // בדיקה אם הנתונים השמורים תואמים את הערכים החדשים
        // אם שנת 2025 היא 35% במקום 57%, זה אומר שהנתונים ישנים
        const year2025 = savedData.find((item: ExemptCapitalPercentage) => item.year === 2025);
        if (year2025 && year2025.percentage === 57) {
          // הנתונים מעודכנים, השתמש בהם
          setExemptCapitalPercentages(savedData);
          return;
        }
      } catch (e) {
        console.error('Error parsing saved percentages:', e);
      }
    }
    
    // אם אין נתונים שמורים או שהם לא מעודכנים, השתמש בערכים החדשים
    setExemptCapitalPercentages(defaultPercentages);
    localStorage.setItem('exemptCapitalPercentages', JSON.stringify(defaultPercentages));
  };
  
  const handleEditPercentages = () => {
    setEditedPercentages([...exemptCapitalPercentages]);
    setIsEditingPercentages(true);
  };
  
  const handleSavePercentages = () => {
    setExemptCapitalPercentages([...editedPercentages]);
    localStorage.setItem('exemptCapitalPercentages', JSON.stringify(editedPercentages));
    setIsEditingPercentages(false);
    alert('אחוזי ההון הפטור נשמרו בהצלחה!');
  };
  
  const handleCancelPercentages = () => {
    setEditedPercentages([]);
    setIsEditingPercentages(false);
  };
  
  const handlePercentageChange = (index: number, field: keyof ExemptCapitalPercentage, value: any) => {
    const updated = [...editedPercentages];
    updated[index] = { ...updated[index], [field]: field === 'year' ? parseInt(value) : (field === 'percentage' ? parseFloat(value) : value) };
    setEditedPercentages(updated);
  };
  
  const handleAddPercentage = () => {
    const currentYear = new Date().getFullYear();
    // שיעור ברירת מחדל לשנים מ-2028 ואילך הוא 67%
    const defaultPercentage = currentYear + 1 >= 2028 ? 67 : 57;
    const newPercentage: ExemptCapitalPercentage = {
      year: currentYear + 1,
      percentage: defaultPercentage,
      description: `אחוז הון פטור לשנת ${currentYear + 1}`
    };
    setEditedPercentages([newPercentage, ...editedPercentages]);
  };

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">⚙️ הגדרות מערכת</h1>
            <p className="card-subtitle">ניהול מדרגות מס, תקרות פיצויים, חוקי המרה ונתוני קיבוע זכויות</p>
          </div>
        </div>
        
        {/* Tabs Navigation */}
        <div className="modern-tabs">
          <button
            onClick={() => setActiveTab('tax')}
            className={`tab-button ${activeTab === 'tax' ? 'active' : ''}`}
          >
            📊 מדרגות מס
          </button>
          <button
            onClick={() => setActiveTab('severance')}
            className={`tab-button ${activeTab === 'severance' ? 'active' : ''}`}
          >
            💰 תקרות פיצויים
          </button>
          <button
            onClick={() => setActiveTab('conversion')}
            className={`tab-button ${activeTab === 'conversion' ? 'active' : ''}`}
          >
            🔄 חוקי המרה
          </button>
          <button
            onClick={() => setActiveTab('fixation')}
            className={`tab-button ${activeTab === 'fixation' ? 'active' : ''}`}
          >
            📋 נתוני קיבוע זכויות
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'tax' && (
        <div style={{ marginBottom: '40px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '20px' 
          }}>
            <h2 style={{ color: '#2c3e50', fontSize: '24px', margin: 0 }}>
              מדרגות מס הכנסה לשנת 2025
            </h2>
            
            {!isEditing ? (
              <button onClick={handleEdit} className="btn btn-primary">
                ✏️ ערוך מדרגות מס
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={handleSave} className="btn btn-success">
                  ✅ שמור
                </button>
                <button onClick={handleCancel} className="btn btn-secondary">
                  ❌ ביטול
                </button>
              </div>
            )}
          </div>

          {/* טבלת מדרגות המס */}
          <div>
            <table className="modern-table">
              <thead>
                <tr style={{ backgroundColor: '#f8f9fa' }}>
                  <th style={{ 
                    padding: '15px', 
                    textAlign: 'center', 
                    borderBottom: '2px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#2c3e50'
                  }}>
                    שיעור מס
                  </th>
                  <th style={{ 
                    padding: '15px', 
                    textAlign: 'center', 
                    borderBottom: '2px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#2c3e50'
                  }}>
                    הכנסה חודשית
                  </th>
                  <th style={{ 
                    padding: '15px', 
                    textAlign: 'center', 
                    borderBottom: '2px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#2c3e50'
                  }}>
                    הכנסה שנתית
                  </th>
                </tr>
              </thead>
              <tbody>
                {currentBrackets.map((bracket, index) => (
                  <tr key={bracket.id} style={{ 
                    backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                    borderBottom: '1px solid #dee2e6'
                  }}>
                    <td style={{ 
                      padding: '12px', 
                      textAlign: 'center', 
                      fontWeight: 'bold',
                      color: '#007bff',
                      fontSize: '16px'
                    }}>
                      {isEditing ? (
                        <input
                          type="number"
                          value={bracket.rate}
                          onChange={(e) => handleBracketChange(index, 'rate', parseInt(e.target.value))}
                          style={{
                            width: '60px',
                            padding: '5px',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                            textAlign: 'center'
                          }}
                        />
                      ) : (
                        `${bracket.rate}%`
                      )}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}>
                          <input
                            type="number"
                            value={bracket.minMonthly}
                            onChange={(e) => handleBracketChange(index, 'minMonthly', parseInt(e.target.value))}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                          <span>-</span>
                          {bracket.maxMonthly === Infinity ? (
                            <span>ומעלה</span>
                          ) : (
                            <input
                              type="number"
                              value={bracket.maxMonthly}
                              onChange={(e) => handleBracketChange(index, 'maxMonthly', parseInt(e.target.value))}
                              style={{
                                width: '80px',
                                padding: '5px',
                                border: '1px solid #ccc',
                                borderRadius: '4px',
                                textAlign: 'center'
                              }}
                            />
                          )}
                        </div>
                      ) : (
                        bracket.maxMonthly === Infinity ? 
                          `${formatCurrency(bracket.minMonthly)} ומעלה` :
                          `${formatCurrency(bracket.minMonthly)} - ${formatCurrency(bracket.maxMonthly)}`
                      )}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}>
                          <input
                            type="number"
                            value={bracket.minAnnual}
                            onChange={(e) => handleBracketChange(index, 'minAnnual', parseInt(e.target.value))}
                            style={{
                              width: '100px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                          <span>-</span>
                          {bracket.maxAnnual === Infinity ? (
                            <span>ומעלה</span>
                          ) : (
                            <input
                              type="number"
                              value={bracket.maxAnnual}
                              onChange={(e) => handleBracketChange(index, 'maxAnnual', parseInt(e.target.value))}
                              style={{
                                width: '100px',
                                padding: '5px',
                                border: '1px solid #ccc',
                                borderRadius: '4px',
                                textAlign: 'center'
                              }}
                            />
                          )}
                        </div>
                      ) : (
                        bracket.maxAnnual === Infinity ? 
                          `${formatCurrency(bracket.minAnnual)} ומעלה` :
                          `${formatCurrency(bracket.minAnnual)} - ${formatCurrency(bracket.maxAnnual)}`
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ 
            marginTop: '15px', 
            padding: '15px', 
            backgroundColor: '#e7f3ff', 
            borderRadius: '4px',
            border: '1px solid #b3d9ff'
          }}>
            <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
              <strong>הערה:</strong> מדרגות המס מתעדכנות אוטומטית בכל חישובי המס במערכת. 
              שינויים נשמרים במחשב המקומי ויישמרו עד לעדכון הבא.
            </p>
          </div>
        </div>

        )}
        
        {activeTab === 'severance' && (
        <div style={{ marginBottom: '40px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '20px' 
          }}>
            <h2 style={{ color: '#2c3e50', fontSize: '24px', margin: 0 }}>
              תקרות פיצויים פטורות ממס
            </h2>
            
            {!isEditingCaps ? (
              <button
                onClick={handleEditCaps}
                style={{
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                ערוך תקרות פיצויים
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={handleSaveCaps}
                  style={{
                    backgroundColor: '#28a745',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  שמור
                </button>
                <button
                  onClick={handleCancelCaps}
                  style={{
                    backgroundColor: '#6c757d',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  ביטול
                </button>
              </div>
            )}
          </div>

          {capsError && (
            <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
              {capsError}
            </div>
          )}

          {capsLoading ? (
            <div style={{ padding: 16, textAlign: 'center' }}>טוען תקרות פיצויים...</div>
          ) : (
            <div style={{ 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              overflow: 'hidden',
              backgroundColor: 'white'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa' }}>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      שנה
                    </th>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      תקרה חודשית
                    </th>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      תקרה שנתית
                    </th>
                    <th style={{ 
                      padding: '15px', 
                      textAlign: 'center', 
                      borderBottom: '2px solid #dee2e6',
                      fontWeight: 'bold',
                      color: '#2c3e50'
                    }}>
                      תיאור
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(isEditingCaps ? editedCaps : severanceCaps).map((cap, index) => (
                    <tr key={cap.year} style={{ 
                      backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                      borderBottom: '1px solid #dee2e6'
                    }}>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCaps ? (
                          <input
                            type="number"
                            value={cap.year}
                            onChange={(e) => handleCapChange(index, 'year', e.target.value)}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          cap.year
                        )}
                      </td>
                      <td style={{ 
                        padding: '12px', 
                        textAlign: 'center',
                        fontWeight: 'bold',
                        color: '#007bff'
                      }}>
                        {isEditingCaps ? (
                          <input
                            type="number"
                            value={cap.monthly_cap}
                            onChange={(e) => handleCapChange(index, 'monthly_cap', e.target.value)}
                            style={{
                              width: '100px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          formatCurrency(cap.monthly_cap)
                        )}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCaps ? (
                          <input
                            type="number"
                            value={cap.annual_cap}
                            disabled
                            style={{
                              width: '120px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center',
                              backgroundColor: '#f8f9fa'
                            }}
                          />
                        ) : (
                          formatCurrency(cap.annual_cap)
                        )}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCaps ? (
                          <input
                            type="text"
                            value={cap.description}
                            onChange={(e) => handleCapChange(index, 'description', e.target.value)}
                            style={{
                              width: '200px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px'
                            }}
                          />
                        ) : (
                          cap.description
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {isEditingCaps && (
                <div style={{ padding: '15px', textAlign: 'center' }}>
                  <button
                    onClick={handleAddCap}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#17a2b8',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    הוסף תקרה חדשה
                  </button>
                </div>
              )}
            </div>
          )}

          <div style={{ 
            marginTop: '15px', 
            padding: '15px', 
            backgroundColor: '#e7f3ff', 
            borderRadius: '4px',
            border: '1px solid #b3d9ff'
          }}>
            <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
              <strong>הערה:</strong> תקרות הפיצויים משמשות לחישוב הפטור ממס על מענקי פרישה.
              התקרה החודשית מוכפלת במספר שנות העבודה לחישוב הסכום הפטור.
            </p>
          </div>
        </div>

        )}
        
        {activeTab === 'conversion' && (
        <div style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '20px' }}>
            חוקי המרת יתרות
          </h2>
          
          {conversionSaved && (
            <div style={{ 
              padding: '12px', 
              backgroundColor: '#d4edda', 
              border: '1px solid #c3e6cb',
              borderRadius: '4px',
              marginBottom: '16px',
              color: '#155724'
            }}>
              ✓ השינויים נשמרו בהצלחה
            </div>
          )}
          
          <div style={{ marginBottom: '20px' }}>
            <p style={{ fontSize: '14px', color: '#666' }}>
              דף זה מאפשר לך לערוך את חוקי המרת היתרות מתיק פנסיוני.<br/>
              שים לב: שינויים בחוקים ישפיעו על כל ההמרות העתידיות במערכת.
            </p>
          </div>
          
          <div style={{ marginBottom: '16px', display: 'flex', gap: '10px' }}>
            <button
              onClick={handleSaveConversionRules}
              style={{
                padding: '10px 20px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '14px'
              }}
            >
              💾 שמור שינויים
            </button>
            <button
              onClick={handleResetConversionRules}
              style={{
                padding: '10px 20px',
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '14px'
              }}
            >
              🔄 אפס לברירת מחדל
            </button>
          </div>
          
          <div style={{ 
            border: '1px solid #dee2e6', 
            borderRadius: '8px', 
            overflow: 'hidden',
            backgroundColor: 'white'
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa' }}>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '200px', textAlign: 'right' }}>רכיב כספי</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '100px', textAlign: 'center' }}>המרה לקצבה</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '100px', textAlign: 'center' }}>המרה להון</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '120px', textAlign: 'center' }}>יחס מס (קצבה)</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '120px', textAlign: 'center' }}>יחס מס (הון)</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', minWidth: '300px', textAlign: 'right' }}>הודעת שגיאה</th>
                  </tr>
                </thead>
                <tbody>
                  {conversionRules.map((rule, index) => (
                    <tr key={rule.field} style={{ 
                      backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                      borderBottom: '1px solid #dee2e6'
                    }}>
                      <td style={{ padding: '12px' }}>
                        <strong>{rule.displayName}</strong>
                        <br/>
                        <span style={{ fontSize: '11px', color: '#666' }}>({rule.field})</span>
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={rule.canConvertToPension}
                          onChange={(e) => updateConversionRule(index, 'canConvertToPension', e.target.checked)}
                          style={{ transform: 'scale(1.2)', cursor: 'pointer' }}
                        />
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={rule.canConvertToCapital}
                          onChange={(e) => updateConversionRule(index, 'canConvertToCapital', e.target.checked)}
                          style={{ transform: 'scale(1.2)', cursor: 'pointer' }}
                        />
                      </td>
                      <td style={{ padding: '12px' }}>
                        <select
                          value={rule.taxTreatmentWhenPension}
                          onChange={(e) => updateConversionRule(index, 'taxTreatmentWhenPension', e.target.value)}
                          style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #ccc' }}
                        >
                          <option value="taxable">חייב במס</option>
                          <option value="exempt">פטור ממס</option>
                        </select>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <select
                          value={rule.taxTreatmentWhenCapital || 'capital_gain'}
                          onChange={(e) => updateConversionRule(index, 'taxTreatmentWhenCapital', e.target.value)}
                          style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #ccc' }}
                          disabled={!rule.canConvertToCapital}
                        >
                          <option value="capital_gain">מס רווח הון</option>
                          <option value="exempt">פטור ממס</option>
                        </select>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <textarea
                          value={rule.errorMessage || ''}
                          onChange={(e) => updateConversionRule(index, 'errorMessage', e.target.value)}
                          style={{ width: '100%', padding: '6px', minHeight: '40px', fontSize: '12px', borderRadius: '4px', border: '1px solid #ccc' }}
                          placeholder="הודעת שגיאה במקרה של המרה לא חוקית"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          
          <div style={{ 
            marginTop: '20px', 
            padding: '16px', 
            backgroundColor: '#e7f3ff', 
            borderRadius: '4px',
            border: '1px solid #b3d9ff'
          }}>
            <h3 style={{ color: '#0056b3', marginBottom: '10px', fontSize: '16px' }}>הסבר על השדות:</h3>
            <ul style={{ fontSize: '13px', lineHeight: 1.8, color: '#0056b3', margin: 0 }}>
              <li><strong>המרה לקצבה:</strong> האם ניתן להמיר את הרכיב הזה לקצבה</li>
              <li><strong>המרה להון:</strong> האם ניתן להמיר את הרכיב הזה לנכס הון</li>
              <li><strong>יחס מס (קצבה):</strong> יחס המס שיחול על הקצבה שתיווצר מהרכיב הזה</li>
              <li><strong>יחס מס (הון):</strong> יחס המס שיחול על נכס ההון שייווצר מהרכיב הזה</li>
              <li><strong>הודעת שגיאה:</strong> הודעה שתוצג למשתמש אם ינסה לבצע המרה לא חוקית</li>
            </ul>
          </div>
        </div>
        )}
        
        {activeTab === 'fixation' && (
        <div style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '30px' }}>
            נתוני קיבוע זכויות
          </h2>
          
          {/* Pension Ceilings Table */}
          <div style={{ marginBottom: '50px' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              marginBottom: '20px' 
            }}>
              <h3 style={{ color: '#2c3e50', fontSize: '20px', margin: 0 }}>
                תקרות קצבה מזכה (2012-2025)
              </h3>
              
              {!isEditingCeilings ? (
                <button
                  onClick={handleEditCeilings}
                  style={{
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  ערוך תקרות
                </button>
              ) : (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleSaveCeilings}
                    style={{
                      backgroundColor: '#28a745',
                      color: 'white',
                      border: 'none',
                      padding: '10px 20px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    שמור
                  </button>
                  <button
                    onClick={handleCancelCeilings}
                    style={{
                      backgroundColor: '#6c757d',
                      color: 'white',
                      border: 'none',
                      padding: '10px 20px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    ביטול
                  </button>
                </div>
              )}
            </div>
            
            <div style={{ 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              overflow: 'hidden',
              backgroundColor: 'white'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa' }}>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>שנה</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>תקרה חודשית (₪)</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'right' }}>תיאור</th>
                  </tr>
                </thead>
                <tbody>
                  {(isEditingCeilings ? editedCeilings : pensionCeilings).map((ceiling, index) => (
                    <tr key={ceiling.year} style={{ 
                      backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                      borderBottom: '1px solid #dee2e6'
                    }}>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingCeilings ? (
                          <input
                            type="number"
                            value={ceiling.year}
                            onChange={(e) => handleCeilingChange(index, 'year', e.target.value)}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          ceiling.year
                        )}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#007bff' }}>
                        {isEditingCeilings ? (
                          <input
                            type="number"
                            value={ceiling.monthly_ceiling}
                            onChange={(e) => handleCeilingChange(index, 'monthly_ceiling', e.target.value)}
                            style={{
                              width: '100px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          ceiling.monthly_ceiling.toLocaleString()
                        )}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {isEditingCeilings ? (
                          <input
                            type="text"
                            value={ceiling.description}
                            onChange={(e) => handleCeilingChange(index, 'description', e.target.value)}
                            style={{
                              width: '100%',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px'
                            }}
                          />
                        ) : (
                          ceiling.description
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {isEditingCeilings && (
                <div style={{ padding: '15px', textAlign: 'center', borderTop: '1px solid #dee2e6' }}>
                  <button
                    onClick={handleAddCeiling}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#17a2b8',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    הוסף שנה חדשה
                  </button>
                </div>
              )}
            </div>
            
            <div style={{ 
              marginTop: '15px', 
              padding: '15px', 
              backgroundColor: '#e7f3ff', 
              borderRadius: '4px',
              border: '1px solid #b3d9ff'
            }}>
              <p style={{ margin: 0, fontSize: '14px', color: '#0056b3' }}>
                <strong>הערה:</strong> תקרות הקצבה המזכה משמשות לחישוב הקצבה הפטורה ממס בקיבוע זכויות.
              </p>
            </div>
          </div>
          
          {/* Exempt Capital Percentages Table */}
          <div style={{ marginBottom: '40px' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              marginBottom: '20px' 
            }}>
              <h3 style={{ color: '#2c3e50', fontSize: '20px', margin: 0 }}>
                אחוזי הון פטור לחישוב יתרת הון (2012-2025)
              </h3>
              
              {!isEditingPercentages ? (
                <button
                  onClick={handleEditPercentages}
                  style={{
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  ערוך אחוזים
                </button>
              ) : (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleSavePercentages}
                    style={{
                      backgroundColor: '#28a745',
                      color: 'white',
                      border: 'none',
                      padding: '10px 20px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    שמור
                  </button>
                  <button
                    onClick={handleCancelPercentages}
                    style={{
                      backgroundColor: '#6c757d',
                      color: 'white',
                      border: 'none',
                      padding: '10px 20px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    ביטול
                  </button>
                </div>
              )}
            </div>
            
            <div style={{ 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              overflow: 'hidden',
              backgroundColor: 'white'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa' }}>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>שנה</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'center' }}>אחוז (%)</th>
                    <th style={{ padding: '15px', borderBottom: '2px solid #dee2e6', fontWeight: 'bold', color: '#2c3e50', textAlign: 'right' }}>תיאור</th>
                  </tr>
                </thead>
                <tbody>
                  {(isEditingPercentages ? editedPercentages : exemptCapitalPercentages).map((percentage, index) => (
                    <tr key={percentage.year} style={{ 
                      backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                      borderBottom: '1px solid #dee2e6'
                    }}>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        {isEditingPercentages ? (
                          <input
                            type="number"
                            value={percentage.year}
                            onChange={(e) => handlePercentageChange(index, 'year', e.target.value)}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          percentage.year
                        )}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#28a745' }}>
                        {isEditingPercentages ? (
                          <input
                            type="number"
                            value={percentage.percentage}
                            onChange={(e) => handlePercentageChange(index, 'percentage', e.target.value)}
                            style={{
                              width: '80px',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px',
                              textAlign: 'center'
                            }}
                          />
                        ) : (
                          `${percentage.percentage}%`
                        )}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {isEditingPercentages ? (
                          <input
                            type="text"
                            value={percentage.description}
                            onChange={(e) => handlePercentageChange(index, 'description', e.target.value)}
                            style={{
                              width: '100%',
                              padding: '5px',
                              border: '1px solid #ccc',
                              borderRadius: '4px'
                            }}
                          />
                        ) : (
                          percentage.description
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {isEditingPercentages && (
                <div style={{ padding: '15px', textAlign: 'center', borderTop: '1px solid #dee2e6' }}>
                  <button
                    onClick={handleAddPercentage}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#17a2b8',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    הוסף שנה חדשה
                  </button>
                </div>
              )}
            </div>
            
            <div style={{ 
              marginTop: '15px', 
              padding: '15px', 
              backgroundColor: '#e7f3ff', 
              borderRadius: '4px',
              border: '1px solid #b3d9ff'
            }}>
              <p style={{ margin: 0, fontSize: '14px', color: '#0056b3', marginBottom: '10px' }}>
                <strong>הערה:</strong> אחוזי ההון הפטור משמשים לחישוב יתרת ההון הפטורה ממס בקיבוע זכויות.
              </p>
              <p style={{ margin: 0, fontSize: '13px', color: '#0056b3' }}>
                <strong>נוסחה:</strong> יתרת הון פטורה = תקרת קצבה מזכה × 180 × אחוז הון פטור<br/>
                <strong>דוגמה לשנת 2025:</strong> 9,430 × 180 × 57% = 967,986 ₪
              </p>
            </div>
          </div>
        </div>
        )}
      </div>
    </div>
  );
};

export default SystemSettings;
