import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Grid,
  TextField,
  Typography,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip
} from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface Scenario {
  id: number;
  scenario_name: string;
  apply_tax_planning: boolean;
  apply_capitalization: boolean;
  apply_exemption_shield: boolean;
  created_at: string;
}

interface ScenarioResult {
  id: number;
  scenario_name: string;
  client_id: number;
  apply_tax_planning: boolean;
  apply_capitalization: boolean;
  apply_exemption_shield: boolean;
  seniority_years: number;
  grant_gross: number;
  grant_exempt: number;
  grant_tax: number;
  grant_net: number;
  pension_monthly: number;
  indexation_factor: number;
  cashflow: Array<{
    date: string;
    inflow: number;
    outflow: number;
    net: number;
  }>;
  created_at: string;
}

interface ScenariosProps {
  clientId: number;
}

const Scenarios: React.FC<ScenariosProps> = ({ clientId }) => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarios, setSelectedScenarios] = useState<ScenarioResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    scenario_name: '',
    planned_termination_date: '',
    monthly_expenses: '',
    apply_tax_planning: false,
    apply_capitalization: false,
    apply_exemption_shield: false,
    other_parameters: {}
  });

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

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

  const createScenario = async () => {
    try {
      setLoading(true);
      setError(null);
      
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
        setShowCreateForm(false);
        setFormData({
          scenario_name: '',
          planned_termination_date: '',
          monthly_expenses: '',
          apply_tax_planning: false,
          apply_capitalization: false,
          apply_exemption_shield: false,
          other_parameters: {}
        });
        loadScenarios();
      } else {
        const errorData = await response.json();
        setError(`Failed to create scenario: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      setError('Error creating scenario: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runScenario = async (scenarioId: number) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${apiBaseUrl}/api/v1/scenarios/${scenarioId}/run`, {
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

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('he-IL');
  };

  const prepareCashflowData = () => {
    if (selectedScenarios.length === 0) return [];
    
    const allMonths = selectedScenarios[0]?.cashflow?.map(cf => cf.date) || [];
    
    return allMonths.map(month => {
      const dataPoint: any = { month: formatDate(month) };
      
      selectedScenarios.forEach((scenario, index) => {
        const cfPoint = scenario.cashflow.find(cf => cf.date === month);
        if (cfPoint) {
          dataPoint[`scenario_${scenario.id}_net`] = cfPoint.net;
        }
      });
      
      return dataPoint;
    });
  };

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

      {/* Create Scenario Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">יצירת תרחיש חדש</Typography>
            <Button
              variant="contained"
              onClick={() => setShowCreateForm(!showCreateForm)}
              disabled={loading}
            >
              {showCreateForm ? 'ביטול' : 'תרחיש חדש'}
            </Button>
          </Box>

          {showCreateForm && (
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="שם התרחיש"
                  value={formData.scenario_name}
                  onChange={(e) => setFormData({ ...formData, scenario_name: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="תאריך פרישה מתוכנן"
                  type="date"
                  value={formData.planned_termination_date}
                  onChange={(e) => setFormData({ ...formData, planned_termination_date: e.target.value })}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="הוצאות חודשיות"
                  type="number"
                  value={formData.monthly_expenses}
                  onChange={(e) => setFormData({ ...formData, monthly_expenses: e.target.value })}
                />
              </Grid>
              <Grid item xs={12}>
                <Typography variant="subtitle2" gutterBottom>
                  דגלי תכנון:
                </Typography>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.apply_tax_planning}
                      onChange={(e) => setFormData({ ...formData, apply_tax_planning: e.target.checked })}
                    />
                  }
                  label="תכנון מס"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.apply_capitalization}
                      onChange={(e) => setFormData({ ...formData, apply_capitalization: e.target.checked })}
                    />
                  }
                  label="קפיטליזציה"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.apply_exemption_shield}
                      onChange={(e) => setFormData({ ...formData, apply_exemption_shield: e.target.checked })}
                    />
                  }
                  label="מגן פטור"
                />
              </Grid>
              <Grid item xs={12}>
                <Button
                  variant="contained"
                  onClick={createScenario}
                  disabled={loading || !formData.scenario_name}
                  sx={{ mr: 1 }}
                >
                  יצירת תרחיש
                </Button>
              </Grid>
            </Grid>
          )}
        </CardContent>
      </Card>

      {/* Scenarios List */}
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
                          onClick={() => runScenario(scenario.id)}
                          disabled={loading}
                        >
                          הרץ תרחיש
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Results Section */}
      {selectedScenarios.length > 0 && (
        <>
          {/* Summary Results Table */}
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

          {/* Cashflow Chart */}
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
        </>
      )}
    </Box>
  );
};

export default Scenarios;
