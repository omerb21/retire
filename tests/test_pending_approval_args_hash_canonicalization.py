from decimal import Decimal

from app.services.llm_chat.pending_approvals import compute_args_hash


def test_pending_approval_args_hash_canonicalization_is_stable() -> None:
    args_a = {
        "b": {
            "z": 1,
            "y": "1.00",
            "x": "01",
        },
        "a": 1.0,
        "accounts": [
            {
                "account_id": "A",
                "amount": 31000.00,
            }
        ],
    }

    args_b = {
        "accounts": [
            {
                "amount": Decimal("31000"),
                "account_id": "A",
            }
        ],
        "a": Decimal("1.000"),
        "b": {
            "x": "01",
            "y": "1",
            "z": "1",
        },
    }

    assert compute_args_hash(args_a) == compute_args_hash(args_b)
