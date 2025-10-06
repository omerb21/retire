import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
} from '@mui/material';
import FormField from '../components/forms/FormField';

interface TaxBracket {
  min_income: number;
  max_income: number | null;
  rate: number;
}

interface TaxParams {
  tax_year: number;
  brackets: TaxBracket[];
  basic_credit: number;
  pension_credit_rate: number;
  severance_exemption_ceiling: number;
  grant_exemption_ceiling: number;
}

interface CPIData {
  year: number;
  month: number;
  index_value: number;
  annual_change: number;
}

const TaxAdmin: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [taxParams, setTaxParams] = useState<TaxParams>({
    tax_year: 2024,
    brackets: [
      { min_income: 0, max_income: 77400, rate: 10 },
      { min_income: 77400, max_income: 111000, rate: 14 },
      { min_income: 111000, max_income: 178080, rate: 20 },
      { min_income: 178080, max_income: 247440, rate: 31 },
      { min_income: 247440, max_income: 525600, rate: 35 },
      { min_income: 525600, max_income: null, rate: 47 },
    ],
    basic_credit: 2640,
    pension_credit_rate: 35,
    severance_exemption_ceiling: 378000,
    grant_exemption_ceiling: 378000,
  });

  const [cpiData, setCpiData] = useState<CPIData[]>([
    { year: 2024, month: 12, index_value: 112.5, annual_change: 2.8 },
    { year: 2023, month: 12, index_value: 109.4, annual_change: 3.1 },
    { year: 2022, month: 12, index_value: 106.1, annual_change: 5.3 },
  ]);

  const [editingTax, setEditingTax] = useState(false);
  const [editingCPI, setEditingCPI] = useState(false);

  useEffect(() => {
    // Check if user has admin privileges (simplified check)
    const adminMode = localStorage.getItem('adminMode') === 'true' || 
                     process.env.NODE_ENV === 'development';
    setIsAdminMode(adminMode);
  }, []);

  const handleTaxParamChange = (field: keyof TaxParams) => (value: string) => {
    setTaxParams(prev => ({
      ...prev,
      [field]: field === 'tax_year' ? parseInt(value) : parseFloat(value)
    }));
  };

  const handleBracketChange = (index: number, field: keyof TaxBracket) => (value: string) => {
    setTaxParams(prev => ({
      ...prev,
      brackets: prev.brackets.map((bracket, idx) => 
        idx === index ? {
          ...bracket,
          [field]: field === 'rate' ? parseFloat(value) : 
                  field === 'max_income' && value === '' ? null : parseFloat(value)
        } : bracket
      )
    }));
  };

  const handleSaveTaxParams = () => {
    // Here you would save to API
    setEditingTax(false);
    // Show success message
  };

  const handleNext = () => {
    navigate('/scenarios');
  };

  const handlePrevious = () => {
    navigate('/income-assets');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('nav.taxAdmin')}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" paragraph>
        צפייה ועדכון פרמטרי המס והמדד הנוכחיים. עדכונים זמינים למנהלי המערכת בלבד.
      </Typography>

      {!isAdminMode && (
        <Alert severity="info" sx={{ mb: 3 }}>
          אתה צופה במצב קריאה בלבד. עדכון פרמטרים זמין למנהלי מערכת בלבד.
        </Alert>
      )}

      {/* Tax Parameters */}
      <Paper className="form-section">
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">
            פרמטרי מס לשנת {taxParams.tax_year}
          </Typography>
          {isAdminMode && (
            <Button
              variant={editingTax ? "contained" : "outlined"}
              onClick={() => setEditingTax(!editingTax)}
            >
              {editingTax ? 'שמור שינויים' : 'ערוך פרמטרים'}
            </Button>
          )}
        </Box>

        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <FormField
              label="שנת מס"
              value={taxParams.tax_year.toString()}
              onChange={handleTaxParamChange('tax_year')}
              type="number"
              disabled={!editingTax}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <FormField
              label="זיכוי בסיסי (₪)"
              value={taxParams.basic_credit.toString()}
              onChange={handleTaxParamChange('basic_credit')}
              type="number"
              disabled={!editingTax}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <FormField
              label="זיכוי פנסיוני (%)"
              value={taxParams.pension_credit_rate.toString()}
              onChange={handleTaxParamChange('pension_credit_rate')}
              type="number"
              disabled={!editingTax}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <FormField
              label="תקרת פטור פיצויים (₪)"
              value={taxParams.severance_exemption_ceiling.toString()}
              onChange={handleTaxParamChange('severance_exemption_ceiling')}
              type="number"
              disabled={!editingTax}
            />
          </Grid>
        </Grid>

        {/* Tax Brackets Table */}
        <Typography variant="subtitle1" gutterBottom>
          מדרגות מס
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>הכנסה מינימלית (₪)</TableCell>
                <TableCell>הכנסה מקסימלית (₪)</TableCell>
                <TableCell>שיעור מס (%)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {taxParams.brackets.map((bracket, index) => (
                <TableRow key={index}>
                  <TableCell>
                    {editingTax ? (
                      <FormField
                        label=""
                        value={bracket.min_income.toString()}
                        onChange={handleBracketChange(index, 'min_income')}
                        type="number"
                      />
                    ) : (
                      bracket.min_income.toLocaleString()
                    )}
                  </TableCell>
                  <TableCell>
                    {editingTax ? (
                      <FormField
                        label=""
                        value={bracket.max_income?.toString() || ''}
                        onChange={handleBracketChange(index, 'max_income')}
                        type="number"
                        placeholder="ללא הגבלה"
                      />
                    ) : (
                      bracket.max_income ? bracket.max_income.toLocaleString() : 'ללא הגבלה'
                    )}
                  </TableCell>
                  <TableCell>
                    {editingTax ? (
                      <FormField
                        label=""
                        value={bracket.rate.toString()}
                        onChange={handleBracketChange(index, 'rate')}
                        type="number"
                      />
                    ) : (
                      `${bracket.rate}%`
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* CPI Data */}
      <Paper className="form-section">
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">
            נתוני מדד המחירים לצרכן
          </Typography>
          {isAdminMode && (
            <Button
              variant={editingCPI ? "contained" : "outlined"}
              onClick={() => setEditingCPI(!editingCPI)}
            >
              {editingCPI ? 'שמור שינויים' : 'ערוך נתונים'}
            </Button>
          )}
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>שנה</TableCell>
                <TableCell>חודש</TableCell>
                <TableCell>ערך המדד</TableCell>
                <TableCell>שינוי שנתי (%)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cpiData.map((item, index) => (
                <TableRow key={index}>
                  <TableCell>{item.year}</TableCell>
                  <TableCell>{item.month}</TableCell>
                  <TableCell>{item.index_value}</TableCell>
                  <TableCell>{item.annual_change}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
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
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'warning.light' }}>
        <Typography variant="subtitle2" gutterBottom>
          מידע חשוב על פרמטרי מס
        </Typography>
        <Typography variant="body2">
          • פרמטרי המס מתעדכנים מדי שנה על ידי רשויות המס<br/>
          • מדד המחירים משמש להצמדת הסכומים לאורך זמן<br/>
          • שינויים בפרמטרים ישפיעו על כל החישובים במערכת<br/>
          • רק מנהלי מערכת יכולים לעדכן את הפרמטרים
        </Typography>
      </Paper>
    </Box>
  );
};

export default TaxAdmin;
