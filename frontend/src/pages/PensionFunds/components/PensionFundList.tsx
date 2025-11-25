import React from 'react';
import { PensionFund } from '../types';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { calculateOriginalBalance } from '../utils';
import { formatCurrency } from '../../../lib/validation';

interface PensionFundListProps {
  funds: PensionFund[];
  onCompute: (fundId: number) => void;
  onEdit: (fund: PensionFund) => void;
  onDelete: (fundId: number) => void;
}

export const PensionFundList: React.FC<PensionFundListProps> = ({
  funds,
  onCompute,
  onEdit,
  onDelete
}) => {
  if (funds.length === 0) {
    return (
      <div className="pension-funds-empty-card">
        אין קצבאות
      </div>
    );
  }

  return (
    <div className="pension-funds-list-grid">
      {funds.map((fund, index) => (
        <div key={fund.id || index} className="pension-funds-card">
          <div className="pension-funds-card-grid">
            <div><strong>שם המשלם:</strong> {fund.fund_name || "קצבה"}</div>
            {fund.deduction_file && <div><strong>תיק ניכויים:</strong> {fund.deduction_file}</div>}
            <div><strong>מצב:</strong> {fund.input_mode === "calculated" ? "מחושב" : "ידני"}</div>
            
            {/* הצגת יתרה שעליה מבוססת הקצבה - תמיד */}
            <div className="pension-funds-balance-box">
              <strong>יתרה שעליה מבוססת הקצבה:</strong> {formatCurrency(calculateOriginalBalance(fund))}
            </div>
            
            {fund.input_mode === "calculated" && (
              <>
                {((fund.balance || 0) > 0 || (fund.current_balance || 0) > 0) && (
                  <div><strong>מקדם קצבה:</strong> {fund.annuity_factor}</div>
                )}
                {(fund.balance === 0 || fund.balance === undefined) && 
                 (fund.current_balance === 0 || fund.current_balance === undefined) && 
                 (fund.computed_monthly_amount || 0) > 0 && (
                  <div className="pension-funds-converted-message">
                    <strong>היתרה הומרה לקצבה חודשית</strong>
                  </div>
                )}
              </>
            )}
            
            <div><strong>תאריך תחילה:</strong> {fund.pension_start_date ? formatDateToDDMMYY(new Date(fund.pension_start_date)) : (fund.start_date ? formatDateToDDMMYY(new Date(fund.start_date)) : "לא צוין")}</div>
            <div><strong>הצמדה:</strong> {
              fund.indexation_method === "none" ? "ללא" :
              fund.indexation_method === "fixed" ? `קבועה ${fund.indexation_rate}%` :
              "למדד"
            }</div>
            <div><strong>יחס למס:</strong> {
              fund.tax_treatment === "exempt" ? "פטור ממס" :
              fund.tax_treatment === "capital_gains" ? "מס רווח הון" :
              "חייב במס"
            }</div>
            
            {/* הצגת סכום חודשי בכל מקרה - מודגש ובולט */}
            <div className="pension-funds-monthly-box">
              <strong>סכום חודשי:</strong> {formatCurrency(
                // השרת מחזיר את הסכום החודשי הנכון
                fund.monthly || fund.computed_monthly_amount || fund.pension_amount || fund.monthly_amount || 0
              )}
              {fund.annuity_factor && (
                <span className="pension-funds-annuity-factor-hint">
                  {' '}| <strong>מקדם קצבה:</strong> {fund.annuity_factor}
                </span>
              )}
            </div>
            
            <div className="pension-funds-actions-row">
              {/* כפתור חישוב - רק למצב מחושב עם יתרה */}
              {fund.id && (fund.input_mode === "calculated" || fund.calculation_mode === "calculated") && 
               ((fund.balance || 0) > 0 || (fund.current_balance || 0) > 0) && (
                <button
                  type="button"
                  onClick={() => onCompute(fund.id!)}
                  className="pension-funds-button-compute"
                >
                  חשב ושמור
                </button>
              )}
              
              {/* כפתור עריכה - תמיד מוצג */}
              <button
                type="button"
                onClick={() => onEdit(fund)}
                className="pension-funds-button-edit"
              >
                ערוך
              </button>
              
              {/* כפתור מחיקה - רק אם יש ID */}
              {fund.id && (
                <button
                  type="button"
                  onClick={() => onDelete(fund.id!)}
                  className="pension-funds-button-delete"
                >
                  מחק
                </button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
