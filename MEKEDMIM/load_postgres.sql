-- load_postgres.sql
-- 1) Create tables
CREATE TABLE IF NOT EXISTS policy_generation_coefficient (
  id INTEGER PRIMARY KEY,
  generation_code TEXT NOT NULL,
  generation_label TEXT NOT NULL,
  net_rate NUMERIC,
  base_coefficient_m65 NUMERIC,
  default_guarantee_months INTEGER,
  notes TEXT,
  valid_from DATE,
  valid_to DATE
);
CREATE TABLE IF NOT EXISTS product_to_generation_map (
  id INTEGER PRIMARY KEY,
  product_type TEXT NOT NULL,
  rule_from_date DATE,
  rule_to_date DATE,
  generation_code TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS company_annuity_coefficient (
  id INTEGER PRIMARY KEY,
  company_name TEXT NOT NULL,
  option_name TEXT NOT NULL,
  sex TEXT NOT NULL,
  age INTEGER NOT NULL,
  base_year INTEGER NOT NULL,
  base_coefficient NUMERIC NOT NULL,
  annual_increment_rate NUMERIC NOT NULL,
  notes TEXT,
  valid_from DATE,
  valid_to DATE
);
CREATE TABLE IF NOT EXISTS pension_fund_coefficient (
  id INTEGER PRIMARY KEY,
  fund_name TEXT NOT NULL,
  survivors_option TEXT NOT NULL,
  sex TEXT NOT NULL,
  retirement_age INTEGER NOT NULL,
  spouse_age_diff INTEGER NOT NULL,
  base_coefficient NUMERIC NOT NULL,
  adjust_percent NUMERIC NOT NULL,
  notes TEXT,
  valid_from DATE,
  valid_to DATE
);

-- 2) Load CSVs (adjust the absolute paths on your machine if needed)
\COPY policy_generation_coefficient FROM 'policy_generation_coefficient.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
\COPY product_to_generation_map FROM 'product_to_generation_map.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
\COPY company_annuity_coefficient FROM 'company_annuity_coefficient.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
\COPY pension_fund_coefficient FROM 'pension_fund_coefficient.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
