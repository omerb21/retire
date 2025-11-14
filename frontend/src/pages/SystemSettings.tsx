/**
 * SystemSettings - Wrapper component using modular sub-components
 * 
 * This file provides the same functionality as the original SystemSettings.tsx
 * but delegates all logic to specialized sub-components in components/system-settings/
 */

import React, { useState, useEffect } from 'react';
import { DEFAULT_RULES, ComponentConversionRule, loadConversionRules } from '../config/conversionRules';
import TaxCalculationDocumentation from '../components/TaxCalculationDocumentation';
import TaxSettings from '../components/system-settings/TaxSettings';
import SeveranceSettings from '../components/system-settings/SeveranceSettings';
import ConversionSettings from '../components/system-settings/ConversionSettings';
import RetirementSettings from '../components/system-settings/RetirementSettings';
import FixationSettings from '../components/system-settings/FixationSettings';
import ScenariosSettings from '../components/system-settings/ScenariosSettings';
import TerminationSettings from '../components/system-settings/TerminationSettings';
import AnnuitySettings from '../components/system-settings/AnnuitySettings';
import SystemHealthMonitor from '../components/system-settings/SystemHealthMonitor';
import { useSystemSettings } from '../hooks/useSystemSettings';
import { 
  TabType, 
  TaxBracket, 
  SeveranceCap, 
  PensionCeiling, 
  ExemptCapitalPercentage 
} from '../types/system-settings.types';

