import argparse
import codecs
import json
import os
import socket
import sqlite3
import sys
import urllib.request
from collections import Counter
from typing import Any


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


def _contains_required_tools(*, text: str, required_tools: set[str]) -> bool:
    if not required_tools:
        return True
    hay = text or ""
    for tool in required_tools:
        tool_name = str(tool or "").strip()
        if not tool_name:
            continue
        if tool_name == "GET_TAX_PROJECTION":
            if (
                "Tool Output (GET_TAX_PROJECTION" not in hay
                and "Tool Result (GET_TAX_PROJECTION" not in hay
            ):
                return False
            continue

        if (
            f"Tool Output ({tool_name}" not in hay
            and f"Tool Result ({tool_name}" not in hay
        ):
            return False
    return True


def _contains_required_substrings(*, text: str, required_contains: list[str]) -> bool:
    if not required_contains:
        return True
    hay = text or ""
    for item in required_contains:
        if not item:
            continue
        if str(item) not in hay:
            return False
    return True


def _post_json_stream_until(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_s: int,
    require_ui_action: bool,
    require_open_path: bool,
    require_pass_fail: bool,
    require_pension_portfolio_update: bool,
    required_tools: set[str],
    required_contains: list[str],
    max_chars: int = 2_000_000,
) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    chunks: list[str] = []

    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        while True:
            try:
                data = resp.read(4096)
            except (TimeoutError, socket.timeout):
                break

            if not data:
                break

            chunks.append(decoder.decode(data))
            text = "".join(chunks)

            if len(text) >= max_chars:
                break

            if not _contains_required_tools(text=text, required_tools=required_tools):
                continue

            if not _contains_required_substrings(
                text=text, required_contains=required_contains
            ):
                continue

            if require_ui_action and "###UI_ACTION###" not in text:
                continue

            if require_open_path:
                lowered = text.lower()
                if (
                    "open_path" not in text
                    and "/reports" not in text
                    and "auto_html" not in text
                    and "/reports" not in lowered
                    and "auto_html" not in lowered
                ):
                    continue

            if require_pass_fail:
                lowered = text.lower()
                if ("pass" not in lowered) and ("fail" not in lowered):
                    continue

            if require_pension_portfolio_update:
                if (
                    "###PENSION_PORTFOLIO_UPDATE###" not in text
                    or "###END_PENSION_PORTFOLIO_UPDATE###" not in text
                ):
                    continue

            break

    try:
        chunks.append(decoder.decode(b"", final=True))
    except Exception:
        pass

    return "".join(chunks)


def _extract_ui_action_payload(response_text: str) -> dict[str, Any] | None:
    marker = "###UI_ACTION###"
    if marker not in (response_text or ""):
        return None

    try:
        after = response_text.split(marker, 1)[1].lstrip()
        if not after:
            return None

        # The payload is typically a single JSON object right after the marker.
        # We try to parse up to the first newline; if that fails, try the whole tail.
        first_line = after.splitlines()[0].strip()
        try:
            return json.loads(first_line)
        except Exception:
            return json.loads(after)
    except Exception:
        return None


def _extract_tools_used(response_text: str) -> list[str]:
    tools: list[str] = []
    text = response_text or ""

    markers = ["Tool Output (", "Tool Result ("]
    for marker in markers:
        start = 0
        while True:
            idx = text.find(marker, start)
            if idx == -1:
                break
            name_start = idx + len(marker)
            name_end = text.find(")", name_start)
            if name_end == -1:
                break
            tool_name = text[name_start:name_end].strip()
            if tool_name:
                tools.append(tool_name)
            start = name_end + 1

    # Normalize known variants
    normalized: list[str] = []
    for t in tools:
        if t.startswith("GET_TAX_PROJECTION"):
            normalized.append("GET_TAX_PROJECTION")
        else:
            normalized.append(t)

    # Deduplicate while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for t in normalized:
        if t in seen:
            continue
        deduped.append(t)
        seen.add(t)

    if (
        "###PENSION_PORTFOLIO_UPDATE###" in text
        and "TRANSFORM_FUNDS_TO_ASSETS" not in seen
    ):
        deduped.append("TRANSFORM_FUNDS_TO_ASSETS")
        seen.add("TRANSFORM_FUNDS_TO_ASSETS")
    return deduped


def _summarize_db(*, db_path: str, client_id: int) -> dict[str, Any]:
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


def _load_portfolio_from_llm_capital_assets(
    *, db_path: str, client_id: int
) -> list[dict[str, Any]]:
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

            try:
                balance = float(current_value)
            except Exception:
                balance = 0.0

            accounts.append(
                {
                    "מספר_חשבון": str(account_number),
                    "שם_תכנית": meta.get("account_name") or "",
                    "חברה_מנהלת": meta.get("company") or "",
                    "סוג_מוצר": meta.get("product_type") or "",
                    "יתרה": balance,
                    "תאריך_התחלה": meta.get("start_date") or None,
                }
            )

        return accounts
    finally:
        con.close()


