import React from 'react';
import { Button, TableCell, TableRow, Chip } from '@mui/material';
import { Scenario } from '../../../types/scenario';

interface ScenarioItemProps {
  scenario: Scenario;
  loading: boolean;
  onRun: (scenarioId: number) => void;
  formatDate: (dateString: string) => string;
}

export const ScenarioItem: React.FC<ScenarioItemProps> = ({
  scenario,
  loading,
  onRun,
  formatDate
}) => {
  return (
    <TableRow key={scenario.id}>
      <TableCell>{scenario.scenario_name}</TableCell>
      <TableCell>
        {scenario.apply_tax_planning && <Chip label="תכנון מס" size="small" sx={{ mr: 0.5 }} />}
        {scenario.apply_capitalization && <Chip label="קפיטליזציה" size="small" sx={{ mr: 0.5 }} />}
        {scenario.apply_exemption_shield && <Chip label="מגן פטור" size="small" />}
      </TableCell>
      <TableCell>{formatDate(scenario.created_at)}</TableCell>
      <TableCell>
        <Button
          variant="outlined"
          size="small"
          onClick={() => onRun(scenario.id)}
          disabled={loading}
        >
          הרץ תרחיש
        </Button>
      </TableCell>
    </TableRow>
  );
};
