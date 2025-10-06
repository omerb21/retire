# API Verification Checklist

## Client Lookup
- [ ] Look up client by ID number
- [ ] Verify client details display correctly
- [ ] Use client ID across all forms with "Use This Client" button

## Automatic Test Sequence
- [ ] Enter valid client ID
- [ ] Select test modules to include (pension funds, additional incomes, etc.)
- [ ] Run automatic test sequence
- [ ] Verify progress bar updates during test execution
- [ ] Check test results display with pass/fail status
- [ ] Verify test resources are properly cleaned up

## Pension Fund Module
- [ ] Create calculated pension fund with fixed indexation rate
- [ ] Create manual pension fund with CPI indexation
- [ ] Verify indexation display shows correct percentage (not "undefined%")
- [ ] Delete individual pension fund using delete button
- [ ] Delete all pension funds

## Fixation Module
- [ ] Compute fixation for a client
- [ ] Verify proper response handling and display

## Scenario Module
- [ ] Create new scenario
- [ ] List scenarios
- [ ] Select scenario for integration
- [ ] View cashflow for scenario

## Additional Income Module
- [ ] Create additional income
- [ ] List additional incomes
- [ ] Delete individual income using delete button
- [ ] Delete all incomes

## Capital Asset Module
- [ ] Create capital asset
- [ ] List capital assets
- [ ] Delete individual asset using delete button
- [ ] Delete all assets

## Integration
- [ ] Integrate scenario with all components
- [ ] View integrated cashflow

## Cross-Module Tests
- [ ] Create client with pension funds, incomes, and assets
- [ ] Create scenario and integrate all components
- [ ] Verify cashflow includes all components

## Error Handling
- [ ] Test with invalid client ID
- [ ] Test with missing required fields
- [ ] Verify error messages display correctly
- [ ] Check console for detailed error logging
