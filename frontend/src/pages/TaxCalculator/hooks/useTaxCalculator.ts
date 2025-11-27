import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../../../lib/api';

export interface PersonalDetails {
  birth_date?: string;
  marital_status: string;
  num_children: number;
  is_new_immigrant: boolean;
  is_veteran: boolean;
  is_disabled: boolean;
  disability_percentage?: number;
  is_student: boolean;
  reserve_duty_days: number;
}

export interface TaxCalculationInput {
  tax_year: number;
  personal_details: PersonalDetails;
  salary_income: number;
  pension_income: number;
  rental_income: number;
  capital_gains: number;
  business_income: number;
  interest_income: number;
  dividend_income: number;
  other_income: number;
  pension_contributions: number;
  study_fund_contributions: number;
  insurance_premiums: number;
  charitable_donations: number;
}

export interface TaxCalculationResult {
  total_income: number;
  taxable_income: number;
  exempt_income: number;
  income_tax: number;
  national_insurance: number;
  health_tax: number;
  total_tax: number;
  tax_credits_amount: number;
  net_tax: number;
  net_income: number;
  effective_tax_rate: number;
  marginal_tax_rate: number;
  applied_credits: Array<{
    code: string;
    amount: number;
    description: string;
  }>;
  tax_breakdown: Array<{
    bracket_min: number;
    bracket_max?: number;
    rate: number;
    taxable_amount: number;
    tax_amount: number;
  }>;
}

export function useTaxCalculator(clientId?: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TaxCalculationResult | null>(null);

  const [formData, setFormData] = useState<TaxCalculationInput>({
    tax_year: new Date().getFullYear(),
    personal_details: {
      birth_date: '',
      marital_status: 'single',
      num_children: 0,
      is_new_immigrant: false,
      is_veteran: false,
      is_disabled: false,
      disability_percentage: undefined,
      is_student: false,
      reserve_duty_days: 0,
    },
    salary_income: 0,
    pension_income: 0,
    rental_income: 0,
    capital_gains: 0,
    business_income: 0,
    interest_income: 0,
    dividend_income: 0,
    other_income: 0,
    pension_contributions: 0,
    study_fund_contributions: 0,
    insurance_premiums: 0,
    charitable_donations: 0,
  });

  const loadClientData = async () => {
    if (!clientId) return;

    try {
      const systemPassword = window.localStorage.getItem('systemAccessPassword');
      const response = await axios.get(`${API_BASE}/clients/${clientId}`, {
        headers: systemPassword
          ? { 'X-System-Password': systemPassword }
          : undefined,
      });
      const client = response.data;

      setFormData((prev) => ({
        ...prev,
        personal_details: {
          ...prev.personal_details,
          birth_date: client.birth_date || '',
          marital_status: client.marital_status || 'single',
          num_children: client.num_children || 0,
          is_new_immigrant: client.is_new_immigrant || false,
          is_veteran: client.is_veteran || false,
          is_disabled: client.is_disabled || false,
          disability_percentage: client.disability_percentage,
          is_student: client.is_student || false,
          reserve_duty_days: client.reserve_duty_days || 0,
        },
        salary_income: client.annual_salary || 0,
        pension_contributions: client.pension_contributions || 0,
        study_fund_contributions: client.study_fund_contributions || 0,
        insurance_premiums: client.insurance_premiums || 0,
        charitable_donations: client.charitable_donations || 0,
      }));
    } catch (err) {
      console.error('שגיאה בטעינת נתוני לקוח:', err);
    }
  };

  useEffect(() => {
    if (clientId) {
      loadClientData();
    }
  }, [clientId]);

  const handleInputChange = (field: string, value: any, isPersonal = false) => {
    if (isPersonal) {
      setFormData((prev) => ({
        ...prev,
        personal_details: {
          ...prev.personal_details,
          [field]: value,
        },
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        [field]: value,
      }));
    }
  };

  const calculateTax = async () => {
    try {
      setLoading(true);
      setError(null);

      const systemPassword = window.localStorage.getItem('systemAccessPassword');
      const response = await axios.post(`${API_BASE}/tax/calculate`, formData, {
        headers: systemPassword
          ? { 'X-System-Password': systemPassword }
          : undefined,
      });
      setResult(response.data);
    } catch (err: any) {
      setError('שגיאה בחישוב מס: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const saveClientTaxData = async () => {
    if (!clientId) return;

    try {
      const systemPassword = window.localStorage.getItem('systemAccessPassword');
      await axios.put(
        `${API_BASE}/clients/${clientId}`,
        {
        num_children: formData.personal_details.num_children,
        is_new_immigrant: formData.personal_details.is_new_immigrant,
        is_veteran: formData.personal_details.is_veteran,
        is_disabled: formData.personal_details.is_disabled,
        disability_percentage: formData.personal_details.disability_percentage,
        is_student: formData.personal_details.is_student,
        reserve_duty_days: formData.personal_details.reserve_duty_days,
        annual_salary: formData.salary_income,
        pension_contributions: formData.pension_contributions,
        study_fund_contributions: formData.study_fund_contributions,
        insurance_premiums: formData.insurance_premiums,
        charitable_donations: formData.charitable_donations,
        },
        {
          headers: systemPassword
            ? { 'X-System-Password': systemPassword }
            : undefined,
        }
      );

      alert('נתוני המס נשמרו בהצלחה');
    } catch (err) {
      alert('שגיאה בשמירת נתונים');
    }
  };

  return {
    loading,
    error,
    result,
    formData,
    handleInputChange,
    calculateTax,
    saveClientTaxData,
  };
}
