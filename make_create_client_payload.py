import json
from pathlib import Path

doc = json.load(open("openapi_prod.json", encoding="utf-8"))
paths = doc.get("paths") or {}
schemas = ((doc.get("components") or {}).get("schemas") or {})

def deref(s):
    if not isinstance(s, dict):
        return {}
    if "$ref" in s:
        name = s["$ref"].split("/")[-1]
        return schemas.get(name) or {}
    return s

def dummy(schema):
    schema = deref(schema) or {}
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "anyOf" in schema:
        for s in schema["anyOf"]:
            if (s or {}).get("type") != "null":
                return dummy(s)
        return None
    if "$ref" in schema:
        return dummy(deref(schema))
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
            out[k] = dummy(props.get(k) or {})
        return out
    return "test"

p = "/api/v1/clients"
op = (paths.get(p) or {}).get("post") or {}
rb = op.get("requestBody") or {}
content = (rb.get("content") or {})
appjson = content.get("application/json") or {}
schema = appjson.get("schema") or {}

payload = dummy(schema)

Path("create_client_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE: create_client_payload.json")
print(payload)
