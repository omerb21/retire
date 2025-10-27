-- load_sqlite.sql
-- Run with: sqlite3 retire.db < load_sqlite.sql

DROP TABLE IF EXISTS policy_generation_coefficient;
CREATE TABLE policy_generation_coefficient (
  id INTEGER PRIMARY KEY,
  generation_code TEXT NOT NULL,
  generation_label TEXT NOT NULL,
  net_rate REAL,
  base_coefficient_m65 REAL,
  default_guarantee_months INTEGER,
  notes TEXT,
  valid_from TEXT,
  valid_to TEXT
);
DROP TABLE IF EXISTS product_to_generation_map;
CREATE TABLE product_to_generation_map (
  id INTEGER PRIMARY KEY,
  product_type TEXT NOT NULL,
  rule_from_date TEXT,
  rule_to_date TEXT,
  generation_code TEXT NOT NULL
);
DROP TABLE IF EXISTS company_annuity_coefficient;
CREATE TABLE company_annuity_coefficient (
  id INTEGER PRIMARY KEY,
  company_name TEXT NOT NULL,
  option_name TEXT NOT NULL,
  sex TEXT NOT NULL,
  age INTEGER NOT NULL,
  base_year INTEGER NOT NULL,
  base_coefficient REAL NOT NULL,
  annual_increment_rate REAL NOT NULL,
  notes TEXT,
  valid_from TEXT,
  valid_to TEXT
);
DROP TABLE IF EXISTS pension_fund_coefficient;
CREATE TABLE pension_fund_coefficient (
  id INTEGER PRIMARY KEY,
  fund_name TEXT NOT NULL,
  survivors_option TEXT NOT NULL,
  sex TEXT NOT NULL,
  retirement_age INTEGER NOT NULL,
  spouse_age_diff INTEGER NOT NULL,
  base_coefficient REAL NOT NULL,
  adjust_percent REAL NOT NULL,
  notes TEXT,
  valid_from TEXT,
  valid_to TEXT
);

.mode csv
.headers on
.import policy_generation_coefficient.csv policy_generation_coefficient
.import product_to_generation_map.csv product_to_generation_map
.import company_annuity_coefficient.csv company_annuity_coefficient
.import pension_fund_coefficient.csv pension_fund_coefficient
