"""Fetch commutation rows for document generation."""

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset

logger = logging.getLogger(__name__)


def fetch_commutations_data(db: Session, client_id: int) -> List[CapitalAsset]:
    """Return capital assets that represent pension commutations.

    Commutations are marked by ``COMMUTATION:`` in ``CapitalAsset.remarks``.
    Their ``tax_treatment`` can still be ``taxable`` before fixation applies
    the exemption, so document generation must not filter them out by tax flag.
    """
    try:
        commutations = (
            db.query(CapitalAsset)
            .filter(
                CapitalAsset.client_id == client_id,
                CapitalAsset.remarks.like("%COMMUTATION:%"),
            )
            .order_by(CapitalAsset.start_date.asc(), CapitalAsset.id.asc())
            .all()
        )

        logger.info(
            "Fetched %s commutations for client %s", len(commutations), client_id
        )
        return commutations

    except Exception as exc:
        logger.error("Error fetching commutations data: %s", exc, exc_info=True)
        return []
