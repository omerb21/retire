import json
from pathlib import Path

doc = json.load(open("openapi_prod.json", encoding="utf-8"))
paths = doc.get("paths", {}) or {}
schemas = ((doc.get("components") or {}).get("schemas") or {})

def resolve_ref(ref: str):
    name = ref.split("/")[-1]
    return schemas.get(name) or {}

def make_dummy(schema):
    if not schema:
        return "test"
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "anyOf" in schema:
        for s in schema["anyOf"]:
            if s.get("type") != "null":
                return make_dummy(s)
        return None
    if "$ref" in schema:
        return make_dummy(resolve_ref(schema["$ref"]))
    t = schema.get("type")
    if t == "string":
        fmt = schema.get("format")
        if fmt == "date":
            return "1990-01-01"
        if fmt == "date-time":
            return "1990-01-01T00:00:00Z"
        return "test"
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return False
    if t == "array":
        return []
    if t == "object" or "properties" in schema:
        props = schema.get("properties") or {}
        req = schema.get("required") or []
        out = {}
        for k in req:
            out[k] = make_dummy(props.get(k) or {})
        return out
    return "test"

cands = []
for p, methods in paths.items():
    for m, op in (methods or {}).items():
        if str(m).lower() != "post":
            continue
        pl = p.lower()
        if not any(x in pl for x in ("chat", "llm", "public-chat", "public_chat")):
            continue
        rb = (op or {}).get("requestBody") or {}
        content = (rb.get("content") or {})
        appjson = content.get("application/json") or {}
        schema = appjson.get("schema") or {}
        cands.append((p, op.get("operationId"), schema))

if not cands:
    Path("chat_endpoint.txt").write_text("", encoding="utf-8")
    Path("chat_payload.json").write_text("{}", encoding="utf-8")
    print("NO_CHAT_POST_ENDPOINT_FOUND")
    raise SystemExit(0)

cands.sort(key=lambda x: (0 if "public" in x[0].lower() else 1, x[0]))
path, opid, schema = cands[0]
payload = make_dummy(schema)

Path("chat_endpoint.txt").write_text(path, encoding="utf-8")
json.dump(payload, open("chat_payload.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("CHOSEN_CHAT_POST:", path)
print("OPERATION_ID:", opid)
print("PAYLOAD_KEYS:", list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
