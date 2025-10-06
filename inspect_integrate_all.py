# inspect_integrate_all.py
# Deterministic, no-guess introspection of FastAPI endpoint:
# Finds POST route that ends with "/cashflow/integrate-all", prints the exact body type,
# required fields (from Pydantic model if any), or heuristically extracts required keys
# from the endpoint source when the body is a List[dict]/free-form.
#
# Run: python inspect_integrate_all.py
# (from the repo root where "app.main:app" is importable)

import sys, os, json, inspect, typing, importlib

def eprint(*a, **k): print(*a, file=sys.stderr, **k)

# --- Import FastAPI app ---
APP_IMPORT = "app.main"
APP_ATTR   = "app"

try:
    mod = importlib.import_module(APP_IMPORT)
    app = getattr(mod, APP_ATTR)
except Exception as ex:
    eprint(f"[ERROR] Failed to import {APP_IMPORT}:{APP_ATTR}: {ex}")
    eprint("Make sure you run this from the project root (PYTHONPATH) so 'app.main' is importable.")
    sys.exit(1)

# --- Find the route ---
from fastapi.routing import APIRoute

target_routes = []
for r in app.routes:
    if isinstance(r, APIRoute):
        if "POST" in r.methods and r.path.endswith("/cashflow/integrate-all"):
            target_routes.append(r)

if not target_routes:
    eprint("[ERROR] No POST route found ending with '/cashflow/integrate-all'.")
    eprint("Available POST routes:")
    for r in app.routes:
        if isinstance(r, APIRoute) and "POST" in r.methods:
            eprint(f"  {r.path}")
    sys.exit(1)

# If multiple, take the first (print them all anyway)
print("FOUND POST routes for '/cashflow/integrate-all':")
for r in target_routes:
    print(f"  PATH: {r.path}  METHODS: {sorted(r.methods)}")
route = target_routes[0]
print()

endpoint = route.endpoint
ep_file  = inspect.getsourcefile(endpoint) or "<unknown file>"
try:
    ep_src   = inspect.getsource(endpoint)
except OSError:
    ep_src   = "<source not available>"

print(f"ENDPOINT: {endpoint.__module__}.{endpoint.__qualname__}")
print(f"FILE: {ep_file}")
print("---- Endpoint Source (first 200 lines) ----")
print("\n".join(ep_src.splitlines()[:200]))
print("---- End Source ----\n")

# --- Determine body param annotation ---
from typing import get_type_hints, get_origin, get_args

hints = {}
try:
    hints = get_type_hints(endpoint)
except Exception:
    # it's fine; we can still use __annotations__
    hints = getattr(endpoint, "__annotations__", {}) or {}

sig = inspect.signature(endpoint)

# Prefer FastAPI's dependant info if present (more reliable than heuristics)
body_params = []
try:
    for p in route.dependant.body_params:  # type: ignore[attr-defined]
        body_params.append(p)
except Exception:
    body_params = []

def pretty_type(t):
    try:
        return str(t)
    except Exception:
        return repr(t)

def is_base_model(cls):
    try:
        from pydantic import BaseModel
        return isinstance(cls, type) and issubclass(cls, BaseModel)
    except Exception:
        return False

def schema_from_model(model_cls):
    try:
        # pydantic v2
        if hasattr(model_cls, "model_json_schema"):
            return model_cls.model_json_schema()
        # pydantic v1
        if hasattr(model_cls, "schema"):
            return model_cls.schema()
    except Exception:
        pass
    return None

def example_for_field(name, fsch):
    # Try to propose a sensible example based on type/format/name
    if not isinstance(fsch, dict):
        return "string"
    t = fsch.get("type")
    fmt = fsch.get("format")
    if (t == "string" and fmt == "date") or name.lower() == "date":
        from datetime import date
        return date.today().isoformat()
    if t == "integer" or "int" in (fsch.get("title","").lower()):
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    if t == "array":
        item = fsch.get("items") or {}
        return [example_for_field(name, item)]
    if t == "object":
        props = fsch.get("properties") or {}
        return {k: example_for_field(k, v) for k, v in props.items()}
    # common names
    if name.lower() in ("scenario_id","sid","scenarioid"):
        return 0
    if name.lower() in ("inflow","outflow","amount","sum"):
        return 0.0
    return "string"

def print_schema(schema):
    required = schema.get("required") or []
    props    = schema.get("properties") or {}
    print("REQUIRED:", ", ".join(required) if required else "(none)")
    if props:
        print("\nPROPERTIES:")
        rows = []
        for k, v in props.items():
            rows.append({
                "name": k,
                "type": v.get("type", ""),
                "format": v.get("format", ""),
                "required": k in required
            })
        # sort required desc then name
        rows.sort(key=lambda r:(not r["required"], r["name"]))
        w_name = max([4] + [len(r["name"]) for r in rows])
        print(f"{'name'.ljust(w_name)}  type      format     required")
        print(f"{'-'*w_name}  --------  ---------  --------")
        for r in rows:
            print(f"{r['name'].ljust(w_name)}  {r['type'] or '-':8}  {r['format'] or '-':9}  {str(r['required'])}")
    else:
        print("\nSchema has no properties (free-form object).")

