import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  Grid,
  Card,
  CardContent,
  IconButton,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon } from '@mui/icons-material';
import FormField from '../components/forms/FormField';
import DateField from '../components/forms/DateField';
import { useCaseDetection } from '../lib/case-detection';

interface PastEmployer {
  id?: number;
  employer_name: string;
  start_date: string;
  end_date: string;
  monthly_salary_nominal: string;
  severance_paid: string;
  grant_exempt: string;
}

const EmployersPast: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { currentCase } = useCaseDetection();
  
  const [employers, setEmployers] = useState<PastEmployer[]>([]);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [currentEmployer, setCurrentEmployer] = useState<PastEmployer>({
    employer_name: '',
    start_date: '',
    end_date: '',
    monthly_salary_nominal: '',
    severance_paid: '',
    grant_exempt: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleFieldChange = (field: keyof PastEmployer) => (value: string) => {
    setCurrentEmployer(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleDateChange = (field: keyof PastEmployer) => (value: string | null) => {
    setCurrentEmployer(prev => ({ ...prev, [field]: value || '' }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const validateEmployer = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!currentEmployer.employer_name.trim()) {
      newErrors.employer_name = 'שם המעסיק הוא שדה חובה';
    }

    if (!currentEmployer.start_date) {
      newErrors.start_date = 'תאריך התחלה הוא שדה חובה';
    }

    if (!currentEmployer.end_date) {
      newErrors.end_date = 'תאריך סיום הוא שדה חובה';
    }

    if (currentEmployer.start_date && currentEmployer.end_date) {
      const start = new Date(currentEmployer.start_date);
      const end = new Date(currentEmployer.end_date);
      if (end <= start) {
        newErrors.end_date = 'תאריך הסיום חייב להיות אחרי תאריך ההתחלה';
      }
    }

    if (!currentEmployer.monthly_salary_nominal || parseFloat(currentEmployer.monthly_salary_nominal) <= 0) {
      newErrors.monthly_salary_nominal = 'שכר חודשי חייב להיות מספר חיובי';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAddNew = () => {
    setIsAddingNew(true);
    setEditingIndex(null);
    setCurrentEmployer({
      employer_name: '',
      start_date: '',
      end_date: '',
      monthly_salary_nominal: '',
      severance_paid: '',
      grant_exempt: '',
    });
    setErrors({});
  };

  const handleEdit = (index: number) => {
    setIsAddingNew(false);
    setEditingIndex(index);
    setCurrentEmployer({ ...employers[index] });
    setErrors({});
  };

  const handleSave = () => {
    if (!validateEmployer()) {
      return;
    }

    if (isAddingNew) {
      setEmployers(prev => [...prev, { ...currentEmployer, id: Date.now() }]);
    } else if (editingIndex !== null) {
      setEmployers(prev => prev.map((emp, idx) => 
        idx === editingIndex ? { ...currentEmployer } : emp
      ));
    }

    setIsAddingNew(false);
    setEditingIndex(null);
    setCurrentEmployer({
      employer_name: '',
      start_date: '',
      end_date: '',
      monthly_salary_nominal: '',
      severance_paid: '',
      grant_exempt: '',
    });
  };

  const handleCancel = () => {
    setIsAddingNew(false);
    setEditingIndex(null);
    setErrors({});
  };

  const handleDelete = (index: number) => {
    setEmployers(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleNext = () => {
    navigate('/pensions');
  };

  const handlePrevious = () => {
    if (currentCase === 5) {
      navigate('/employer-current');
    } else {
      navigate('/client');
    }
  };

  const isEditing = isAddingNew || editingIndex !== null;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.pastEmployers')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        הוסף מעסיקים קודמים ופרטי העסקה אצלם. מידע זה נדרש לחישוב זכויות הפנסיה והמענקים.
      </Typography>

      {/* List of existing employers */}
      {employers.length > 0 && (
        <Box mb={3}>
          <Typography variant="h6" gutterBottom>
            מעסיקים קודמים ({employers.length})
          </Typography>
          <Grid container spacing={2}>
            {employers.map((employer, index) => (
              <Grid item xs={12} md={6} key={employer.id || index}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box flex={1}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          {employer.employer_name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {employer.start_date} - {employer.end_date}
                        </Typography>
                        <Typography variant="body2">
                          שכר חודשי: ₪{parseFloat(employer.monthly_salary_nominal).toLocaleString()}
                        </Typography>
                        {employer.severance_paid && (
                          <Typography variant="body2">
                            פיצויים שולמו: ₪{parseFloat(employer.severance_paid).toLocaleString()}
                          </Typography>
                        )}
                      </Box>
                      <Box>
                        <IconButton onClick={() => handleEdit(index)} size="small">
                          <EditIcon />
                        </IconButton>
                        <IconButton onClick={() => handleDelete(index)} size="small" color="error">
                          <DeleteIcon />
                        </IconButton>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Add/Edit form */}
      {isEditing && (
        <Paper className="form-section">
          <Typography variant="h6" gutterBottom>
            {isAddingNew ? 'הוספת מעסיק קודם' : 'עריכת מעסיק קודם'}
          </Typography>
          
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormField
                label="שם המעסיק"
                value={currentEmployer.employer_name}
                onChange={handleFieldChange('employer_name')}
                error={errors.employer_name}
                required
                placeholder="לדוגמה: חברת הייטק בע״מ"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <DateField
                label="תאריך התחלה"
                value={currentEmployer.start_date}
                onChange={handleDateChange('start_date')}
                error={errors.start_date}
                required
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <DateField
                label="תאריך סיום"
                value={currentEmployer.end_date}
                onChange={handleDateChange('end_date')}
                error={errors.end_date}
                required
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <FormField
                label="שכר חודשי נומינלי (₪)"
                value={currentEmployer.monthly_salary_nominal}
                onChange={handleFieldChange('monthly_salary_nominal')}
                error={errors.monthly_salary_nominal}
                required
                type="number"
                placeholder="15000"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <FormField
                label="פיצויים ששולמו (₪)"
                value={currentEmployer.severance_paid}
                onChange={handleFieldChange('severance_paid')}
                error={errors.severance_paid}
                type="number"
                placeholder="100000"
                helperText="סכום פיצויים ששולמו (אופציונלי)"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <FormField
                label="מענק פטור (₪)"
                value={currentEmployer.grant_exempt}
                onChange={handleFieldChange('grant_exempt')}
                error={errors.grant_exempt}
                type="number"
                placeholder="50000"
                helperText="סכום מענק פטור ממס (אופציונלי)"
              />
            </Grid>
          </Grid>

          <Box display="flex" gap={2} mt={3}>
            <Button variant="contained" onClick={handleSave}>
              שמור
            </Button>
            <Button variant="outlined" onClick={handleCancel}>
              ביטול
            </Button>
          </Box>
        </Paper>
      )}

      {/* Add button */}
      {!isEditing && (
        <Paper sx={{ p: 2, mb: 3, textAlign: 'center' }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleAddNew}
            size="large"
          >
            הוסף מעסיק קודם
          </Button>
        </Paper>
      )}

      {/* Navigation */}
      {!isEditing && (
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
      )}

      {/* Information */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'info.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          מידע חשוב
        </Typography>
        <Typography variant="body2">
          מעסיקים קודמים נדרשים לחישוב זכויות הפנסיה המצטברות ומענקי הפרישה. 
          ניתן להוסיף מספר מעסיקים או לדלג אם אין מעסיקים קודמים.
        </Typography>
      </Paper>
    </Box>
  );
};

export default EmployersPast;