def _load_portfolio_from_llm_pension_funds(
    *, db_path: str, client_id: int
) -> list[dict[str, Any]]:
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


def _load_portfolio(*, db_path: str, client_id: int) -> list[dict[str, Any]]:
    accounts_by_number: dict[str, dict[str, Any]] = {}

    for acc in _load_portfolio_from_llm_capital_assets(
        db_path=db_path, client_id=client_id
    ):
        acc_no = str(acc.get("מספר_חשבון") or "").strip()
        if not acc_no:
            continue
        accounts_by_number[acc_no] = acc

    for acc in _load_portfolio_from_llm_pension_funds(
        db_path=db_path, client_id=client_id
    ):
        acc_no = str(acc.get("מספר_חשבון") or "").strip()
        if not acc_no:
            continue
        accounts_by_number.setdefault(acc_no, acc)

    return list(accounts_by_number.values())


def _evaluate_response(*, response_text: str) -> dict[str, bool]:
    lowered = (response_text or "").lower()

    ui_payload = _extract_ui_action_payload(response_text)
    has_open_path_via_ui = False
    if isinstance(ui_payload, dict):
        actions = ui_payload.get("actions")
        if isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                path = action.get("path")
                if isinstance(path, str) and (
                    "/reports" in path or "auto_html" in path
                ):
                    has_open_path_via_ui = True
                    break

    pension_portfolio_update_start = "###PENSION_PORTFOLIO_UPDATE###"
    pension_portfolio_update_end = "###END_PENSION_PORTFOLIO_UPDATE###"
    has_pension_portfolio_update = False
    if pension_portfolio_update_start in (
        response_text or ""
    ) and pension_portfolio_update_end in (response_text or ""):
        try:
            start_idx = response_text.index(pension_portfolio_update_start) + len(
                pension_portfolio_update_start
            )
            end_idx = response_text.index(pension_portfolio_update_end, start_idx)
            payload = response_text[start_idx:end_idx].strip()
            if payload:
                json.loads(payload)
                has_pension_portfolio_update = True
        except Exception:
            has_pension_portfolio_update = False

    return {
        "has_ui_action": "###UI_ACTION###" in response_text,
        "has_open_path": (
            ("open_path" in response_text)
            or ("/reports" in response_text)
            or ("auto_html" in response_text)
            or has_open_path_via_ui
        ),
        "has_pass_fail": ("pass" in lowered) or ("fail" in lowered),
        "has_pension_portfolio_update": has_pension_portfolio_update,
    }


def _run_case_once(
    *,
    base_url: str,
    timeout_s: int,
    case: dict[str, Any],
    db_path: str,
) -> dict[str, Any]:
    client_id = int(case["client_id"])
    endpoint = case.get("endpoint") or "stream"

    portfolio: list[dict[str, Any]] | None = None
    inline_portfolio = case.get("pension_portfolio")
    if isinstance(inline_portfolio, list):
        portfolio = inline_portfolio
    elif case.get("include_portfolio"):
        portfolio = _load_portfolio(db_path=db_path, client_id=client_id)

    payload: dict[str, Any] = {
        "client_id": client_id,
        "messages": [{"role": "user", "content": case["prompt"]}],
    }

    if portfolio is not None:
        payload["pension_portfolio"] = portfolio

    if endpoint == "stream":
        url = f"{base_url}/api/v1/llm/pension-chat-stream"
    else:
        url = f"{base_url}/api/v1/llm/pension-chat"

    before = _summarize_db(db_path=db_path, client_id=client_id)
    request_error: str | None = None
    response_text = ""
    try:
        expect: dict[str, Any] = case.get("expect") or {}
        required_tools = {
            str(t)
            for t in (expect.get("require_tools_used") or [])
            if t is not None and str(t).strip()
        }
        required_contains = expect.get("require_contains") or []

        if endpoint == "stream" and (
            expect.get("require_ui_action")
            or expect.get("require_open_path")
            or expect.get("require_pass_fail")
            or expect.get("require_pension_portfolio_update")
            or required_tools
            or (isinstance(required_contains, list) and len(required_contains) > 0)
        ):
            response_text = _post_json_stream_until(
                url=url,
                payload=payload,
                timeout_s=timeout_s,
                require_ui_action=bool(expect.get("require_ui_action")),
                require_open_path=bool(expect.get("require_open_path")),
                require_pass_fail=bool(expect.get("require_pass_fail")),
                require_pension_portfolio_update=bool(
                    expect.get("require_pension_portfolio_update")
                ),
                required_tools=required_tools,
                required_contains=(
                    required_contains if isinstance(required_contains, list) else []
                ),
            )
        else:
            response_text = _post_json(url=url, payload=payload, timeout_s=timeout_s)
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict) and isinstance(parsed.get("reply"), str):
                    response_text = parsed["reply"]
            except Exception:
                pass
    except Exception as e:
        request_error = f"{type(e).__name__}: {e}"
    after = _summarize_db(db_path=db_path, client_id=client_id)

    markers = _evaluate_response(response_text=response_text)
    tools_used = _extract_tools_used(response_text)

    return {
        "client_id": client_id,
        "endpoint": endpoint,
        "url": url,
        "before": before,
        "after": after,
        "request_error": request_error,
        "markers": markers,
        "tools_used": tools_used,
        "response_preview": response_text[:4000],
    }


