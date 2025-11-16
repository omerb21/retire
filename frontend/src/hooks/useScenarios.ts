import { useState, useEffect } from 'react';
import { Scenario, ScenarioResult } from '../types/scenario';
import { API_BASE } from '../lib/api';

export const useScenarios = (clientId: number) => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarios, setSelectedScenarios] = useState<ScenarioResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiBaseUrl = API_BASE;

  useEffect(() => {
    loadScenarios();
  }, [clientId]);

  const loadScenarios = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${apiBaseUrl}/clients/${clientId}/scenarios`);
      if (response.ok) {
        const data = await response.json();
        setScenarios(data.scenarios || []);
      } else {
        setError('Failed to load scenarios');
      }
    } catch (err) {
      setError('Error loading scenarios: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runScenario = async (scenarioId: number) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${apiBaseUrl}/scenarios/${scenarioId}/run`, {
        method: 'POST',
      });

      if (response.ok) {
        const result = await response.json();
        setSelectedScenarios(prev => {
          const existing = prev.find(s => s.id === scenarioId);
          if (existing) {
            return prev.map(s => s.id === scenarioId ? result : s);
          } else {
            return [...prev, result];
          }
        });
      } else {
        const errorData = await response.json();
        setError(`Failed to run scenario: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      setError('Error running scenario: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return {
    scenarios,
    selectedScenarios,
    loading,
    error,
    setError,
    loadScenarios,
    runScenario
  };
};
