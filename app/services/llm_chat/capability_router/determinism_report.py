from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.llm_chat.capability_router.resolver import resolve


def _sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def fingerprint_fields(*, capability_id: str, tool_chain: list[str], output_schema_id: str) -> str:
    payload = {
        "capability_id": str(capability_id or ""),
        "tool_chain": [str(x) for x in (tool_chain or [])],
        "output_schema_id": str(output_schema_id or ""),
    }
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return _sha256_hex(stable)


def run_determinism_report(*, cases: list[dict[str, Any]], runs: int = 3) -> dict[str, Any]:
    per_case: dict[str, dict[str, Any]] = {}
    mismatches: list[dict[str, Any]] = []

    for case in cases:
        case_id = str(case.get("case_id") or "")
        user_text = str(case.get("user_text") or "")
        fingerprints: list[str] = []
        observed: list[dict[str, Any]] = []

        for i in range(int(runs)):
            d = resolve(user_text=user_text, client_id=None, trace_id=f"det_{case_id}_{i}")
            fp = fingerprint_fields(
                capability_id=d.capability_id,
                tool_chain=list(d.tool_chain or []),
                output_schema_id=d.output_schema_id,
            )
            fingerprints.append(fp)
            observed.append(
                {
                    "capability_id": d.capability_id,
                    "tool_chain": list(d.tool_chain or []),
                    "output_schema_id": d.output_schema_id,
                }
            )

        baseline = fingerprints[0] if fingerprints else ""
        per_case[case_id] = {
            "fingerprint": baseline,
            "capability_id": observed[0]["capability_id"] if observed else "",
            "tool_chain": observed[0]["tool_chain"] if observed else [],
            "output_schema_id": observed[0]["output_schema_id"] if observed else "",
        }

        if any(fp != baseline for fp in fingerprints[1:]):
            mismatches.append(
                {
                    "case_id": case_id,
                    "fingerprints": list(fingerprints),
                    "observed": list(observed),
                }
            )

    return {
        "total_cases": int(len(cases)),
        "runs": int(runs),
        "mismatches": mismatches,
        "per_case": per_case,
    }
