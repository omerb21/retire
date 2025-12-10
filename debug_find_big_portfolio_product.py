import json
from decimal import Decimal

from app.database import get_db
from app.models.pension_fund import PensionFund


def main() -> None:
    db = next(get_db())
    try:
        query = db.query(PensionFund).filter(PensionFund.conversion_source != None)  # noqa: E711
        largest = None
        largest_data = None

        for pf in query:
            try:
                data = json.loads(pf.conversion_source or "{}")
            except Exception:
                continue

            # We expect structure created by PortfolioImportService.import_pension_portfolio
            original_balance = data.get("original_balance") or data.get("amount")
            try:
                if original_balance is not None:
                    original_balance = float(original_balance)
                else:
                    continue
            except Exception:
                continue

            if largest is None or original_balance > largest[0]:
                largest = (original_balance, pf)
                largest_data = data

        print("=== Largest pension_portfolio product by original_balance ===")
        if not largest or not largest_data:
            print("No pension_portfolio-based PensionFund with original_balance found")
            return

        balance, pf = largest
        product_type = largest_data.get("product_type")
        account_name = largest_data.get("account_name")
        account_number = largest_data.get("account_number")

        print(f"client_id={pf.client_id}")
        print(f"fund_name={pf.fund_name}")
        print(f"product_type={product_type}")
        print(f"original_balance={balance}")
        print(f"conversion_source_account_name={account_name}")
        print(f"conversion_source_account_number={account_number}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