def _check_case_expectations(
    *, case: dict[str, Any], case_runs: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []

    if not case_runs:
        return ["no_runs"]

    final_run = case_runs[-1]

    expect: dict[str, Any] = case.get("expect") or {}
    markers: dict[str, Any] = final_run.get("markers") or {}
    response_preview = final_run.get("response_preview") or ""
    tools_used = final_run.get("tools_used") or []

    if expect.get("require_ui_action") and not markers.get("has_ui_action"):
        errors.append("missing_ui_action")
    if expect.get("require_open_path") and not markers.get("has_open_path"):
        errors.append("missing_open_path")
    if expect.get("require_pass_fail") and not markers.get("has_pass_fail"):
        errors.append("missing_pass_fail")

    if expect.get("require_pension_portfolio_update") and not markers.get(
        "has_pension_portfolio_update"
    ):
        errors.append("missing_pension_portfolio_update_marker")

    if expect.get("forbid_pension_portfolio_update") and markers.get(
        "has_pension_portfolio_update"
    ):
        errors.append("forbidden_pension_portfolio_update_marker")

    required_contains = expect.get("require_contains")
    if isinstance(required_contains, list):
        for item in required_contains:
            if not item:
                continue
            if str(item) not in response_preview:
                errors.append(f"missing_required_substring:{item}")

    require_no_tools_used = expect.get("require_no_tools_used")
    if require_no_tools_used:
        if isinstance(tools_used, list) and len(tools_used) > 0:
            errors.append("expected_no_tools_used")

    required_tools = expect.get("require_tools_used")
    if isinstance(required_tools, list):
        used_set = {str(t) for t in tools_used if t}
        for t in required_tools:
            if not t:
                continue
            if str(t) not in used_set:
                errors.append(f"missing_required_tool:{t}")

    forbidden_tools = expect.get("forbid_tools_used")
    if isinstance(forbidden_tools, list):
        used_set = {str(t) for t in tools_used if t}
        for t in forbidden_tools:
            if not t:
                continue
            if str(t) in used_set:
                errors.append(f"forbidden_tool_used:{t}")

    db_assert: dict[str, Any] = case.get("db_assert") or {}
    after: dict[str, Any] = final_run.get("after") or {}
    if (
        db_assert.get("require_no_duplicate_pension_funds_by_deduction_file")
        and after.get("pension_funds_duplicate_deduction_file")
        and int(after.get("pension_funds_duplicate_deduction_file")) > 0
    ):
        errors.append("duplicate_pension_funds_by_deduction_file")

    if db_assert.get("require_idempotent_counts") and len(case_runs) > 1:
        keys_to_compare = [
            "pension_funds_total",
            "capital_assets_total",
            "pension_funds_llm_transform",
            "capital_assets_llm_transform",
            "pension_funds_duplicate_deduction_file",
        ]

        prev_after = case_runs[0].get("after") or {}
        for idx in range(1, len(case_runs)):
            curr_after = case_runs[idx].get("after") or {}
            for key in keys_to_compare:
                if int(curr_after.get(key, 0)) != int(prev_after.get(key, 0)):
                    errors.append("non_idempotent_counts")
                    break
            prev_after = curr_after
            if "non_idempotent_counts" in errors:
                break

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", type=str, default="http://localhost:8005")
    parser.add_argument("--db", type=str, default="retire.db")
    parser.add_argument(
        "--cases", type=str, default=os.path.join("scripts", "llm_eval_cases.json")
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--output", type=str, default=os.path.join("logs", "llm_eval_results.json")
    )
    parser.add_argument("--case-id", type=str, default=None)
    args = parser.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if args.case_id:
        cases = [c for c in cases if c.get("case_id") == args.case_id]

    if not cases:
        print("No cases to run.", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for case in cases:
        case_id = case.get("case_id") or "unknown"
        repeat = int(case.get("repeat") or 1)

        case_runs: list[dict[str, Any]] = []
        for _ in range(repeat):
            run_result = _run_case_once(
                base_url=args.base_url,
                timeout_s=int(args.timeout),
                case=case,
                db_path=args.db,
            )
            case_runs.append(run_result)

        errors = _check_case_expectations(case=case, case_runs=case_runs)

        passed = len(errors) == 0
        results.append(
            {
                "case_id": case_id,
                "passed": passed,
                "errors": errors,
                "runs": case_runs,
            }
        )

        status = "PASS" if passed else "FAIL"
        print(f"{status} {case_id} errors={errors}")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)

    any_fail = any(not r.get("passed") for r in results)
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
