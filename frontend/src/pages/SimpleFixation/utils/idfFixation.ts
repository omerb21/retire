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
  // גיל מלא + חצי שנה לפי מספר החודשים השלמים שעברו מאז יום ההולדת האחרון
  let totalMonths = (ref.getFullYear() - birth.getFullYear()) * 12 + (ref.getMonth() - birth.getMonth());

  // אם יום בחודש של התאריך הנוכחי קטן מיום ההולדת – החודש הנוכחי עוד לא הושלם
  if (ref.getDate() < birth.getDate()) {
    totalMonths -= 1;
  }

  if (totalMonths < 0) {
    return 0;
  }

  const fullYears = Math.floor(totalMonths / 12);
  const remainingMonths = totalMonths % 12;

  // פחות מ-6 חודשים → גיל שלם, 6 חודשים ומעלה → חצי שנה (n.5)
  return remainingMonths >= 6 ? fullYears + 0.5 : fullYears;
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
