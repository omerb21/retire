import app.services.public_chat_service as public_chat_service


def test_public_chat_portfolio_update_preserves_accounts_with_hebrew_space_key() -> None:
    accounts = [
        {
            "מספר חשבון": "A-001",
            "שם_תכנית": "תכנית 1",
            "יתרה": 1000,
            "תגמולי_עובד_אחרי_2000": 1000,
        },
        {
            "מספר_חשבון": "B-002",
            "שם_תכנית": "תכנית 2",
            "יתרה": 2000,
            "תגמולי_עובד_אחרי_2000": 2000,
        },
    ]

    payload = {
        "type": "pension_portfolio_updates",
        "updates": [
            {
                "account_number": "A-001",
                "converted_amount": 500,
                "specific_amounts": {"תגמולי_עובד_אחרי_2000": 500},
            }
        ],
    }

    updated = public_chat_service._apply_portfolio_updates_to_accounts(accounts, payload)

    assert isinstance(updated, list)
    account_numbers = {
        str(a.get("מספר_חשבון") or a.get("מספר חשבון") or a.get("account_number") or "").strip()
        for a in updated
        if isinstance(a, dict)
    }
    assert "A-001" in account_numbers
    assert "B-002" in account_numbers

    a = next(
        a
        for a in updated
        if str(a.get("מספר_חשבון") or a.get("מספר חשבון") or "").strip() == "A-001"
    )
    assert a.get("מספר_חשבון") == "A-001"
    assert a.get("מספר חשבון") == "A-001"
    assert float(a.get("תגמולי_עובד_אחרי_2000") or 0) == 500


def test_public_chat_portfolio_update_preserves_accounts_with_hyphen_key() -> None:
    accounts = [
        {
            "מספר-חשבון": "C-003",
            "שם_תכנית": "תכנית 3",
            "יתרה": 3000,
            "תגמולי_עובד_אחרי_2000": 3000,
        },
        {
            "מספר_חשבון": "D-004",
            "שם_תכנית": "תכנית 4",
            "יתרה": 4000,
            "תגמולי_עובד_אחרי_2000": 4000,
        },
    ]

    payload = {
        "type": "pension_portfolio_updates",
        "updates": [
            {
                "account_number": "C-003",
                "converted_amount": 1000,
                "specific_amounts": {"תגמולי_עובד_אחרי_2000": 1000},
            }
        ],
    }

    updated = public_chat_service._apply_portfolio_updates_to_accounts(accounts, payload)

    assert isinstance(updated, list)
    account_numbers = {
        str(a.get("מספר_חשבון") or a.get("מספר חשבון") or a.get("מספר-חשבון") or "").strip()
        for a in updated
        if isinstance(a, dict)
    }
    assert "C-003" in account_numbers
    assert "D-004" in account_numbers

    c = next(
        a
        for a in updated
        if str(a.get("מספר_חשבון") or a.get("מספר חשבון") or a.get("מספר-חשבון") or "").strip() == "C-003"
    )
    assert c.get("מספר_חשבון") == "C-003"
    assert c.get("מספר חשבון") == "C-003"
    assert float(c.get("תגמולי_עובד_אחרי_2000") or 0) == 2000
