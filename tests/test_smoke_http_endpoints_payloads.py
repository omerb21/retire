import json

import pytest


def _post_json(test_client, url: str, payload: dict):
    res = test_client.post(
        url,
        data=json.dumps(payload),
        headers={"content-type": "application/json"},
    )
    if res.status_code == 422:
        pytest.fail(f"422 on POST {url}: {res.text}")
    assert res.status_code in (200, 201), (url, res.status_code, res.text)
    return res


@pytest.mark.parametrize(
    "url,payload_variants",
    [
        (
            "/api/v1/clients/{client_id}/capital-assets",
            [
                {
                    "asset_name": "smoke-asset",
                    "asset_type": "other",
                    "description": "smoke test",
                    "current_value": 0,
                    "annual_return_rate": 0.03,
                    "payment_frequency": "monthly",
                    "start_date": "2025-01-01",
                    "indexation_method": "none",
                    "tax_treatment": "taxable",
                    "monthly_income": 0,
                },
                {
                    "asset_name": "smoke-asset-extra",
                    "asset_type": "other",
                    "description": "smoke test (extra FE keys)",
                    "current_value": 0,
                    "annual_return_rate": 0.03,
                    "payment_frequency": "monthly",
                    "start_date": "2025-01-01",
                    "indexation_method": "none",
                    "tax_treatment": "taxable",
                    "monthly_income": 100,
                    "conversion_source": json.dumps(
                        {"type": "pension_portfolio", "account_name": "x"}
                    ),
                    "purchase_value": 123,
                    "purchase_date": "2025-01-01",
                    "annual_return": 0,
                    "liquidity": "medium",
                    "risk_level": "medium",
                },
            ],
        ),
        (
            "/api/v1/clients/{client_id}/pension-funds",
            [
                {
                    "client_id": "{client_id}",
                    "fund_name": "smoke-fund",
                    "fund_type": "computed",
                    "input_mode": "manual",
                    "balance": 1000,
                    "pension_start_date": "2025-01-01",
                    "indexation_method": "none",
                    "tax_treatment": "taxable",
                },
                {
                    "client_id": "{client_id}",
                    "fund_name": "smoke-fund-extra",
                    "fund_type": "computed",
                    "input_mode": "manual",
                    "balance": 1000.0,
                    "annuity_factor": 200,
                    "pension_amount": 5,
                    "pension_start_date": "2025-01-01",
                    "indexation_method": "none",
                    "tax_treatment": "taxable",
                    "remarks": "smoke test",
                },
            ],
        ),
        (
            "/api/v1/clients/{client_id}/additional-incomes",
            [
                {
                    "source_type": "rental",
                    "description": "smoke-income",
                    "amount": 100,
                    "frequency": "monthly",
                    "start_date": "2025-01-01",
                    "indexation_method": "none",
                    "tax_treatment": "taxable",
                },
                {
                    "source_type": "rental",
                    "description": "smoke-income-extra",
                    "amount": 100.0,
                    "frequency": "monthly",
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "indexation_method": "none",
                    "tax_treatment": "taxable",
                    "remarks": "smoke test",
                },
            ],
        ),
    ],
)
def test_smoke_post_payloads_against_schemas(
    test_client, client, url, payload_variants
):
    url = url.format(client_id=client.id)

    for payload in payload_variants:
        normalized = json.loads(json.dumps(payload))
        if "client_id" in normalized and normalized["client_id"] == "{client_id}":
            normalized["client_id"] = int(client.id)
        _post_json(test_client, url, normalized)


def _load_openapi(test_client):
    preferred = test_client.get("/api/v1/openapi.json")
    if preferred.status_code == 200:
        return preferred.json()

    fallback = test_client.get("/openapi.json")
    assert fallback.status_code == 200, fallback.text
    return fallback.json()


def _extract_request_schema_name(op: dict, path: str, method: str) -> str:
    node = op.get("paths", {}).get(path, {}).get(method, {})
    rb = node.get("requestBody") or {}
    content = (rb.get("content") or {}).get("application/json") or {}
    schema = content.get("schema") or {}

    ref = schema.get("$ref")
    if not ref and isinstance(schema.get("anyOf"), list) and schema["anyOf"]:
        ref = schema["anyOf"][0].get("$ref")

    assert isinstance(ref, str) and "/schemas/" in ref, (path, method, schema)
    return ref.split("/schemas/")[-1]


def test_openapi_contract_snapshot_for_request_bodies(test_client):
    op = _load_openapi(test_client)

    expected = {
        "/api/v1/clients/{client_id}/capital-assets": {"post": "CapitalAssetCreate"},
        "/api/v1/clients/{client_id}/pension-funds": {"post": "PensionFundCreate"},
        "/api/v1/clients/{client_id}/additional-incomes": {
            "post": "AdditionalIncomeCreate"
        },
    }

    paths = op.get("paths", {})
    for path, methods in expected.items():
        assert path in paths, f"Missing path in OpenAPI: {path}"
        for method, expected_schema in methods.items():
            assert (
                method in paths[path]
            ), f"Missing method in OpenAPI: {method.upper()} {path}"
            actual = _extract_request_schema_name(op, path, method)
            assert (
                actual == expected_schema
            ), f"Request schema changed for {method.upper()} {path}: {actual} != {expected_schema}"
