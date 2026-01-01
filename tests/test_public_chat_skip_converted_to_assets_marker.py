import app.services.public_chat_service as public_chat_service


def test_public_chat_marker_apply_skips_converted_to_assets_operation() -> None:
    accounts = [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "תכנית 1",
            "יתרה": 1000,
            "תגמולי_עובד_אחרי_2000": 1000,
        }
    ]

    payloads = [
        {
            "type": "pension_portfolio_updates",
            "operation": "converted_to_assets",
            "updates": [
                {
                    "account_number": "A-001",
                    "converted_amount": 500,
                    "specific_amounts": {"תגמולי_עובד_אחרי_2000": 500},
                }
            ],
        }
    ]

    updated = public_chat_service._apply_marker_payloads_to_snapshot_accounts(
        accounts=accounts,
        portfolio_payloads=payloads,
        severance_payloads=[],
    )

    # Should not apply subtraction because the DB snapshot is already updated by the tool.
    a = next(a for a in updated if a.get("מספר_חשבון") == "A-001")
    assert float(a.get("תגמולי_עובד_אחרי_2000") or 0) == 1000
    assert float(a.get("יתרה") or 0) == 1000


def test_public_chat_marker_apply_still_applies_other_operations() -> None:
    accounts = [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "תכנית 1",
            "יתרה": 1000,
            "תגמולי_עובד_אחרי_2000": 1000,
        }
    ]

    payloads = [
        {
            "type": "pension_portfolio_updates",
            "operation": "pension_commutation",
            "updates": [
                {
                    "account_number": "A-001",
                    "converted_amount": 500,
                    "specific_amounts": {"תגמולי_עובד_אחרי_2000": 500},
                }
            ],
        }
    ]

    updated = public_chat_service._apply_marker_payloads_to_snapshot_accounts(
        accounts=accounts,
        portfolio_payloads=payloads,
        severance_payloads=[],
    )

    a = next(a for a in updated if a.get("מספר_חשבון") == "A-001")
    assert float(a.get("תגמולי_עובד_אחרי_2000") or 0) == 500
    assert float(a.get("יתרה") or 0) == 1000
