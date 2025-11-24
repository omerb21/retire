/**
 * Termination Steps Component - All termination workflow steps
 */

import React from 'react';
import { SimpleEmployer, TerminationDecision } from '../types';
import { convertDDMMYYToISO } from '../../../utils/dateUtils';
import { calculateServiceYears } from '../utils/calculations';
import { formatCurrency } from '../../../lib/validation';

interface TerminationStepsProps {
  employer: SimpleEmployer;
  terminationDecision: TerminationDecision;
  setTerminationDecision: React.Dispatch<React.SetStateAction<TerminationDecision>>;
  loading: boolean;
  onSubmit: () => Promise<void>;
  onDelete: () => Promise<void>;
  onCancel: () => void;
}

export const TerminationSteps: React.FC<TerminationStepsProps> = ({
  employer,
  terminationDecision,
  setTerminationDecision,
  loading,
  onSubmit,
  onDelete,
  onCancel
}) => {
  // Step 1: End date display
  const renderStep1 = () => (
    <div className="termination-step termination-step--green">
      <h4 className="termination-step-header">שלב 1: תאריך סיום עבודה</h4>
      <div className="termination-step-enddate-box">
        <p className="termination-step-enddate-text">
          תאריך סיום עבודה: <strong>{employer.end_date || 'לא הוזן'}</strong>
        </p>
        {!employer.end_date && (
          <p className="termination-warning-secondary">
            יש להזין תאריך סיום עבודה בטאב "פרטי מעסיק" לפני המשך התהליך
          </p>
        )}
      </div>
    </div>
  );

  // Step 2: Rights summary
  const renderStep2 = () => {
    if (!terminationDecision.termination_date || !employer.start_date) return null;

    const serviceYears = calculateServiceYears(employer.start_date, terminationDecision.termination_date);
    const expectedFromSalary = Math.round(employer.last_salary * serviceYears);
    const expectedGrant = Math.max(expectedFromSalary, employer.severance_accrued);

    return (
      <div className="termination-step termination-step--green">
        <h4 className="termination-step-header">שלב 2: סיכום זכויות</h4>
        <div className="termination-summary-grid">
          <div><strong>שנות וותק:</strong> {serviceYears.toFixed(2)} שנים</div>
          <div><strong>פיצויים צבורים:</strong> {formatCurrency(employer.severance_accrued)}</div>
          <div><strong>פיצויים צפויים:</strong> {formatCurrency(expectedGrant)}</div>
        </div>
      </div>
    );
  };

  // Step 3: Employer completion
  const renderStep3 = () => {
    if (!terminationDecision.termination_date || !employer.start_date) return null;

    const serviceYears = calculateServiceYears(employer.start_date, terminationDecision.termination_date);
    const expectedGrant = Math.round(employer.last_salary * serviceYears);
    const completion = Math.max(0, expectedGrant - employer.severance_accrued);

    return (
      <div className="termination-step termination-step--yellow">
        <h4 className="termination-step-header">שלב 3: השלמת מעסיק</h4>
        <label
          className={`termination-checkbox-label ${terminationDecision.confirmed ? 'termination-checkbox-label--disabled' : ''}`}
        >
          <input
            type="checkbox"
            checked={terminationDecision.use_employer_completion}
            onChange={(e) => setTerminationDecision(prev => ({ ...prev, use_employer_completion: e.target.checked }))}
            disabled={terminationDecision.confirmed}
            className="termination-checkbox-input"
          />
          תבוצע השלמת מעסיק
        </label>
        {terminationDecision.use_employer_completion && (
          <div className="termination-completion-box">
            <p><strong>גובה השלמת המעסיק:</strong> {formatCurrency(completion)}</p>
            <small>ההפרש בין המענק הצפוי ליתרת הפיצויים הנצברת</small>
          </div>
        )}
      </div>
    );
  };

  // Step 4: Tax split
  const renderStep4 = () => {
    if (!terminationDecision.termination_date) return null;

    let endISO = terminationDecision.termination_date.includes('/') 
      ? convertDDMMYYToISO(terminationDecision.termination_date) 
      : terminationDecision.termination_date;

    return (
      <div className="termination-step termination-step--info">
        <h4 className="termination-step-header">שלב 4: חלוקה לפטור/חייב במס</h4>
        
        <div className="termination-tax-info-box">
          <strong>🔍 פרטי חישוב:</strong>
          <div>תאריך עזיבה מקורי: <strong>{terminationDecision.termination_date}</strong></div>
          <div>שנת עזיבה מחושבת: <strong>{new Date(endISO || '').getFullYear()}</strong></div>
          <div>סכום פיצויים: <strong>{formatCurrency(terminationDecision.severance_amount || 0)}</strong></div>
        </div>
        
        <div className="termination-tax-grid">
          <div className="termination-tax-exempt-card">
            <strong className="termination-tax-exempt-title">חלק פטור ממס:</strong>
            <p className="termination-tax-amount">{formatCurrency(terminationDecision.exempt_amount || 0)}</p>
          </div>
          <div className="termination-tax-taxable-card">
            <strong className="termination-tax-taxable-title">חלק חייב במס:</strong>
            <p className="termination-tax-amount">{formatCurrency(terminationDecision.taxable_amount || 0)}</p>
          </div>
        </div>
      </div>
    );
  };

  // Step 5a: Exempt choice
  const renderStep5a = () => {
    if ((terminationDecision.exempt_amount || 0) <= 0) return null;

    return (
      <div className="termination-step termination-step--green termination-choice-group">
        <h4 className="termination-step-header">שלב 5א: בחירת אפשרות לחלק הפטור ממס</h4>
        {['redeem_with_exemption', 'redeem_no_exemption', 'annuity'].map(choice => (
          <label
            key={choice}
            className={`termination-radio-label ${terminationDecision.confirmed ? 'termination-radio-label--disabled' : ''}`}
          >
            <input
              type="radio"
              value={choice}
              checked={terminationDecision.exempt_choice === choice}
              onChange={(e) => setTerminationDecision(prev => ({ ...prev, exempt_choice: e.target.value as any }))}
              disabled={terminationDecision.confirmed}
              className="termination-radio-input"
            />
            {choice === 'redeem_with_exemption' ? 'פדיון הסכום עם שימוש בפטור' :
             choice === 'redeem_no_exemption' ? 'פדיון הסכום ללא שימוש בפטור (עם פריסת מס)' : 'סימון כקצבה'}
          </label>
        ))}
        
        {terminationDecision.exempt_choice === 'redeem_no_exemption' && (terminationDecision.max_spread_years || 0) > 0 && (
          <div className="termination-spread-info-box">
            <strong>📋 פריסת מס אוטומטית</strong>
            <p className="termination-spread-description">
              הסכום יפרס על פני <strong>{terminationDecision.max_spread_years} שנים</strong> (שנה לכל 4 שנות וותק)
            </p>
          </div>
        )}
      </div>
    );
  };

  // Step 5b: Taxable choice
  const renderStep5b = () => {
    if ((terminationDecision.taxable_amount || 0) <= 0) return null;

    return (
      <div className="termination-step termination-step--danger termination-choice-group">
        <h4 className="termination-step-header">שלב 5ב: בחירת אפשרות לחלק החייב במס</h4>
        {['redeem_no_exemption', 'annuity'].map(choice => (
          <label
            key={choice}
            className={`termination-radio-label ${terminationDecision.confirmed ? 'termination-radio-label--disabled' : ''}`}
          >
            <input
              type="radio"
              value={choice}
              checked={terminationDecision.taxable_choice === choice}
              onChange={(e) => setTerminationDecision(prev => ({ ...prev, taxable_choice: e.target.value as any }))}
              disabled={terminationDecision.confirmed}
              className="termination-radio-input"
            />
            {choice === 'redeem_no_exemption' ? 'פדיון הסכום ללא שימוש בפטור (עם פריסת מס)' : 'סימון כקצבה'}
          </label>
        ))}
        
        {terminationDecision.taxable_choice === 'redeem_no_exemption' && (
          <div className="termination-spread-info-box">
            <h5>זכאות לפריסת פיצויים</h5>
            
            <div className="termination-spread-explanation">
              <strong>📘 מה זה פריסת פיצויים?</strong>
              <p className="termination-spread-description">
                פריסת פיצויים מאפשרת לפרוס את החלק החייב במס של המענק על פני מספר שנות מס.
                הזכאות נקבעת לפי <strong>שנת פריסה אחת לכל 4 שנות וותק מלאות</strong>.
                פריסה עשויה להקטין את המס הכולל על המענק בזכות מדרגות המס השנתיות.
              </p>
              <p className="termination-spread-note">
                <strong>תשלום המס:</strong> בשנה הראשונה משולם כל סכום המענק, אך המס מחושב בהתחשב 
                בפריסה על פני כל השנים. בשאר השנים, המס מוצג רק ויזואלית ולא משולם בפועל.
              </p>
            </div>
            
            <p><strong>זכאות מקסימלית:</strong> {terminationDecision.max_spread_years || 0} שנים<br/>
            <small className="termination-spread-note">(שנת פריסה אחת לכל 4 שנות וותק מלאות)</small></p>
            {(terminationDecision.max_spread_years || 0) > 0 ? (
              <div>
                <label>בחר מספר שנות פריסה:</label>
                <input
                  type="number"
                  min="1"
                  max={terminationDecision.max_spread_years}
                  value={terminationDecision.tax_spread_years || terminationDecision.max_spread_years}
                  onChange={(e) => setTerminationDecision(prev => ({
                    ...prev,
                    tax_spread_years: Math.min(parseInt(e.target.value) || 0, terminationDecision.max_spread_years || 0)
                  }))}
                  disabled={terminationDecision.confirmed}
                  className={`termination-spread-input ${terminationDecision.confirmed ? 'termination-spread-input--disabled' : ''}`}
                />
                <small className="termination-spread-note">
                  המערכת ממליצה על פריסה מלאה של {terminationDecision.max_spread_years} שנים לחיסכון מרבי במס
                </small>
              </div>
            ) : (
              <div className="termination-no-spread-box">
                <strong>אין זכאות לפריסה</strong>
                <p className="termination-spread-description">נדרשות לפחות 4 שנות וותק מלאות לזכאות לפריסת מס</p>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // Action buttons
  const renderActions = () => {
    if (!terminationDecision.termination_date) return null;

    return (
      <div className="termination-actions">
        {!terminationDecision.confirmed ? (
          <>
            <button
              type="button"
              onClick={onSubmit}
              disabled={loading}
              className="termination-button-primary"
            >
              {loading ? 'שומר...' : 'שמור החלטות ועדכן מערכת'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="termination-button-secondary"
            >
              ביטול
            </button>
          </>
        ) : (
          <div className="termination-confirm-box">
            <p className="termination-confirm-title">
              ⚠️ קיימת עזיבת עבודה שמורה במערכת
            </p>
            <p className="termination-confirm-text">
              כדי לערוך החלטות עזיבה חדשות, יש למחוק תחילה את העזיבה הקיימת. 
              פעולה זו תמחק את כל המענקים, הקצבאות ונכסי ההון שנוצרו מהעזיבה הקודמת.
            </p>
            <button
              type="button"
              onClick={onDelete}
              disabled={loading}
              className="termination-button-danger"
            >
              {loading ? 'מוחק...' : '🗑️ מחק עזיבה ואפשר עריכה מחדש'}
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="termination-steps-container">
      <h3>מסך עזיבת עבודה</h3>
      {renderStep1()}
      {renderStep2()}
      {renderStep3()}
      {renderStep4()}
      {renderStep5a()}
      {renderStep5b()}
      {renderActions()}
    </div>
  );
};
