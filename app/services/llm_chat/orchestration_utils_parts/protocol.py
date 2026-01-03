import json
from typing import Any


def _extract_single_line_json_after_marker(reply: str, marker: str) -> dict[str, Any]:
    if marker not in reply:
        raise ValueError(f"Missing marker: {marker}")

    after = reply.split(marker, 1)[1].strip()
    json_str = after.strip("`").strip()
    json_str = json_str.splitlines()[0] if json_str else ""
    if not json_str:
        raise json.JSONDecodeError(f"Empty JSON after {marker}", after, 0)

    parsed = json.loads(json_str)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected object JSON after {marker}")
    return parsed


def validate_tool_call_protocol_for_execution(reply: str) -> tuple[bool, str | None]:
    """Server-side enforcement for the mandatory pre-tool protocol.

    Only call this when you are about to execute a tool.
    """

    if "###TOOL_CALL###" not in (reply or ""):
        return True, None

    if "###APPROVAL_REQUIRED###" in reply:
        approval_payload = None
        try:
            approval_payload = _extract_single_line_json_after_marker(
                reply, "###APPROVAL_REQUIRED###"
            )
        except Exception:
            approval_payload = None

        reason = None
        if isinstance(approval_payload, dict):
            try:
                reason = str(approval_payload.get("reason") or "").strip() or None
            except Exception:
                reason = None

        msg = (
            "ERROR: TOOL_CALL blocked (Approval Step). The model indicated approval is required.\n"
            + (f"reason: {reason}\n" if reason else "")
            + "details: reply contained ###APPROVAL_REQUIRED###\n"
        )
        return False, msg

    idx_tool = reply.find("###TOOL_CALL###")
    idx_transparency = reply.find("###TRANSPARENCY_LOG###")
    idx_risk = reply.find("###RISK_REVIEW###")

    missing: list[str] = []
    if idx_transparency < 0:
        missing.append("###TRANSPARENCY_LOG###")
    if idx_risk < 0:
        missing.append("###RISK_REVIEW###")
    if missing:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Missing required sections: "
            + ", ".join(missing)
            + ".",
        )

    if not (idx_transparency < idx_risk < idx_tool):
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Required sections are out of order. "
            "Expected: ###TRANSPARENCY_LOG### then ###RISK_REVIEW### then ###TOOL_CALL###.",
        )

    try:
        _ = _extract_single_line_json_after_marker(reply, "###TRANSPARENCY_LOG###")
    except Exception as e:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Invalid or missing JSON after ###TRANSPARENCY_LOG###. "
            + f"Details: {type(e).__name__}: {e}",
        )

    try:
        risk = _extract_single_line_json_after_marker(reply, "###RISK_REVIEW###")
    except Exception as e:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Invalid or missing JSON after ###RISK_REVIEW###. "
            + f"Details: {type(e).__name__}: {e}",
        )

    approval_required = False
    conflict_with_rag = False
    try:
        approval_required = bool(risk.get("approval_required"))
    except Exception:
        approval_required = False
    try:
        conflict_with_rag = bool(risk.get("conflict_with_rag"))
    except Exception:
        conflict_with_rag = False

    if approval_required or conflict_with_rag:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Risk Review requires approval or indicates conflict with RAG. "
            f"approval_required={approval_required}, conflict_with_rag={conflict_with_rag}.",
        )

    return True, None


def parse_tool_call_from_reply(reply: str) -> tuple[str, dict[str, Any]] | None:
    marker = "###TOOL_CALL###"
    if marker not in reply:
        return None

    parts = reply.split(marker)
    if len(parts) <= 1:
        return None

    text_part = parts[0].strip()
    tool_part = parts[1].strip()

    tool_json_str = tool_part.strip("`").strip()
    if not tool_json_str:
        return None

    tool_json_str = tool_json_str.splitlines()[0]
    try:
        tool_data = json.loads(tool_json_str)
    except json.JSONDecodeError:
        return None

    return text_part, tool_data


def apply_max_exemption_if_requested(
    tool_name: str | None, tool_args: dict[str, Any], force_max_exemption: bool
) -> None:
    if force_max_exemption and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        tool_args["apply_max_exemption"] = True


def build_tool_call_message_content(tool_data: dict[str, Any], ensure_ascii: bool) -> str:
    return f"###TOOL_CALL### {json.dumps(tool_data, ensure_ascii=ensure_ascii)}"
