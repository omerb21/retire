import React from 'react';
import { useParams } from 'react-router-dom';
import { useTaxCalculator } from '../hooks/useTaxCalculator';
import { TaxCalculatorForm } from './TaxCalculatorForm';
import { TaxCalculatorResults } from './TaxCalculatorResults';
import '../TaxCalculator.css';

const TaxCalculatorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const {
    loading,
    error,
    result,
    formData,
    handleInputChange,
    calculateTax,
    saveClientTaxData,
  } = useTaxCalculator(id);

  return (
    <div className="tax-calculator-container">
      <h1>מחשבון מס הכנסה</h1>

      {error && <div className="tax-calculator-error">{error}</div>}

      <div className="tax-calculator-grid">
        <TaxCalculatorForm
          clientId={id}
          formData={formData}
          loading={loading}
          handleInputChange={handleInputChange}
          calculateTax={calculateTax}
          saveClientTaxData={saveClientTaxData}
        />

        <div>
          <TaxCalculatorResults result={result} />
        </div>
      </div>
    </div>
  );
};

export default TaxCalculatorPage;
