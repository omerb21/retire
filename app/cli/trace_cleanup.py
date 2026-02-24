from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.cli.trace_cleanup")
    p.add_argument("--retention-days", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    retention_days = args.retention_days
    if retention_days is None:
        try:
            retention_days = int((os.getenv("TRACE_RETENTION_DAYS") or "30").strip())
        except Exception:
            retention_days = 30

    if retention_days < 0:
        retention_days = 0

    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(days=int(retention_days))

    from app.services.agent_eyes.event_collector import delete_trace_events_older_than

    count = delete_trace_events_older_than(
        cutoff_dt=cutoff_dt, dry_run=bool(args.dry_run)
    )

    if args.dry_run:
        print(
            f"trace_cleanup dry_run=1 retention_days={retention_days} would_delete={count}"
        )
    else:
        print(
            f"trace_cleanup dry_run=0 retention_days={retention_days} deleted={count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
