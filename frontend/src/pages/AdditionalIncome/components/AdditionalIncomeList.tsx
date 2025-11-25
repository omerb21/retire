import React from 'react';
import { formatCurrency } from '../../../lib/validation';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { AdditionalIncome } from '../hooks/useAdditionalIncome';

const INCOME_TYPE_MAP: Record<string, string> = {
  rental: 'שכירות',
  dividends: 'דיבידנדים',
  interest: 'ריבית',
  business: 'עסק',
  salary: 'שכיר',
  other: 'אחר',
};

interface AdditionalIncomeListProps {
  incomes: AdditionalIncome[];
  onEdit: (income: AdditionalIncome) => void;
  onDelete: (id: number) => void;
}

export const AdditionalIncomeList: React.FC<AdditionalIncomeListProps> = ({
  incomes,
  onEdit,
  onDelete,
}) => {
  if (incomes.length === 0) {
    return (
      <section>
        <h3>רשימת הכנסות נוספות</h3>
        <div className="additional-income-empty">אין הכנסות נוספות</div>
      </section>
    );
  }

  return (
    <section>
      <h3>רשימת הכנסות נוספות</h3>
      <div className="additional-income-list">
        {incomes.map((income, index) => (
          <div key={income.id || index} className="additional-income-card">
            <div className="additional-income-card-content">
              <div>
                <strong>סוג:</strong>{' '}
                {INCOME_TYPE_MAP[income.source_type] || income.source_type}
              </div>
              <div>
                <strong>שם הכנסה:</strong> {income.description || ''}
              </div>
              <div>
                <strong>סכום:</strong>{' '}
                {income.amount != null ? formatCurrency(income.amount) : ''}
              </div>
              <div>
                <strong>תדירות:</strong>{' '}
                {income.frequency === 'monthly'
                  ? 'חודשי'
                  : income.frequency === 'annually'
                  ? 'שנתי'
                  : 'לא ידוע'}
              </div>
              <div>
                <strong>תאריך התחלה:</strong>{' '}
                {formatDateToDDMMYY(new Date(income.start_date))}
              </div>
              {income.end_date && (
                <div>
                  <strong>תאריך סיום:</strong>{' '}
                  {formatDateToDDMMYY(new Date(income.end_date))}
                </div>
              )}
              <div>
                <strong>הצמדה:</strong>{' '}
                {income.indexation_method === 'none'
                  ? 'ללא'
                  : income.indexation_method === 'fixed'
                  ? `קבועה ${income.fixed_rate}%`
                  : 'למדד'}
              </div>
              <div>
                <strong>יחס מס:</strong>{' '}
                {income.tax_treatment === 'exempt'
                  ? 'פטור ממס'
                  : income.tax_treatment === 'taxable'
                  ? 'חייב במס'
                  : `שיעור קבוע ${income.tax_rate}%`}
              </div>

              {income.computed_monthly_amount && (
                <div className="additional-income-computed">
                  <strong>סכום חודשי מחושב:</strong>{' '}
                  {formatCurrency(income.computed_monthly_amount)}
                </div>
              )}

              <div className="additional-income-card-actions">
                {income.id && (
                  <button
                    type="button"
                    onClick={() => onEdit(income)}
                    className="additional-income-card-button additional-income-card-button--edit"
                  >
                    ערוך
                  </button>
                )}

                {income.id && (
                  <button
                    type="button"
                    onClick={() => onDelete(income.id!)}
                    className="additional-income-card-button additional-income-card-button--delete"
                  >
                    מחק
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
