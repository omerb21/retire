"""
Tool handler for GET_CLIENT_SNAPSHOT.

Returns snapshot info for a client via SnapshotService – the same data
served by GET /api/v1/clients/{client_id}/snapshot/info.
"""

import json
import logging

from sqlalchemy.orm import Session

from app.services.snapshot_service import SnapshotService

logger = logging.getLogger("app.llm_agent_tools")


def handle_get_client_snapshot(*, args: dict, client_id: int, db: Session) -> str:
    """Return a JSON summary of the client's current data in the system."""
    try:
        service = SnapshotService(db)
        snapshot = service.save_snapshot(client_id, "agent_snapshot")

        result = {
            "success": True,
            "tool_name": "GET_CLIENT_SNAPSHOT",
            "client_id": client_id,
            "total_items": snapshot["total_items"],
            "breakdown": {
                "pension_funds": len(snapshot["snapshot"]["data"]["pension_funds"]),
                "capital_assets": len(snapshot["snapshot"]["data"]["capital_assets"]),
                "additional_incomes": len(
                    snapshot["snapshot"]["data"]["additional_incomes"]
                ),
                "grants": len(snapshot["snapshot"]["data"]["grants"]),
                "has_employer": snapshot["snapshot"]["data"]["current_employer"]
                is not None,
                "has_termination": snapshot["snapshot"]["data"]["termination_event"]
                is not None,
                "has_fixation": snapshot["snapshot"]["data"]["fixation_result"]
                is not None,
            },
        }
        return result

    except ValueError as e:
        return {
            "success": False,
            "tool_name": "GET_CLIENT_SNAPSHOT",
            "error": str(e),
        }
    except Exception as e:
        logger.error("GET_CLIENT_SNAPSHOT failed: %s", e, exc_info=True)
        return {
            "success": False,
            "tool_name": "GET_CLIENT_SNAPSHOT",
            "error": f"Internal error: {str(e)[:500]}",
        }
