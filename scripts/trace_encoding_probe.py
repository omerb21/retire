import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _hexdump(data: bytes, start: int = 0, length: int = 96) -> str:
    s = max(0, int(start))
    e = min(len(data), s + max(0, int(length)))
    chunk = data[s:e]
    return " ".join(f"{b:02x}" for b in chunk)


def _http_json(
    method: str, url: str, headers: dict[str, str], body: dict | None = None
) -> tuple[int, bytes, dict]:
    raw_body = None
    req_headers = dict(headers)
    if body is not None:
        raw_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(
        url=url, data=raw_body, method=method, headers=req_headers
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            status = int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as e:
        data = e.read() if hasattr(e, "read") else b""
        status = int(getattr(e, "code", 0) or 0)
        raise RuntimeError(f"HTTP {status} calling {method} {url}: {data[:500]!r}")

    parsed = {}
    try:
        parsed = json.loads(data.decode("utf-8", errors="replace"))
    except Exception:
        parsed = {}
    return status, data, parsed


def _http_bytes(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    req = urllib.request.Request(url=url, data=None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            status = int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as e:
        data = e.read() if hasattr(e, "read") else b""
        status = int(getattr(e, "code", 0) or 0)
        raise RuntimeError(f"HTTP {status} calling {method} {url}: {data[:500]!r}")
    return status, data


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Proof-first encoding probe for trace JSON."
    )
    ap.add_argument(
        "--base-url",
        default=os.getenv("TRACE_PROBE_BASE_URL") or "http://localhost:8005",
    )
    ap.add_argument("--admin-token", default=os.getenv("ADMIN_DEBUG_TOKEN") or "")
    ap.add_argument("--client-id", type=int, required=True)
    ap.add_argument(
        "--fixture",
        default="termination",
        choices=["cashflow", "target_plan", "termination"],
    )
    args = ap.parse_args()

    headers: dict[str, str] = {}
    if args.admin_token:
        headers["X-Admin-Token"] = args.admin_token

    run_url = f"{args.base_url.rstrip('/')}/api/v1/debug/trace-fixtures/run"
    _, run_bytes, run_json = _http_json(
        "POST",
        run_url,
        headers=headers,
        body={"client_id": args.client_id, "fixture": args.fixture},
    )

    trace_id = run_json.get("trace_id")
    evidence = run_json.get("evidence") or {}
    pre = evidence.get("tool_result_pre_write") or {}
    from_db = evidence.get("tool_result_from_db") or {}

    print("=== FIXTURE RESULT ===")
    print(f"trace_id: {trace_id}")
    print(f"run endpoint response bytes len: {len(run_bytes)}")
    print(f"run endpoint bytes head hex: {_hexdump(run_bytes, 0, 96)}")

    print("=== PRE-WRITE PREVIEW (in-memory) ===")
    print(f"tool_name: {pre.get('tool_name')}")
    print(f"tool_call_id: {pre.get('tool_call_id')}")
    print(f"status: {pre.get('status')} success: {pre.get('success')}")
    print(f"preview head: {(pre.get('result_preview') or '')[:120]!r}")
    print(f"preview utf8 hex head: {pre.get('result_preview_utf8_hex')}")

    print("=== FROM DB (post-write) ===")
    print(f"event_id: {from_db.get('event_id')}")
    print(f"payload_json utf8 hex head: {from_db.get('payload_json_utf8_hex')}")
    print(f"stored preview head: {(from_db.get('result_preview') or '')[:120]!r}")
    print(f"stored preview utf8 hex head: {from_db.get('result_preview_utf8_hex')}")

    if not trace_id:
        print("No trace_id returned; cannot continue", file=sys.stderr)
        return 3

    # 1) Fetch full trace JSON from endpoint (bytes) and show where preview appears.
    trace_url = f"{args.base_url.rstrip('/')}/api/v1/debug/traces/{trace_id}"
    _, trace_bytes = _http_bytes("GET", trace_url, headers=headers)
    print("=== TRACE ENDPOINT BYTES (/traces/{trace_id}) ===")
    print(f"trace endpoint bytes len: {len(trace_bytes)}")

    preview_text = (
        pre.get("result_preview") if isinstance(pre.get("result_preview"), str) else ""
    )
    if preview_text:
        preview_bytes = preview_text.encode("utf-8", errors="replace")
        idx = trace_bytes.find(preview_bytes)
        print(f"preview utf8 bytes found at index: {idx}")
        if idx >= 0:
            start = max(0, idx - 32)
            print(
                f"trace bytes around preview hex: {_hexdump(trace_bytes, start, 160)}"
            )
        else:
            print(f"trace bytes head hex: {_hexdump(trace_bytes, 0, 160)}")
    else:
        print(f"trace bytes head hex: {_hexdump(trace_bytes, 0, 160)}")

    # 2) Fetch raw stored payload_json bytes for the tool_result event.
    event_id = from_db.get("event_id")
    if isinstance(event_id, int) and event_id > 0:
        raw_url = f"{args.base_url.rstrip('/')}/api/v1/debug/traces/{trace_id}/events/{event_id}/payload-raw"
        _, raw_bytes = _http_bytes("GET", raw_url, headers=headers)
        print("=== RAW DB PAYLOAD JSON BYTES (/payload-raw) ===")
        print(f"payload-raw bytes len: {len(raw_bytes)}")
        print(f"payload-raw bytes head hex: {_hexdump(raw_bytes, 0, 160)}")

        try:
            decoded = raw_bytes.decode("utf-8", errors="replace")
            print(f"payload-raw decoded head: {decoded[:200]!r}")
        except Exception:
            pass
    else:
        print(
            "No event_id from evidence.tool_result_from_db; skipping /payload-raw fetch"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
