import json


def test_post_capital_assets_without_trailing_slash_returns_201(test_client, client):
    payload = {
        "asset_name": "test-asset",
        "asset_type": "other",
        "description": "created by test",
        "current_value": 0,
        "annual_return_rate": 0,
        "payment_frequency": "monthly",
        "start_date": "2025-01-01",
        "indexation_method": "none",
        "tax_treatment": "taxable",
    }

    res = test_client.post(
        f"/api/v1/clients/{client.id}/capital-assets",
        data=json.dumps(payload),
        headers={"content-type": "application/json"},
    )

    assert res.status_code == 201, res.text


def test_get_capital_assets_without_trailing_slash_returns_200(test_client, client):
    res = test_client.get(f"/api/v1/clients/{client.id}/capital-assets")
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)
