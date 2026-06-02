def _grant_payload(amount: float) -> dict:
    return {
        "employer_name": "Previous Employer",
        "work_start_date": "2010-01-01",
        "work_end_date": "2015-12-31",
        "grant_type": "severance",
        "grant_date": "2015-12-31",
        "grant_amount": amount,
        "reason": "Prior employer with no exempt grant",
    }


def test_create_prior_employer_grant_allows_zero_amount(client):
    response = client.post(
        f"/api/v1/clients/{client.id}/grants",
        json=_grant_payload(0),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["employer_name"] == "Previous Employer"
    assert data["grant_amount"] == 0


def test_create_prior_employer_grant_rejects_negative_amount(client):
    response = client.post(
        f"/api/v1/clients/{client.id}/grants",
        json=_grant_payload(-1),
    )

    assert response.status_code == 422
