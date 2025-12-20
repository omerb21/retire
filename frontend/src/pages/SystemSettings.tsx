/**
 * SystemSettings - Wrapper component using modular sub-components
 *
 * This file provides the same functionality as the original SystemSettings.tsx
 * but delegates all logic to specialized sub-components and the useSystemSettingsPage hook.
 */

import React from 'react';
import TaxCalculationDocumentation from '../components/TaxCalculationDocumentation';
import TaxSettings from '../components/system-settings/TaxSettings';
import SeveranceSettings from '../components/system-settings/SeveranceSettings';
import ConversionSettings from '../components/system-settings/ConversionSettings';
import RetirementSettings from '../components/system-settings/RetirementSettings';
import FixationSettings from '../components/system-settings/FixationSettings';
import ScenariosSettings from '../components/system-settings/ScenariosSettings';
import TerminationSettings from '../components/system-settings/TerminationSettings';
import AnnuitySettings from '../components/system-settings/AnnuitySettings';
import SystemHealthMonitor from '../components/system-settings/SystemHealthMonitor';
import PublicChatSettings from '../components/system-settings/PublicChatSettings';
import { useSystemSettingsPage } from './SystemSettings/hooks/useSystemSettingsPage';
import './SystemSettings.css';

const SystemSettings: React.FC = () => {
  const {
    activeTab,
    setActiveTab,
    taxBrackets,
    isEditing,
    editedBrackets,
    handleEdit,
    handleSave,
    handleCancel,
    handleBracketChange,
    severanceCaps,
    isEditingCaps,
    editedCaps,
    capsLoading,
    capsError,
    handleEditCaps,
    handleSaveCaps,
    handleCancelCaps,
    handleCapChange,
    handleAddCap,
    conversionRules,
    conversionSaved,
    handleSaveConversionRules,
    handleResetConversionRules,
    updateConversionRule,
    pensionCeilings,
    isEditingCeilings,
    editedCeilings,
    exemptCapitalPercentages,
    isEditingPercentages,
    editedPercentages,
    handleEditCeilings,
    handleSaveCeilings,
    handleCancelCeilings,
    handleCeilingChange,
    handleAddCeiling,
    handleEditPercentages,
    handleSavePercentages,
    handleCancelPercentages,
    handlePercentageChange,
    handleAddPercentage,
    idfPromoterTable,
    isEditingIdfPromoterTable,
    editedIdfPromoterTable,
    handleEditIdfPromoterTable,
    handleSaveIdfPromoterTable,
    handleCancelIdfPromoterTable,
    handleIdfPromoterRowChange,
    handleAddIdfPromoterRow,
    maleRetirementAge,
    setMaleRetirementAge,
    retirementSaved,
    handleSaveRetirement,
    formatCurrency,
  } = useSystemSettingsPage();

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">⚙️ הגדרות מערכת</h1>
            <p className="card-subtitle">ניהול מדרגות מס, תקרות פיצויים, חוקי המרה ונתוני קיבוע זכויות</p>
          </div>
        </div>
        
        {/* Tabs Navigation */}
        <div className="modern-tabs">
          <button
            onClick={() => setActiveTab('tax')}
            className={`tab-button ${activeTab === 'tax' ? 'active' : ''}`}
          >
            📊 מדרגות מס
          </button>
          <button
            onClick={() => setActiveTab('severance')}
            className={`tab-button ${activeTab === 'severance' ? 'active' : ''}`}
          >
            💰 תקרות פיצויים
          </button>
          <button
            onClick={() => setActiveTab('conversion')}
            className={`tab-button ${activeTab === 'conversion' ? 'active' : ''}`}
          >
            🔄 חוקי המרה
          </button>
          <button
            onClick={() => setActiveTab('fixation')}
            className={`tab-button ${activeTab === 'fixation' ? 'active' : ''}`}
          >
            📋 נתוני קיבוע זכויות
          </button>
          <button
            onClick={() => setActiveTab('scenarios')}
            className={`tab-button ${activeTab === 'scenarios' ? 'active' : ''}`}
          >
            🎯 לוגיקת תרחישים
          </button>
          <button
            onClick={() => setActiveTab('retirement')}
            className={`tab-button ${activeTab === 'retirement' ? 'active' : ''}`}
          >
            👤 גיל פרישה
          </button>
          <button
            onClick={() => setActiveTab('termination')}
            className={`tab-button ${activeTab === 'termination' ? 'active' : ''}`}
          >
            🚪 עזיבות עבודה
          </button>
          <button
            onClick={() => setActiveTab('annuity')}
            className={`tab-button ${activeTab === 'annuity' ? 'active' : ''}`}
          >
            📊 מקדמי קצבה
          </button>
          <button
            onClick={() => setActiveTab('tax_calculation')}
            className={`tab-button ${activeTab === 'tax_calculation' ? 'active' : ''}`}
          >
            🧮 חישובי מס
          </button>
          <button
            onClick={() => setActiveTab('health')}
            className={`tab-button ${activeTab === 'health' ? 'active' : ''}`}
          >
            🏥 תקינות מערכת
          </button>
          <button
            onClick={() => setActiveTab('public_chat')}
            className={`tab-button ${activeTab === 'public_chat' ? 'active' : ''}`}
          >
            💬 צ'אט לקוח
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'tax' && (
          <TaxSettings
            taxBrackets={taxBrackets}
            isEditing={isEditing}
            editedBrackets={editedBrackets}
            onEdit={handleEdit}
            onSave={handleSave}
            onCancel={handleCancel}
            onBracketChange={handleBracketChange}
            formatCurrency={formatCurrency}
          />
        )}
        
        {activeTab === 'severance' && (
          <SeveranceSettings
            severanceCaps={severanceCaps}
            isEditingCaps={isEditingCaps}
            editedCaps={editedCaps}
            capsLoading={capsLoading}
            capsError={capsError}
            onEditCaps={handleEditCaps}
            onSaveCaps={handleSaveCaps}
            onCancelCaps={handleCancelCaps}
            onCapChange={handleCapChange}
            onAddCap={handleAddCap}
            formatCurrency={formatCurrency}
          />
        )}
        
        {activeTab === 'conversion' && (
          <ConversionSettings
            conversionRules={conversionRules}
            conversionSaved={conversionSaved}
            onSave={handleSaveConversionRules}
            onReset={handleResetConversionRules}
            onUpdateRule={updateConversionRule}
          />
        )}
        
        {activeTab === 'retirement' && (
          <RetirementSettings
            maleRetirementAge={maleRetirementAge}
            retirementSaved={retirementSaved}
            onMaleRetirementAgeChange={setMaleRetirementAge}
            onSave={handleSaveRetirement}
          />
        )}

        {activeTab === 'fixation' && (
          <FixationSettings
            pensionCeilings={pensionCeilings}
            isEditingCeilings={isEditingCeilings}
            editedCeilings={editedCeilings}
            exemptCapitalPercentages={exemptCapitalPercentages}
            isEditingPercentages={isEditingPercentages}
            editedPercentages={editedPercentages}
            onEditCeilings={handleEditCeilings}
            onSaveCeilings={handleSaveCeilings}
            onCancelCeilings={handleCancelCeilings}
            onCeilingChange={handleCeilingChange}
            onAddCeiling={handleAddCeiling}
            onEditPercentages={handleEditPercentages}
            onSavePercentages={handleSavePercentages}
            onCancelPercentages={handleCancelPercentages}
            onPercentageChange={handlePercentageChange}
            onAddPercentage={handleAddPercentage}
            idfPromoterTable={idfPromoterTable}
            isEditingIdfPromoterTable={isEditingIdfPromoterTable}
            editedIdfPromoterTable={editedIdfPromoterTable}
            onEditIdfPromoterTable={handleEditIdfPromoterTable}
            onSaveIdfPromoterTable={handleSaveIdfPromoterTable}
            onCancelIdfPromoterTable={handleCancelIdfPromoterTable}
            onIdfPromoterRowChange={handleIdfPromoterRowChange}
            onAddIdfPromoterRow={handleAddIdfPromoterRow}
          />
        )}
        
        {activeTab === 'scenarios' && <ScenariosSettings />}
        
        {activeTab === 'termination' && <TerminationSettings />}
        
        {activeTab === 'annuity' && <AnnuitySettings />}

        {activeTab === 'tax_calculation' && (
          <div className="system-settings-tax-doc-section">
            <h2 className="system-settings-tax-doc-title">
              תיעוד חישובי מס
            </h2>
            <TaxCalculationDocumentation />
          </div>
        )}

        {activeTab === 'health' && <SystemHealthMonitor />}

        {activeTab === 'public_chat' && <PublicChatSettings />}
      </div>
    </div>
  );
};

export default SystemSettings;
