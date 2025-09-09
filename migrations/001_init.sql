-- Migration 001: Initial schema creation for retirement planning system
-- Created: 2025-09-09
-- Description: Creates all core tables for Client, CurrentEmployer, PensionFund, AdditionalIncome, CapitalAssets, Scenario, Grant entities

-- Enable UUID extension if needed
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. CLIENT TABLE - Core client entity
-- ============================================================================
CREATE TABLE client (
    id SERIAL PRIMARY KEY,
    
    -- ID number fields
    id_number_raw VARCHAR(20) NOT NULL,
    id_number VARCHAR(9) NOT NULL UNIQUE,
    
    -- Name fields
    full_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    
    -- Personal details
    birth_date DATE NOT NULL,
    gender VARCHAR(10), -- male, female, other
    marital_status VARCHAR(20), -- single, married, divorced, widowed
    
    -- Employment details
    self_employed BOOLEAN DEFAULT FALSE,
    current_employer_exists BOOLEAN DEFAULT FALSE,
    planned_termination_date DATE,
    
    -- Contact information
    email VARCHAR(100),
    phone VARCHAR(20),
    
    -- Address
    address_street VARCHAR(100),
    address_city VARCHAR(50),
    address_postal_code VARCHAR(10),
    
    -- Retirement planning
    retirement_target_date DATE,
    
    -- Record management
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================================
-- 2. CURRENT_EMPLOYER TABLE - Current employment details
-- ============================================================================
CREATE TABLE current_employer (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    
    -- Basic employer information
    employer_name VARCHAR(255) NOT NULL,
    employer_id_number VARCHAR(50),
    
    -- Employment period
    start_date DATE NOT NULL,
    end_date DATE, -- null = still employed
    
    -- Non-continuous periods (JSON array)
    non_continuous_periods JSONB DEFAULT '[]'::jsonb,
    
    -- Salary information
    last_salary DECIMAL(12,2),
    average_salary DECIMAL(12,2),
    
    -- Grant and severance information
    severance_accrued DECIMAL(12,2),
    other_grants JSONB DEFAULT '{}'::jsonb,
    tax_withheld DECIMAL(12,2),
    grant_installments JSONB DEFAULT '[]'::jsonb,
    
    -- Continuity and pension
    active_continuity VARCHAR(20) DEFAULT 'none', -- none, severance, pension
    continuity_years DECIMAL(8,2) DEFAULT 0.0 NOT NULL,
    pre_retirement_pension DECIMAL(12,2),
    existing_deductions JSONB DEFAULT '{}'::jsonb,
    
    -- Tracking
    last_update DATE DEFAULT CURRENT_DATE NOT NULL,
    
    -- Internal calculation fields
    indexed_severance DECIMAL(12,2),
    severance_exemption_cap DECIMAL(12,2),
    severance_exempt DECIMAL(12,2),
    severance_taxable DECIMAL(12,2),
    severance_tax_due DECIMAL(12,2),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================================
-- 3. EMPLOYER_GRANT TABLE - Grants from current employer
-- ============================================================================
CREATE TABLE employer_grant (
    id SERIAL PRIMARY KEY,
    employer_id INTEGER NOT NULL REFERENCES current_employer(id) ON DELETE CASCADE,
    
    -- Grant details
    grant_type VARCHAR(20) NOT NULL, -- severance, adjustment, other
    grant_amount DECIMAL(12,2) NOT NULL,
    grant_date DATE NOT NULL,
    
    -- Tax information
    tax_withheld DECIMAL(12,2) DEFAULT 0.0,
    
    -- Calculated fields
    grant_exempt DECIMAL(12,2),
    grant_taxable DECIMAL(12,2),
    tax_due DECIMAL(12,2),
    indexed_amount DECIMAL(12,2),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================================
-- 4. GRANT TABLE - General grants (past employers, etc.)
-- ============================================================================
CREATE TABLE grant (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    
    -- Grant details
    employer_name VARCHAR(200),
    work_start_date DATE,
    work_end_date DATE,
    grant_amount DECIMAL(12,2),
    grant_date DATE,
    grant_indexed_amount DECIMAL(12,2),
    limited_indexed_amount DECIMAL(12,2),
    grant_ratio DECIMAL(8,4),
    impact_on_exemption DECIMAL(12,2),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================================
-- 5. PENSION_FUNDS TABLE - Pension fund details
-- ============================================================================
CREATE TABLE pension_funds (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    
    -- Fund details
    fund_name VARCHAR(200) NOT NULL,
    fund_type VARCHAR(50),
    
    -- Input mode and amounts
    input_mode VARCHAR(20) NOT NULL, -- calculated, manual
    balance DECIMAL(15,2),
    annuity_factor DECIMAL(8,6),
    pension_amount DECIMAL(12,2),
    
    -- Pension timing
    pension_start_date DATE,
    
    -- Indexation
    indexation_method VARCHAR(20) DEFAULT 'none' NOT NULL, -- none, cpi, fixed
    fixed_index_rate DECIMAL(5,4),
    indexed_pension_amount DECIMAL(12,2),
    
    -- Metadata
    remarks VARCHAR(500),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Constraints
    CONSTRAINT pf_balance_nonneg CHECK (balance IS NULL OR balance >= 0),
    CONSTRAINT pf_annuity_pos CHECK (annuity_factor IS NULL OR annuity_factor > 0),
    CONSTRAINT pf_pension_nonneg CHECK (pension_amount IS NULL OR pension_amount >= 0),
    CONSTRAINT pf_fixed_rate_nonneg CHECK (fixed_index_rate IS NULL OR fixed_index_rate >= 0)
);

-- ============================================================================
-- 6. ADDITIONAL_INCOME TABLE - Non-pension income sources
-- ============================================================================
CREATE TABLE additional_income (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    
    -- Income details
    source_type VARCHAR(50) NOT NULL, -- rental, dividends, interest, business, freelance, other
    description VARCHAR(255),
    amount DECIMAL(12,2) NOT NULL,
    frequency VARCHAR(20) NOT NULL, -- monthly, quarterly, annually
    
    -- Date range
    start_date DATE NOT NULL,
    end_date DATE,
    
    -- Indexation
    indexation_method VARCHAR(20) DEFAULT 'none' NOT NULL, -- none, fixed, cpi
    fixed_rate DECIMAL(5,4),
    
    -- Tax treatment
    tax_treatment VARCHAR(20) DEFAULT 'taxable' NOT NULL, -- exempt, taxable, fixed_rate
    tax_rate DECIMAL(5,4),
    
    -- Metadata
    remarks VARCHAR(500),
    
    -- Constraints
    CONSTRAINT check_positive_amount CHECK (amount > 0),
    CONSTRAINT check_valid_date_range CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT check_fixed_rate_when_fixed_indexation CHECK (
        indexation_method != 'fixed' OR fixed_rate IS NOT NULL
    ),
    CONSTRAINT check_tax_rate_when_fixed_tax CHECK (
        tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL
    ),
    CONSTRAINT check_non_negative_fixed_rate CHECK (fixed_rate IS NULL OR fixed_rate >= 0),
    CONSTRAINT check_valid_tax_rate CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1))
);

-- ============================================================================
-- 7. CAPITAL_ASSETS TABLE - Investment and capital assets
-- ============================================================================
CREATE TABLE capital_assets (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    
    -- Asset details
    asset_type VARCHAR(50) NOT NULL, -- stocks, bonds, mutual_funds, real_estate, savings_account, deposits, other
    description VARCHAR(255),
    current_value DECIMAL(15,2) NOT NULL,
    annual_return_rate DECIMAL(5,4) NOT NULL,
    payment_frequency VARCHAR(20) NOT NULL, -- monthly, quarterly, annually
    
    -- Date range
    start_date DATE NOT NULL,
    end_date DATE,
    
    -- Indexation
    indexation_method VARCHAR(20) DEFAULT 'none' NOT NULL, -- none, fixed, cpi
    fixed_rate DECIMAL(5,4),
    
    -- Tax treatment
    tax_treatment VARCHAR(20) DEFAULT 'taxable' NOT NULL, -- exempt, taxable, fixed_rate
    tax_rate DECIMAL(5,4),
    
    -- Metadata
    remarks VARCHAR(500),
    
    -- Constraints
    CONSTRAINT check_positive_value CHECK (current_value > 0),
    CONSTRAINT check_non_negative_return CHECK (annual_return_rate >= 0),
    CONSTRAINT check_valid_date_range CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT check_fixed_rate_when_fixed_indexation CHECK (
        indexation_method != 'fixed' OR fixed_rate IS NOT NULL
    ),
    CONSTRAINT check_tax_rate_when_fixed_tax CHECK (
        tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL
    ),
    CONSTRAINT check_non_negative_fixed_rate CHECK (fixed_rate IS NULL OR fixed_rate >= 0),
    CONSTRAINT check_valid_tax_rate CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1))
);

