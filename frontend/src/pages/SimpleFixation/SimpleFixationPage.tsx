import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useFixationData } from './hooks/useFixationData';
import { FixationSummaryCard } from './components/FixationSummaryCard';
import { GrantsTable } from './components/GrantsTable';
import { CommutationsTable } from './components/CommutationsTable';
import { FixationExplanation } from './components/FixationExplanation';

const SimpleFixationPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    loading,
    error,
    fixationData,
    grantsSummary,
    exemptionSummary,
    clientData,
    commutations,
    futureGrantReserved,
    setFutureGrantReserved,
    retirementAge,
    isFixationStale,
    handleCalculateFixation,
    handleDeleteFixation
  } = useFixationData(id);

  if (loading && !fixationData) {
    return <div style={{ padding: '20px' }}>טוען נתוני קיבוע זכויות...</div>;
  }

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">📊 קיבוע זכויות</h1>
            <p className="card-subtitle">חישוב וקיבוע זכויות פנסיוניות למס הכנסה</p>
          </div>
          <button onClick={() => navigate(`/clients/${id}`)} className="btn btn-secondary">
            ← חזרה
          </button>
        </div>

        {isFixationStale && (
          <div className="fixation-stale-warning">
            <strong>שימו לב:</strong> תאריך הקצבה הראשונה של הלקוח השתנה מאז קיבוע הזכויות האחרון
            שנשמר.
            מומלץ לבצע חישוב קיבוע זכויות מחדש כדי לוודא שהנתונים מעודכנים.
          </div>
        )}

        {error && (
          <div
            style={{
              color: 'red',
              marginBottom: '20px',
              padding: '10px',
              backgroundColor: '#fee',
              borderRadius: '4px'
            }}
          >
            {error}
          </div>
        )}

        {fixationData && (
          <FixationSummaryCard
            fixationData={fixationData}
            clientData={clientData}
            retirementAge={retirementAge}
            futureGrantReserved={futureGrantReserved}
            setFutureGrantReserved={setFutureGrantReserved}
            loading={loading}
            grantsSummary={grantsSummary}
            exemptionSummary={exemptionSummary}
            commutations={commutations}
            onCalculateFixation={handleCalculateFixation}
            onDeleteFixation={handleDeleteFixation}
          />
        )}

        {grantsSummary.length > 0 && <GrantsTable grantsSummary={grantsSummary} />}

        {commutations.length > 0 && <CommutationsTable commutations={commutations} />}

        <FixationExplanation />
      </div>
    </div>
  );
};

export default SimpleFixationPage;