const SystemSettings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('tax');
  
  // Use custom hook for state management
  const {
    taxBrackets,
    setTaxBrackets,
    isEditing,
    setIsEditing,
    editedBrackets,
    setEditedBrackets,
    severanceCaps,
    isEditingCaps,
    setIsEditingCaps,
    editedCaps,
    setEditedCaps,
    capsLoading,
    capsError,
    loadSeveranceCaps,
    saveSeveranceCaps,
    pensionCeilings,
    setPensionCeilings,
    isEditingCeilings,
    setIsEditingCeilings,
    editedCeilings,
    setEditedCeilings,
    exemptCapitalPercentages,
    setExemptCapitalPercentages,
    isEditingPercentages,
    setIsEditingPercentages,
    editedPercentages,
    setEditedPercentages,
    formatCurrency,
  } = useSystemSettings();

  // Conversion rules state
  const [conversionRules, setConversionRules] = useState<ComponentConversionRule[]>(loadConversionRules());
  const [conversionSaved, setConversionSaved] = useState(false);

  // Retirement age state
  const [maleRetirementAge, setMaleRetirementAge] = useState(67);
  const [retirementSaved, setRetirementSaved] = useState(false);

  useEffect(() => {
    // Load tax brackets from localStorage
    const savedBrackets = localStorage.getItem('taxBrackets');
    if (savedBrackets) {
      setTaxBrackets(JSON.parse(savedBrackets));
    }
    
    // Load severance caps
    loadSeveranceCaps();
    
    // Load pension ceilings
    loadPensionCeilings();
    
    // Load exempt capital percentages
    loadExemptCapitalPercentages();
  }, []);

  // Tax brackets handlers
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

  // Severance caps handlers
  const handleEditCaps = () => {
    setEditedCaps([...severanceCaps]);
    setIsEditingCaps(true);
  };

  const handleSaveCaps = async () => {
    try {
      await saveSeveranceCaps(editedCaps);
      alert('תקרות הפיצויים נשמרו בהצלחה!');
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleCancelCaps = () => {
    setEditedCaps([]);
    setIsEditingCaps(false);
  };

  const handleCapChange = (index: number, field: keyof SeveranceCap, value: any) => {
    const updated = [...editedCaps];
    updated[index] = { ...updated[index], [field]: field === 'year' ? parseInt(value) : parseFloat(value) };
    
    if (field === 'monthly_cap') {
      updated[index].annual_cap = parseFloat(value) * 12;
    }
    
    if (field === 'year') {
      updated[index].description = `תקרה חודשית לשנת ${value}`;
    }
    
    setEditedCaps(updated);
  };

  const handleAddCap = () => {
    const currentYear = new Date().getFullYear();
    const newCap: SeveranceCap = {
      year: currentYear + 1,
      monthly_cap: 41667,
      annual_cap: 41667 * 12,
      description: `תקרה חודשית לשנת ${currentYear + 1}`
    };
    
    setEditedCaps([...editedCaps, newCap]);
  };

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

    const defaultCeilings: PensionCeiling[] = [
      { year: 2028, monthly_ceiling: 9430, description: 'תקרת קצבה מזכה לשנת 2028' },
      { year: 2027, monthly_ceiling: 9430, description: 'תקרת קצבה מזכה לשנת 2027' },
      { year: 2026, monthly_ceiling: 9430, description: 'תקרת קצבה מזכה לשנת 2026' },
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

    if (saved) {
      try {
        const parsed: PensionCeiling[] = JSON.parse(saved);
        const years = new Set(parsed.map((item) => item.year));
        const merged = [...parsed];

        [2026, 2027, 2028].forEach((year) => {
          if (!years.has(year)) {
            merged.unshift({
              year,
              monthly_ceiling: 9430,
              description: `תקרת קצבה מזכה לשנת ${year}`,
            });
          }
        });

        setPensionCeilings(merged);
        localStorage.setItem('pensionCeilings', JSON.stringify(merged));
        return;
      } catch (e) {
        // אם הנתונים השמורים אינם תקינים, נשתמש בברירת המחדל
        console.error('Error parsing pensionCeilings from localStorage, using defaults instead', e);
      }
    }

    setPensionCeilings(defaultCeilings);
    localStorage.setItem('pensionCeilings', JSON.stringify(defaultCeilings));
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
    
    const saved = localStorage.getItem('exemptCapitalPercentages');
    
    if (saved) {
      try {
        const savedData = JSON.parse(saved);
        const year2025 = savedData.find((item: ExemptCapitalPercentage) => item.year === 2025);
        if (year2025 && year2025.percentage === 57) {
          setExemptCapitalPercentages(savedData);
          return;
        }
      } catch (e) {
        console.error('Error parsing saved percentages:', e);
      }
    }
    
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
    const defaultPercentage = currentYear + 1 >= 2028 ? 67 : 57;
    const newPercentage: ExemptCapitalPercentage = {
      year: currentYear + 1,
      percentage: defaultPercentage,
      description: `אחוז הון פטור לשנת ${currentYear + 1}`
    };
    setEditedPercentages([newPercentage, ...editedPercentages]);
  };

  // Retirement age handlers
  const handleSaveRetirement = () => {
    localStorage.setItem('maleRetirementAge', maleRetirementAge.toString());
    setRetirementSaved(true);
    setTimeout(() => setRetirementSaved(false), 3000);
    alert('הגדרות גיל פרישה נשמרו בהצלחה!');
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
          <button
            onClick={() => setActiveTab('scenarios')}
            className={`tab-button ${activeTab === 'scenarios' ? 'active' : ''}`}
          >
            🎯 לוגיקת תרחישים
          </button>
          <button
            onClick={() => setActiveTab('retirement')}
            className={`tab-button ${activeTab === 'retirement' ? 'active' : ''}`}
          >
            👤 גיל פרישה
          </button>
          <button
            onClick={() => setActiveTab('termination')}
            className={`tab-button ${activeTab === 'termination' ? 'active' : ''}`}
          >
            🚪 עזיבות עבודה
          </button>
          <button
            onClick={() => setActiveTab('annuity')}
            className={`tab-button ${activeTab === 'annuity' ? 'active' : ''}`}
          >
            📊 מקדמי קצבה
          </button>
          <button
            onClick={() => setActiveTab('tax_calculation')}
            className={`tab-button ${activeTab === 'tax_calculation' ? 'active' : ''}`}
          >
            🧮 חישובי מס
          </button>
          <button
            onClick={() => setActiveTab('health')}
            className={`tab-button ${activeTab === 'health' ? 'active' : ''}`}
          >
            🏥 תקינות מערכת
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'tax' && (
          <TaxSettings
            taxBrackets={taxBrackets}
            isEditing={isEditing}
            editedBrackets={editedBrackets}
            onEdit={handleEdit}
            onSave={handleSave}
            onCancel={handleCancel}
            onBracketChange={handleBracketChange}
            formatCurrency={formatCurrency}
          />
        )}
        
        {activeTab === 'severance' && (
          <SeveranceSettings
            severanceCaps={severanceCaps}
            isEditingCaps={isEditingCaps}
            editedCaps={editedCaps}
            capsLoading={capsLoading}
            capsError={capsError}
            onEditCaps={handleEditCaps}
            onSaveCaps={handleSaveCaps}
            onCancelCaps={handleCancelCaps}
            onCapChange={handleCapChange}
            onAddCap={handleAddCap}
            formatCurrency={formatCurrency}
          />
        )}
        
        {activeTab === 'conversion' && (
          <ConversionSettings
            conversionRules={conversionRules}
            conversionSaved={conversionSaved}
            onSave={handleSaveConversionRules}
            onReset={handleResetConversionRules}
            onUpdateRule={updateConversionRule}
          />
        )}
        
        {activeTab === 'retirement' && (
          <RetirementSettings
            maleRetirementAge={maleRetirementAge}
            retirementSaved={retirementSaved}
            onMaleRetirementAgeChange={setMaleRetirementAge}
            onSave={handleSaveRetirement}
          />
        )}

        {activeTab === 'fixation' && (
          <FixationSettings
            pensionCeilings={pensionCeilings}
            isEditingCeilings={isEditingCeilings}
            editedCeilings={editedCeilings}
            exemptCapitalPercentages={exemptCapitalPercentages}
            isEditingPercentages={isEditingPercentages}
            editedPercentages={editedPercentages}
            onEditCeilings={handleEditCeilings}
            onSaveCeilings={handleSaveCeilings}
            onCancelCeilings={handleCancelCeilings}
            onCeilingChange={handleCeilingChange}
            onAddCeiling={handleAddCeiling}
            onEditPercentages={handleEditPercentages}
            onSavePercentages={handleSavePercentages}
            onCancelPercentages={handleCancelPercentages}
            onPercentageChange={handlePercentageChange}
            onAddPercentage={handleAddPercentage}
          />
        )}
        
        {activeTab === 'scenarios' && <ScenariosSettings />}
        
        {activeTab === 'termination' && <TerminationSettings />}
        
        {activeTab === 'annuity' && <AnnuitySettings />}

        {activeTab === 'tax_calculation' && (
          <div style={{ marginBottom: '40px' }}>
            <h2 style={{ color: '#2c3e50', fontSize: '24px', marginBottom: '30px' }}>
              תיעוד חישובי מס
            </h2>
            <TaxCalculationDocumentation />
          </div>
        )}

        {activeTab === 'health' && <SystemHealthMonitor />}
      </div>
    </div>
  );
};

export default SystemSettings;