-- ============================================================================
-- 8. SCENARIO TABLE - Planning scenarios
-- ============================================================================
CREATE TABLE scenario (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    scenario_name VARCHAR(255) NOT NULL,
    
    -- Planning flags
    apply_tax_planning BOOLEAN DEFAULT FALSE NOT NULL,
    apply_capitalization BOOLEAN DEFAULT FALSE NOT NULL,
    apply_exemption_shield BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- JSON fields for storing scenario data
    parameters TEXT DEFAULT '{}' NOT NULL, -- ScenarioIn as JSON
    summary_results TEXT, -- ScenarioOut summary as JSON
    cashflow_projection TEXT, -- Cashflow data as JSON
    
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Client indexes
CREATE INDEX ix_client_id_number ON client(id_number);
CREATE INDEX ix_client_full_name ON client(full_name);
CREATE INDEX ix_client_full_name_id_number ON client(full_name, id_number);
CREATE INDEX ix_client_is_active ON client(is_active);
CREATE INDEX ix_client_birth_date ON client(birth_date);

-- Current employer indexes
CREATE INDEX ix_current_employer_client_id ON current_employer(client_id);
CREATE INDEX ix_current_employer_employer_name ON current_employer(employer_name);
CREATE INDEX ix_current_employer_start_date ON current_employer(start_date);
CREATE INDEX ix_current_employer_end_date ON current_employer(end_date);

-- Employer grant indexes
CREATE INDEX ix_employer_grant_employer_id ON employer_grant(employer_id);
CREATE INDEX ix_employer_grant_grant_type ON employer_grant(grant_type);
CREATE INDEX ix_employer_grant_grant_date ON employer_grant(grant_date);

-- Grant indexes
CREATE INDEX ix_grant_client_id ON grant(client_id);
CREATE INDEX ix_grant_employer_name ON grant(employer_name);
CREATE INDEX ix_grant_grant_date ON grant(grant_date);

-- Pension fund indexes
CREATE INDEX ix_pension_funds_client_id ON pension_funds(client_id);
CREATE INDEX ix_pension_funds_fund_name ON pension_funds(fund_name);
CREATE INDEX ix_pension_funds_input_mode ON pension_funds(input_mode);

-- Additional income indexes
CREATE INDEX ix_additional_income_client_id ON additional_income(client_id);
CREATE INDEX ix_additional_income_source_type ON additional_income(source_type);
CREATE INDEX ix_additional_income_start_date ON additional_income(start_date);
CREATE INDEX ix_additional_income_end_date ON additional_income(end_date);

-- Capital assets indexes
CREATE INDEX ix_capital_assets_client_id ON capital_assets(client_id);
CREATE INDEX ix_capital_assets_asset_type ON capital_assets(asset_type);
CREATE INDEX ix_capital_assets_start_date ON capital_assets(start_date);
CREATE INDEX ix_capital_assets_end_date ON capital_assets(end_date);

-- Scenario indexes
CREATE INDEX ix_scenario_client_id ON scenario(client_id);
CREATE INDEX ix_scenario_scenario_name ON scenario(scenario_name);
CREATE INDEX ix_scenario_created_at ON scenario(created_at);

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT TIMESTAMPS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at columns
CREATE TRIGGER update_client_updated_at 
    BEFORE UPDATE ON client 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_current_employer_updated_at 
    BEFORE UPDATE ON current_employer 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_employer_grant_updated_at 
    BEFORE UPDATE ON employer_grant 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_grant_updated_at 
    BEFORE UPDATE ON grant 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pension_funds_updated_at 
    BEFORE UPDATE ON pension_funds 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE client IS 'Core client entity with personal and contact information';
COMMENT ON TABLE current_employer IS 'Current employment details including salary and grants';
COMMENT ON TABLE employer_grant IS 'Grants from current employer (severance, adjustments, etc.)';
COMMENT ON TABLE grant IS 'General grants from past employers or other sources';
COMMENT ON TABLE pension_funds IS 'Pension fund details and calculations';
COMMENT ON TABLE additional_income IS 'Non-pension income sources (rental, dividends, etc.)';
COMMENT ON TABLE capital_assets IS 'Investment and capital assets';
COMMENT ON TABLE scenario IS 'Planning scenarios with parameters and results';

COMMENT ON COLUMN client.id_number IS 'Israeli ID number (9 digits)';
COMMENT ON COLUMN client.id_number_raw IS 'Raw ID number as entered (may include formatting)';
COMMENT ON COLUMN current_employer.non_continuous_periods IS 'JSON array of non-continuous employment periods';
COMMENT ON COLUMN current_employer.other_grants IS 'JSON object for various grant types';
COMMENT ON COLUMN current_employer.grant_installments IS 'JSON array of grant installment details';
COMMENT ON COLUMN current_employer.existing_deductions IS 'JSON object for deduction details';
COMMENT ON COLUMN scenario.parameters IS 'ScenarioIn parameters as JSON';
COMMENT ON COLUMN scenario.summary_results IS 'ScenarioOut summary results as JSON';
COMMENT ON COLUMN scenario.cashflow_projection IS 'Cashflow projection data as JSON';
