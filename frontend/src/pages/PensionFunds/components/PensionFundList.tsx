import React from 'react';
import { PensionFund } from '../types';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { calculateOriginalBalance } from '../utils';

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
      <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
        אין קצבאות
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {funds.map((fund, index) => (
        <div key={fund.id || index} style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4 }}>
          <div style={{ display: "grid", gap: 8 }}>
            <div><strong>שם המשלם:</strong> {fund.fund_name || "קצבה"}</div>
            {fund.deduction_file && <div><strong>תיק ניכויים:</strong> {fund.deduction_file}</div>}
            <div><strong>מצב:</strong> {fund.input_mode === "calculated" ? "מחושב" : "ידני"}</div>
            
            {/* הצגת יתרה שעליה מבוססת הקצבה - תמיד */}
            <div style={{ 
              backgroundColor: "#fff3cd", 
              padding: "8px", 
              borderRadius: "4px", 
              border: "1px solid #ffc107",
              marginTop: "8px",
              marginBottom: "8px",
              fontSize: "1.05em"
            }}>
              <strong>יתרה שעליה מבוססת הקצבה:</strong> ₪{calculateOriginalBalance(fund).toLocaleString()}
            </div>
            
            {fund.input_mode === "calculated" && (
              <>
                {((fund.balance || 0) > 0 || (fund.current_balance || 0) > 0) && (
                  <div><strong>מקדם קצבה:</strong> {fund.annuity_factor}</div>
                )}
                {(fund.balance === 0 || fund.balance === undefined) && 
                 (fund.current_balance === 0 || fund.current_balance === undefined) && 
                 (fund.computed_monthly_amount || 0) > 0 && (
                  <div style={{ color: "green", fontWeight: "bold" }}>
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
            <div style={{ 
              color: "green", 
              fontWeight: "bold", 
              backgroundColor: "#f0fff0", 
              padding: "12px", 
              borderRadius: "4px", 
              border: "1px solid #28a745",
              marginTop: "10px",
              marginBottom: "10px",
              fontSize: "1.1em"
            }}>
              <strong>סכום חודשי:</strong> ₪{(
                // השרת מחזיר את הסכום החודשי הנכון
                fund.monthly || fund.computed_monthly_amount || fund.pension_amount || fund.monthly_amount || 0
              ).toLocaleString()}
              {fund.annuity_factor && (
                <span style={{ marginRight: "15px", fontSize: "0.9em", color: "#155724" }}>
                  {' '}| <strong>מקדם קצבה:</strong> {fund.annuity_factor}
                </span>
              )}
            </div>
            
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              {/* כפתור חישוב - רק למצב מחושב עם יתרה */}
              {fund.id && (fund.input_mode === "calculated" || fund.calculation_mode === "calculated") && 
               ((fund.balance || 0) > 0 || (fund.current_balance || 0) > 0) && (
                <button
                  type="button"
                  onClick={() => onCompute(fund.id!)}
                  style={{ padding: "8px 12px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: 4 }}
                >
                  חשב ושמור
                </button>
              )}
              
              {/* כפתור עריכה - תמיד מוצג */}
              <button
                type="button"
                onClick={() => onEdit(fund)}
                style={{ padding: "8px 12px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}
              >
                ערוך
              </button>
              
              {/* כפתור מחיקה - רק אם יש ID */}
              {fund.id && (
                <button
                  type="button"
                  onClick={() => onDelete(fund.id!)}
                  style={{ padding: "8px 12px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: 4 }}
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
