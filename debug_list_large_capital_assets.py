import json

from app.database import get_db
from app.models.capital_asset import CapitalAsset


def main() -> None:
    db = next(get_db())
    try:
        assets = (
            db.query(CapitalAsset)
            .filter(CapitalAsset.current_value != None)  # noqa: E711
            .all()
        )
        print("=== Capital assets with current_value >= 1,000,000 ===")
        large = [a for a in assets if float(a.current_value or 0) >= 1_000_000]
        if not large:
            print("(none)")
            return
        for a in large:
            print("-")
            print(f"id={a.id}")
            print(f"client_id={a.client_id}")
            print(f"asset_name={a.asset_name}")
            print(f"asset_type={a.asset_type}")
            print(f"current_value={float(a.current_value or 0):,.2f}")
            print(f"tax_treatment={a.tax_treatment}")
            print(f"remarks={a.remarks}")
            if a.conversion_source:
                try:
                    src = json.loads(a.conversion_source)
                except Exception:
                    src = a.conversion_source
                print(f"conversion_source={src}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
