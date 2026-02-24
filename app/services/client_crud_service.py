from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.services.retirement.utils.pension_utils import (
    compute_pension_start_date_from_funds,
)
from app.services.client_service import normalize_id_number


class ClientCrudService:
    @staticmethod
    def create_client(db: Session, client: ClientCreate) -> Client:
        normalized_id = client.id_number
        if not normalized_id and client.id_number_raw:
            normalized_id = normalize_id_number(client.id_number_raw)

        existing_client = None
        if normalized_id:
            existing_client = (
                db.query(Client).filter(Client.id_number == normalized_id).first()
            )
        if existing_client:
            raise ValueError("duplicate_id_number")

        client_data = client.model_dump()
        if normalized_id:
            client_data["id_number"] = normalized_id

        db_client = Client(**client_data)
        db.add(db_client)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("duplicate_id_number") from exc

        db.refresh(db_client)
        return db_client

    @staticmethod
    def get_client(db: Session, client_id: int) -> Client:
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise ValueError("client_not_found")

        effective_pension_start_date = compute_pension_start_date_from_funds(
            db, db_client
        )
        if db_client.pension_start_date != effective_pension_start_date:
            db_client.pension_start_date = effective_pension_start_date
            db.add(db_client)
            db.commit()
            db.refresh(db_client)

        return db_client

    @staticmethod
    def update_client(db: Session, client_id: int, client: ClientUpdate) -> Client:
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise ValueError("client_not_found")

        update_data = client.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_client, field, value)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("duplicate_id_number") from exc

        db.refresh(db_client)
        return db_client

    @staticmethod
    def delete_client(db: Session, client_id: int) -> None:
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise ValueError("client_not_found")

        # Hard delete all related data so recreating a client with the same id_number has no residual state.
        # We use bulk deletes to avoid relying on DB-level cascade settings.
        try:
            from app.models.public_chat import PublicChatMessage, PublicChatSession
        except Exception:
            PublicChatSession = None
            PublicChatMessage = None

        try:
            from app.models.employment import Employment
        except Exception:
            Employment = None

        try:
            from app.models.termination_event import TerminationEvent
        except Exception:
            TerminationEvent = None

        try:
            from app.models.pension import Pension
        except Exception:
            Pension = None

        try:
            from app.models.scenario import Scenario
        except Exception:
            Scenario = None

        try:
            from app.models.pension_fund import PensionFund
        except Exception:
            PensionFund = None

        try:
            from app.models.capital_asset import CapitalAsset
        except Exception:
            CapitalAsset = None

        try:
            from app.models.grant import Grant
        except Exception:
            Grant = None

        try:
            from app.models.fixation_result import FixationResult
        except Exception:
            FixationResult = None

        try:
            from app.models.current_employment.employer import CurrentEmployer
            from app.models.current_employment.grant import EmployerGrant
        except Exception:
            CurrentEmployer = None
            EmployerGrant = None

        # 1) Public chat (messages -> sessions)
        if PublicChatSession is not None and PublicChatMessage is not None:
            session_ids = [
                row[0]
                for row in db.query(PublicChatSession.id)
                .filter(PublicChatSession.client_id == client_id)
                .all()
            ]
            if session_ids:
                db.query(PublicChatMessage).filter(
                    PublicChatMessage.session_id.in_(session_ids)
                ).delete(synchronize_session=False)
            db.query(PublicChatSession).filter(
                PublicChatSession.client_id == client_id
            ).delete(synchronize_session=False)

        # 2) Termination events (depend on employment)
        if TerminationEvent is not None:
            db.query(TerminationEvent).filter(
                TerminationEvent.client_id == client_id
            ).delete(synchronize_session=False)

        # 3) Employment
        if Employment is not None:
            db.query(Employment).filter(Employment.client_id == client_id).delete(
                synchronize_session=False
            )

        # 4) Pensions
        if Pension is not None:
            db.query(Pension).filter(Pension.client_id == client_id).delete(
                synchronize_session=False
            )

        # 5) Scenarios
        if Scenario is not None:
            db.query(Scenario).filter(Scenario.client_id == client_id).delete(
                synchronize_session=False
            )

        # 6) Retirement assets
        if PensionFund is not None:
            db.query(PensionFund).filter(PensionFund.client_id == client_id).delete(
                synchronize_session=False
            )
        if CapitalAsset is not None:
            db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).delete(
                synchronize_session=False
            )

        # 7) Grants / fixation results
        if Grant is not None:
            db.query(Grant).filter(Grant.client_id == client_id).delete(
                synchronize_session=False
            )
        if FixationResult is not None:
            db.query(FixationResult).filter(
                FixationResult.client_id == client_id
            ).delete(synchronize_session=False)

        # 8) Current employer + employer grants
        if CurrentEmployer is not None:
            employer_ids = [
                row[0]
                for row in db.query(CurrentEmployer.id)
                .filter(CurrentEmployer.client_id == client_id)
                .all()
            ]
            if employer_ids and EmployerGrant is not None:
                db.query(EmployerGrant).filter(
                    EmployerGrant.employer_id.in_(employer_ids)
                ).delete(synchronize_session=False)
            db.query(CurrentEmployer).filter(
                CurrentEmployer.client_id == client_id
            ).delete(synchronize_session=False)

        # 9) Finally delete the client row
        db.delete(db_client)
        db.commit()

    @staticmethod
    def list_clients(
        db: Session,
        *,
        skip: int,
        limit: int,
        is_active: Optional[bool] = None,
        gender: Optional[str] = None,
        search: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Tuple[list[Client], int]:
        query = db.query(Client)

        if is_active is not None:
            query = query.filter(Client.is_active == is_active)
        if gender is not None:
            query = query.filter(Client.gender == gender)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Client.full_name.ilike(pattern),
                    Client.id_number.ilike(pattern),
                )
            )

        total = query.count()

        if sort == "full_name":
            query = query.order_by(Client.full_name.asc())

        items = query.offset(skip).limit(limit).all()
        return items, total
