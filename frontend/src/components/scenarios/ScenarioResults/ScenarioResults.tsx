import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper
} from '@mui/material';
import { ScenarioResult } from '../../../types/scenario';

interface ScenarioResultsProps {
  selectedScenarios: ScenarioResult[];
  formatCurrency: (amount: number) => string;
}

export const ScenarioResults: React.FC<ScenarioResultsProps> = ({
  selectedScenarios,
  formatCurrency
}) => {
  if (selectedScenarios.length === 0) {
    return null;
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          תוצאות תרחישים
        </Typography>
        
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>תרחיש</TableCell>
                <TableCell>שנות ותק</TableCell>
                <TableCell>מענק ברוטו</TableCell>
                <TableCell>מענק נטו</TableCell>
                <TableCell>קצבה חודשית</TableCell>
                <TableCell>מקדם הצמדה</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {selectedScenarios.map((result) => (
                <TableRow key={result.id}>
                  <TableCell>{result.scenario_name}</TableCell>
                  <TableCell>{result.seniority_years.toFixed(2)}</TableCell>
                  <TableCell>{formatCurrency(result.grant_gross)}</TableCell>
                  <TableCell>{formatCurrency(result.grant_net)}</TableCell>
                  <TableCell>{formatCurrency(result.pension_monthly)}</TableCell>
                  <TableCell>{result.indexation_factor.toFixed(3)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
};
