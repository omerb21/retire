import json


def _extract_first_json_object(raw: str) -> dict | None:
    if not isinstance(raw, str) or not raw:
        return None
    start = raw.find("{")
    if start < 0:
        return None

    in_string = False
    escaped = False
    depth = 0
    end = None
    for i in range(start, len(raw)):
        ch = raw[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end is None:
        return None
    try:
        parsed = json.loads(raw[start:end])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _append_transform_next_step_hint(*, tool_name: str, rendered_output: str) -> str:
    if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
        return rendered_output
    parsed = _extract_first_json_object(rendered_output)
    if not (isinstance(parsed, dict) and parsed.get("success") is True):
        return rendered_output
    if "השלב הבא המומלץ: הפקת דוח" in rendered_output:
        return rendered_output
    return rendered_output + "\n\nהשלב הבא המומלץ: הפקת דוח"
