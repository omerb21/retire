import { apiFetch } from '../../../lib/api';

/**
 * שירות לחישוב תאריך פרישה עבור לקוח על בסיס נתוני הלקוח
 */
export async function calculateRetirementDateForClient(clientData: any): Promise<string | null> {
  if (!clientData?.birth_date) return null;

  try {
    const response: any = await apiFetch('/retirement-age/calculate-simple', {
      method: 'POST',
      body: JSON.stringify({
        birth_date: clientData.birth_date,
        gender: clientData.gender,
      }),
    });

    if (response && response.retirement_date) {
      return response.retirement_date;
    }

    const birthDate = new Date(clientData.birth_date);
    const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 65 : 67;
    const retirementDate = new Date(birthDate);
    retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
    return retirementDate.toISOString().split('T')[0];
  } catch (error) {
    console.error('Error calculating retirement date:', error);
    const birthDate = new Date(clientData.birth_date);
    const retirementAge = clientData.gender?.toLowerCase() === 'female' ? 65 : 67;
    const retirementDate = new Date(birthDate);
    retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
    return retirementDate.toISOString().split('T')[0];
  }
}
