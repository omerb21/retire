import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import {
  ResponsiveContainer,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Bar,
} from 'recharts';
import './RetirementScenarioCharts.css';

interface RetirementScenarioSummary {
  scenario_name: string;
  total_pension_monthly: number;
  total_capital: number;
  total_additional_income_monthly: number;
  estimated_npv: number;
}

interface RetirementScenariosMap {
  scenario_1_max_pension: RetirementScenarioSummary;
  scenario_2_max_capital: RetirementScenarioSummary;
  scenario_3_max_npv: RetirementScenarioSummary;
}

interface RetirementScenarioChartsProps {
  scenarios: RetirementScenariosMap;
  formatCurrency: (amount: number) => string;
}

const RetirementScenarioCharts: React.FC<RetirementScenarioChartsProps> = ({
  scenarios,
  formatCurrency,
}) => {
  if (!scenarios) {
    return null;
  }

  const items: RetirementScenarioSummary[] = [
    scenarios.scenario_1_max_pension,
    scenarios.scenario_2_max_capital,
    scenarios.scenario_3_max_npv,
  ].filter(Boolean) as RetirementScenarioSummary[];

  if (items.length === 0) {
    return null;
  }

  const incomeData = items.map((s) => ({
    name: s.scenario_name,
    pensionMonthly: s.total_pension_monthly || 0,
    additionalMonthly: s.total_additional_income_monthly || 0,
  }));

  const currencyFormatter = (value: number) => formatCurrency(value || 0);

  return (
    <div className="retirement-charts-container">
      <Card className="retirement-chart-card">
        <CardContent>
          <Typography className="retirement-chart-title" gutterBottom>
            השוואת הכנסות חודשיות בין תרחישים
          </Typography>
          <div className="retirement-chart-wrapper">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={incomeData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip formatter={(value) => currencyFormatter(value as number)} />
                <Legend />
                <Bar dataKey="pensionMonthly" name="קצבה חודשית" fill="#007bff" />
                <Bar dataKey="additionalMonthly" name="הכנסה נוספת חודשית" fill="#28a745" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default RetirementScenarioCharts;
