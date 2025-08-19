# Pension Fund Calculation Features

This document describes the pension fund calculation features implemented in Sprint 5 of the Retirement Benefits Calculator project.

## Overview

The pension fund calculation system allows for calculating, indexing, and projecting pension amounts from various pension funds. It supports different input modes and indexation methods to provide flexible and accurate pension calculations.

## Core Components

### 1. Pension Fund Model

The `PensionFund` model supports:
- Two input modes: `calculated` and `manual`
- Three indexation methods: `none`, `fixed`, and `cpi`
- Storing both base pension amount and indexed pension amount

### 2. Calculation Services

#### Pension Fund Service (`app/services/pension_fund_service.py`)

- `calculate_pension_amount`: Calculates the base pension amount based on input mode
- `compute_and_apply_indexation`: Applies indexation to the base pension amount
- `compute_and_persist`: Calculates and persists pension amounts to the database
- `compute_all_pension_funds`: Calculates all pension funds for a client

#### Pension Calculation (`app/calculation/pensions.py`)

- `calc_monthly_pension_from_capital`: Calculates monthly pension from capital using annuity factor
- `calc_pension_from_fund`: Calculates pension amount from a pension fund
- `apply_indexation`: Applies indexation to a pension amount
- `project_pension_cashflow`: Projects pension cashflow for a number of months

#### Pension Integration (`app/calculation/pension_integration.py`)

- `calculate_total_monthly_pension`: Calculates total monthly pension from all funds
- `generate_combined_pension_cashflow`: Generates combined pension cashflow for all client's funds
- `integrate_pension_funds_with_scenario`: Integrates pension funds cashflow with scenario cashflow

### 3. API Endpoints

#### Pension Fund Router (`app/routers/pension_fund.py`)

- `POST /api/v1/clients/{client_id}/pension-funds`: Create a new pension fund
- `GET /api/v1/pension-funds/{fund_id}`: Get a specific pension fund
- `PUT /api/v1/pension-funds/{fund_id}`: Update a pension fund
- `DELETE /api/v1/pension-funds/{fund_id}`: Delete a pension fund
- `POST /api/v1/pension-funds/{fund_id}/compute`: Compute a pension fund
- `POST /api/v1/clients/{client_id}/pension-funds/compute-all`: Compute all pension funds for a client
- `GET /api/v1/clients/{client_id}/pension-funds`: Get all pension funds for a client

#### Pension Scenario Router (`app/routers/pension_scenario.py`)

- `POST /api/v1/clients/{client_id}/pension-cashflow`: Get pension cashflow for a client
- `POST /api/v1/clients/{client_id}/pension-scenario`: Calculate scenario with pension funds integration

## Indexation Methods

### None Indexation
No indexation is applied. The indexed amount equals the base amount.

### Fixed Indexation
Applies a fixed annual rate using compound interest formula: `amount * (1 + rate)^years`

### CPI Indexation
Applies Consumer Price Index (CPI) indexation using the ratio of CPI values: `amount * (current_cpi / start_cpi)`

## Testing

The pension calculation features are tested through:

1. Unit tests in `tests/test_pension_fund_calculation.py`
2. Manual test script in `manual_test_pension_calculation.py`
3. Simple test script in `simple_pension_test.py`

## Integration with Scenario Calculation

The pension fund calculations are integrated with the scenario calculation engine to provide a comprehensive retirement planning solution. This integration allows for:

1. Including pension income in cashflow projections
2. Combining multiple pension sources into a single cashflow
3. Applying different indexation methods to different pension sources

## Future Enhancements

Potential future enhancements include:

1. Support for more complex indexation methods
2. Integration with tax calculation for pension income
3. Support for pension fund transfers and withdrawals
4. Frontend components for pension fund management
