import argparse
import json
import os
import sys
from collections import Counter
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Expected dict JSON root")
    return data


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = set(before.keys()) | set(after.keys())
    out: dict[str, int] = {}
    for key in sorted(keys):
        if key.endswith("_counts"):
            continue
        if isinstance(before.get(key), (int, float, str)) or isinstance(after.get(key), (int, float, str)):
            out[key] = _to_int(after.get(key)) - _to_int(before.get(key))
    return out


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    case_id = result.get("case_id")
    passed = bool(result.get("passed"))
    errors = result.get("errors") or []
    runs = result.get("runs") or []

    last_run = runs[-1] if isinstance(runs, list) and runs else {}
    before = last_run.get("before") or {}
    after = last_run.get("after") or {}
    markers = last_run.get("markers") or {}
    tools_used = last_run.get("tools_used") or []

    return {
        "case_id": case_id,
        "passed": passed,
        "errors": errors,
        "markers": markers,
        "tools_used": tools_used,
        "db_delta": _delta(before, after),
    }


def _compare_baseline(
    *,
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    issues: list[str] = []

    b_results = baseline.get("results") or []
    c_results = current.get("results") or []

    baseline_by_case = {r.get("case_id"): r for r in b_results if isinstance(r, dict)}
    current_by_case = {r.get("case_id"): r for r in c_results if isinstance(r, dict)}

    for case_id, c in current_by_case.items():
        b = baseline_by_case.get(case_id)
        if not b:
            issues.append(f"new_case:{case_id}")
            continue

        if bool(b.get("passed")) and not bool(c.get("passed")):
            issues.append(f"regression_pass_to_fail:{case_id}")

    for case_id in baseline_by_case.keys():
        if case_id not in current_by_case:
            issues.append(f"missing_case:{case_id}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default=os.path.join("logs", "llm_eval_results.json"),
    )
    parser.add_argument("--baseline", type=str, default=None)
    args = parser.parse_args()

    current = _load_json(args.input)
    results = current.get("results") or []

    if not isinstance(results, list):
        print("Invalid results format: expected list under 'results'", file=sys.stderr)
        return 2

    total = len(results)
    passed = sum(1 for r in results if isinstance(r, dict) and r.get("passed"))
    failed = total - passed

    errors_counter = Counter()
    for r in results:
        if not isinstance(r, dict):
            continue
        for e in r.get("errors") or []:
            errors_counter[str(e)] += 1

    print(f"Total cases: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if errors_counter:
        print("Errors summary:")
        for err, count in errors_counter.most_common():
            print(f"  {err}: {count}")

    print("Case summaries:")
    for r in results:
        if not isinstance(r, dict):
            continue
        s = _summarize_result(r)
        status = "PASS" if s["passed"] else "FAIL"
        print(f"  {status} {s['case_id']} errors={s['errors']}")

    if args.baseline:
        baseline = _load_json(args.baseline)
        issues = _compare_baseline(baseline=baseline, current=current)
        if issues:
            print("Baseline comparison issues:")
            for issue in issues:
                print(f"  {issue}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
