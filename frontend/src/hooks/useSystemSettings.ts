import { useState } from 'react';
import { 
  TaxBracket, 
  SeveranceCap, 
  PensionCeiling, 
  ExemptCapitalPercentage 
} from '../types/system-settings.types';
import { formatCurrency as baseFormatCurrency } from '../lib/validation';
import { 
  loadSeveranceCapsFromAPI, 
  saveSeveranceCapsToAPI, 
  getDefaultSeveranceCaps 
} from '../services/systemSettingsService';
import {
  loadSeveranceCapsFromStorage,
  saveSeveranceCapsToStorage,
} from '../services/systemSettingsStorageService';

export const useSystemSettings = () => {
  // Tax brackets state
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

  // Severance caps state
  const [severanceCaps, setSeveranceCaps] = useState<SeveranceCap[]>([]);
  const [isEditingCaps, setIsEditingCaps] = useState(false);
  const [editedCaps, setEditedCaps] = useState<SeveranceCap[]>([]);
  const [capsLoading, setCapsLoading] = useState(false);
  const [capsError, setCapsError] = useState<string>("");

  // Pension ceilings state
  const [pensionCeilings, setPensionCeilings] = useState<PensionCeiling[]>([]);
  const [isEditingCeilings, setIsEditingCeilings] = useState(false);
  const [editedCeilings, setEditedCeilings] = useState<PensionCeiling[]>([]);

  // Exempt capital percentages state
  const [exemptCapitalPercentages, setExemptCapitalPercentages] = useState<ExemptCapitalPercentage[]>([]);
  const [isEditingPercentages, setIsEditingPercentages] = useState(false);
  const [editedPercentages, setEditedPercentages] = useState<ExemptCapitalPercentage[]>([]);

  // Load severance caps
  const loadSeveranceCaps = async () => {
    setCapsLoading(true);
    setCapsError("");
    
    try {
      try {
        const caps = await loadSeveranceCapsFromAPI();
        setSeveranceCaps(caps);
        saveSeveranceCapsToStorage(caps);
        return;
      } catch (apiError) {
        console.log("API error, falling back to local data:", apiError);
      }

      const storedCaps = loadSeveranceCapsFromStorage();
      setSeveranceCaps(storedCaps);
    } catch (e: any) {
      console.error("Error loading severance caps:", e);
      setCapsError(`שגיאה בטעינת תקרות פיצויים: ${e?.message || e}`);
    } finally {
      setCapsLoading(false);
    }
  };

  // Save severance caps
  const saveSeveranceCaps = async (caps: SeveranceCap[]) => {
    try {
      await saveSeveranceCapsToAPI(caps);
      setSeveranceCaps([...caps]);
      saveSeveranceCapsToStorage(caps);
      setIsEditingCaps(false);
      return true;
    } catch (e: any) {
      console.error("Error saving severance caps:", e);
      throw new Error(`שגיאה בשמירת תקרות פיצויים: ${e?.message || e}`);
    }
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    if (amount === Infinity) return 'ומעלה';
    return baseFormatCurrency(amount);
  };

  return {
    // Tax brackets
    taxBrackets,
    setTaxBrackets,
    isEditing,
    setIsEditing,
    editedBrackets,
    setEditedBrackets,
    
    // Severance caps
    severanceCaps,
    setSeveranceCaps,
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
    
    // Utilities
    formatCurrency,
  };
};
