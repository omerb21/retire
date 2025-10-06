# Database Migration Guide

## Overview
This guide covers the initial database schema setup for the retirement planning system using PostgreSQL.

## Prerequisites
- PostgreSQL 12+ installed and running
- Database user with CREATE privileges
- psql command-line tool or database management interface

## Migration Files
- `migrations/001_init.sql` - Initial schema creation with all core tables

## Database Schema
The migration creates the following tables:

### Core Entities
1. **client** - Core client information (ID, name, personal details, contact info)
2. **current_employer** - Current employment details and grants
3. **employer_grant** - Grants from current employer
4. **grant** - General grants from past employers
5. **pension_funds** - Pension fund details and calculations
6. **additional_income** - Non-pension income sources
7. **capital_assets** - Investment and capital assets
8. **scenario** - Planning scenarios with parameters and results

### Key Features
- Foreign key relationships with CASCADE DELETE
- Comprehensive indexes for performance
- Check constraints for data validation
- Automatic timestamp management with triggers
- JSONB fields for flexible data storage
- Proper decimal precision for financial calculations

## Running the Migration

### Option 1: Using psql command line
```bash
# Connect to your PostgreSQL database
psql -h localhost -U your_username -d your_database_name

# Run the migration
\i migrations/001_init.sql

# Verify tables were created
\dt
```

### Option 2: Using psql with file input
```bash
psql -h localhost -U your_username -d your_database_name -f migrations/001_init.sql
```

### Option 3: Using environment variables
```bash
# Set connection parameters
export PGHOST=localhost
export PGUSER=your_username
export PGDATABASE=your_database_name
export PGPASSWORD=your_password

# Run migration
psql -f migrations/001_init.sql
```

## Verification Commands

After running the migration, verify the setup:

```sql
-- Check all tables were created
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Check indexes
SELECT indexname, tablename FROM pg_indexes 
WHERE schemaname = 'public' 
ORDER BY tablename, indexname;

-- Check foreign key constraints
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;

-- Check triggers
SELECT trigger_name, event_object_table 
FROM information_schema.triggers 
WHERE trigger_schema = 'public'
ORDER BY event_object_table;
```

## Sample Data Insert

Test the schema with sample data:

```sql
-- Insert a test client
INSERT INTO client (id_number, full_name, birth_date) 
VALUES ('123456789', 'ישראל ישראלי', '1970-01-01');

-- Insert current employer
INSERT INTO current_employer (client_id, employer_name, start_date, continuity_years)
VALUES (1, 'חברת טכנולוגיה בע"מ', '2020-01-01', 5.0);

-- Insert pension fund
INSERT INTO pension_funds (client_id, fund_name, input_mode, balance, annuity_factor)
VALUES (1, 'מנורה מבטחים פנסיה', 'calculated', 500000.00, 0.05);
```

## Rollback (if needed)

To rollback the migration:

```sql
-- Drop all tables in reverse dependency order
DROP TABLE IF EXISTS scenario CASCADE;
DROP TABLE IF EXISTS capital_assets CASCADE;
DROP TABLE IF EXISTS additional_income CASCADE;
DROP TABLE IF EXISTS pension_funds CASCADE;
DROP TABLE IF EXISTS grant CASCADE;
DROP TABLE IF EXISTS employer_grant CASCADE;
DROP TABLE IF EXISTS current_employer CASCADE;
DROP TABLE IF EXISTS client CASCADE;

-- Drop the trigger function
DROP FUNCTION IF EXISTS update_updated_at_column();
```

## Performance Notes

- All foreign key columns are indexed
- Client lookup by ID number is optimized
- Date range queries on income/assets are indexed
- JSONB fields support GIN indexes if needed for complex queries

## Security Considerations

- Use connection pooling in production
- Set appropriate user permissions
- Consider row-level security for multi-tenant scenarios
- Regular backup strategy recommended

## Next Steps

After successful migration:
1. Update application database connection settings
2. Run application tests to verify ORM compatibility
3. Consider adding additional indexes based on query patterns
4. Set up monitoring for database performance
