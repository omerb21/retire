import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createClient } from '../lib/api';
import { Button, TextField, Grid, Paper, Typography, FormControl, InputLabel, Select, MenuItem, FormHelperText } from '@mui/material';
import { DateField } from '../components/forms/DateField';
import { formatDateToDDMMYY } from '../utils/dateUtils';
import DateField from '../components/forms/DateField';
import { clientApi, handleApiError, ClientCreate } from '../lib/api';
import { validateClientForm } from '../lib/validation';
import { useCaseDetection } from '../lib/case-detection';

interface ClientFormData {
  full_name: string;
  id_number_raw: string;
  birth_date: string;
  email: string;
  phone: string;
  retirement_date: string;
  marital_status: string;
}

const ClientNew: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { updateClientData, currentCase } = useCaseDetection();
  
  const [formData, setFormData] = useState<ClientFormData>({
    full_name: '',
    id_number_raw: '',
    birth_date: '',
    email: '',
    phone: '',
    retirement_date: '',
    marital_status: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  // Calculate minimum birth date (120 years ago) and maximum (18 years ago)
  const today = new Date();
  const maxBirthDate = new Date(today.getFullYear() - 18, today.getMonth(), today.getDate());
  const minBirthDate = new Date(today.getFullYear() - 120, today.getMonth(), today.getDate());

  const handleFieldChange = (field: keyof ClientFormData) => (value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
    setSubmitError('');
  };

  const handleDateChange = (field: keyof ClientFormData) => (value: string | null) => {
    setFormData(prev => ({ ...prev, [field]: value || '' }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
    setSubmitError('');
  };

  const validateForm = (): boolean => {
    const validation = validateClientForm(formData);
    
    if (!validation.isValid) {
      const fieldErrors: Record<string, string> = {};
      validation.errors.forEach(error => {
        // Map errors to fields (simplified mapping)
        if (error.includes('שם מלא')) fieldErrors.full_name = error;
        else if (error.includes('זהות')) fieldErrors.id_number_raw = error;
        else if (error.includes('לידה')) fieldErrors.birth_date = error;
        else if (error.includes('דוא"ל')) fieldErrors.email = error;
        else if (error.includes('טלפון')) fieldErrors.phone = error;
        else if (error.includes('פרישה')) fieldErrors.retirement_date = error;
      });
      setErrors(fieldErrors);
      return false;
    }

    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setSubmitError('');
    setSuccess('');

    try {
      // Convert full_name to first_name and last_name for API
      const nameParts = formData.full_name.trim().split(' ');
      const first_name = nameParts[0] || '';
      const last_name = nameParts.slice(1).join(' ') || '';
      
      // הכנת נתוני הלקוח לשליחה ל-API
      const clientData: ClientCreate = {
        first_name,
        last_name,
        id_number: formData.id_number_raw,
        birth_date: formData.birth_date,
        email: formData.email || "",
        phone: formData.phone || "",
        marital_status: formData.marital_status || "",
        gender: "" // שדה נדרש ע"י ה-API
      };
      
      const response = await clientApi.create(clientData);
      
      // Update case detection with new client data
      // המרה לפורמט הנדרש על ידי updateClientData
      updateClientData({
        id: response.id,
        full_name: `${response.first_name} ${response.last_name}`.trim(),
        id_number: response.id_number
      });
      
      setSuccess('פרטי הלקוח נשמרו בהצלחה');
      
      // Navigate to next step based on case
      setTimeout(() => {
        if (currentCase === 5) {
          navigate('/employer-current');
        } else {
          navigate('/employers-past');
        }
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

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('client.title')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        אנא מלא את פרטי הלקוח הבסיסיים. שדות המסומנים בכוכבית (*) הם חובה.
      </Typography>

      <Paper className="form-section">
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <FormField
              label={t('client.fullName')}
              value={formData.full_name}
              onChange={handleFieldChange('full_name')}
              error={errors.full_name}
              required
              placeholder="לדוגמה: ישראל ישראלי"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormField
              label={t('client.idNumber')}
              value={formData.id_number_raw}
              onChange={handleFieldChange('id_number_raw')}
              error={errors.id_number_raw}
              required
              placeholder="123456789"
              helperText="מספר זהות ישראלי תקין (9 ספרות)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <DateField
              label={t('client.birthDate')}
              value={formData.birth_date}
              onChange={handleDateChange('birth_date')}
              error={errors.birth_date}
              required
              minDate={formatDateToDDMMYY(minBirthDate)}
              maxDate={formatDateToDDMMYY(maxBirthDate)}
              helperText="גיל חייב להיות בין 18 ל-120"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <DateField
              label={t('client.retirementDate')}
              value={formData.retirement_date}
              onChange={handleDateChange('retirement_date')}
              error={errors.retirement_date}
              minDate={formatDateToDDMMYY(today)}
              helperText="תאריך פרישה מתוכנן (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormField
              label={t('client.email')}
              value={formData.email}
              onChange={handleFieldChange('email')}
              error={errors.email}
              type="email"
              placeholder="example@email.com"
              helperText="כתובת דוא״ל (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormField
              label={t('client.phone')}
              value={formData.phone}
              onChange={handleFieldChange('phone')}
              error={errors.phone}
              type="tel"
              placeholder="050-1234567"
              helperText="מספר טלפון (אופציונלי)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <Box sx={{ width: '100%' }}>
              <Typography variant="subtitle2" gutterBottom>
                מצב משפחתי
              </Typography>
              <select
                value={formData.marital_status}
                onChange={(e) => handleFieldChange('marital_status')(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '4px',
                  border: '1px solid #ccc',
                  fontSize: '16px'
                }}
              >
                <option value="">בחר מצב משפחתי</option>
                <option value="single">רווק/ה</option>
                <option value="married">נשוי/ה</option>
                <option value="divorced">גרוש/ה</option>
                <option value="widowed">אלמן/ה</option>
              </select>
            </Box>
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
          <Box />
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

      {/* Case Information */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'info.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          מידע על המקרה הנוכחי
        </Typography>
        <Typography variant="body2">
          {t(`case.${currentCase}`)}
        </Typography>
      </Paper>
    </Box>
  );
};

export default ClientNew;
