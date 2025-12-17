import argparse
import json
import os
import sys
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Expected dict JSON root")
    return data


def _normalize_results(data: dict[str, Any]) -> dict[str, Any]:
    raw_results = data.get("results") or []
    if not isinstance(raw_results, list):
        raise ValueError("Expected 'results' list")

    normalized: list[dict[str, Any]] = []
    for r in raw_results:
        if not isinstance(r, dict):
            continue
        case_id = r.get("case_id")
        if not case_id:
            continue
        normalized.append(
            {
                "case_id": case_id,
                "passed": bool(r.get("passed")),
                "errors": list(r.get("errors") or []),
            }
        )

    normalized.sort(key=lambda x: str(x.get("case_id")))
    return {"results": normalized}


def _compare(*, baseline: dict[str, Any], current: dict[str, Any], allow_new: bool) -> list[str]:
    issues: list[str] = []

    b_results = baseline.get("results") or []
    c_results = current.get("results") or []

    if not isinstance(b_results, list) or not isinstance(c_results, list):
        return ["invalid_results_format"]

    b_by_case = {r.get("case_id"): r for r in b_results if isinstance(r, dict)}
    c_by_case = {r.get("case_id"): r for r in c_results if isinstance(r, dict)}

    for case_id, b in b_by_case.items():
        c = c_by_case.get(case_id)
        if c is None:
            issues.append(f"missing_case:{case_id}")
            continue

        if bool(b.get("passed")) and not bool(c.get("passed")):
            issues.append(f"regression_pass_to_fail:{case_id}")

    if not allow_new:
        for case_id in c_by_case.keys():
            if case_id not in b_by_case:
                issues.append(f"new_case:{case_id}")

    return issues


def _write_json_atomic(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default=os.path.join("scripts", "llm_eval_results_tmp.json"),
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=os.path.join("scripts", "baselines", "llm_eval_baseline.json"),
    )
    parser.add_argument("--set", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-new", action="store_true")
    args = parser.parse_args()

    if not args.set and not args.check:
        print("Nothing to do: pass --set and/or --check", file=sys.stderr)
        return 2

    if not os.path.exists(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 2

    current_raw = _load_json(args.input)
    current = _normalize_results(current_raw)

    if args.set:
        if os.path.exists(args.baseline) and not args.overwrite:
            print(
                f"Baseline already exists: {args.baseline} (pass --overwrite to replace)",
                file=sys.stderr,
            )
            return 2

        _write_json_atomic(args.baseline, current)
        print(f"Baseline saved: {args.baseline}")

    if args.check:
        if not os.path.exists(args.baseline):
            print(f"Baseline not found: {args.baseline}", file=sys.stderr)
            return 2

        baseline_raw = _load_json(args.baseline)
        baseline = _normalize_results(baseline_raw)

        issues = _compare(baseline=baseline, current=current, allow_new=bool(args.allow_new))
        if issues:
            print("Baseline check: FAIL")
            for issue in issues:
                print(f"  {issue}")
            return 1

        print("Baseline check: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
