import json

from app.database import get_db
from app.models.scenario import Scenario


def main() -> None:
    session = next(get_db())
    try:
        scenarios = session.query(Scenario).all()
        print(f"Total scenarios: {len(scenarios)}")
        largest = None
        largest_ctx = None
        for sc in scenarios:
            if not sc.parameters:
                continue
            try:
                params = json.loads(sc.parameters)
            except Exception as e:
                print(f"Scenario {sc.id} params JSON error: {e}")
                continue
            portfolio = params.get("pension_portfolio")
            if not isinstance(portfolio, list):
                continue
            for acc in portfolio:
                try:
                    bal = float(acc.get("יתרה", 0) or 0)
                except Exception:
                    bal = 0.0
                if bal <= 0:
                    continue
                if largest is None or bal > largest[0]:
                    largest = (bal, sc.id)
                    largest_ctx = {
                        "client_id": sc.client_id,
                        "scenario_id": sc.id,
                        "account": acc,
                    }
        print("Largest balance from any scenario.pension_portfolio:")
        if not largest_ctx:
            print("  (none)")
        else:
            print(f"  client_id={largest_ctx['client_id']}, scenario_id={largest_ctx['scenario_id']}")
            acc = largest_ctx["account"]
            print(f"  account name={acc.get('שם_תכנית')}")
            print(f"  product_type (סוג_מוצר)={acc.get('סוג_מוצר')}")
            print(f"  balance (יתרה)={largest[0]:,.2f}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
