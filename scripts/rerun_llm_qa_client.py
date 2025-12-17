import argparse
import json
import sqlite3
import sys
import urllib.request
from collections import Counter
from typing import Any


def _load_portfolio_from_llm_capital_assets(*, db_path: str, client_id: int) -> list[dict[str, Any]]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        rows = cur.execute(
            """
            select current_value, conversion_source
            from capital_assets
            where client_id = ? and conversion_source like ?
            order by id asc
            """,
            (client_id, "%llm_transform_funds_to_assets%"),
        ).fetchall()

        accounts: list[dict[str, Any]] = []
        for current_value, conversion_source in rows:
            meta: dict[str, Any] = {}
            if conversion_source:
                try:
                    meta = json.loads(conversion_source)
                except Exception:
                    meta = {}

            account_number = meta.get("account_number")
            if not account_number:
                continue

            balance = None
            try:
                balance = float(current_value)
            except Exception:
                balance = None

            accounts.append(
                {
                    "מספר_חשבון": str(account_number),
                    "שם_תכנית": meta.get("account_name") or "", 
                    "חברה_מנהלת": meta.get("company") or "",
                    "סוג_מוצר": meta.get("product_type") or "",
                    "יתרה": balance or 0,
                    "תאריך_התחלה": meta.get("start_date") or None,
                }
            )

        return accounts
    finally:
        con.close()


def _load_portfolio_from_llm_pension_funds(*, db_path: str, client_id: int) -> list[dict[str, Any]]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        rows = cur.execute(
            """
            select balance, conversion_source
            from pension_funds
            where client_id = ? and conversion_source like ?
            order by id asc
            """,
            (client_id, "%llm_transform_funds_to_assets%"),
        ).fetchall()

        accounts: list[dict[str, Any]] = []
        for balance, conversion_source in rows:
            meta: dict[str, Any] = {}
            if conversion_source:
                try:
                    meta = json.loads(conversion_source)
                except Exception:
                    meta = {}

            account_number = meta.get("account_number")
            if not account_number:
                continue

            try:
                numeric_balance = float(balance)
            except Exception:
                numeric_balance = 0.0

            accounts.append(
                {
                    "מספר_חשבון": str(account_number),
                    "שם_תכנית": meta.get("account_name") or "",
                    "חברה_מנהלת": meta.get("company") or "",
                    "סוג_מוצר": meta.get("product_type") or "",
                    "יתרה": numeric_balance,
                    "תאריך_התחלה": meta.get("start_date") or None,
                }
            )

        return accounts
    finally:
        con.close()


def _summarize_after(*, db_path: str, client_id: int) -> dict[str, Any]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()

        pf_total = cur.execute(
            "select count(1) from pension_funds where client_id=?", (client_id,)
        ).fetchone()[0]
        ca_total = cur.execute(
            "select count(1) from capital_assets where client_id=?", (client_id,)
        ).fetchone()[0]

        pf_llm = cur.execute(
            "select count(1) from pension_funds where client_id=? and conversion_source like ?",
            (client_id, "%llm_transform_funds_to_assets%"),
        ).fetchone()[0]

        ca_llm = cur.execute(
            "select count(1) from capital_assets where client_id=? and conversion_source like ?",
            (client_id, "%llm_transform_funds_to_assets%"),
        ).fetchone()[0]

        dup_pf = cur.execute(
            """
            select count(1) from (
              select deduction_file
              from pension_funds
              where client_id=? and deduction_file is not null
              group by deduction_file
              having count(1) > 1
            )
            """,
            (client_id,),
        ).fetchone()[0]

        coeff_counts = Counter()
        rows = cur.execute(
            "select conversion_source from pension_funds where client_id=? and conversion_source like ?",
            (client_id, "%llm_transform_funds_to_assets%"),
        ).fetchall()
        for (cs,) in rows:
            meta: dict[str, Any] = {}
            if cs:
                try:
                    meta = json.loads(cs)
                except Exception:
                    meta = {}
            coeff_counts[meta.get("coeff_source_table")] += 1

        return {
            "pension_funds_total": int(pf_total),
            "capital_assets_total": int(ca_total),
            "pension_funds_llm_transform": int(pf_llm),
            "capital_assets_llm_transform": int(ca_llm),
            "pension_funds_duplicate_deduction_file": int(dup_pf),
            "coeff_source_table_counts": dict(coeff_counts),
        }
    finally:
        con.close()


def _post_json(*, url: str, payload: dict[str, Any], timeout_s: int) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", type=int, default=1)
    parser.add_argument("--base-url", type=str, default="http://localhost:8005")
    parser.add_argument("--db", type=str, default="retire.db")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    accounts_by_number: dict[str, dict[str, Any]] = {}

    for acc in _load_portfolio_from_llm_capital_assets(db_path=args.db, client_id=args.client_id):
        acc_no = str(acc.get("מספר_חשבון") or "").strip()
        if not acc_no:
            continue
        accounts_by_number[acc_no] = acc

    for acc in _load_portfolio_from_llm_pension_funds(db_path=args.db, client_id=args.client_id):
        acc_no = str(acc.get("מספר_חשבון") or "").strip()
        if not acc_no:
            continue
        accounts_by_number.setdefault(acc_no, acc)

    accounts = list(accounts_by_number.values())

    if not accounts:
        print(
            "No existing LLM-converted capital_assets found to reconstruct pension_portfolio. "
            "Upload maslaka XML or provide pension_portfolio via UI first.",
            file=sys.stderr,
        )
        return 2

    prompt = (
        "אנא בצע בדיקת מערכת מקיפה (QA) עבור הלקוח הנוכחי. "
        "חובה לבצע את השלבים הבאים: "
        "1) GET_PENSION_PRODUCTS, "
        "2) TRANSFORM_FUNDS_TO_ASSETS על בסיס התיק הפנסיוני המצורף (accounts), "
        "3) GENERATE_FULL_REPORT. "
        "בסוף החזר PASS/FAIL + סיכום קצר, וציין את open_path של הדוח."
    )

    payload = {
        "client_id": args.client_id,
        "messages": [{"role": "user", "content": prompt}],
        "pension_portfolio": accounts,
    }

    before = _summarize_after(db_path=args.db, client_id=args.client_id)

    print("=== BEFORE ===")
    print(json.dumps(before, ensure_ascii=False, indent=2))

    url = f"{args.base_url}/api/v1/llm/pension-chat-stream"
    print(f"\nCalling: {url} (accounts={len(accounts)})")

    stream_text = _post_json(url=url, payload=payload, timeout_s=args.timeout)

    print("\n=== STREAM RESPONSE (first 4000 chars) ===")
    print(stream_text[:4000])

    markers = {
        "has_ui_action": "###UI_ACTION###" in stream_text,
        "has_open_path": "open_path" in stream_text,
        "has_summary_keyword": "PASS" in stream_text or "FAIL" in stream_text,
    }
    print("\n=== RESPONSE MARKERS ===")
    print(json.dumps(markers, ensure_ascii=False, indent=2))

    after = _summarize_after(db_path=args.db, client_id=args.client_id)
    print("\n=== AFTER ===")
    print(json.dumps(after, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
