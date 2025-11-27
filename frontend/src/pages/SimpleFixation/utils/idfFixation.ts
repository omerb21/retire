import { IdfPromoterRow } from '../../../types/system-settings.types';
import { loadIdfPromoterTableFromStorage } from '../../../services/systemSettingsStorageService';

interface PromoterAgeInput {
  birthDateIso?: string | null;
  gender?: string | null;
  commutationDateIso?: string | null;
}

const isValidIsoDate = (value: string | null | undefined): value is string => {
  if (!value) return false;
  const d = new Date(value);
  return !isNaN(d.getTime());
};

const calculateAgeAtDate = (birth: Date, ref: Date): number => {
  let age = ref.getFullYear() - birth.getFullYear();
  const m = ref.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && ref.getDate() < birth.getDate())) {
    age -= 1;
  }
  return age;
};

const addYearsAndMonths = (birth: Date, years: number, months: number): Date => {
  const totalMonths = birth.getMonth() + months + years * 12;
  const year = birth.getFullYear() + Math.floor(totalMonths / 12);
  const month = totalMonths % 12;
  const day = birth.getDate();
  return new Date(year, month, day);
};

export const calculatePromoterAgeDate = ({
  birthDateIso,
  gender,
  commutationDateIso,
}: PromoterAgeInput): string | null => {
  if (!birthDateIso || !gender || !commutationDateIso) {
    return null;
  }

  if (!isValidIsoDate(birthDateIso) || !isValidIsoDate(commutationDateIso)) {
    return null;
  }

  const birth = new Date(birthDateIso);
  const commutation = new Date(commutationDateIso);

  const table: IdfPromoterRow[] = loadIdfPromoterTableFromStorage();
  if (!Array.isArray(table) || table.length === 0) {
    return null;
  }

  const normalizedGender = (gender || '').toLowerCase() === 'female' ? 'female' : 'male';
  const ageAtCommutation = calculateAgeAtDate(birth, commutation);

  const row = table.find(
    (r) => r.gender === normalizedGender && r.age_at_commutation === ageAtCommutation
  );

  if (!row) {
    return null;
  }

  const promoterDate = addYearsAndMonths(birth, row.promoter_age_years, row.promoter_age_months);
  if (isNaN(promoterDate.getTime())) {
    return null;
  }

  return promoterDate.toISOString().slice(0, 10);
};
