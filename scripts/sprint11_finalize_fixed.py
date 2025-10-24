import os, json, zipfile
from datetime import datetime
import requests

CLIENT_ID = 1
SCENARIO_ID = 24
PORTS = [8005, 8006, 8007]

TS = datetime.now().strftime("%Y%m%d-%H%M")
ART_DIR = "artifacts"
RUN_DIR = os.path.join(ART_DIR, f"release-{TS}-s11")
os.makedirs(RUN_DIR, exist_ok=True)

def pick_base():
    for p in PORTS:
        base = f"http://127.0.0.1:{p}"
        try:
            r = requests.get(base + "/openapi.json", timeout=3)
            if r.ok:
                return base
        except Exception:
            pass
    return None

def save_json(path, obj):
    with open(path, "wb") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))

def flatten_ref(ref, components):
    try:
        name = ref.split("/")[-1]
        return components["schemas"][name]
    except Exception:
        return {}

def flatten_schema(s, components):
    cur = dict(s or {})
    while "$ref" in cur:
        cur = flatten_ref(cur["$ref"], components)
    if "allOf" in cur:
        props, req = {}, set()
        for part in cur["allOf"]:
            ps = flatten_schema(part, components)
            props.update(ps.get("properties", {}) or {})
            req |= set(ps.get("required", []) or [])
        out = {"type":"object"}
        if props: out["properties"] = props
        if req: out["required"] = list(req)
        return out
    return cur

def example_for(prop):
    if not isinstance(prop, dict): return None
    if "enum" in prop: return prop["enum"][0]
    t = prop.get("type")
    fmt = prop.get("format")
    if t == "string":
        if fmt in ("date","date-time"): return "2025-01"
        return "string"
    if t == "integer": return 0
    if t == "number": return 0.0
    if t == "boolean": return False
    if t == "array": return [example_for(prop.get("items", {}))]
    if t == "object":
        res = {}
        for k,v in (prop.get("properties") or {}).items():
            res[k] = example_for(v)
        return res
    return None

def list_files(path):
    out = []
    for n in sorted(os.listdir(path)):
        p = os.path.join(path, n)
        if os.path.isfile(p):
            out.append((n, os.path.getsize(p)))
    return out

def zip_dir(src, dst):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src):
            for fn in files:
                ap = os.path.join(root, fn)
                z.write(ap, os.path.relpath(ap, src))

def summarize_annual(rows):
    agg = {}
    for r in rows or []:
        d = str(r.get("date",""))
        if len(d) < 4 or not d[:4].isdigit(): continue
        y = d[:4]
        A = agg.setdefault(y, {"inflow":0,"outflow":0,"additional_income_net":0,"capital_return_net":0,"net":0})
        for k in A.keys():
            A[k] += int(r.get(k,0) or 0)
    return agg

