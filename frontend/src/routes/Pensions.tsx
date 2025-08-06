import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
} from '@mui/material';
import FormField from '../components/forms/FormField';

interface PensionFund {
  id?: number;
  fund_name: string;
  calculation_mode: 'calculated' | 'manual';
  balance?: string;
  annuity_factor?: string;
  pension_amount?: string;
}

const Pensions: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  const [pensionFunds, setPensionFunds] = useState<PensionFund[]>([
    {
      id: 1,
      fund_name: '',
      calculation_mode: 'calculated',
      balance: '',
      annuity_factor: '',
      pension_amount: '',
    }
  ]);

  const handleFieldChange = (index: number, field: keyof PensionFund) => (value: string) => {
    setPensionFunds(prev => prev.map((fund, idx) => 
      idx === index ? { ...fund, [field]: value } : fund
    ));
  };

  const handleModeChange = (index: number) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const mode = event.target.value as 'calculated' | 'manual';
    setPensionFunds(prev => prev.map((fund, idx) => 
      idx === index ? { 
        ...fund, 
        calculation_mode: mode,
        // Clear opposite mode fields
        ...(mode === 'calculated' ? { pension_amount: '' } : { balance: '', annuity_factor: '' })
      } : fund
    ));
  };

  const addPensionFund = () => {
    setPensionFunds(prev => [...prev, {
      id: Date.now(),
      fund_name: '',
      calculation_mode: 'calculated',
      balance: '',
      annuity_factor: '',
      pension_amount: '',
    }]);
  };

  const removePensionFund = (index: number) => {
    if (pensionFunds.length > 1) {
      setPensionFunds(prev => prev.filter((_, idx) => idx !== index));
    }
  };

  const handleNext = () => {
    navigate('/income-assets');
  };

  const handlePrevious = () => {
    navigate('/employers-past');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.pensions')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        הגדר את קרנות הפנסיה והקצבאות. ניתן לבחור בין חישוב אוטומטי על בסיס יתרה או הזנה ידנית של סכום הקצבה.
      </Typography>

      {pensionFunds.map((fund, index) => (
        <Paper key={fund.id || index} className="form-section" sx={{ mb: 3 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              קרן פנסיה {index + 1}
            </Typography>
            {pensionFunds.length > 1 && (
              <Button 
                color="error" 
                onClick={() => removePensionFund(index)}
                size="small"
              >
                הסר
              </Button>
            )}
          </Box>

          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormField
                label="שם הקרן"
                value={fund.fund_name}
                onChange={handleFieldChange(index, 'fund_name')}
                placeholder="לדוגמה: מנורה מבטחים פנסיה"
                required
              />
            </Grid>

            <Grid item xs={12}>
              <FormControl component="fieldset">
                <FormLabel component="legend">אופן חישוב הקצבה</FormLabel>
                <RadioGroup
                  value={fund.calculation_mode}
                  onChange={handleModeChange(index)}
                  row
                >
                  <FormControlLabel 
                    value="calculated" 
                    control={<Radio />} 
                    label="חישוב אוטומטי (יתרה × מקדם)" 
                  />
                  <FormControlLabel 
                    value="manual" 
                    control={<Radio />} 
                    label="הזנה ידנית של סכום קצבה" 
                  />
                </RadioGroup>
              </FormControl>
            </Grid>

            {fund.calculation_mode === 'calculated' ? (
              <>
                <Grid item xs={12} md={6}>
                  <FormField
                    label="יתרה בקרן (₪)"
                    value={fund.balance || ''}
                    onChange={handleFieldChange(index, 'balance')}
                    type="number"
                    placeholder="500000"
                    required
                    helperText="יתרה נוכחית בקרן הפנסיה"
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <FormField
                    label="מקדם קצבה"
                    value={fund.annuity_factor || ''}
                    onChange={handleFieldChange(index, 'annuity_factor')}
                    type="number"
                    placeholder="0.045"
                    required
                    helperText="מקדם המרה ליתרה לקצבה חודשית (בדרך כלל 0.04-0.05)"
                  />
                </Grid>
              </>
            ) : (
              <Grid item xs={12} md={6}>
                <FormField
                  label="סכום קצבה חודשית (₪)"
                  value={fund.pension_amount || ''}
                  onChange={handleFieldChange(index, 'pension_amount')}
                  type="number"
                  placeholder="8000"
                  required
                  helperText="סכום הקצבה החודשית הצפויה"
                />
              </Grid>
            )}

            {/* Display calculated pension if in calculated mode */}
            {fund.calculation_mode === 'calculated' && fund.balance && fund.annuity_factor && (
              <Grid item xs={12}>
                <Paper sx={{ p: 2, bgcolor: 'success.light' }}>
                  <Typography variant="subtitle2">
                    קצבה חודשית משוערת: ₪
                    {(parseFloat(fund.balance) * parseFloat(fund.annuity_factor)).toLocaleString()}
                  </Typography>
                </Paper>
              </Grid>
            )}
          </Grid>
        </Paper>
      ))}

      <Box textAlign="center" mb={3}>
        <Button variant="outlined" onClick={addPensionFund}>
          הוסף קרן פנסיה נוספת
        </Button>
      </Box>

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
          מידע על קרנות פנסיה
        </Typography>
        <Typography variant="body2">
          • <strong>חישוב אוטומטי:</strong> המערכת תחשב את הקצבה על בסיס היתרה והמקדם<br/>
          • <strong>הזנה ידנית:</strong> הזן את סכום הקצבה החודשית הידוע לך<br/>
          • מקדם הקצבה הרגיל נע בין 0.04 ל-0.05 (4%-5% מהיתרה בשנה)
        </Typography>
      </Paper>
    </Box>
  );
};

export default Pensions;
