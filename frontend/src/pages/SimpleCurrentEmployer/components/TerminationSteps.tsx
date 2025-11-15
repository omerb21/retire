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
    <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
      <h4>שלב 1: תאריך סיום עבודה</h4>
      <div style={{ padding: '15px', backgroundColor: '#d4edda', borderRadius: '4px' }}>
        <p style={{ margin: 0, fontWeight: 'bold', color: '#155724' }}>
          תאריך סיום עבודה: <strong>{employer.end_date || 'לא הוזן'}</strong>
        </p>
        {!employer.end_date && (
          <p style={{ margin: '10px 0 0 0', fontSize: '14px', color: '#856404' }}>
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
      <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
        <h4>שלב 2: סיכום זכויות</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
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
      <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ffc107', borderRadius: '4px', backgroundColor: '#fffdf5' }}>
        <h4>שלב 3: השלמת מעסיק</h4>
        <label style={{ display: 'flex', alignItems: 'center', cursor: terminationDecision.confirmed ? 'not-allowed' : 'pointer', opacity: terminationDecision.confirmed ? 0.6 : 1 }}>
          <input
            type="checkbox"
            checked={terminationDecision.use_employer_completion}
            onChange={(e) => setTerminationDecision(prev => ({ ...prev, use_employer_completion: e.target.checked }))}
            disabled={terminationDecision.confirmed}
            style={{ marginLeft: '10px', width: '20px', height: '20px', cursor: terminationDecision.confirmed ? 'not-allowed' : 'pointer' }}
          />
          תבוצע השלמת מעסיק
        </label>
        {terminationDecision.use_employer_completion && (
          <div style={{ padding: '10px', backgroundColor: '#e8f4f8', borderRadius: '4px', marginTop: '10px' }}>
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
      <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #17a2b8', borderRadius: '4px', backgroundColor: '#f0f9fc' }}>
        <h4>שלב 4: חלוקה לפטור/חייב במס</h4>
        
        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#fff3cd', borderRadius: '4px', fontSize: '12px', border: '1px solid #ffc107' }}>
          <strong>🔍 פרטי חישוב:</strong>
          <div>תאריך עזיבה מקורי: <strong>{terminationDecision.termination_date}</strong></div>
          <div>שנת עזיבה מחושבת: <strong>{new Date(endISO || '').getFullYear()}</strong></div>
          <div>סכום פיצויים: <strong>{formatCurrency(terminationDecision.severance_amount || 0)}</strong></div>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
          <div style={{ padding: '15px', backgroundColor: '#d4edda', borderRadius: '4px' }}>
            <strong style={{ color: '#155724' }}>חלק פטור ממס:</strong>
            <p style={{ fontSize: '20px', fontWeight: 'bold', margin: '10px 0' }}>{formatCurrency(terminationDecision.exempt_amount || 0)}</p>
          </div>
          <div style={{ padding: '15px', backgroundColor: '#f8d7da', borderRadius: '4px' }}>
            <strong style={{ color: '#721c24' }}>חלק חייב במס:</strong>
            <p style={{ fontSize: '20px', fontWeight: 'bold', margin: '10px 0' }}>{formatCurrency(terminationDecision.taxable_amount || 0)}</p>
          </div>
        </div>
      </div>
    );
  };

  // Step 5a: Exempt choice
  const renderStep5a = () => {
    if ((terminationDecision.exempt_amount || 0) <= 0) return null;

    return (
      <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #28a745', borderRadius: '4px', backgroundColor: '#f8fff9' }}>
        <h4>שלב 5א: בחירת אפשרות לחלק הפטור ממס</h4>
        {['redeem_with_exemption', 'redeem_no_exemption', 'annuity'].map(choice => (
          <label key={choice} style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: terminationDecision.confirmed ? 'not-allowed' : 'pointer', opacity: terminationDecision.confirmed ? 0.6 : 1 }}>
            <input
              type="radio"
              value={choice}
              checked={terminationDecision.exempt_choice === choice}
              onChange={(e) => setTerminationDecision(prev => ({ ...prev, exempt_choice: e.target.value as any }))}
              disabled={terminationDecision.confirmed}
              style={{ marginLeft: '10px', width: '18px', height: '18px', cursor: terminationDecision.confirmed ? 'not-allowed' : 'pointer' }}
            />
            {choice === 'redeem_with_exemption' ? 'פדיון הסכום עם שימוש בפטור' :
             choice === 'redeem_no_exemption' ? 'פדיון הסכום ללא שימוש בפטור (עם פריסת מס)' : 'סימון כקצבה'}
          </label>
        ))}
        
        {terminationDecision.exempt_choice === 'redeem_no_exemption' && (terminationDecision.max_spread_years || 0) > 0 && (
          <div style={{ marginTop: '15px', padding: '15px', backgroundColor: '#fff3cd', borderRadius: '4px', border: '1px solid #ffc107' }}>
            <strong>📋 פריסת מס אוטומטית</strong>
            <p style={{ fontSize: '14px', margin: '8px 0' }}>
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
      <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #dc3545', borderRadius: '4px', backgroundColor: '#fff5f5' }}>
        <h4>שלב 5ב: בחירת אפשרות לחלק החייב במס</h4>
        {['redeem_no_exemption', 'annuity'].map(choice => (
          <label key={choice} style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', cursor: terminationDecision.confirmed ? 'not-allowed' : 'pointer', opacity: terminationDecision.confirmed ? 0.6 : 1 }}>
            <input
              type="radio"
              value={choice}
              checked={terminationDecision.taxable_choice === choice}
              onChange={(e) => setTerminationDecision(prev => ({ ...prev, taxable_choice: e.target.value as any }))}
              disabled={terminationDecision.confirmed}
              style={{ marginLeft: '10px', width: '18px', height: '18px', cursor: terminationDecision.confirmed ? 'not-allowed' : 'pointer' }}
            />
            {choice === 'redeem_no_exemption' ? 'פדיון הסכום ללא שימוש בפטור (עם פריסת מס)' : 'סימון כקצבה'}
          </label>
        ))}

        {terminationDecision.taxable_choice === 'redeem_no_exemption' && (
          <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fff3cd', borderRadius: '4px', border: '1px solid #ffc107' }}>
            <h5>זכאות לפריסת פיצויים</h5>
            
            <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#e7f3ff', borderRadius: '4px', fontSize: '14px' }}>
              <strong>📘 מה זה פריסת פיצויים?</strong>
              <p style={{ margin: '8px 0 0 0' }}>
                פריסת פיצויים מאפשרת לפרוס את החלק החייב במס של המענק על פני מספר שנות מס.
                הזכאות נקבעת לפי <strong>שנת פריסה אחת לכל 4 שנות וותק מלאות</strong>.
                פריסה עשויה להקטין את המס הכולל על המענק בזכות מדרגות המס השנתיות.
              </p>
              <p style={{ margin: '8px 0 0 0', fontSize: '13px', color: '#555' }}>
                <strong>תשלום המס:</strong> בשנה הראשונה משולם כל סכום המענק, אך המס מחושב בהתחשב 
                בפריסה על פני כל השנים. בשאר השנים, המס מוצג רק ויזואלית ולא משולם בפועל.
              </p>
            </div>
            
            <p><strong>זכאות מקסימלית:</strong> {terminationDecision.max_spread_years || 0} שנים<br/>
            <small style={{ color: '#666' }}>(שנת פריסה אחת לכל 4 שנות וותק מלאות)</small></p>
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
                  style={{ 
                    width: '100%', 
                    padding: '8px', 
                    marginTop: '5px', 
                    border: '1px solid #ddd', 
                    borderRadius: '4px',
                    backgroundColor: terminationDecision.confirmed ? '#f0f0f0' : 'white',
                    cursor: terminationDecision.confirmed ? 'not-allowed' : 'text'
                  }}
                />
                <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
                  המערכת ממליצה על פריסה מלאה של {terminationDecision.max_spread_years} שנים לחיסכון מרבי במס
                </small>
              </div>
            ) : (
              <div style={{ padding: '10px', backgroundColor: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
                <strong>אין זכאות לפריסה</strong>
                <p style={{ marginTop: '5px', fontSize: '14px' }}>נדרשות לפחות 4 שנות וותק מלאות לזכאות לפריסת מס</p>
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
      <div style={{ marginTop: '30px', textAlign: 'center' }}>
        {!terminationDecision.confirmed ? (
          <>
            <button
              type="button"
              onClick={onSubmit}
              disabled={loading}
              style={{
                backgroundColor: loading ? '#6c757d' : '#28a745',
                color: 'white',
                border: 'none',
                padding: '15px 40px',
                borderRadius: '4px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                marginLeft: '10px'
              }}
            >
              {loading ? 'שומר...' : 'שמור החלטות ועדכן מערכת'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              style={{
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                padding: '15px 40px',
                borderRadius: '4px',
                fontSize: '16px',
                cursor: 'pointer'
              }}
            >
              ביטול
            </button>
          </>
        ) : (
          <div style={{ backgroundColor: '#fff3cd', padding: '20px', borderRadius: '4px', marginBottom: '20px', border: '1px solid #ffeaa7' }}>
            <p style={{ fontWeight: 'bold', color: '#856404', marginBottom: '10px', fontSize: '18px' }}>
              ⚠️ קיימת עזיבת עבודה שמורה במערכת
            </p>
            <p style={{ color: '#856404', marginBottom: '15px', fontSize: '14px' }}>
              כדי לערוך החלטות עזיבה חדשות, יש למחוק תחילה את העזיבה הקיימת. 
              פעולה זו תמחק את כל המענקים, הקצבאות ונכסי ההון שנוצרו מהעזיבה הקודמת.
            </p>
            <button
              type="button"
              onClick={onDelete}
              disabled={loading}
              style={{
                backgroundColor: loading ? '#6c757d' : '#dc3545',
                color: 'white',
                border: 'none',
                padding: '15px 40px',
                borderRadius: '4px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'מוחק...' : '🗑️ מחק עזיבה ואפשר עריכה מחדש'}
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div>
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
