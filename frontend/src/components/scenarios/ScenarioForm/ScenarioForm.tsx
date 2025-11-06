import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Grid,
  TextField,
  Typography
} from '@mui/material';
import { ScenarioFormData } from '../../../types/scenario';

interface ScenarioFormProps {
  formData: ScenarioFormData;
  showCreateForm: boolean;
  loading: boolean;
  onFormChange: (field: keyof ScenarioFormData, value: any) => void;
  onSubmit: () => void;
  onToggleForm: () => void;
}

export const ScenarioForm: React.FC<ScenarioFormProps> = ({
  formData,
  showCreateForm,
  loading,
  onFormChange,
  onSubmit,
  onToggleForm
}) => {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">יצירת תרחיש חדש</Typography>
          <Button
            variant="contained"
            onClick={onToggleForm}
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
                onChange={(e) => onFormChange('scenario_name', e.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="תאריך פרישה מתוכנן"
                type="date"
                value={formData.planned_termination_date}
                onChange={(e) => onFormChange('planned_termination_date', e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="הוצאות חודשיות"
                type="number"
                value={formData.monthly_expenses}
                onChange={(e) => onFormChange('monthly_expenses', e.target.value)}
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
                    onChange={(e) => onFormChange('apply_tax_planning', e.target.checked)}
                  />
                }
                label="תכנון מס"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={formData.apply_capitalization}
                    onChange={(e) => onFormChange('apply_capitalization', e.target.checked)}
                  />
                }
                label="קפיטליזציה"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={formData.apply_exemption_shield}
                    onChange={(e) => onFormChange('apply_exemption_shield', e.target.checked)}
                  />
                }
                label="מגן פטור"
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                onClick={onSubmit}
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
  );
};
