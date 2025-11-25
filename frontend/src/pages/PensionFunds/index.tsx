import React from 'react';
import { Link } from 'react-router-dom';
import { PensionFundForm } from './components/PensionFundForm';
import { PensionFundList } from './components/PensionFundList';
import { CommutationForm } from './components/CommutationForm';
import { CommutationList } from './components/CommutationList';
import { usePensionFundsPage } from './hooks/usePensionFundsPage';
import './PensionFunds.css';

export default function PensionFunds() {
  const {
    clientId,
    loading,
    error,
    funds,
    commutations,
    clientData,
    form,
    setForm,
    editingFundId,
    commutationForm,
    setCommutationForm,
    handleSubmit,
    handleCompute,
    handleDeleteAll,
    handleEdit,
    handleCancelEdit,
    handleDelete,
    handleCommutationSubmit,
    handleCommutationDelete,
  } = usePensionFundsPage();

  if (loading) return <div>טוען קצבאות...</div>;

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💰 קצבאות והיוונים</h1>
            <p className="card-subtitle">ניהול קצבאות פנסיוניות והיוונים פטורים ממס</p>
          </div>
          <div className="pension-funds-header-actions">
            <button 
              onClick={handleDeleteAll}
              className="btn pension-funds-delete-all-button"
              disabled={funds.length === 0 && commutations.length === 0}
            >
              🗑️ מחק הכל
            </button>
            <Link to={`/clients/${clientId}`} className="btn btn-secondary">
              ← חזרה
            </Link>
          </div>
        </div>

        {error && (
          <div className="pension-funds-error">
            {error}
          </div>
        )}

        {/* Create Forms - Side by Side */}
        <div className="pension-funds-forms-grid">
          <PensionFundForm
            form={form}
            setForm={setForm}
            onSubmit={handleSubmit}
            editingFundId={editingFundId}
            onCancelEdit={handleCancelEdit}
            clientData={clientData}
          />

          <CommutationForm
            commutationForm={commutationForm}
            setCommutationForm={setCommutationForm}
            onSubmit={handleCommutationSubmit}
            funds={funds}
          />
        </div>

        {/* Main Content - Two Columns */}
        <div className="pension-funds-main-grid">
          {/* Left Column - Pension Funds */}
          <section>
            <h3>רשימת קצבאות</h3>
            <PensionFundList
              funds={funds}
              onCompute={handleCompute}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          </section>

          {/* Right Column - Commutations List */}
          <section>
            <h3>רשימת היוונים</h3>
            <CommutationList
              commutations={commutations}
              funds={funds}
              onDelete={handleCommutationDelete}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
