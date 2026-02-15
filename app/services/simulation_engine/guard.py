from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session


class ReadOnlyViolation(Exception):
    pass


@contextmanager
def read_only_session(db: Session) -> Generator[Session, None, None]:
    """Hard read-only guard for SQLAlchemy Session.

    Guarantees:
    - blocks commit always
    - allows flush only when there are no pending changes
    - disables autoflush
    - always rollbacks at the end
    - ensures session has no pending changes when exiting
    """

    original_autoflush = db.autoflush
    original_commit = db.commit
    original_flush = db.flush

    def _blocked_commit(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ReadOnlyViolation("commit is blocked in read-only simulation")

    def _guarded_flush(*args, **kwargs):  # type: ignore[no-untyped-def]
        if db.new or db.dirty or db.deleted:
            raise ReadOnlyViolation("flush with pending changes is blocked in read-only simulation")
        return original_flush(*args, **kwargs)

    try:
        db.autoflush = False
        db.commit = _blocked_commit  # type: ignore[method-assign]
        db.flush = _guarded_flush  # type: ignore[method-assign]

        yield db

        db.rollback()
        if db.new or db.dirty or db.deleted:
            raise ReadOnlyViolation("read-only simulation left pending changes in session")

    finally:
        try:
            db.rollback()
        except Exception:
            pass

        db.autoflush = original_autoflush
        db.commit = original_commit  # type: ignore[method-assign]
        db.flush = original_flush  # type: ignore[method-assign]
