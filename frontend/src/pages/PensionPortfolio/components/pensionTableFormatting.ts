import { formatCurrency } from '../../../lib/validation';

export function formatMoney(value: number | string | null | undefined): string {
  const numeric = Number(value) || 0;
  const formatted = formatCurrency(numeric);
  return formatted.replace('₪', '').trim();
}
