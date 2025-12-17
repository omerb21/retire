from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.services.retirement.utils.pension_utils import compute_pension_start_date_from_funds
from app.services.client_service import normalize_id_number


class ClientCrudService:
    @staticmethod
    def create_client(db: Session, client: ClientCreate) -> Client:
        normalized_id = client.id_number
        if not normalized_id and client.id_number_raw:
            normalized_id = normalize_id_number(client.id_number_raw)

        existing_client = None
        if normalized_id:
            existing_client = db.query(Client).filter(Client.id_number == normalized_id).first()
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

        if not db_client.pension_start_date:
            effective_pension_start_date = compute_pension_start_date_from_funds(db, db_client)
            if effective_pension_start_date:
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
