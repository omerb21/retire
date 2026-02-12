"""
Probe script: end-to-end trace evidence for "בנה תכנית יעד קצבה 30000 נטו".
Runs locally against the app using TestClient (no external server needed).
"""

import os
import json

os.environ.setdefault("AGENT_EYES_DEBUG_API_ENABLED", "1")
os.environ.setdefault("AGENT_EYES_ADMIN_TOKEN", "probe-token-123")
os.environ.setdefault("SYSTEM_ACCESS_DISABLED", "1")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import SessionLocal, Base  # noqa: E402
from app.models.client import Client  # noqa: E402

ADMIN_TOKEN = "probe-token-123"
TRACE_ID = "probe-target-plan-20260212"
CLIENT_ID = 39
HEADERS_AUTH = {"X-Admin-Token": ADMIN_TOKEN}


def ensure_db():
    tmp = SessionLocal()
    engine = tmp.get_bind()
    Base.metadata.create_all(bind=engine)
    c = tmp.query(Client).filter(Client.id == CLIENT_ID).first()
    if not c:
        tmp.add(Client(
            id=CLIENT_ID, id_number_raw="39",
            id_number="39", full_name="Probe User",
        ))
        tmp.commit()
    tmp.close()


def step1(api):
    print("=" * 60)
    print("STEP 1: Debug API health check")
    print("=" * 60)

    r_no = api.get("/api/v1/agent-eyes/traces", params={"limit": 5})
    print(f"  No token   -> status={r_no.status_code}")

    r_bad = api.get("/api/v1/agent-eyes/traces", params={"limit": 5},
                    headers={"X-Admin-Token": "wrong"})
    print(f"  Bad token  -> status={r_bad.status_code}")

    r_ok = api.get("/api/v1/agent-eyes/traces", params={"limit": 5},
                   headers=HEADERS_AUTH)
    print(f"  Good token -> status={r_ok.status_code}")

    ok = r_no.status_code == 403 and r_bad.status_code == 403 and r_ok.status_code == 200
    print(f"  PASS: {ok}")
    print()
    return ok


def step2(api):
    print("=" * 60)
    print("STEP 2: POST /pension-chat-stream with X-Trace-Id")
    print("=" * 60)

    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": CLIENT_ID,
            "messages": [
                {"role": "user",
                 "content": "בנה תכנית יעד קצבה 30000 נטו"}
            ],
        },
        headers={"X-Trace-Id": TRACE_ID},
    )
    returned_tid = resp.headers.get("X-Trace-Id")
    print(f"  HTTP status:  {resp.status_code}")
    print(f"  X-Trace-Id:   {returned_tid}")
    print(f"  Matches sent: {returned_tid == TRACE_ID}")
    body_preview = resp.text[:500]
    print(f"  Body preview: {body_preview}")
    print()

    # Check trace appears in list
    r_list = api.get(
        "/api/v1/agent-eyes/traces",
        params={"limit": 20, "client_id": CLIENT_ID},
        headers=HEADERS_AUTH,
    )
    items = r_list.json().get("items", [])
    matching = [t for t in items if t["trace_id"] == TRACE_ID]
    found = len(matching) == 1
    print(f"  Trace in list: {found}")
    if matching:
        m = matching[0]
        print(f"    events_count = {m['events_count']}")
        print(f"    endpoint     = {m['endpoint']}")
    print()
    return resp.status_code == 200 and found


def step3(api):
    print("=" * 60)
    print("STEP 3: Trace events -> 6-line evidence report")
    print("=" * 60)

    r = api.get(
        f"/api/v1/agent-eyes/traces/{TRACE_ID}",
        headers=HEADERS_AUTH,
    )
    if r.status_code != 200:
        print(f"  ERROR: status={r.status_code} body={r.text[:300]}")
        return False

    events = r.json().get("items", [])
    print(f"  Total events: {len(events)}")
    print()

    # --- 6-line report ---
    print("  ┌─────────────────────────────────────────────┐")
    print("  │         6-LINE EVIDENCE REPORT              │")
    print("  └─────────────────────────────────────────────┘")

    # 1) execution_path
    ep = [e for e in events if e["event_type"] == "execution_path"]
    if ep:
        p = ep[0].get("payload_json") or {}
        print(f"  1. execution_path.path_id = {p.get('path_id', 'N/A')}")
    else:
        print("  1. execution_path.path_id = NOT FOUND")

    # 2) endpoint
    endpoints = [e.get("endpoint") for e in events if e.get("endpoint")]
    print(f"  2. endpoint = {endpoints[0] if endpoints else 'N/A'}")

    # 3) tool_call
    tc = [e for e in events if e["event_type"] == "tool_call"]
    if tc:
        tcp = tc[0].get("payload_json") or {}
        print(f"  3. tool_call.payload.tool_name = {tcp.get('tool_name', 'N/A')}")
        args = tcp.get("args") or tcp.get("arguments") or {}
        print(f"  4. tool_call.payload.args = {json.dumps(args, ensure_ascii=False)}")
    else:
        print("  3. tool_call.payload.tool_name = NOT FOUND")
        print("  4. tool_call.payload.args = NOT FOUND")

    # 4) tool_result
    tr = [e for e in events if e["event_type"] == "tool_result"]
    if tr:
        trp = tr[0].get("payload_json") or {}
        print(f"  5. tool_result.payload.tool_name = {trp.get('tool_name', 'N/A')}")
        preview = trp.get("result_preview") or trp.get("result") or "N/A"
        if isinstance(preview, str) and len(preview) > 300:
            preview = preview[:300] + "..."
        print(f"  6. tool_result.payload.result_preview = {preview}")
    else:
        print("  5. tool_result.payload.tool_name = NOT FOUND")
        print("  6. tool_result.payload.result_preview = NOT FOUND")

    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │         ALL EVENTS (chronological)          │")
    print("  └─────────────────────────────────────────────┘")
    for e in events:
        et = e["event_type"]
        ts = e.get("created_at", "?")
        p = e.get("payload_json") or {}
        extra = ""
        if et == "tool_call":
            extra = f" tool={p.get('tool_name', '?')}"
        elif et == "tool_result":
            extra = f" tool={p.get('tool_name', '?')} success={p.get('success', '?')}"
        elif et == "execution_path":
            extra = f" path_id={p.get('path_id', '?')}"
        elif et == "user_input":
            msg = (p.get("user_message") or "")[:60]
            extra = f" msg={msg}"
        elif et == "assistant_output":
            rp = (p.get("reply_preview") or "")[:60]
            extra = f" preview={rp}"
        print(f"    [{ts}] {et}{extra}")

    print()
    return True


def main():
    ensure_db()
    api = TestClient(app)

    s1 = step1(api)
    s2 = step2(api)
    s3 = step3(api)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Step 1 (API alive):    {'PASS' if s1 else 'FAIL'}")
    print(f"  Step 2 (trace created):{'PASS' if s2 else 'FAIL'}")
    print(f"  Step 3 (evidence):     {'PASS' if s3 else 'FAIL'}")


if __name__ == "__main__":
    main()
