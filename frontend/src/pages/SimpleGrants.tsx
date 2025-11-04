/**
 * SimpleGrants Page - Refactored Version
 * עמוד ניהול מענקים - גרסה מפוצלת
 */

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGrants } from '../hooks/useGrants';
import { GrantForm } from '../components/grants/GrantForm';
import { GrantList } from '../components/grants/GrantList';

const SimpleGrants: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const {
    grants,
    grantDetails,
    loading,
    error,
    createGrant,
    deleteGrant
  } = useGrants(id);

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💰 מענקים ממעסיקים קודמים</h1>
            <p className="card-subtitle">ניהול מענקי פיצויים מכל מעסיקי העבר</p>
          </div>
          <button onClick={() => navigate(`/clients/${id}`)} className="btn btn-secondary">
            ← חזרה
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            {error}
          </div>
        )}

        {/* Add new grant form */}
        <GrantForm onSubmit={createGrant} loading={loading} />

        {/* Grants list */}
        <div>
          <h3>רשימת מענקים</h3>
          <GrantList 
            grants={grants} 
            grantDetails={grantDetails} 
            onDelete={deleteGrant} 
          />
        </div>

        <div style={{ 
          marginTop: '30px', 
          padding: '15px', 
          backgroundColor: '#e9ecef', 
          borderRadius: '4px',
          fontSize: '14px'
        }}>
          <strong>הסבר:</strong> המענקים הפטורים שהתקבלו ממעסיקים קודמים. 
          משמשים לחישוב סה"כ הפטור שנוצל ויקוזז מיתרת ההון הפטורה.
          הסכומים הפטורים יופיעו בטבלת המענקים, בעמוד קיבוע הזכויות, ממודדים ומוכפלים בפקטור ההכפלה.
        </div>
      </div>
    </div>
  );
};

export default SimpleGrants;
