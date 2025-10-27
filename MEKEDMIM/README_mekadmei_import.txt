CSV and loaders generated on 2025-10-26.
Files:
- policy_generation_coefficient.csv
- product_to_generation_map.csv
- company_annuity_coefficient.csv
- pension_fund_coefficient.csv
- load_postgres.sql
- load_sqlite.sql

Quick start - PostgreSQL (Windows PowerShell):
1) cd to the folder with the files
2) psql -U postgres -d retire -h localhost -f load_postgres.sql

Quick start - SQLite:
1) sqlite3 retire.db < load_sqlite.sql

Integration note:
Use select_annuity_factor(product) as specified earlier. product_type 'קרן פנסיה' should query pension_fund_coefficient;
otherwise map generation via product_to_generation_map and attempt a company-specific match before falling back to policy_generation_coefficient.
