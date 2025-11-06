import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ScenarioResult } from '../../../types/scenario';

interface ScenarioChartProps {
  selectedScenarios: ScenarioResult[];
  formatCurrency: (amount: number) => string;
  formatDate: (dateString: string) => string;
}

export const ScenarioChart: React.FC<ScenarioChartProps> = ({
  selectedScenarios,
  formatCurrency,
  formatDate
}) => {
  if (selectedScenarios.length === 0) {
    return null;
  }

  const prepareCashflowData = () => {
    if (selectedScenarios.length === 0) return [];
    
    const allMonths = selectedScenarios[0]?.cashflow?.map(cf => cf.date) || [];
    
    return allMonths.map(month => {
      const dataPoint: any = { month: formatDate(month) };
      
      selectedScenarios.forEach((scenario) => {
        const cfPoint = scenario.cashflow.find(cf => cf.date === month);
        if (cfPoint) {
          dataPoint[`scenario_${scenario.id}_net`] = cfPoint.net;
        }
      });
      
      return dataPoint;
    });
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          תזרים מזומנים - השוואת תרחישים
        </Typography>
        
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={prepareCashflowData()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <YAxis />
            <Tooltip formatter={(value) => formatCurrency(value as number)} />
            <Legend />
            {selectedScenarios.map((scenario, index) => (
              <Line
                key={scenario.id}
                type="monotone"
                dataKey={`scenario_${scenario.id}_net`}
                stroke={`hsl(${index * 120}, 70%, 50%)`}
                name={scenario.scenario_name}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
