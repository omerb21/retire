import React from 'react';
import { Box, Typography, Alert } from '@mui/material';
import { ScenariosProps } from '../../types/scenario';
import { useScenarios } from '../../hooks/useScenarios';
import { useScenarioForm } from '../../hooks/useScenarioForm';
import { ScenarioForm } from '../../components/scenarios/ScenarioForm/ScenarioForm';
import { ScenarioList } from '../../components/scenarios/ScenarioList/ScenarioList';
import { ScenarioResults } from '../../components/scenarios/ScenarioResults/ScenarioResults';
import { ScenarioChart } from '../../components/scenarios/ScenarioChart/ScenarioChart';
import { formatDateToDDMMYYYY } from '../../utils/dateUtils';

const Scenarios: React.FC<ScenariosProps> = ({ clientId }) => {
  const {
    scenarios,
    selectedScenarios,
    loading: scenariosLoading,
    error,
    setError,
    loadScenarios,
    runScenario
  } = useScenarios(clientId);

  const {
    formData,
    showCreateForm,
    loading: formLoading,
    handleFormChange,
    createScenario,
    toggleForm
  } = useScenarioForm(clientId, loadScenarios, setError);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return formatDateToDDMMYYYY(dateString);
  };

  const loading = scenariosLoading || formLoading;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        תרחישי חישוב
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <ScenarioForm
        formData={formData}
        showCreateForm={showCreateForm}
        loading={loading}
        onFormChange={handleFormChange}
        onSubmit={createScenario}
        onToggleForm={toggleForm}
      />

      <ScenarioList
        scenarios={scenarios}
        loading={loading}
        onRunScenario={runScenario}
        formatDate={formatDate}
      />

      <ScenarioResults
        selectedScenarios={selectedScenarios}
        formatCurrency={formatCurrency}
      />

      <ScenarioChart
        selectedScenarios={selectedScenarios}
        formatCurrency={formatCurrency}
        formatDate={formatDate}
      />
    </Box>
  );
};

export default Scenarios;
