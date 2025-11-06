import { useState } from 'react';
import { ScenarioFormData, INITIAL_FORM_STATE } from '../types/scenario';

export const useScenarioForm = (
  clientId: number,
  onSuccess: () => void,
  onError: (error: string) => void
) => {
  const [formData, setFormData] = useState<ScenarioFormData>(INITIAL_FORM_STATE);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(false);

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

  const handleFormChange = (field: keyof ScenarioFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const resetForm = () => {
    setFormData(INITIAL_FORM_STATE);
    setShowCreateForm(false);
  };

  const createScenario = async () => {
    try {
      setLoading(true);
      onError('');
      
      const response = await fetch(`${apiBaseUrl}/clients/${clientId}/scenarios`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...formData,
          monthly_expenses: formData.monthly_expenses ? parseFloat(formData.monthly_expenses) : null,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Scenario created:', result);
        resetForm();
        onSuccess();
      } else {
        const errorData = await response.json();
        onError(`Failed to create scenario: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      onError('Error creating scenario: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggleForm = () => {
    setShowCreateForm(prev => !prev);
  };

  return {
    formData,
    showCreateForm,
    loading,
    handleFormChange,
    createScenario,
    toggleForm,
    resetForm,
    setFormData
  };
};
