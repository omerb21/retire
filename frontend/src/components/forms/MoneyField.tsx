import React from 'react';
import {
  TextField,
  FormControl,
  FormHelperText,
  InputAdornment,
} from '@mui/material';
import { formatCurrency } from '../../lib/validation';

interface MoneyFieldProps {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  placeholder?: string;
}

const MoneyField: React.FC<MoneyFieldProps> = ({
  label,
  value,
  onChange,
  error,
  required = false,
  disabled = false,
  helperText,
  placeholder,
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const inputValue = event.target.value;
    // Allow only numbers and decimal point
    const numericValue = inputValue.replace(/[^0-9.]/g, '');
    onChange(numericValue);
  };

  const formatDisplayValue = (val: string | number): string => {
    if (!val) return '';
    const numVal = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(numVal)) return '';
    const formatted = formatCurrency(numVal);
    return formatted.replace('₪', '').trim();
  };

  return (
    <FormControl fullWidth margin="normal" error={!!error}>
      <TextField
        label={label}
        value={formatDisplayValue(value)}
        onChange={handleChange}
        error={!!error}
        required={required}
        disabled={disabled}
        placeholder={placeholder}
        variant="outlined"
        InputProps={{
          startAdornment: <InputAdornment position="start">₪</InputAdornment>,
        }}
        InputLabelProps={{
          shrink: true,
        }}
        sx={{
          '& .MuiInputLabel-root': {
            right: 14,
            left: 'auto',
            transformOrigin: 'top right',
          },
          '& .MuiOutlinedInput-root': {
            '& fieldset': {
              textAlign: 'right',
            },
          },
        }}
      />
      {(error || helperText) && (
        <FormHelperText>
          {error || helperText}
        </FormHelperText>
      )}
    </FormControl>
  );
};

export default MoneyField;
