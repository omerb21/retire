/**
 * חישובי קצבה ופטורים ממס
 */

/**
 * מחזיר את תקרת הקצבה הפטורה לפי שנה
 * @param year שנה
 * @returns תקרת קצבה חודשית פטורה
 */
export function getPensionCeiling(year: number): number {
  const ceilings: { [key: number]: number } = {
    2025: 9430, 2024: 9430, 2023: 9120, 2022: 8660,
    2021: 8460, 2020: 8510, 2019: 8480, 2018: 8380
  };
  return ceilings[year] || 9430;
}

/**
 * מחזיר את אחוז ההון הפטור ממס לפי שנה
 * @param year שנה
 * @returns אחוז פטור (0-1)
 */
export function getExemptCapitalPercentage(year: number): number {
  const percentages: { [key: number]: number } = {
    2028: 0.67, 2027: 0.625, 2026: 0.575, 2025: 0.57,
    2024: 0.52, 2023: 0.52, 2022: 0.52, 2021: 0.52, 2020: 0.52,
    2019: 0.49, 2018: 0.49, 2017: 0.49, 2016: 0.49,
    2015: 0.435, 2014: 0.435, 2013: 0.435, 2012: 0.435
  };
  return percentages[year] || 0.67;
}
