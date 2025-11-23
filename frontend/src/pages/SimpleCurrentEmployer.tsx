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
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <Link to={`/clients/${id}`} style={{ color: '#007bff', textDecoration: 'none' }}>
          ← חזרה לפרטי לקוח
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>מעסיק נוכחי</h2>
        
        {/* כפתור נקה מצב - למקרי חירום: מחיקת עזיבה ונתוני מעסיק נוכחי */}
        <button
          onClick={() => {
            if (!id) return;
            handleClearAllState();
          }}
          style={{
            padding: '5px 10px',
            fontSize: '12px',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
          title="לחץ אם השדות מוקפאים בטעות"
        >
          🔧 נקה מצב
        </button>
      </div>

      {error && (
        <div style={{ padding: '15px', backgroundColor: '#f8d7da', color: '#721c24', borderRadius: '4px', marginBottom: '20px', border: '1px solid #f5c6cb' }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: '20px', borderBottom: '2px solid #ddd' }}>
        <button
          onClick={() => setActiveTab('details')}
          style={{
            padding: '10px 20px',
            marginLeft: '5px',
            border: 'none',
            borderBottom: activeTab === 'details' ? '3px solid #007bff' : 'none',
            backgroundColor: activeTab === 'details' ? '#f8f9fa' : 'transparent',
            cursor: 'pointer',
            fontWeight: activeTab === 'details' ? 'bold' : 'normal'
          }}
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
          style={{
            padding: '10px 20px',
            border: 'none',
            borderBottom: activeTab === 'termination' ? '3px solid #007bff' : 'none',
            backgroundColor: activeTab === 'termination' ? '#f8f9fa' : 'transparent',
            cursor: 'pointer',
            fontWeight: activeTab === 'termination' ? 'bold' : 'normal'
          }}
        >
          עזיבת עבודה
        </button>
      </div>

      {/* Employer Details Tab */}
      {activeTab === 'details' && (
        <div>
          <SavedDataDisplay employer={employer} />
          
          {error && (
            <div style={{ 
              color: 'red', 
              marginBottom: '20px', 
              padding: '10px', 
              backgroundColor: '#fee', 
              borderRadius: '4px' 
            }}>
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
