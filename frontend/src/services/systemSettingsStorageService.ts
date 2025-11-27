import { PensionCeiling, ExemptCapitalPercentage, SeveranceCap, IdfPromoterRow } from '../types/system-settings.types';
import { getDefaultSeveranceCaps } from './systemSettingsService';

export const loadPensionCeilingsFromStorage = (): PensionCeiling[] => {
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

      localStorage.setItem('pensionCeilings', JSON.stringify(merged));
      return merged;
    } catch (e) {
      console.error('Error parsing pensionCeilings from localStorage, using defaults instead', e);
    }
  }

  localStorage.setItem('pensionCeilings', JSON.stringify(defaultCeilings));
  return defaultCeilings;
};

export const savePensionCeilingsToStorage = (ceilings: PensionCeiling[]): void => {
  localStorage.setItem('pensionCeilings', JSON.stringify(ceilings));
};

export const loadExemptCapitalPercentagesFromStorage = (): ExemptCapitalPercentage[] => {
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
      const savedData: ExemptCapitalPercentage[] = JSON.parse(saved);
      const year2025 = savedData.find((item) => item.year === 2025);

      if (year2025 && year2025.percentage === 57) {
        return savedData;
      }
    } catch (e) {
      console.error('Error parsing saved percentages:', e);
    }
  }

  localStorage.setItem('exemptCapitalPercentages', JSON.stringify(defaultPercentages));
  return defaultPercentages;
};

export const saveExemptCapitalPercentagesToStorage = (
  percentages: ExemptCapitalPercentage[],
): void => {
  localStorage.setItem('exemptCapitalPercentages', JSON.stringify(percentages));
};

export const saveMaleRetirementAgeToStorage = (age: number): void => {
  localStorage.setItem('maleRetirementAge', age.toString());
};

export const loadSeveranceCapsFromStorage = (): SeveranceCap[] => {
  const saved = localStorage.getItem('severanceCaps');

  if (saved) {
    try {
      const parsed: SeveranceCap[] = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    } catch (e) {
      console.error('Error parsing severanceCaps from localStorage, using defaults instead', e);
    }
  }

  const defaultCaps = getDefaultSeveranceCaps();
  localStorage.setItem('severanceCaps', JSON.stringify(defaultCaps));
  return defaultCaps;
};

export const saveSeveranceCapsToStorage = (caps: SeveranceCap[]): void => {
  localStorage.setItem('severanceCaps', JSON.stringify(caps));
};

