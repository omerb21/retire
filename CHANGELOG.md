# Changelog

## [Unreleased]

### Added - Sprint 3: Current Employer & Grants
- **New Models**: CurrentEmployer and EmployerGrant with comprehensive fields for retirement calculations
- **New API Endpoints**:
  - `POST /api/v1/clients/{client_id}/employment/current` - Create/update current employer
  - `GET /api/v1/clients/{client_id}/employment/current` - Retrieve current employer
  - `POST /api/v1/clients/{client_id}/employment/current/grants` - Add grant with calculations
- **Calculation Services**: Service years calculation with non-continuous periods support
- **Grant Calculations**: Severance grant calculation with indexing and tax breakdown (stub implementation)
- **Comprehensive Test Suite**: Unit tests for calculation logic and API integration tests

### Fixed
- Updated all fixation endpoints to use SQLAlchemy 2.0's `db.get()` method
- Standardized response structure across all fixation endpoints
- Ensured consistent Hebrew error messages for client not found (404)
- Added missing fields to `/compute` endpoint response (client_name, success, status, message)

### Changed
- Improved test reliability by ensuring proper database session handling
- Updated documentation to reflect response structure changes

### Removed
- Removed temporary test skips in fixation API tests

## [1.0.0] - YYYY-MM-DD
### Added
- Initial version of the retirement benefits calculator
