import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Card,
  CardContent,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Chip,
} from '@mui/material';
import { Add as AddIcon, PlayArrow as RunIcon, Save as SaveIcon } from '@mui/icons-material';
import FormField from '../components/forms/FormField';
import { scenarioApi, calculationApi, handleApiError } from '../lib/api';
import { formatDateToDDMMYYYY } from '../utils/dateUtils';
import { useCaseDetection } from '../lib/case-detection';

interface Scenario {
  id?: number;
  name: string;
  description: string;
  calculation_results?: any;
  created_at?: string;
  updated_at?: string;
}

const Scenarios: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { clientData } = useCaseDetection();
  
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [currentScenario, setCurrentScenario] = useState<Scenario>({
    name: '',
    description: '',
  });
  const [calculatingScenario, setCalculatingScenario] = useState<number | null>(null);

  useEffect(() => {
    if (clientData?.id) {
      loadScenarios();
    }
  }, [clientData]);

  const loadScenarios = async () => {
    if (!clientData?.id) return;

    setLoading(true);
    try {
      const response = await scenarioApi.list(clientData.id);
      setScenarios(response);
    } catch (error) {
      setError(handleApiError(error));
    } finally {
      setLoading(false);
    }
  };

  const handleCreateScenario = () => {
    setCurrentScenario({ name: '', description: '' });
    setDialogOpen(true);
  };

  const handleSaveScenario = async () => {
    if (!clientData?.id || !currentScenario.name.trim()) {
      return;
    }

    setLoading(true);
    try {
      await scenarioApi.create(clientData.id, currentScenario);
      setDialogOpen(false);
      setCurrentScenario({ name: '', description: '' });
      await loadScenarios();
    } catch (error) {
      setError(handleApiError(error));
    } finally {
      setLoading(false);
    }
  };

  const handleRunCalculation = async (scenario?: Scenario) => {
    if (!clientData?.id) return;

    const scenarioId = scenario?.id;
    setCalculatingScenario(scenarioId || 0);
    setError('');

    try {
      const request = {
        client_id: clientData.id,
        scenario_name: scenario?.name,
        save_scenario: !!scenario,
      };

      const result = await calculationApi.calculate(request);
      
      // Navigate to results with the calculation data
      navigate('/results', { state: { calculationResult: result, scenario } });

    } catch (error) {
      setError(handleApiError(error));
    } finally {
      setCalculatingScenario(null);
    }
  };

  const handleFieldChange = (field: keyof Scenario) => (value: string) => {
    setCurrentScenario(prev => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    // Run a quick calculation without saving scenario
    handleRunCalculation();
  };

  const handlePrevious = () => {
    navigate('/tax-admin');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.scenarios')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        צור ונהל תרחישי תכנון פרישה שונים. כל תרחיש יכול לכלול הנחות שונות לבדיקת אלטרנטיבות.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Quick Calculation */}
      <Paper className="form-section">
        <Typography variant="h6" gutterBottom>
          חישוב מהיר
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          הרץ חישוב מהיר על בסיס הנתונים שהוזנו ללא שמירת תרחיש.
        </Typography>
        <Button
          variant="contained"
          startIcon={calculatingScenario === 0 ? <CircularProgress size={20} /> : <RunIcon />}
          onClick={() => handleRunCalculation()}
          disabled={calculatingScenario !== null}
          size="large"
        >
          {calculatingScenario === 0 ? 'מחשב...' : 'הרץ חישוב מהיר'}
        </Button>
      </Paper>

      {/* Saved Scenarios */}
      <Paper className="form-section">
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">
            תרחישים שמורים ({scenarios.length})
          </Typography>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleCreateScenario}
          >
            צור תרחיש חדש
          </Button>
        </Box>

        {loading && scenarios.length === 0 ? (
          <Box textAlign="center" py={4}>
            <CircularProgress />
          </Box>
        ) : scenarios.length === 0 ? (
          <Box textAlign="center" py={4}>
            <Typography variant="body2" color="text.secondary">
              אין תרחישים שמורים. צור תרחיש חדש כדי לשמור הנחות חישוב ספציפיות.
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {scenarios.map((scenario) => (
              <Grid item xs={12} md={6} key={scenario.id}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      {scenario.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {scenario.description || 'ללא תיאור'}
                    </Typography>
                    {scenario.created_at && (
                      <Typography variant="caption" color="text.secondary">
                        נוצר: {formatDateToDDMMYYYY(scenario.created_at)}
                      </Typography>
                    )}
                    {scenario.calculation_results && (
                      <Chip 
                        label="יש תוצאות חישוב" 
                        color="success" 
                        size="small" 
                        sx={{ mt: 1 }}
                      />
                    )}
                  </CardContent>
                  <CardActions>
                    <Button
                      size="small"
                      startIcon={calculatingScenario === scenario.id ? <CircularProgress size={16} /> : <RunIcon />}
                      onClick={() => handleRunCalculation(scenario)}
                      disabled={calculatingScenario !== null}
                    >
                      {calculatingScenario === scenario.id ? 'מחשב...' : 'הרץ חישוב'}
                    </Button>
                    {scenario.calculation_results && (
                      <Button
                        size="small"
                        onClick={() => navigate('/results', { 
                          state: { 
                            calculationResult: scenario.calculation_results, 
                            scenario 
                          } 
                        })}
                      >
                        צפה בתוצאות
                      </Button>
                    )}
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Paper>

      {/* Navigation */}
      <Box className="form-actions">
        <Button
          variant="outlined"
          onClick={handlePrevious}
        >
          {t('common.previous')}
        </Button>
        <Button
          variant="contained"
          onClick={handleNext}
          disabled={calculatingScenario !== null}
        >
          {calculatingScenario !== null ? 'מחשב...' : 'חשב תוצאות'}
        </Button>
      </Box>

      {/* Create Scenario Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>צור תרחיש חדש</DialogTitle>
        <DialogContent>
          <Box pt={1}>
            <FormField
              label="שם התרחיש"
              value={currentScenario.name}
              onChange={handleFieldChange('name')}
              required
              placeholder="לדוגמה: תרחיש בסיסי, פרישה מוקדמת"
            />
            <FormField
              label="תיאור התרחיש"
              value={currentScenario.description}
              onChange={handleFieldChange('description')}
              multiline
              rows={3}
              placeholder="תיאור קצר של ההנחות והמטרות של התרחיש"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>
            ביטול
          </Button>
          <Button 
            onClick={handleSaveScenario} 
            variant="contained"
            disabled={!currentScenario.name.trim() || loading}
            startIcon={loading ? <CircularProgress size={20} /> : <SaveIcon />}
          >
            {loading ? 'שומר...' : 'שמור תרחיש'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Information */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'info.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          מידע על תרחישים
        </Typography>
        <Typography variant="body2">
          • <strong>חישוב מהיר:</strong> חישוב חד-פעמי ללא שמירה<br/>
          • <strong>תרחישים שמורים:</strong> שמירת הנחות ותוצאות להשוואה עתידית<br/>
          • ניתן להריץ מספר תרחישים ולהשוות ביניהם במסך התוצאות<br/>
          • כל תרחיש שומר את ההנחות והתוצאות לעיון עתידי
        </Typography>
      </Paper>
    </Box>
  );
};

export default Scenarios;
