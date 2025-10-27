-- Migration: Add plan_name and plan_start_date to employer_grant table
-- Date: 2025-10-27
-- Description: Add fields to link employer grants to specific pension plans

-- Add plan_name column
ALTER TABLE employer_grant ADD COLUMN plan_name TEXT;

-- Add plan_start_date column
ALTER TABLE employer_grant ADD COLUMN plan_start_date DATE;

-- Add comment
COMMENT ON COLUMN employer_grant.plan_name IS 'שם התכנית מתיק הפנסיה';
COMMENT ON COLUMN employer_grant.plan_start_date IS 'תאריך התחלת התכנית (לחישוב מקדם קצבה)';
