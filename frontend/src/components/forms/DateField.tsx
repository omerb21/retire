import React from 'react';
import { TextField, FormControl, FormHelperText } from '@mui/material';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs, { Dayjs } from 'dayjs';
import 'dayjs/locale/he';

// Configure dayjs for Hebrew
dayjs.locale('he');

interface DateFieldProps {
  label: string;
  value: string | null;
  onChange: (value: string | null) => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  minDate?: string;
  maxDate?: string;
}

const DateField: React.FC<DateFieldProps> = ({
  label,
  value,
  onChange,
  error,
  required = false,
  disabled = false,
  helperText,
  minDate,
  maxDate,
}) => {
  const handleChange = (newValue: Dayjs | null) => {
    if (newValue) {
      onChange(newValue.format('YYYY-MM-DD'));
    } else {
      onChange(null);
    }
  };

  const dayjsValue = value ? dayjs(value) : null;
  const minDayjs = minDate ? dayjs(minDate) : undefined;
  const maxDayjs = maxDate ? dayjs(maxDate) : undefined;

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="he">
      <FormControl fullWidth margin="normal" error={!!error}>
        <DatePicker
          label={label}
          value={dayjsValue}
          onChange={handleChange}
          disabled={disabled}
          minDate={minDayjs}
          maxDate={maxDayjs}
          format="DD/MM/YYYY"
          slotProps={{
            textField: {
              required,
              error: !!error,
              variant: 'outlined',
              InputLabelProps: {
                shrink: true,
              },
              sx: {
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
    </LocalizationProvider>
  );
};

export default DateField;
