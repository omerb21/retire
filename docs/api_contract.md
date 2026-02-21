| Path | Methods | Purpose |
| --- | --- | --- |
| `/api/v1/clients/{id}/capital-assets` | GET, POST | List/create capital assets for a client |
| `/api/v1/clients/{id}/capital-assets/{asset_id}` | GET, PUT, DELETE | CRUD for a specific capital asset |
| `/api/v1/clients/{id}/additional-incomes` | GET, POST | List/create additional incomes for a client |
| `/api/v1/clients/{id}/additional-incomes/{income_id}` | GET, PUT, DELETE | CRUD for a specific additional income |
| `/api/v1/clients/{id}/pension-funds` | GET, POST | List/create pension funds for a client |
| `/api/v1/clients/{id}/pension-funds/{fund_id}` | GET, PUT, DELETE | CRUD for a specific pension fund |
| `/api/v1/clients/{id}/pension-funds/{fund_id}/compute` | POST | Recompute a pension fund |
| `/api/v1/clients/{id}` | GET | Fetch client details |

## Potential 422 risks

- **Capital assets conversion payload includes extra keys**
  Frontend `PensionPortfolio` conversion builds capital-asset payloads with keys like `purchase_value`, `purchase_date`, `annual_return`, `liquidity`, `risk_level` that are not part of `CapitalAssetCreate` (backend schema). The API currently tolerates this, but if the backend becomes strict about extra fields, this can start returning 422.
