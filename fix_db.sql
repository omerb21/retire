-- Fix tax_rate constraint in SQLite database

-- 1. Create backup
CREATE TABLE additional_income_backup AS SELECT * FROM additional_income;

-- 2. Drop old table
DROP TABLE additional_income;

-- 3. Create new table with updated constraint
CREATE TABLE additional_income (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    amount NUMERIC(12, 2) NOT NULL,
    frequency VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    indexation_method VARCHAR(20) NOT NULL DEFAULT 'none',
    fixed_rate NUMERIC(5, 4),
    tax_treatment VARCHAR(20) NOT NULL DEFAULT 'taxable',
    tax_rate NUMERIC(5, 2),
    remarks VARCHAR(500),
    FOREIGN KEY(client_id) REFERENCES client (id) ON DELETE CASCADE,
    CHECK (amount > 0),
    CHECK (end_date IS NULL OR end_date >= start_date),
    CHECK (indexation_method != 'fixed' OR fixed_rate IS NOT NULL),
    CHECK (tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL),
    CHECK (fixed_rate IS NULL OR fixed_rate >= 0),
    CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 99))
);

-- 4. Restore data
INSERT INTO additional_income SELECT * FROM additional_income_backup;

-- 5. Drop backup
DROP TABLE additional_income_backup;

-- 6. Create index
CREATE INDEX ix_additional_income_client_id ON additional_income (client_id);
