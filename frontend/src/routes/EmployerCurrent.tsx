import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  CircularProgress,
  Grid,
} from '@mui/material';
import FormField from '../components/forms/FormField';
import DateField from '../components/forms/DateField';
import { employmentApi, handleApiError } from '../lib/api';
import { validateEmploymentForm } from '../lib/validation';
import { useCaseDetection } from '../lib/case-detection';

interface EmploymentFormData {
  employer_name: string;
  reg_no: string;
  start_date: string;
  monthly_salary_nominal: string;
  annual_bonus: string;
  severance_fund_balance: string;
  pension_fund_balance: string;
  compensation_fund_balance: string;
}

const EmployerCurrent: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { clientData, updateEmploymentData } = useCaseDetection();
  
  const [formData, setFormData] = useState<EmploymentFormData>({
    employer_name: '',
    reg_no: '',
    start_date: '',
    monthly_salary_nominal: '',
    annual_bonus: '',
    severance_fund_balance: '',
    pension_fund_balance: '',
    compensation_fund_balance: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  const handleFieldChange = (field: keyof EmploymentFormData) => (value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
    setSubmitError('');
  };

  const handleDateChange = (field: keyof EmploymentFormData) => (value: string | null) => {
    setFormData(prev => ({ ...prev, [field]: value || '' }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
    setSubmitError('');
  };

  const validateForm = (): boolean => {
    const validation = validateEmploymentForm(formData);
    
    if (!validation.isValid) {
      const fieldErrors: Record<string, string> = {};
      validation.errors.forEach(error => {
        if (error.includes('מעסיק')) fieldErrors.employer_name = error;
        else if (error.includes('התחלה')) fieldErrors.start_date = error;
        else if (error.includes('שכר')) fieldErrors.monthly_salary_nominal = error;
      });
      setErrors(fieldErrors);
      return false;
    }

    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm() || !clientData?.id) {
      return;
    }

    setLoading(true);
    setSubmitError('');
    setSuccess('');

    try {
      const employmentData = {
        employer_name: formData.employer_name,
        reg_no: formData.reg_no,
        start_date: formData.start_date,
        monthly_salary_nominal: parseFloat(formData.monthly_salary_nominal),
        annual_bonus: formData.annual_bonus ? parseFloat(formData.annual_bonus) : 0,
        severance_fund_balance: formData.severance_fund_balance ? parseFloat(formData.severance_fund_balance) : 0,
        pension_fund_balance: formData.pension_fund_balance ? parseFloat(formData.pension_fund_balance) : 0,
        compensation_fund_balance: formData.compensation_fund_balance ? parseFloat(formData.compensation_fund_balance) : 0,
      };

      const response = await employmentApi.setCurrent(clientData.id, employmentData);
      
      // Update case detection with employment data
      updateEmploymentData(response);
      
      setSuccess('פרטי המעסיק הנוכחי נשמרו בהצלחה');
      
      setTimeout(() => {
        navigate('/employers-past');
      }, 1500);

    } catch (error) {
      setSubmitError(handleApiError(error));
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    handleSubmit();
  };

  const handlePrevious = () => {
    navigate('/client');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.currentEmployer')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        אנא מלא את פרטי המעסיק הנוכחי. מסך זה מוצג רק במקרה של עובד פעיל עם תכנון עזיבה.
      </Typography>

      <Paper className="form-section">
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <FormField
              label="שם המעסיק"
              value={formData.employer_name}
              onChange={handleFieldChange('employer_name')}
              error={errors.employer_name}
              required
              placeholder="לדוגמה: חברת הטכנולוגיה בע״מ"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormField
              label="מספר רישום (ח.פ./ע.מ.)"
              value={formData.reg_no}
              onChange={handleFieldChange('reg_no')}
              error={errors.reg_no}
              placeholder="123456789"
              helperText="מספר רישום של המעסיק (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <DateField
              label="תאריך תחילת עבודה"
              value={formData.start_date}
              onChange={handleDateChange('start_date')}
              error={errors.start_date}
              required
              helperText="תאריך תחילת העבודה אצל המעסיק הנוכחי"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormField
              label="שכר חודשי נומינלי (₪)"
              value={formData.monthly_salary_nominal}
              onChange={handleFieldChange('monthly_salary_nominal')}
              error={errors.monthly_salary_nominal}
              required
              type="number"
              placeholder="15000"
              helperText="שכר חודשי ברוטו"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormField
              label="בונוס שנתי (₪)"
              value={formData.annual_bonus}
              onChange={handleFieldChange('annual_bonus')}
              error={errors.annual_bonus}
              type="number"
              placeholder="50000"
              helperText="בונוס שנתי ממוצע (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={4}>
            <FormField
              label="יתרת קרן פיצויים (₪)"
              value={formData.severance_fund_balance}
              onChange={handleFieldChange('severance_fund_balance')}
              error={errors.severance_fund_balance}
              type="number"
              placeholder="100000"
              helperText="יתרה נוכחית (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={4}>
            <FormField
              label="יתרת קרן פנסיה (₪)"
              value={formData.pension_fund_balance}
              onChange={handleFieldChange('pension_fund_balance')}
              error={errors.pension_fund_balance}
              type="number"
              placeholder="200000"
              helperText="יתרה נוכחית (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={4}>
            <FormField
              label="יתרת קרן השתלמות (₪)"
              value={formData.compensation_fund_balance}
              onChange={handleFieldChange('compensation_fund_balance')}
              error={errors.compensation_fund_balance}
              type="number"
              placeholder="50000"
              helperText="יתרה נוכחית (אופציונלי)"
            />
          </Grid>
        </Grid>

        {submitError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {submitError}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mt: 2 }}>
            {success}
          </Alert>
        )}

        <Box className="form-actions">
          <Button
            variant="outlined"
            onClick={handlePrevious}
            disabled={loading}
          >
            {t('common.previous')}
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            {loading ? t('common.loading') : t('common.next')}
          </Button>
        </Box>
      </Paper>

      {/* Information about current employer screen */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'warning.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          מידע חשוב
        </Typography>
        <Typography variant="body2">
          מסך זה מוצג רק במקרה 5 - עובד פעיל עם תכנון עזיבה. 
          במקרים אחרים המערכת תדלג ישירות למעסיקים קודמים.
        </Typography>
      </Paper>
    </Box>
  );
};

export default EmployerCurrent;
