import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Tabs,
  Tab,
  Card,
  CardContent,
  IconButton,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon } from '@mui/icons-material';
import FormField from '../components/forms/FormField';

interface AdditionalIncome {
  id?: number;
  income_type: string;
  monthly_amount: string;
  indexation_rate: string;
  start_year: string;
  end_year: string;
}

interface CapitalAsset {
  id?: number;
  asset_type: string;
  current_value: string;
  annual_return: string;
  withdrawal_schedule: string;
}

const IncomeAssets: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  const [tabValue, setTabValue] = useState(0);
  const [additionalIncomes, setAdditionalIncomes] = useState<AdditionalIncome[]>([]);
  const [capitalAssets, setCapitalAssets] = useState<CapitalAsset[]>([]);
  const [isAddingIncome, setIsAddingIncome] = useState(false);
  const [isAddingAsset, setIsAddingAsset] = useState(false);
  
  const [currentIncome, setCurrentIncome] = useState<AdditionalIncome>({
    income_type: '',
    monthly_amount: '',
    indexation_rate: '',
    start_year: '',
    end_year: '',
  });

  const [currentAsset, setCurrentAsset] = useState<CapitalAsset>({
    asset_type: '',
    current_value: '',
    annual_return: '',
    withdrawal_schedule: '',
  });

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleIncomeFieldChange = (field: keyof AdditionalIncome) => (value: string) => {
    setCurrentIncome(prev => ({ ...prev, [field]: value }));
  };

  const handleAssetFieldChange = (field: keyof CapitalAsset) => (value: string) => {
    setCurrentAsset(prev => ({ ...prev, [field]: value }));
  };

  const handleAddIncome = () => {
    setIsAddingIncome(true);
    setCurrentIncome({
      income_type: '',
      monthly_amount: '',
      indexation_rate: '',
      start_year: '',
      end_year: '',
    });
  };

  const handleSaveIncome = () => {
    setAdditionalIncomes(prev => [...prev, { ...currentIncome, id: Date.now() }]);
    setIsAddingIncome(false);
  };

  const handleCancelIncome = () => {
    setIsAddingIncome(false);
  };

  const handleDeleteIncome = (index: number) => {
    setAdditionalIncomes(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleAddAsset = () => {
    setIsAddingAsset(true);
    setCurrentAsset({
      asset_type: '',
      current_value: '',
      annual_return: '',
      withdrawal_schedule: '',
    });
  };

  const handleSaveAsset = () => {
    setCapitalAssets(prev => [...prev, { ...currentAsset, id: Date.now() }]);
    setIsAddingAsset(false);
  };

  const handleCancelAsset = () => {
    setIsAddingAsset(false);
  };

  const handleDeleteAsset = (index: number) => {
    setCapitalAssets(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleNext = () => {
    navigate('/tax-admin');
  };

  const handlePrevious = () => {
    navigate('/pensions');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.incomeAssets')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        הגדר הכנסות נוספות ונכסי הון שישפיעו על התכנון הפיננסי לפרישה.
      </Typography>

      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant="fullWidth">
          <Tab label="הכנסות נוספות" />
          <Tab label="נכסי הון" />
        </Tabs>

        {/* Additional Income Tab */}
        {tabValue === 0 && (
          <Box p={3}>
            <Typography variant="h6" gutterBottom>
              הכנסות נוספות
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              הכנסות חודשיות נוספות כמו דמי שכירות, דיבידנדים, או הכנסות מעבודה חלקית.
            </Typography>

            {/* List of existing incomes */}
            {additionalIncomes.length > 0 && (
              <Grid container spacing={2} sx={{ mb: 3 }}>
                {additionalIncomes.map((income, index) => (
                  <Grid item xs={12} md={6} key={income.id || index}>
                    <Card>
                      <CardContent>
                        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                          <Box flex={1}>
                            <Typography variant="subtitle1" fontWeight="bold">
                              {income.income_type}
                            </Typography>
                            <Typography variant="body2">
                              ₪{parseFloat(income.monthly_amount).toLocaleString()} לחודש
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {income.start_year} - {income.end_year || 'ללא הגבלה'}
                            </Typography>
                            {income.indexation_rate && (
                              <Typography variant="body2" color="text.secondary">
                                הצמדה: {income.indexation_rate}% שנתי
                              </Typography>
                            )}
                          </Box>
                          <IconButton onClick={() => handleDeleteIncome(index)} size="small" color="error">
                            <DeleteIcon />
                          </IconButton>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}

            {/* Add income form */}
            {isAddingIncome && (
              <Paper sx={{ p: 3, mb: 3, bgcolor: 'grey.50' }}>
                <Typography variant="subtitle1" gutterBottom>
                  הוספת הכנסה נוספת
                </Typography>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <FormField
                      label="סוג ההכנסה"
                      value={currentIncome.income_type}
                      onChange={handleIncomeFieldChange('income_type')}
                      placeholder="לדוגמה: דמי שכירות, דיבידנדים"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <FormField
                      label="סכום חודשי (₪)"
                      value={currentIncome.monthly_amount}
                      onChange={handleIncomeFieldChange('monthly_amount')}
                      type="number"
                      placeholder="5000"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <FormField
                      label="שיעור הצמדה שנתי (%)"
                      value={currentIncome.indexation_rate}
                      onChange={handleIncomeFieldChange('indexation_rate')}
                      type="number"
                      placeholder="2.5"
                      helperText="אופציונלי - הצמדה למדד המחירים"
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <FormField
                      label="שנת התחלה"
                      value={currentIncome.start_year}
                      onChange={handleIncomeFieldChange('start_year')}
                      type="number"
                      placeholder="2024"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <FormField
                      label="שנת סיום"
                      value={currentIncome.end_year}
                      onChange={handleIncomeFieldChange('end_year')}
                      type="number"
                      placeholder="2040"
                      helperText="אופציונלי - השאר ריק להכנסה קבועה"
                    />
                  </Grid>
                </Grid>
                <Box display="flex" gap={2} mt={2}>
                  <Button variant="contained" onClick={handleSaveIncome}>
                    שמור
                  </Button>
                  <Button variant="outlined" onClick={handleCancelIncome}>
                    ביטול
                  </Button>
                </Box>
              </Paper>
            )}

            {!isAddingIncome && (
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleAddIncome}
              >
                הוסף הכנסה נוספת
              </Button>
            )}
          </Box>
        )}

        {/* Capital Assets Tab */}
        {tabValue === 1 && (
          <Box p={3}>
            <Typography variant="h6" gutterBottom>
              נכסי הון
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              נכסים כמו דירות להשכרה, תיק השקעות, או נכסים אחרים שיניבו הכנסה או יימכרו בפרישה.
            </Typography>

            {/* List of existing assets */}
            {capitalAssets.length > 0 && (
              <Grid container spacing={2} sx={{ mb: 3 }}>
                {capitalAssets.map((asset, index) => (
                  <Grid item xs={12} md={6} key={asset.id || index}>
                    <Card>
                      <CardContent>
                        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                          <Box flex={1}>
                            <Typography variant="subtitle1" fontWeight="bold">
                              {asset.asset_type}
                            </Typography>
                            <Typography variant="body2">
                              ערך נוכחי: ₪{parseFloat(asset.current_value).toLocaleString()}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              תשואה שנתית: {asset.annual_return}%
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              לוח משיכות: {asset.withdrawal_schedule}
                            </Typography>
                          </Box>
                          <IconButton onClick={() => handleDeleteAsset(index)} size="small" color="error">
                            <DeleteIcon />
                          </IconButton>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}

            {/* Add asset form */}
            {isAddingAsset && (
              <Paper sx={{ p: 3, mb: 3, bgcolor: 'grey.50' }}>
                <Typography variant="subtitle1" gutterBottom>
                  הוספת נכס הון
                </Typography>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <FormField
                      label="סוג הנכס"
                      value={currentAsset.asset_type}
                      onChange={handleAssetFieldChange('asset_type')}
                      placeholder="לדוגמה: דירה להשכרה, תיק השקעות"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <FormField
                      label="ערך נוכחי (₪)"
                      value={currentAsset.current_value}
                      onChange={handleAssetFieldChange('current_value')}
                      type="number"
                      placeholder="1000000"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <FormField
                      label="תשואה שנתית צפויה (%)"
                      value={currentAsset.annual_return}
                      onChange={handleAssetFieldChange('annual_return')}
                      type="number"
                      placeholder="5.0"
                      required
                      helperText="תשואה ריאלית שנתית (אחרי אינפלציה)"
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <FormField
                      label="לוח משיכות/מכירה"
                      value={currentAsset.withdrawal_schedule}
                      onChange={handleAssetFieldChange('withdrawal_schedule')}
                      placeholder="לדוגמה: מכירה בשנת 2030"
                      required
                      helperText="מתי ואיך תמשוך/תמכור את הנכס"
                    />
                  </Grid>
                </Grid>
                <Box display="flex" gap={2} mt={2}>
                  <Button variant="contained" onClick={handleSaveAsset}>
                    שמור
                  </Button>
                  <Button variant="outlined" onClick={handleCancelAsset}>
                    ביטול
                  </Button>
                </Box>
              </Paper>
            )}

            {!isAddingAsset && (
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleAddAsset}
              >
                הוסף נכס הון
              </Button>
            )}
          </Box>
        )}
      </Paper>

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
        >
          {t('common.next')}
        </Button>
      </Box>

      {/* Information */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'info.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          מידע על הכנסות ונכסים
        </Typography>
        <Typography variant="body2">
          • <strong>הכנסות נוספות:</strong> הכנסות קבועות שתמשיכו גם בפרישה<br/>
          • <strong>נכסי הון:</strong> נכסים שיניבו הכנסה או יימכרו לצורך מימון הפרישה<br/>
          • כל הסכומים יוצמדו למדד המחירים אלא אם צוין אחרת
        </Typography>
      </Paper>
    </Box>
  );
};

export default IncomeAssets;
