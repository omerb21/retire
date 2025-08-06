import React from 'react';
import {
  TextField,
  FormControl,
  FormLabel,
  FormHelperText,
  Box,
} from '@mui/material';

interface FormFieldProps {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  type?: 'text' | 'email' | 'tel' | 'number' | 'date';
  placeholder?: string;
  disabled?: boolean;
  multiline?: boolean;
  rows?: number;
  helperText?: string;
}

const FormField: React.FC<FormFieldProps> = ({
  label,
  value,
  onChange,
  error,
  required = false,
  type = 'text',
  placeholder,
  disabled = false,
  multiline = false,
  rows = 1,
  helperText,
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.value);
  };

  return (
    <FormControl fullWidth margin="normal" error={!!error}>
      <TextField
        label={label}
        value={value}
        onChange={handleChange}
        error={!!error}
        required={required}
        type={type}
        placeholder={placeholder}
        disabled={disabled}
        multiline={multiline}
        rows={multiline ? rows : undefined}
        variant="outlined"
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

export default FormField;
