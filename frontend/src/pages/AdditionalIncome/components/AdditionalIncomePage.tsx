import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAdditionalIncome } from '../hooks/useAdditionalIncome';
import { AdditionalIncomeForm } from './AdditionalIncomeForm';
import { AdditionalIncomeList } from './AdditionalIncomeList';
import '../../AdditionalIncome.css';

const AdditionalIncomePage: React.FC = () => {
  const { id: clientId } = useParams<{ id: string }>();

  const {
    incomes,
    loading,
    error,
    form,
    setForm,
    editingIncomeId,
    setEditingIncomeId,
    handleSubmit,
    handleDeleteAll,
    handleDelete,
    handleEdit,
  } = useAdditionalIncome(clientId);

  if (loading) {
    return <div>טוען הכנסות נוספות...</div>;
  }

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💵 הכנסות נוספות</h1>
            <p className="card-subtitle">ניהול הכנסות נוספות מעבודה, השכרה ועוד</p>
          </div>
          <div className="additional-income-header-actions">
            <button
              onClick={handleDeleteAll}
              className="btn additional-income-delete-all-button"
              disabled={incomes.length === 0}
            >
              🗑️ מחק הכל
            </button>
            <Link to={`/clients/${clientId}`} className="btn btn-secondary">
              ← חזרה
            </Link>
          </div>
        </div>

        {error && <div className="additional-income-error">{error}</div>}

        <AdditionalIncomeForm
          form={form}
          setForm={setForm}
          editingIncomeId={editingIncomeId}
          setEditingIncomeId={setEditingIncomeId}
          handleSubmit={handleSubmit}
        />

        <AdditionalIncomeList
          incomes={incomes}
          onEdit={handleEdit}
          onDelete={handleDelete}
        />
      </div>
    </div>
  );
};

export default AdditionalIncomePage;
