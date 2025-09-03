import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


def ensure_logs_dir():
    """Ensure logs directory exists"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def log_calc(event: str, payload: Dict[str, Any], result: Optional[Any] = None, debug_info: Optional[Dict[str, Any]] = None):
    """
    Log calculation events to JSONL format
    
    Args:
        event: Event name (e.g., "generate_cashflow", "compare_scenarios", "generate_pdf")
        payload: Input parameters/data
        result: Calculation result (optional)
        debug_info: Additional debug information when DEBUG_CALC=1
    """
    logs_dir = ensure_logs_dir()
    log_file = logs_dir / "calculation.log"
    
    # Create log entry
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        "payload": payload,
    }
    
    # Add result if provided
    if result is not None:
        # For large results, log summary instead of full data
        if isinstance(result, list) and len(result) > 10:
            log_entry["result_summary"] = {
                "type": "list",
                "length": len(result),
                "first_item": result[0] if result else None,
                "last_item": result[-1] if result else None
            }
        elif isinstance(result, dict) and "scenarios" in result:
            # For scenario comparison results
            log_entry["result_summary"] = {
                "type": "scenario_comparison",
                "scenario_count": len(result.get("scenarios", {})),
                "meta": result.get("meta", {})
            }
        else:
            log_entry["result"] = result
    
    # Add debug info if DEBUG_CALC is enabled
    debug_enabled = os.getenv("DEBUG_CALC", "0") == "1"
    if debug_enabled and debug_info:
        log_entry["debug"] = debug_info
    
    # Write to JSONL file
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        # Don't let logging errors break the main application
        print(f"Warning: Failed to write calculation log: {e}")


def get_recent_logs(limit: int = 100) -> list:
    """Get recent calculation logs for debugging"""
    logs_dir = ensure_logs_dir()
    log_file = logs_dir / "calculation.log"
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Get last N lines
            recent_lines = lines[-limit:] if len(lines) > limit else lines
            return [json.loads(line.strip()) for line in recent_lines if line.strip()]
    except Exception as e:
        print(f"Warning: Failed to read calculation log: {e}")
        return []


def clear_logs():
    """Clear calculation logs (for testing)"""
    logs_dir = ensure_logs_dir()
    log_file = logs_dir / "calculation.log"
    
    if log_file.exists():
        log_file.unlink()
