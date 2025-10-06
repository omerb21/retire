import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { reportsApi } from '../lib/api';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Card,
  CardContent,
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { performSanityChecks, formatCurrency } from '../lib/validation';
import { useCaseDetection } from '../lib/case-detection';
import { reportsApi } from '../lib/api';

interface CalculationResult {
  client_id: number;
  scenario_name?: string;
  case_number: number;
  assumptions: any;
  cash_flow: Array<{
    year: number;
    month: number;
    gross_income: number;
    tax_amount: number;
    net_income: number;
    asset_balances: any;
  }>;
  summary: {
    total_gross: number;
    total_tax: number;
    total_net: number;
    final_balances: any;
  };
}

const Results: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { currentCase, isDevMode } = useCaseDetection();
  
  const [tabValue, setTabValue] = useState(0);
  const [calculationResult, setCalculationResult] = useState<CalculationResult | null>(null);
  const [scenario, setScenario] = useState<any>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    // Get calculation result from navigation state
    const state = location.state as any;
    if (state?.calculationResult) {
      setCalculationResult(state.calculationResult);
      setScenario(state.scenario);
      
      // Perform sanity checks
      const sanityWarnings = performSanityChecks(state.calculationResult);
      setWarnings(sanityWarnings);
    }
  }, [location.state]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handlePrevious = () => {
    navigate('/scenarios');
  };

  const handleNewCalculation = () => {
    navigate('/scenarios');
  };

  // Type definitions for scenarios
  type ScenarioLite = { id: number; name?: string };
  
  // Get scenario IDs for export (up to 3 scenarios)
  const getScenarioIdsForExport = (): number[] => {
    try {
      // If we have scenario data, use it; otherwise use calculation result client_id as fallback
      const scenarios: ScenarioLite[] = scenario ? [{ id: scenario.id || 1 }] : [];
      const visible = scenarios?.map(s => s.id) ?? [];
      return visible.slice(0, 3);
    } catch {
      return [];
    }
  };

  const handleExportPdf = async () => {
    const scenarioIds = getScenarioIdsForExport();
    const clientId: number | undefined = calculationResult?.client_id;
    
    if (!clientId || !scenarioIds.length) {
      // Don't block - server returns proper error messages (404/422)
      // But UX: show simple alert to user
      alert('אין תרחישים זמינים לייצוא.');
      return;
    }
    
    try {
      setDownloading(true);
      await reportsApi.exportReportPdf(clientId, scenarioIds);
      // Download already handled inside api.ts
    } catch (err) {
      console.error('PDF export failed', err);
      alert('ייצוא PDF נכשל. נסו מחדש.');
    } finally {
      setDownloading(false);
    }
  };

  if (!calculationResult) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          {t('nav.results')}
        </Typography>
        <Alert severity="info">
          אין תוצאות חישוב להצגה. אנא הרץ חישוב מהמסך הקודם.
        </Alert>
        <Button variant="contained" onClick={handlePrevious} sx={{ mt: 2 }}>
          חזור לתרחישים
        </Button>
      </Box>
    );
  }

  // Prepare chart data
  const cashFlowData = calculationResult.cash_flow.map(item => ({
    period: `${item.year}/${item.month.toString().padStart(2, '0')}`,
    year: item.year,
    month: item.month,
    'הכנסה ברוטו': item.gross_income,
    'מס': item.tax_amount,
    'הכנסה נטו': item.net_income,
  }));

  // Aggregate yearly data for better visualization
  const yearlyData = calculationResult.cash_flow.reduce((acc: any[], item) => {
    const existingYear = acc.find(y => y.year === item.year);
    if (existingYear) {
      existingYear['הכנסה ברוטו'] += item.gross_income;
      existingYear['מס'] += item.tax_amount;
      existingYear['הכנסה נטו'] += item.net_income;
    } else {
      acc.push({
        year: item.year,
        'הכנסה ברוטו': item.gross_income,
        'מס': item.tax_amount,
        'הכנסה נטו': item.net_income,
      });
    }
    return acc;
  }, []);

  // Summary pie chart data
  const summaryPieData = [
    { name: 'הכנסה נטו', value: calculationResult.summary.total_net, color: '#4caf50' },
    { name: 'מס', value: calculationResult.summary.total_tax, color: '#f44336' },
  ];

  const COLORS = ['#4caf50', '#f44336', '#2196f3', '#ff9800', '#9c27b0'];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.results')}
      </Typography>

      {/* Scenario Info */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={6}>
            <Typography variant="h6">
              {scenario?.name || 'חישוב מהיר'}
            </Typography>
            <Typography variant="body2">
              {scenario?.description || 'תוצאות חישוב על בסיס הנתונים שהוזנו'}
            </Typography>
          </Grid>
          <Grid item xs={12} md={6} textAlign="right">
            <Chip 
              label={t(`case.${calculationResult.case_number}`)} 
              color="secondary" 
              sx={{ mb: 1 }}
            />
            <Typography variant="body2">
              תאריך חישוב: {new Date().toLocaleDateString('he-IL')}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Warnings */}
      {warnings.length > 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('qa.warning')}
          </Typography>
          <ul style={{ margin: 0, paddingRight: 20 }}>
            {warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </Alert>
      )}

      {/* Dev Mode Info */}
      {isDevMode && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: 'warning.light' }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('dev.debugValues')}
          </Typography>
          <Typography variant="body2" component="pre" sx={{ fontSize: '0.8rem' }}>
            {JSON.stringify(calculationResult.assumptions, null, 2)}
          </Typography>
        </Paper>
      )}

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent textAlign="center">
              <Typography variant="h4" color="primary">
                {formatCurrency(calculationResult.summary.total_gross)}
              </Typography>
              <Typography variant="subtitle1">
                סך הכנסה ברוטו
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent textAlign="center">
              <Typography variant="h4" color="error">
                {formatCurrency(calculationResult.summary.total_tax)}
              </Typography>
              <Typography variant="subtitle1">
                סך מס
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent textAlign="center">
              <Typography variant="h4" color="success.main">
                {formatCurrency(calculationResult.summary.total_net)}
              </Typography>
              <Typography variant="subtitle1">
                סך הכנסה נטו
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs for different views */}
      <Paper>
        <Tabs value={tabValue} onChange={handleTabChange} variant="fullWidth">
          <Tab label="גרף תזרים שנתי" />
          <Tab label="גרף תזרים חודשי" />
          <Tab label="טבלת פירוט" />
          <Tab label="סיכום והשוואה" />
        </Tabs>

        {/* Yearly Cash Flow Chart */}
        {tabValue === 0 && (
          <Box p={3}>
            <Typography variant="h6" gutterBottom>
              תזרים מזומנים שנתי
            </Typography>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={yearlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis tickFormatter={(value) => `₪${(value / 1000).toFixed(0)}K`} />
                <Tooltip 
                  formatter={(value: number) => [formatCurrency(value), '']}
                  labelFormatter={(label) => `שנת ${label}`}
                />
                <Legend />
                <Bar dataKey="הכנסה ברוטו" fill="#2196f3" />
                <Bar dataKey="מס" fill="#f44336" />
                <Bar dataKey="הכנסה נטו" fill="#4caf50" />
              </BarChart>
            </ResponsiveContainer>
          </Box>
        )}

        {/* Monthly Cash Flow Chart */}
        {tabValue === 1 && (
          <Box p={3}>
            <Typography variant="h6" gutterBottom>
              תזרים מזומנים חודשי (12-24 חודשים ראשונים)
            </Typography>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={cashFlowData.slice(0, 24)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" />
                <YAxis tickFormatter={(value) => `₪${(value / 1000).toFixed(0)}K`} />
                <Tooltip 
                  formatter={(value: number) => [formatCurrency(value), '']}
                />
                <Legend />
                <Line type="monotone" dataKey="הכנסה ברוטו" stroke="#2196f3" strokeWidth={2} />
                <Line type="monotone" dataKey="מס" stroke="#f44336" strokeWidth={2} />
                <Line type="monotone" dataKey="הכנסה נטו" stroke="#4caf50" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Box>
        )}

        {/* Detailed Table */}
        {tabValue === 2 && (
          <Box p={3}>
            <Typography variant="h6" gutterBottom>
              פירוט תזרים מזומנים
            </Typography>
            <TableContainer sx={{ maxHeight: 400 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>תקופה</TableCell>
                    <TableCell align="right">הכנסה ברוטו</TableCell>
                    <TableCell align="right">מס</TableCell>
                    <TableCell align="right">הכנסה נטו</TableCell>
                    <TableCell align="right">יתרות נכסים</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {calculationResult.cash_flow.slice(0, 60).map((item, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        {item.month}/{item.year}
                      </TableCell>
                      <TableCell align="right" className="hebrew-number">
                        {formatCurrency(item.gross_income)}
                      </TableCell>
                      <TableCell align="right" className="hebrew-number">
                        {formatCurrency(item.tax_amount)}
                      </TableCell>
                      <TableCell align="right" className="hebrew-number">
                        {formatCurrency(item.net_income)}
                      </TableCell>
                      <TableCell align="right" className="hebrew-number">
                        {item.asset_balances ? 
                          formatCurrency(Object.values(item.asset_balances).reduce((sum: number, val: any) => sum + (val || 0), 0)) :
                          '₪0'
                        }
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* Summary and Comparison */}
        {tabValue === 3 && (
          <Box p={3}>
            <Typography variant="h6" gutterBottom>
              סיכום והשוואה
            </Typography>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  התפלגות הכנסה ומס
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={summaryPieData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {summaryPieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                  </PieChart>
                </ResponsiveContainer>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  מדדי ביצועים עיקריים
                </Typography>
                <Box>
                  <Typography variant="body2" gutterBottom>
                    <strong>שיעור מס ממוצע:</strong> {
                      ((calculationResult.summary.total_tax / calculationResult.summary.total_gross) * 100).toFixed(1)
                    }%
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>הכנסה נטו חודשית ממוצעת:</strong> {
                      formatCurrency(calculationResult.summary.total_net / calculationResult.cash_flow.length)
                    }
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>תקופת חישוב:</strong> {calculationResult.cash_flow.length} חודשים
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>מקרה:</strong> {t(`case.${calculationResult.case_number}`)}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Box>
        )}
      </Paper>

      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
        <Button
          variant="outlined"
          onClick={handlePrevious}
        >
          {t('common.previous')}
        </Button>
        <Button
          variant="contained"
          onClick={handleNewCalculation}
        >
          חישוב חדש
        </Button>
        <Button
          variant="contained"
          color="secondary"
          onClick={handleExportPdf}
          disabled={downloading}
          title="ייצוא PDF"
        >
          {downloading ? 'מכין PDF…' : 'ייצוא PDF'}
        </Button>
      </Box>

      {/* Information */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'info.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          הסבר על התוצאות
        </Typography>
        <Typography variant="body2">
          • <strong>תזרים שנתי:</strong> מציג את סך ההכנסות והמסים לפי שנים<br/>
          • <strong>תזרים חודשי:</strong> מציג פירוט חודשי לתקופה הראשונה<br/>
          • <strong>טבלת פירוט:</strong> נתונים מפורטים לכל חודש<br/>
          • <strong>סיכום:</strong> מדדי ביצועים ומבט כללי על התוצאות<br/>
          • כל הסכומים מוצגים במונחי שקלים נומינליים
        </Typography>
      </Paper>
    </Box>
  );
};

export default Results;
