from app.schemas.llm_chat import ChatRequest

from app.models.client import Client


def _compute_analysis_default_retirement_age(
    *, request: ChatRequest, db, is_portfolio_analysis: bool
):
    analysis_default_retirement_age: int | None = None
    if is_portfolio_analysis and request.client_id is not None:
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
            client_age = (
                client.get_age() if client and hasattr(client, "get_age") else None
            )
            from app.services.retirement_age_service import (
                DEFAULT_MALE_RETIREMENT_AGE,
                get_retirement_age_simple,
            )

            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            try:
                if (
                    client
                    and getattr(client, "birth_date", None)
                    and getattr(client, "gender", None)
                ):
                    legal_ret_age = int(
                        get_retirement_age_simple(client.birth_date, client.gender)
                    )
            except Exception:
                legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

            analysis_default_retirement_age = max(
                int(legal_ret_age), int(client_age or legal_ret_age)
            )
        except Exception:
            analysis_default_retirement_age = None

    return analysis_default_retirement_age
