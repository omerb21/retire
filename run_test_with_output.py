"""
Script to run a specific test and capture the output
"""
import os
import subprocess
import sys

# Define the test to run - use command line argument if provided
if len(sys.argv) > 1:
    test_path = sys.argv[1]
else:
    test_path = "tests/test_pension_fund_calculation.py"
    
output_file = "test_output.txt"

# Run the test with pytest and capture output
cmd = f"python -m pytest {test_path} -v"
print(f"Running command: {cmd}")

result = subprocess.run(
    cmd, 
    shell=True, 
    capture_output=True,
    text=True
)

# Write output to file
with open(output_file, "w", encoding="utf-8") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\n\nExit code: {result.returncode}")

print(f"Test output written to {output_file}")
print(f"Exit code: {result.returncode}")

# Also print the output
print("\n===== TEST OUTPUT =====")
print(result.stdout)
print("\n===== TEST ERRORS =====")
print(result.stderr)

if result.returncode == 0:
    print("\nTEST PASSED!")
else:
    print("\nTEST FAILED!")
