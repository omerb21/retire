import { useEffect, useState } from 'react';
import {
  DEFAULT_RULES,
  ComponentConversionRule,
  loadConversionRules,
  saveConversionRules,
  clearConversionRules,
} from '../../../config/conversionRules';
import { getTaxBrackets, saveTaxBrackets } from '../../../components/reports/calculations/taxCalculations';
import { useSystemSettings } from '../../../hooks/useSystemSettings';
import {
  TabType,
  TaxBracket,
  SeveranceCap,
  PensionCeiling,
  ExemptCapitalPercentage,
  IdfPromoterRow,
} from '../../../types/system-settings.types';
import {
  loadPensionCeilingsFromStorage,
  savePensionCeilingsToStorage,
  loadExemptCapitalPercentagesFromStorage,
  saveExemptCapitalPercentagesToStorage,
  saveMaleRetirementAgeToStorage,
  loadIdfPromoterTableFromStorage,
  saveIdfPromoterTableToStorage,
} from '../../../services/systemSettingsStorageService';

export const useSystemSettingsPage = () => {
  const [activeTab, setActiveTab] = useState<TabType>('tax');

  const [conversionRules, setConversionRules] = useState<ComponentConversionRule[]>(
    loadConversionRules()
  );
  const [conversionSaved, setConversionSaved] = useState(false);

  const [maleRetirementAge, setMaleRetirementAge] = useState(67);
  const [retirementSaved, setRetirementSaved] = useState(false);

  const [idfPromoterTable, setIdfPromoterTable] = useState<IdfPromoterRow[]>([]);
  const [isEditingIdfPromoterTable, setIsEditingIdfPromoterTable] = useState(false);
  const [editedIdfPromoterTable, setEditedIdfPromoterTable] = useState<IdfPromoterRow[]>([]);

  const {
    // Tax brackets
    taxBrackets,
    setTaxBrackets,
    isEditing,
    setIsEditing,
    editedBrackets,
    setEditedBrackets,
    // Severance caps
    severanceCaps,
    isEditingCaps,
    setIsEditingCaps,
    editedCaps,
    setEditedCaps,
    capsLoading,
    capsError,
    loadSeveranceCaps,
    saveSeveranceCaps,
    // Pension ceilings
    pensionCeilings,
    setPensionCeilings,
    isEditingCeilings,
    setIsEditingCeilings,
    editedCeilings,
    setEditedCeilings,
    // Exempt capital percentages
    exemptCapitalPercentages,
    setExemptCapitalPercentages,
    isEditingPercentages,
    setIsEditingPercentages,
    editedPercentages,
    setEditedPercentages,
    // Utils
    formatCurrency,
  } = useSystemSettings();

  useEffect(() => {
    const loadedBrackets = getTaxBrackets();
    if (loadedBrackets && Array.isArray(loadedBrackets) && loadedBrackets.length > 0) {
      setTaxBrackets(loadedBrackets as TaxBracket[]);
    }

    loadSeveranceCaps();
    loadPensionCeilings();
    loadExemptCapitalPercentages();
    loadIdfPromoterTable();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tax brackets handlers
  const handleEdit = () => {
    setEditedBrackets([...taxBrackets]);
    setIsEditing(true);
  };

  const handleSave = () => {
    setTaxBrackets([...editedBrackets]);
    saveTaxBrackets(editedBrackets);
    setIsEditing(false);
    alert('מדרגות המס נשמרו בהצלחה!');
  };

  const handleCancel = () => {
    setEditedBrackets([]);
    setIsEditing(false);
  };

  const handleBracketChange = (
    index: number,
    field: keyof TaxBracket,
    value: number
  ) => {
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

  const handleCapChange = (
    index: number,
    field: keyof SeveranceCap,
    value: any
  ) => {
    const updated = [...editedCaps];
    updated[index] = {
      ...updated[index],
      [field]: field === 'year' ? parseInt(value, 10) : parseFloat(value),
    };

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
      description: `תקרה חודשית לשנת ${currentYear + 1}`,
    };

    setEditedCaps([...editedCaps, newCap]);
  };

  // Conversion rules handlers
  const handleSaveConversionRules = () => {
    saveConversionRules(conversionRules);
    setConversionSaved(true);
    setTimeout(() => setConversionSaved(false), 3000);
    alert('חוקי ההמרה נשמרו בהצלחה!\nהשינויים ייכנסו לתוקף בהמרות הבאות.');
  };

  const handleResetConversionRules = () => {
    if (confirm('האם אתה בטוח שברצונך לאפס את כל החוקים לברירת המחדל?')) {
      setConversionRules([...DEFAULT_RULES]);
      clearConversionRules();
      alert('החוקים אופסו לברירת המחדל');
    }
  };

  const updateConversionRule = (
    index: number,
    field: keyof ComponentConversionRule,
    value: any
  ) => {
    const newRules = [...conversionRules];
    (newRules[index] as any)[field] = value;
    setConversionRules(newRules);
  };

  // Pension Ceilings handlers
  const loadPensionCeilings = () => {
    const ceilings = loadPensionCeilingsFromStorage();
    setPensionCeilings(ceilings);
  };

  const handleEditCeilings = () => {
    setEditedCeilings([...pensionCeilings]);
    setIsEditingCeilings(true);
  };

  const handleSaveCeilings = () => {
    setPensionCeilings([...editedCeilings]);
    savePensionCeilingsToStorage(editedCeilings);
    setIsEditingCeilings(false);
    alert('תקרות הקצבה המזכה נשמרו בהצלחה!');
  };

  const handleCancelCeilings = () => {
    setEditedCeilings([]);
    setIsEditingCeilings(false);
  };

  const handleCeilingChange = (
    index: number,
    field: keyof PensionCeiling,
    value: any
  ) => {
    const updated = [...editedCeilings];
    updated[index] = {
      ...updated[index],
      [field]:
        field === 'year'
          ? parseInt(value, 10)
          : field === 'monthly_ceiling'
          ? parseFloat(value)
          : value,
    };
    setEditedCeilings(updated);
  };

  const handleAddCeiling = () => {
    const currentYear = new Date().getFullYear();
    const newCeiling: PensionCeiling = {
      year: currentYear + 1,
      monthly_ceiling: 9430,
      description: `תקרת קצבה מזכה לשנת ${currentYear + 1}`,
    };
    setEditedCeilings([newCeiling, ...editedCeilings]);
  };

  // Exempt Capital Percentages handlers
  const loadExemptCapitalPercentages = () => {
    const percentages = loadExemptCapitalPercentagesFromStorage();
    setExemptCapitalPercentages(percentages);
  };

  const loadIdfPromoterTable = () => {
    const rows = loadIdfPromoterTableFromStorage();
    setIdfPromoterTable(rows);
  };

  const handleEditPercentages = () => {
    setEditedPercentages([...exemptCapitalPercentages]);
    setIsEditingPercentages(true);
  };

  const handleSavePercentages = () => {
    setExemptCapitalPercentages([...editedPercentages]);
    saveExemptCapitalPercentagesToStorage(editedPercentages);
    setIsEditingPercentages(false);
    alert('אחוזי ההון הפטור נשמרו בהצלחה!');
  };

  const handleCancelPercentages = () => {
    setEditedPercentages([]);
    setIsEditingPercentages(false);
  };

  const handlePercentageChange = (
    index: number,
    field: keyof ExemptCapitalPercentage,
    value: any
  ) => {
    const updated = [...editedPercentages];
    updated[index] = {
      ...updated[index],
      [field]:
        field === 'year'
          ? parseInt(value, 10)
          : field === 'percentage'
          ? parseFloat(value)
          : value,
    };
    setEditedPercentages(updated);
  };

  const handleAddPercentage = () => {
    const currentYear = new Date().getFullYear();
    const defaultPercentage = currentYear + 1 >= 2028 ? 67 : 57;
    const newPercentage: ExemptCapitalPercentage = {
      year: currentYear + 1,
      percentage: defaultPercentage,
      description: `אחוז הון פטור לשנת ${currentYear + 1}`,
    };
    setEditedPercentages([newPercentage, ...editedPercentages]);
  };

  const handleEditIdfPromoterTable = () => {
    setEditedIdfPromoterTable([...idfPromoterTable]);
    setIsEditingIdfPromoterTable(true);
  };

  const handleSaveIdfPromoterTable = () => {
    setIdfPromoterTable([...editedIdfPromoterTable]);
    saveIdfPromoterTableToStorage(editedIdfPromoterTable);
    setIsEditingIdfPromoterTable(false);
    alert('טבלת גיל מקדם לפורשי צה"ל נשמרה בהצלחה!');
  };

  const handleCancelIdfPromoterTable = () => {
    setEditedIdfPromoterTable([]);
    setIsEditingIdfPromoterTable(false);
  };

  const handleIdfPromoterRowChange = (
    index: number,
    field: keyof IdfPromoterRow,
    value: any
  ) => {
    const updated = [...editedIdfPromoterTable];
    updated[index] = {
      ...updated[index],
      [field]:
        field === 'age_at_commutation' ||
        field === 'promoter_age_years' ||
        field === 'promoter_age_months'
          ? parseFloat(value)
          : value,
    };
    setEditedIdfPromoterTable(updated);
  };

  const handleAddIdfPromoterRow = () => {
    const newRow: IdfPromoterRow = {
      gender: 'male',
      age_at_commutation: 50,
      promoter_age_years: 70,
      promoter_age_months: 0,
      description: '',
    };
    setEditedIdfPromoterTable([newRow, ...editedIdfPromoterTable]);
  };

  // Retirement age handlers
  const handleSaveRetirement = () => {
    saveMaleRetirementAgeToStorage(maleRetirementAge);
    setRetirementSaved(true);
    setTimeout(() => setRetirementSaved(false), 3000);
    alert('הגדרות גיל פרישה נשמרו בהצלחה!');
  };

  return {
    activeTab,
    setActiveTab,
    taxBrackets,
    isEditing,
    editedBrackets,
    handleEdit,
    handleSave,
    handleCancel,
    handleBracketChange,
    severanceCaps,
    isEditingCaps,
    editedCaps,
    capsLoading,
    capsError,
    handleEditCaps,
    handleSaveCaps,
    handleCancelCaps,
    handleCapChange,
    handleAddCap,
    conversionRules,
    conversionSaved,
    handleSaveConversionRules,
    handleResetConversionRules,
    updateConversionRule,
    pensionCeilings,
    isEditingCeilings,
    editedCeilings,
    exemptCapitalPercentages,
    isEditingPercentages,
    editedPercentages,
    handleEditCeilings,
    handleSaveCeilings,
    handleCancelCeilings,
    handleCeilingChange,
    handleAddCeiling,
    handleEditPercentages,
    handleSavePercentages,
    handleCancelPercentages,
    handlePercentageChange,
    handleAddPercentage,
    idfPromoterTable,
    isEditingIdfPromoterTable,
    editedIdfPromoterTable,
    handleEditIdfPromoterTable,
    handleSaveIdfPromoterTable,
    handleCancelIdfPromoterTable,
    handleIdfPromoterRowChange,
    handleAddIdfPromoterRow,
    maleRetirementAge,
    setMaleRetirementAge,
    retirementSaved,
    handleSaveRetirement,
    formatCurrency,
  };
};
