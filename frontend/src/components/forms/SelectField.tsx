import React from 'react';
import {
  FormControl,
  FormLabel,
  Select,
  MenuItem,
  FormHelperText,
  InputLabel,
} from '@mui/material';

interface SelectOption {
  value: string | number;
  label: string;
}

interface SelectFieldProps {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  options: SelectOption[];
  error?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  placeholder?: string;
}

const SelectField: React.FC<SelectFieldProps> = ({
  label,
  value,
  onChange,
  options,
  error,
  required = false,
  disabled = false,
  helperText,
  placeholder,
}) => {
  const handleChange = (event: any) => {
    onChange(event.target.value);
  };

  return (
    <FormControl fullWidth margin="normal" error={!!error}>
      <InputLabel 
        id={`select-${label}`}
        sx={{
          right: 14,
          left: 'auto',
          transformOrigin: 'top right',
        }}
      >
        {label} {required && '*'}
      </InputLabel>
      <Select
        labelId={`select-${label}`}
        value={value}
        onChange={handleChange}
        label={label}
        disabled={disabled}
        displayEmpty={!!placeholder}
        sx={{
          '& .MuiSelect-select': {
            textAlign: 'right',
          },
        }}
      >
        {placeholder && (
          <MenuItem value="" disabled>
            {placeholder}
          </MenuItem>
        )}
        {options.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </Select>
      {(error || helperText) && (
        <FormHelperText>
          {error || helperText}
        </FormHelperText>
      )}
    </FormControl>
  );
};

export default SelectField;
