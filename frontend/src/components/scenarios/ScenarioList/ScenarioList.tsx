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
import { Scenario } from '../../../types/scenario';
import { ScenarioItem } from './ScenarioItem';

interface ScenarioListProps {
  scenarios: Scenario[];
  loading: boolean;
  onRunScenario: (scenarioId: number) => void;
  formatDate: (dateString: string) => string;
}

export const ScenarioList: React.FC<ScenarioListProps> = ({
  scenarios,
  loading,
  onRunScenario,
  formatDate
}) => {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          תרחישים קיימים
        </Typography>
        
        {scenarios.length === 0 ? (
          <Typography color="text.secondary">
            אין תרחישים קיימים
          </Typography>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>שם התרחיש</TableCell>
                  <TableCell>דגלי תכנון</TableCell>
                  <TableCell>תאריך יצירה</TableCell>
                  <TableCell>פעולות</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {scenarios.map((scenario) => (
                  <ScenarioItem
                    key={scenario.id}
                    scenario={scenario}
                    loading={loading}
                    onRun={onRunScenario}
                    formatDate={formatDate}
                  />
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
};
