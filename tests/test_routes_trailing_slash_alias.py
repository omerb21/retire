import json


def test_get_trailing_slash_aliases(test_client, client):
    endpoints = [
        f"/api/v1/clients/{client.id}/capital-assets",
        f"/api/v1/clients/{client.id}/pension-funds",
        f"/api/v1/clients/{client.id}/additional-incomes",
    ]

    for base in endpoints:
        res_no = test_client.get(base)
        res_sl = test_client.get(base + "/")
        assert res_no.status_code == res_sl.status_code, (
            base,
            res_no.status_code,
            res_sl.status_code,
            res_no.text,
            res_sl.text,
        )


def test_post_trailing_slash_aliases(test_client, client):
    payloads = [
        (
            f"/api/v1/clients/{client.id}/capital-assets",
            {
                "asset_name": "test-asset",
                "asset_type": "other",
                "description": "created by test",
                "current_value": 0,
                "annual_return_rate": 0,
                "payment_frequency": "monthly",
                "start_date": "2025-01-01",
                "indexation_method": "none",
                "tax_treatment": "taxable",
            },
        ),
        (
            f"/api/v1/clients/{client.id}/pension-funds",
            {
                "client_id": int(client.id),
                "fund_name": "test-fund",
                "fund_type": "computed",
                "input_mode": "manual",
                "balance": 1000,
                "pension_start_date": "2025-01-01",
                "indexation_method": "none",
                "tax_treatment": "taxable",
            },
        ),
        (
            f"/api/v1/clients/{client.id}/additional-incomes",
            {
                "source_type": "rental",
                "description": "test-income",
                "amount": 100,
                "frequency": "monthly",
                "start_date": "2025-01-01",
                "indexation_method": "none",
                "tax_treatment": "taxable",
            },
        ),
    ]

    for base, payload in payloads:
        res_no = test_client.post(
            base,
            data=json.dumps(payload),
            headers={"content-type": "application/json"},
        )
        res_sl = test_client.post(
            base + "/",
            data=json.dumps(payload),
            headers={"content-type": "application/json"},
        )
        assert res_no.status_code == res_sl.status_code, (
            base,
            res_no.status_code,
            res_sl.status_code,
            res_no.text,
            res_sl.text,
        )
