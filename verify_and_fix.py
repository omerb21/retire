"""
Verification script that runs the specific test and makes fixes if needed
"""
import os
import sys
import subprocess
from datetime import date
import time

# Set up stdout to flush immediately for clearer output
class FlushingStdout:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
    
    def write(self, text):
        self.original_stdout.write(text)
        self.original_stdout.flush()
    
    def flush(self):
        self.original_stdout.flush()

sys.stdout = FlushingStdout(sys.stdout)

print("=" * 80)
print("VERIFYING CURRENT EMPLOYER ENDPOINT FIX")
print("=" * 80)

# 1. First fix the endpoint implementation to ensure it's clean and simple
print("\nStep 1: Verifying current_employer.py endpoint implementation")
endpoint_path = "app/routers/current_employer.py"

with open(endpoint_path, "r", encoding="utf-8") as f:
    content = f.read()

if "raw SQL" in content or "text(" in content or ".execute(" in content:
    print("WARNING: Found raw SQL in endpoint. This should be removed.")
else:
    print("✓ Endpoint implementation looks clean (no raw SQL)")

# 2. Check the conftest.py for proper fixture setup
print("\nStep 2: Checking conftest.py configuration")
conftest_path = "tests/conftest.py"

with open(conftest_path, "r", encoding="utf-8") as f:
    conftest_content = f.read()

if "_enforce_test_db_override" in conftest_content and "autouse=True" in conftest_content:
    print("✓ Found autouse fixture to enforce DB override")
else:
    print("WARNING: Missing autouse fixture to enforce DB override in conftest.py")

if "app.dependency_overrides.clear()" in conftest_content:
    print("WARNING: Found dependency override clear in conftest.py - this should be removed")
else:
    print("✓ No override clearing found in conftest.py")

# 3. Run the test with detailed output capture
print("\nStep 3: Running the specific test")
print("-" * 40)

test_cmd = ["pytest", "-v", 
            "tests/test_current_employer_api.py::TestCurrentEmployerAPI::test_get_current_employer_no_employer_404"]
print(f"Running command: {' '.join(test_cmd)}")

process = subprocess.Popen(
    test_cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1  # Line buffered
)

# Real-time output printing
for line in process.stdout:
    print(f"  {line.rstrip()}")

# Get return code
process.wait()
exit_code = process.returncode

print("-" * 40)
print(f"Test exit code: {exit_code}")

# 4. If test passed, try the full suite
if exit_code == 0:
    print("\nStep 4: Test passed! Running full test suite with maxfail=1")
    print("-" * 40)
    
    full_cmd = ["pytest", "-v", "--maxfail=1", "--disable-warnings"]
    print(f"Running command: {' '.join(full_cmd)}")
    
    full_process = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Count tests
    passed_count = 0
    failed_count = 0
    
    # Print just the test results
    for line in full_process.stdout:
        if "PASSED" in line or "FAILED" in line:
            print(f"  {line.rstrip()}")
            if "PASSED" in line:
                passed_count += 1
            if "FAILED" in line:
                failed_count += 1
                print(f"    ❌ Test failed: {line.strip()}")
                break
    
    full_process.wait()
    print("-" * 40)
    print(f"Full test suite exit code: {full_process.returncode}")
    print(f"Tests passed: {passed_count}")
    print(f"Tests failed: {failed_count}")
    
    if full_process.returncode == 0:
        print("\n✅ SUCCESS: All tests are now passing!")
    else:
        print("\n⚠️ Some tests still failing, but our target test should be fixed.")
else:
    print("\n❌ Test still failing - check the implementation")

print("\nVerification complete.")
