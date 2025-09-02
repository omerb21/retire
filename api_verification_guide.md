# API Verification Guide

This guide explains how to use the API Verification Tool to test and verify the functionality of the retirement planning system's API endpoints.

## Getting Started

1. Make sure the API server is running at http://localhost:8000
2. Open the `api_verification.html` file in your web browser
3. The verification tool will load with multiple tabs for testing different API features

## Client Lookup

Before testing specific API endpoints, you should first look up a client:

1. Enter a valid ID number in the "Client Lookup" section
2. Click "Lookup Client"
3. If found, client details will be displayed
4. Click "Use This Client" to automatically populate all client ID fields in the verification tool

## Automatic Test Sequence

For quick verification of multiple API endpoints:

1. Enter a client ID or use the "Use This Client" button to populate it
2. Select which components to test by checking/unchecking the options
3. Click "Run Automatic Tests"
4. The tool will run through all selected tests sequentially
5. Results will be displayed with pass/fail status for each test
6. Test resources are automatically cleaned up after completion

## Manual Testing

### Pension Funds

The Pension Funds tab allows testing of pension fund creation, listing, and deletion:

- **Calculated Mode**: Create a pension fund with calculated values
- **Manual Mode**: Create a pension fund with manually entered values
- **List Pension Funds**: View all pension funds for a client
- **Delete**: Remove individual pension funds or all funds at once

### Additional Income

Test the additional income API endpoints:

- Create additional income entries with various frequencies and indexation methods
- List all additional incomes for a client
- Delete individual income entries or all at once

### Capital Assets

Test the capital asset API endpoints:

- Create capital assets with different payment frequencies and return rates
- List all capital assets for a client
- Delete individual assets or all at once

### Scenarios

Test scenario creation and management:

- Create scenarios with different parameters
- List all scenarios for a client
- Delete scenarios

### Integration

Test the integration of different components:

- Select a client and scenario
- Integrate pension funds, additional incomes, and capital assets
- View the integrated cashflow

### Fixation

Test the fixation computation:

- Compute fixation for a client
- View the fixation results

## Troubleshooting

If you encounter errors during testing:

1. Check the browser console for detailed error messages
2. Verify that the API server is running at http://localhost:8000
3. Ensure you're using a valid client ID for all operations
4. Check that the client has the necessary data for the operation (e.g., pension funds for integration)

## API Endpoints Reference

### Client Endpoints
- `GET /clients/lookup?id_number={id_number}` - Look up client by ID number
- `GET /clients/{id}` - Get client details

### Pension Fund Endpoints
- `GET /clients/{id}/pension-funds` - List all pension funds
- `POST /clients/{id}/pension-funds` - Create a new pension fund
- `DELETE /clients/{id}/pension-funds/{fund_id}` - Delete a pension fund

### Additional Income Endpoints
- `GET /clients/{id}/additional-incomes` - List all additional incomes
- `POST /clients/{id}/additional-incomes` - Create a new additional income
- `DELETE /clients/{id}/additional-incomes/{income_id}` - Delete an additional income

### Capital Asset Endpoints
- `GET /clients/{id}/capital-assets` - List all capital assets
- `POST /clients/{id}/capital-assets` - Create a new capital asset
- `DELETE /clients/{id}/capital-assets/{asset_id}` - Delete a capital asset

### Scenario Endpoints
- `GET /clients/{id}/scenarios` - List all scenarios
- `POST /clients/{id}/scenarios` - Create a new scenario
- `DELETE /clients/{id}/scenarios/{scenario_id}` - Delete a scenario
- `POST /clients/{id}/scenarios/{scenario_id}/integrate` - Integrate a scenario

### Fixation Endpoints
- `POST /fixation/{id}/compute` - Compute fixation for a client