export const loadIdfPromoterTableFromStorage = (): IdfPromoterRow[] => {
  const defaultTable: IdfPromoterRow[] = [
    // לוח 1 - גברים
    { gender: 'male', age_at_commutation: 40.0, promoter_age_years: 71, promoter_age_months: 6 },
    { gender: 'male', age_at_commutation: 40.5, promoter_age_years: 71, promoter_age_months: 7 },
    { gender: 'male', age_at_commutation: 41.0, promoter_age_years: 71, promoter_age_months: 8 },
    { gender: 'male', age_at_commutation: 41.5, promoter_age_years: 71, promoter_age_months: 9 },
    { gender: 'male', age_at_commutation: 42.0, promoter_age_years: 71, promoter_age_months: 10 },
    { gender: 'male', age_at_commutation: 42.5, promoter_age_years: 71, promoter_age_months: 11 },
    { gender: 'male', age_at_commutation: 43.0, promoter_age_years: 72, promoter_age_months: 0 },
    { gender: 'male', age_at_commutation: 43.5, promoter_age_years: 72, promoter_age_months: 1 },
    { gender: 'male', age_at_commutation: 44.0, promoter_age_years: 72, promoter_age_months: 2 },
    { gender: 'male', age_at_commutation: 44.5, promoter_age_years: 72, promoter_age_months: 4 },
    { gender: 'male', age_at_commutation: 45.0, promoter_age_years: 72, promoter_age_months: 5 },
    { gender: 'male', age_at_commutation: 45.5, promoter_age_years: 72, promoter_age_months: 6 },
    { gender: 'male', age_at_commutation: 46.0, promoter_age_years: 72, promoter_age_months: 7 },
    { gender: 'male', age_at_commutation: 46.5, promoter_age_years: 72, promoter_age_months: 9 },
    { gender: 'male', age_at_commutation: 47.0, promoter_age_years: 72, promoter_age_months: 9 },
    { gender: 'male', age_at_commutation: 47.5, promoter_age_years: 73, promoter_age_months: 1 },
    { gender: 'male', age_at_commutation: 48.0, promoter_age_years: 73, promoter_age_months: 0 },
    { gender: 'male', age_at_commutation: 48.5, promoter_age_years: 73, promoter_age_months: 1 },
    { gender: 'male', age_at_commutation: 49.0, promoter_age_years: 73, promoter_age_months: 3 },
    { gender: 'male', age_at_commutation: 49.5, promoter_age_years: 73, promoter_age_months: 4 },
    { gender: 'male', age_at_commutation: 50.0, promoter_age_years: 73, promoter_age_months: 5 },
    { gender: 'male', age_at_commutation: 50.5, promoter_age_years: 73, promoter_age_months: 7 },
    { gender: 'male', age_at_commutation: 51.0, promoter_age_years: 73, promoter_age_months: 8 },
    { gender: 'male', age_at_commutation: 51.5, promoter_age_years: 73, promoter_age_months: 10 },
    { gender: 'male', age_at_commutation: 52.0, promoter_age_years: 73, promoter_age_months: 11 },
    { gender: 'male', age_at_commutation: 52.5, promoter_age_years: 74, promoter_age_months: 1 },
    { gender: 'male', age_at_commutation: 53.0, promoter_age_years: 74, promoter_age_months: 2 },
    { gender: 'male', age_at_commutation: 53.5, promoter_age_years: 74, promoter_age_months: 4 },
    { gender: 'male', age_at_commutation: 54.0, promoter_age_years: 74, promoter_age_months: 5 },
    { gender: 'male', age_at_commutation: 54.5, promoter_age_years: 74, promoter_age_months: 7 },
    { gender: 'male', age_at_commutation: 55.0, promoter_age_years: 74, promoter_age_months: 9 },
    { gender: 'male', age_at_commutation: 55.5, promoter_age_years: 74, promoter_age_months: 10 },
    { gender: 'male', age_at_commutation: 56.0, promoter_age_years: 75, promoter_age_months: 0 },
    { gender: 'male', age_at_commutation: 56.5, promoter_age_years: 75, promoter_age_months: 2 },
    { gender: 'male', age_at_commutation: 57.0, promoter_age_years: 75, promoter_age_months: 4 },
    { gender: 'male', age_at_commutation: 57.5, promoter_age_years: 75, promoter_age_months: 5 },
    { gender: 'male', age_at_commutation: 58.0, promoter_age_years: 75, promoter_age_months: 7 },
    { gender: 'male', age_at_commutation: 58.5, promoter_age_years: 75, promoter_age_months: 9 },
    { gender: 'male', age_at_commutation: 59.0, promoter_age_years: 75, promoter_age_months: 11 },
    { gender: 'male', age_at_commutation: 59.5, promoter_age_years: 76, promoter_age_months: 1 },
    { gender: 'male', age_at_commutation: 60.0, promoter_age_years: 76, promoter_age_months: 3 },

    // לוח 2 - נשים
    { gender: 'female', age_at_commutation: 40.0, promoter_age_years: 75, promoter_age_months: 4 },
    { gender: 'female', age_at_commutation: 40.5, promoter_age_years: 75, promoter_age_months: 5 },
    { gender: 'female', age_at_commutation: 41.0, promoter_age_years: 75, promoter_age_months: 6 },
    { gender: 'female', age_at_commutation: 41.5, promoter_age_years: 75, promoter_age_months: 7 },
    { gender: 'female', age_at_commutation: 42.0, promoter_age_years: 75, promoter_age_months: 8 },
    { gender: 'female', age_at_commutation: 42.5, promoter_age_years: 75, promoter_age_months: 9 },
    { gender: 'female', age_at_commutation: 43.0, promoter_age_years: 75, promoter_age_months: 10 },
    { gender: 'female', age_at_commutation: 43.5, promoter_age_years: 75, promoter_age_months: 11 },
    { gender: 'female', age_at_commutation: 44.0, promoter_age_years: 76, promoter_age_months: 1 },
    { gender: 'female', age_at_commutation: 44.5, promoter_age_years: 76, promoter_age_months: 2 },
    { gender: 'female', age_at_commutation: 45.0, promoter_age_years: 76, promoter_age_months: 3 },
    { gender: 'female', age_at_commutation: 45.5, promoter_age_years: 76, promoter_age_months: 4 },
    { gender: 'female', age_at_commutation: 46.0, promoter_age_years: 76, promoter_age_months: 5 },
    { gender: 'female', age_at_commutation: 46.5, promoter_age_years: 76, promoter_age_months: 6 },
    { gender: 'female', age_at_commutation: 47.0, promoter_age_years: 76, promoter_age_months: 7 },
    { gender: 'female', age_at_commutation: 47.5, promoter_age_years: 76, promoter_age_months: 8 },
    { gender: 'female', age_at_commutation: 48.0, promoter_age_years: 76, promoter_age_months: 10 },
    { gender: 'female', age_at_commutation: 48.5, promoter_age_years: 76, promoter_age_months: 11 },
    { gender: 'female', age_at_commutation: 49.0, promoter_age_years: 77, promoter_age_months: 0 },
    { gender: 'female', age_at_commutation: 49.5, promoter_age_years: 77, promoter_age_months: 1 },
    { gender: 'female', age_at_commutation: 50.0, promoter_age_years: 77, promoter_age_months: 2 },
    { gender: 'female', age_at_commutation: 50.5, promoter_age_years: 77, promoter_age_months: 4 },
    { gender: 'female', age_at_commutation: 51.0, promoter_age_years: 77, promoter_age_months: 5 },
    { gender: 'female', age_at_commutation: 51.5, promoter_age_years: 77, promoter_age_months: 6 },
    { gender: 'female', age_at_commutation: 52.0, promoter_age_years: 77, promoter_age_months: 8 },
    { gender: 'female', age_at_commutation: 52.5, promoter_age_years: 77, promoter_age_months: 9 },
    { gender: 'female', age_at_commutation: 53.0, promoter_age_years: 77, promoter_age_months: 10 },
    { gender: 'female', age_at_commutation: 53.5, promoter_age_years: 77, promoter_age_months: 11 },
    { gender: 'female', age_at_commutation: 54.0, promoter_age_years: 78, promoter_age_months: 1 },
    { gender: 'female', age_at_commutation: 54.5, promoter_age_years: 78, promoter_age_months: 2 },
    { gender: 'female', age_at_commutation: 55.0, promoter_age_years: 78, promoter_age_months: 4 },
    { gender: 'female', age_at_commutation: 55.5, promoter_age_years: 78, promoter_age_months: 5 },
    { gender: 'female', age_at_commutation: 56.0, promoter_age_years: 78, promoter_age_months: 6 },
    { gender: 'female', age_at_commutation: 56.5, promoter_age_years: 78, promoter_age_months: 8 },
    { gender: 'female', age_at_commutation: 57.0, promoter_age_years: 78, promoter_age_months: 9 },
    { gender: 'female', age_at_commutation: 57.5, promoter_age_years: 78, promoter_age_months: 11 },
    { gender: 'female', age_at_commutation: 58.0, promoter_age_years: 79, promoter_age_months: 0 },
    { gender: 'female', age_at_commutation: 58.5, promoter_age_years: 79, promoter_age_months: 1 },
    { gender: 'female', age_at_commutation: 59.0, promoter_age_years: 79, promoter_age_months: 3 },
    { gender: 'female', age_at_commutation: 59.5, promoter_age_years: 79, promoter_age_months: 5 },
    { gender: 'female', age_at_commutation: 60.0, promoter_age_years: 79, promoter_age_months: 6 },
  ];

  const saved = localStorage.getItem('idfPromoterTable');

  if (saved) {
    try {
      const parsed: IdfPromoterRow[] = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    } catch (e) {
      console.error(
        'Error parsing idfPromoterTable from localStorage, using default table instead',
        e
      );
    }
  }

  localStorage.setItem('idfPromoterTable', JSON.stringify(defaultTable));
  return defaultTable;
};

export const saveIdfPromoterTableToStorage = (rows: IdfPromoterRow[]): void => {
  localStorage.setItem('idfPromoterTable', JSON.stringify(rows));
};
