/**
 * CapitalAssets Page
 * ==================
 * Main page component for managing capital assets
 * 
 * This is the refactored version that uses modular components
 */

import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useCapitalAssets } from '../../hooks/useCapitalAssets';
import { useAssetForm } from '../../hooks/useAssetForm';
import { AssetForm } from '../../components/capitalAssets/AssetForm/AssetForm';
import { AssetList } from '../../components/capitalAssets/AssetList/AssetList';
import './CapitalAssets.css';

export default function CapitalAssets() {
  const { id: clientId } = useParams<{ id: string }>();
  
  // Use custom hooks for state management
  const {
    assets,
    loading,
    error: assetsError,
    setError: setAssetsError,
    loadAssets,
    deleteAsset,
    deleteAllAssets
  } = useCapitalAssets(clientId);

  const {
    form,
    setForm,
    editingAssetId,
    error: formError,
    setError: setFormError,
    resetForm,
    populateForm,
    handleSubmit
  } = useAssetForm(clientId, loadAssets);

  // Combine errors
  const error = assetsError || formError;
  const setError = (err: string) => {
    setAssetsError(err);
    setFormError(err);
  };

  if (loading) return <div>טוען נכסי הון...</div>;

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">🏠 נכסי הון</h1>
            <p className="card-subtitle">ניהול נכסים - תשלום חד פעמי או חישוב NPV</p>
          </div>
          <div className="capital-assets-header-actions">
            <button 
              onClick={deleteAllAssets}
              className="btn capital-assets-delete-all-button"
              disabled={assets.length === 0}
            >
              🗑️ מחק הכל
            </button>
            <Link to={`/clients/${clientId}`} className="btn btn-secondary">
              ← חזרה
            </Link>
          </div>
        </div>
        {error && (
          <div className="capital-assets-error">
            {error}
          </div>
        )}

        {/* Asset Form */}
        <AssetForm
          form={form}
          setForm={setForm}
          editingAssetId={editingAssetId}
          onSubmit={handleSubmit}
          onCancel={resetForm}
        />

        {/* Assets List */}
        <AssetList
          assets={assets}
          onEdit={populateForm}
          onDelete={deleteAsset}
        />
      </div>
    </div>
  );
}