def extract_required_keys_from_source(src: str):
    """
    Heuristics: look for explicit checks like:
      - "Missing required field 'date'"
      - item['date']
      - 'date' not in item
    Returns a sorted list of unique keys.
    """
    keys = set()
    import re
    # Error messages
    for m in re.finditer(r"Missing required field '([^']+)'", src):
        keys.add(m.group(1))
    # item['key']
    for m in re.finditer(r"\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]", src):
        keys.add(m.group(1))
    # 'key' in item
    for m in re.finditer(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s+in\s+([A-Za-z_][A-Za-z0-9_]*)", src):
        keys.add(m.group(1))
    return sorted(keys)

def build_example_from_required(req_keys):
    ex = {}
    for k in req_keys:
        lk = k.lower()
        if "date" in lk:
            from datetime import date
            ex[k] = date.today().isoformat()
        elif "flow" in lk or "amount" in lk or "sum" in lk:
            ex[k] = 0.0
        elif "id" in lk:
            ex[k] = 0
        else:
            ex[k] = "string"
    return [ex]  # endpoint expects an ARRAY

print("---- BODY PARAM ANALYSIS ----")
if body_params:
    # Use FastAPI dependant info
    for bp in body_params:
        ann = getattr(bp, "annotation", None)
        print("Body param annotation:", pretty_type(ann))
else:
    print("(FastAPI dependant.body_params unavailable; using function signature heuristics.)")

# Heuristic fallback: pick the first param that is not path/query "simple" types
body_ann = None
body_ann_name = None
if not body_params:
    for pname, p in sig.parameters.items():
        if pname in ("request","response","background_tasks"):
            continue
        ann = hints.get(pname, p.annotation)
        if ann is inspect._empty:
            continue
        origin = get_origin(ann)
        if origin in (list, typing.List, typing.Sequence) or is_base_model(ann) or ann in (dict, typing.Dict):
            body_ann = ann
            body_ann_name = pname
            break
else:
    # Try to resolve annotation from dependant param
    bp = body_params[0]
    ann = getattr(bp, "annotation", None)
    body_ann = ann
    body_ann_name = getattr(bp, "name", "<body>")

print(f"Chosen body parameter: {body_ann_name}  ->  {pretty_type(body_ann)}")
print()

# Analyze type
origin = get_origin(body_ann)
args   = get_args(body_ann)
required_keys = []

if origin in (list, typing.List, typing.Sequence):
    inner = args[0] if args else None
    print("Body type: ARRAY of", pretty_type(inner))
    if is_base_model(inner):
        print(f"\nModel: {inner.__module__}.{inner.__name__}")
        schema = schema_from_model(inner) or {}
        print_schema(schema)
        # Example payloads
        props = schema.get("properties") or {}
        req   = schema.get("required") or []
        example_req = [{ k: example_for_field(k, props.get(k, {})) for k in req }]
        example_all = [{ k: example_for_field(k, v) for k, v in props.items() }]
        print("\nEXAMPLE PAYLOAD (required only):")
        print(json.dumps(example_req, indent=2, ensure_ascii=False))
        print("\nEXAMPLE PAYLOAD (all fields):")
        print(json.dumps(example_all, indent=2, ensure_ascii=False))
    else:
        # Free-form objects; try extracting from source
        print("Inner type is not a Pydantic model (likely dict/free-form).")
        required_keys = extract_required_keys_from_source(ep_src)
        if required_keys:
            print("Required keys inferred from source:", ", ".join(required_keys))
            ex = build_example_from_required(required_keys)
            print("\nEXAMPLE PAYLOAD (based on source checks):")
            print(json.dumps(ex, indent=2, ensure_ascii=False))
        else:
            print("Could not infer required keys from source; endpoint likely validates dynamically.")
            print("Try reading the source above for explicit 'item[...]' or 'Missing required field' checks.")
else:
    # Not a list body; show pydantic model or dict
    if is_base_model(body_ann):
        print("Body type: SINGLE Pydantic model")
        schema = schema_from_model(body_ann) or {}
        print_schema(schema)
        props = schema.get("properties") or {}
        req   = schema.get("required") or []
        example_req = { k: example_for_field(k, props.get(k, {})) for k in req }
        example_all = { k: example_for_field(k, v) for k, v in props.items() }
        print("\nEXAMPLE PAYLOAD (required only):")
        print(json.dumps(example_req, indent=2, ensure_ascii=False))
        print("\nEXAMPLE PAYLOAD (all fields):")
        print(json.dumps(example_all, indent=2, ensure_ascii=False))
    else:
        print("Body type is not a list and not a Pydantic model (possibly dict or Any).")
        required_keys = extract_required_keys_from_source(ep_src)
        if required_keys:
            print("Required keys inferred from source:", ", ".join(required_keys))
            ex = { k: ("2025-01-01" if "date" in k.lower() else (0 if "id" in k.lower() else 0.0 if "flow" in k.lower() else "string")) for k in required_keys }
            print("\nEXAMPLE PAYLOAD (based on source checks):")
            print(json.dumps(ex, indent=2, ensure_ascii=False))
        else:
            print("Could not infer required keys from source.")

print("\nDONE.")
