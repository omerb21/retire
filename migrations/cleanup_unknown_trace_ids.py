"""
Migration: Delete agent_trace_event rows with trace_id='unknown' or NULL or empty.
Date: 2026-02-12
Description: Clean up polluted trace events that have no real trace_id.
"""

import sqlite3


def run_migration():
    conn = sqlite3.connect("retire.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT COUNT(*) FROM agent_trace_event "
            "WHERE trace_id IS NULL OR trace_id = '' OR trace_id = 'unknown'"
        )
        count = cursor.fetchone()[0]
        print(f"Found {count} rows with unknown/null/empty trace_id")

        if count > 0:
            cursor.execute(
                "DELETE FROM agent_trace_event "
                "WHERE trace_id IS NULL OR trace_id = '' OR trace_id = 'unknown'"
            )
            conn.commit()
            print(f"Deleted {count} polluted rows")
        else:
            print("No polluted rows found — nothing to do")

        print("Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
