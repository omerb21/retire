-- Add severance_before_termination column to current_employer table
ALTER TABLE current_employer ADD COLUMN severance_before_termination FLOAT NULL;

-- Add severance_before_termination column to employment table  
ALTER TABLE employment ADD COLUMN severance_before_termination NUMERIC(12,2) NULL;
