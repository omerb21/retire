import pytest


def test_snapshot_restore_rejects_incomplete_payload_without_wiping_db(db_session, client):
    from app.models.pension_fund import PensionFund

    # Ensure there is at least one row so a destructive restore would be detectable,
    # but do not assume the shared test DB is empty.
    before = db_session.query(PensionFund).filter(PensionFund.client_id == client.id).count()
    if before == 0:
        pf = PensionFund(
            client_id=client.id,
            fund_name="Seed Fund",
            fund_type="קופת גמל",
            input_mode="manual",
            balance=123.0,
            annuity_factor=None,
            pension_amount=None,
            pension_start_date=None,
            indexation_method="none",
            fixed_index_rate=None,
            indexed_pension_amount=None,
            tax_treatment="taxable",
            remarks=None,
            deduction_file="A-1",
            conversion_source=None,
        )
        db_session.add(pf)
        db_session.commit()
        before = db_session.query(PensionFund).filter(PensionFund.client_id == client.id).count()
        assert before >= 1

    # Incomplete payload (missing data.* fields) should be rejected.
    resp = client.post(
        f"/api/v1/clients/{client.id}/snapshot/restore",
        json={"client_id": client.id, "pension_portfolio": []},
    )
    assert resp.status_code == 422

    after = db_session.query(PensionFund).filter(PensionFund.client_id == client.id).count()
    assert after == before


def test_snapshot_restore_accepts_wrapped_snapshot_payload(db_session, client):
    from app.models.pension_fund import PensionFund

    # Start with empty DB.
    db_session.query(PensionFund).filter(PensionFund.client_id == client.id).delete(synchronize_session=False)
    db_session.commit()

    payload = {
        "force_restore": True,
        "snapshot": {
            "client_id": client.id,
            "snapshot_name": "test",
            "created_at": "2026-01-01T00:00:00",
            "data": {
                "pension_funds": [
                    {
                        "client_id": client.id,
                        "fund_name": "Restored Fund",
                        "fund_type": "קופת גמל",
                        "input_mode": "manual",
                        "balance": 456.0,
                        "annuity_factor": None,
                        "pension_amount": None,
                        "pension_start_date": None,
                        "indexation_method": "none",
                        "fixed_index_rate": None,
                        "indexed_pension_amount": None,
                        "tax_treatment": "taxable",
                        "remarks": None,
                        "deduction_file": "B-2",
                        "conversion_source": None,
                    }
                ],
                "capital_assets": [],
                "additional_incomes": [],
                "current_employer": None,
                "grants": [],
                "legacy_grants": [],
                "termination_event": None,
                "fixation_result": None,
            },
        }
    }

    resp = client.post(
        f"/api/v1/clients/{client.id}/snapshot/restore",
        json=payload,
    )
    assert resp.status_code == 200

    funds = db_session.query(PensionFund).filter(PensionFund.client_id == client.id).all()
    assert len(funds) == 1
    assert funds[0].fund_name == "Restored Fund"
