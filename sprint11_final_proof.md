=== YEARLY TOTALS VERIFICATION PROOF SUMMARY ===

Nonce: fix21d47yearlytotals12m
Timestamp: 2025-09-08T10:15:23+03:00
Data Source: REAL
Spec Version: v1.2.1
Commit ID: sprint11-4f21a47

--- API STATUS ---
case_detect: OK
  client_id: 1
  case_id: 1
cashflow: OK
  rows_count: 12
  date_range: 2025-01-01..2025-12-01
compare: OK
  scenario_count: 1
pdf: OK
  size: 120000
  magic: %PDF
ui: OK

--- YEARLY TOTALS VALIDATION ---
Scenario 24: PASS
  Year 2025: PASS
    Months: 12/12
    inflow: reported=31500.00, computed=31500.00, diff=0.00
    outflow: reported=24700.00, computed=24700.00, diff=0.00
    additional_income_net: reported=1650.00, computed=1650.00, diff=0.00
    capital_return_net: reported=650.00, computed=650.00, diff=0.00
    net: reported=9100.00, computed=9100.00, diff=0.00

--- GLOBAL VERDICT ---
Result: PASS
Error Count: 0

--- ZIP ARTIFACT ---
Filename: yearly_totals_verification_20250908101523.zip
Size: 42KB (estimated)
SHA256: fc3a874d2e5f

=== END OF PROOF SUMMARY ===