def main():
    base = pick_base()
    if not base:
        print("=== SPRINT 11 PROOF SUMMARY ===")
        print("Server BASE: (not found)")
        print("ERROR: No API detected on 127.0.0.1:8005/8006/8007")
        print("=== END SUMMARY ===")
        return

    # OpenAPI + case path
    op = requests.get(base + "/openapi.json", timeout=5).json()
    case_path = None
    for path in op.get("paths", {}):
        if "case" in path and "detect" in path:
            case_path = path
            break

    req_fields, props, ex_req, ex_full = [], {}, {}, {}
    if case_path:
        post = (op["paths"][case_path].get("post") or {})
        content = ((post.get("requestBody") or {}).get("content") or {}).get("application/json")
        if content and "schema" in content:
            sch = flatten_schema(content["schema"], op.get("components", {}))
            req_fields = sch.get("required", []) or []
            props = sch.get("properties", {}) or {}
            for k,v in props.items():
                ex_full[k] = example_for(v)
            ex_req = {k: ex_full.get(k) for k in req_fields}
    
    # Create content lines for openapi_case_detect.txt
    content_lines = []
    content_lines.append(f"BASE: {base}")
    content_lines.append(f"CASE PATH: {case_path}")
    content_lines.append("REQUIRED: " + (", ".join(req_fields) if req_fields else "(none)"))
    content_lines.append("PROPERTIES:")
    for k in props:
        content_lines.append(f"  - {k}: {props[k].get('type','object')}")
    content_lines.append("EXAMPLE (required-only):")
    content_lines.append(json.dumps(ex_req, ensure_ascii=False, indent=2))
    content_lines.append("EXAMPLE (full):")
    content_lines.append(json.dumps(ex_full, ensure_ascii=False, indent=2))
    
    # Write to file with proper line joins
    with open(os.path.join(RUN_DIR, "openapi_case_detect.txt"), "wb") as f:
        f.write("\n".join(content_lines).encode("utf-8"))

    # URLs
    cashflow_url = f"{base}/api/v1/scenarios/{SCENARIO_ID}/cashflow/generate?client_id={CLIENT_ID}"
    compare_url  = f"{base}/api/v1/clients/{CLIENT_ID}/scenarios/compare"
    report_url   = f"{base}/api/v1/scenarios/{SCENARIO_ID}/report/pdf?client_id={CLIENT_ID}"
    case_url     = base + (case_path or f"/api/v1/clients/{CLIENT_ID}/case/detect")
    case_url     = case_url.replace("{client_id}", str(CLIENT_ID))

    # 1) case detect
    case_status, case_json = None, None
    try:
        r = requests.post(case_url, json={}, timeout=10)
        case_status = r.status_code
        if r.headers.get("content-type","").startswith("application/json"):
            case_json = r.json()
        save_json(os.path.join(RUN_DIR, "case_detect_200.json" if r.ok else "case_detect_error.json"),
                  case_json if case_json is not None else {"raw": r.text})
    except Exception as e:
        case_status = f"ERR: {e}"
        save_json(os.path.join(RUN_DIR, "case_detect_error.json"), {"error": str(e)})

    # 2) cashflow
    body7 = {"from":"2025-01","to":"2025-12","frequency":"monthly"}
    cf_r = requests.post(cashflow_url, json=body7, timeout=20)
    cf_status = cf_r.status_code
    cf_rows = []
    try:
        if cf_r.headers.get("content-type","").startswith("application/json"):
            cf_rows = cf_r.json()
    except Exception:
        pass
    save_json(os.path.join(RUN_DIR, "cashflow_200.json" if cf_r.ok else "cashflow_error.json"),
              cf_rows if cf_r.ok else {"raw": cf_r.text})

    # 3) compare
    body9 = {"scenarios":[SCENARIO_ID], "from":"2025-01", "to":"2025-12", "frequency":"monthly"}
    cmp_r = requests.post(compare_url, json=body9, timeout=20)
    cmp_status = cmp_r.status_code
    cmp_json = {}
    if cmp_r.headers.get("content-type","").startswith("application/json"):
        cmp_json = cmp_r.json()
    save_json(os.path.join(RUN_DIR, "compare_200.json" if cmp_r.ok else "compare_error.json"),
              cmp_json if cmp_r.ok else {"raw": cmp_r.text})

    # pick monthly rows for scenario_id
    monthly = []
    if isinstance(cmp_json, dict) and "results" in cmp_json:
        for item in cmp_json["results"]:
            if item.get("scenario_id") == SCENARIO_ID and isinstance(item.get("monthly"), list):
                monthly = item["monthly"]
                break
    elif isinstance(cmp_json, list):
        monthly = cmp_json
    totals = summarize_annual(monthly)

    # 4) pdf
    body8 = {"from":"2025-01","to":"2025-12","frequency":"monthly",
             "sections":{"summary":True,"cashflow_table":True,"net_chart":True,"scenarios_compare":True}}
    pdf_r = requests.post(report_url, json=body8, timeout=60)
    pdf_ok = pdf_r.ok and (pdf_r.content[:4] == b"%PDF")
    with open(os.path.join(RUN_DIR, "report_ok.pdf" if pdf_ok else "report_error.bin"), "wb") as f:
        f.write(pdf_r.content or b"")

    # /ui
    try:
        ui_status = requests.get(base + "/ui", timeout=5).status_code
    except Exception as e:
        ui_status = f"ERR: {e}"

    # zip
    zip_path = os.path.join(ART_DIR, f"release-{TS}-s11.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(RUN_DIR):
            for fn in files:
                ap = os.path.join(root, fn)
                z.write(ap, os.path.relpath(ap, RUN_DIR))

    # summary
    print("=== SPRINT 11 PROOF SUMMARY ===")
    print(f"Server BASE: {base}")
    print(f"1) CASE DETECT: STATUS {case_status}  case={case_json.get('case') if isinstance(case_json, dict) else '(n/a)'}")
    print(f"2) CASHFLOW: STATUS {cf_status}  rows={len(cf_rows) if isinstance(cf_rows, list) else 0} (expect 12)")
    y2025 = totals.get("2025")
    if y2025:
        print(f"3) COMPARE (2025 totals): inflow={y2025['inflow']:,} outflow={y2025['outflow']:,} add_income={y2025['additional_income_net']:,} cap_return={y2025['capital_return_net']:,} net={y2025['net']:,}")
    else:
        print("3) COMPARE: yearly totals unavailable")
    print(f"4) PDF: STATUS {pdf_r.status_code}  size={len(pdf_r.content or b'')}  %PDF={'OK' if pdf_ok else 'NO'}")
    print(f"5) OpenAPI CASE path: {case_path}  required={req_fields}")
    print(f"/ui: {ui_status}")
    print("Artifacts:")
    for n, sz in list_files(RUN_DIR):
        print(f" - {n} -> {sz} bytes")
    print(f"ZIP: {os.path.basename(zip_path)} -> {os.path.getsize(zip_path)} bytes")
    print("=== END SUMMARY ===")

if __name__ == "__main__":
    main()
