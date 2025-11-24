/**
 * SimpleCurrentEmployer - Main Component (Refactored)
 * All logic extracted to modular hooks and components
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TerminationDecision } from './SimpleCurrentEmployer/types';
import { useEmployerData } from './SimpleCurrentEmployer/hooks/useEmployerData';
import { useGrantCalculation } from './SimpleCurrentEmployer/hooks/useGrantCalculation';
import { useTerminationCalculation } from './SimpleCurrentEmployer/hooks/useTerminationCalculation';
import { useTerminationActions } from './SimpleCurrentEmployer/hooks/useTerminationActions';
import { SavedDataDisplay } from './SimpleCurrentEmployer/components/SavedDataDisplay';
import { EmployerDetailsForm } from './SimpleCurrentEmployer/components/EmployerDetailsForm';
import { TerminationSteps } from './SimpleCurrentEmployer/components/TerminationSteps';
import { isTerminationConfirmed } from './SimpleCurrentEmployer/utils/storageHelpers';
import './SimpleCurrentEmployer/SimpleCurrentEmployer.css';

const SimpleCurrentEmployer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'details' | 'termination'>('details');
  
  // State for termination decision
  const [terminationDecision, setTerminationDecision] = useState<TerminationDecision>({
    termination_date: '',
    use_employer_completion: false,
    severance_amount: 0,
    exempt_amount: 0,
    taxable_amount: 0,
    exempt_choice: 'redeem_with_exemption',
    taxable_choice: 'redeem_no_exemption',
    tax_spread_years: 0,
    max_spread_years: 0
  });

  // Custom hooks for data management
  const {
    employer,
    setEmployer,
    loading,
    setLoading,
    error,
    setError,
    saveEmployer
  } = useEmployerData(id);

  const { grantDetails } = useGrantCalculation(employer);
  
  useTerminationCalculation(
    employer,
    terminationDecision,
    setTerminationDecision,
    grantDetails
  );

  const { handleTerminationSubmit, handleDeleteTermination, handleClearAllState } = useTerminationActions(
    id,
    employer,
    setEmployer,
    terminationDecision,
    setTerminationDecision,
    setLoading,
    setError
  );

  // Load confirmed state from localStorage on mount
  useEffect(() => {
    if (id) {
      const isConfirmed = isTerminationConfirmed(id);
      if (isConfirmed) {
        setTerminationDecision(prev => ({ ...prev, confirmed: true }));
        console.log('✅ Loaded confirmed state from localStorage: true');
      }
    }
  }, [id]);

  // Sync termination_date with employer.end_date
  useEffect(() => {
    if (employer.end_date && employer.end_date !== terminationDecision.termination_date) {
      setTerminationDecision(prev => ({ ...prev, termination_date: employer.end_date || '' }));
    }
  }, [employer.end_date]);

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await saveEmployer();
    if (success) {
      alert('נתוני מעסיק נשמרו בהצלחה');
    }
  };

  return (
    <div className="simple-current-employer-container">
      <div className="simple-current-employer-back-row">
        <Link to={`/clients/${id}`} className="simple-current-employer-back-link">
          ← חזרה לפרטי לקוח
        </Link>
      </div>

      <div className="simple-current-employer-header-row">
        <h2>מעסיק נוכחי</h2>
        
        {/* כפתור נקה מצב - למקרי חירום: מחיקת עזיבה ונתוני מעסיק נוכחי */}
        <button
          onClick={() => {
            if (!id) return;
            handleClearAllState();
          }}
          className="simple-current-employer-clear-button"
          title="לחץ רק אם המסך תקוע בטעות: פעולה זו תמחק את עזיבת העבודה (אם קיימת), את נתוני המעסיק הנוכחי ותשחזר פיצויים לתיק הפנסיוני"
        >
          🔧 נקה מצב
        </button>
      </div>

      {error && (
        <div className="simple-current-employer-error-banner">
          {error}
        </div>
      )}

      <div className="simple-current-employer-tab-bar">
        <button
          onClick={() => setActiveTab('details')}
          className={`simple-current-employer-tab-button ${activeTab === 'details' ? 'simple-current-employer-tab-button--active' : ''}`}
        >
          פרטי מעסיק
        </button>
        <button
          onClick={() => {
            if (!employer.end_date) {
              alert('נא להזין תאריך סיום עבודה בלשונית "פרטי מעסיק" לפני מעבר לעזיבת עבודה');
              return;
            }
            setTerminationDecision(prev => ({ ...prev, termination_date: employer.end_date || '' }));
            setActiveTab('termination');
          }}
          className={`simple-current-employer-tab-button ${activeTab === 'termination' ? 'simple-current-employer-tab-button--active' : ''}`}
        >
          עזיבת עבודה
        </button>
      </div>

      {terminationDecision.confirmed && (
        <div className="termination-warning-box">
          <p className="termination-warning-title">
            ⚠️ קיימת עזיבת עבודה שמורה למעסיק זה
          </p>
          <p className="termination-warning-text">
            לעריכת החלטות חדשות או למחיקת העזיבה הקיימת, עבור לטאב "עזיבת עבודה".
            במקרים חריגים בלבד, כשמסך העזיבה תקוע או במצב לא עקבי, ניתן להשתמש בכפתור "נקה מצב" כדי לאפס את הנתונים.
          </p>
        </div>
      )}

      {/* Employer Details Tab */}
      {activeTab === 'details' && (
        <div>
          <SavedDataDisplay employer={employer} />
          
          {error && (
            <div className="simple-current-employer-error-banner">
              {error}
            </div>
          )}

          <EmployerDetailsForm
            clientId={id || ''}
            employer={employer}
            setEmployer={setEmployer}
            terminationDecision={terminationDecision}
            setTerminationDecision={setTerminationDecision}
            loading={loading}
            onSubmit={handleSubmit}
          />
        </div>
      )}

      {/* Termination Tab */}
      {activeTab === 'termination' && (
        <TerminationSteps
          employer={employer}
          terminationDecision={terminationDecision}
          setTerminationDecision={setTerminationDecision}
          loading={loading}
          onSubmit={handleTerminationSubmit}
          onDelete={handleDeleteTermination}
          onCancel={() => setActiveTab('details')}
        />
      )}
    </div>
  );
};

export default SimpleCurrentEmployer;
