import logging
import threading

from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("app.fixation_background")


def trigger_fixation_package_for_client_background(db: Session, client_id: int) -> None:
    engine = db.get_bind()
    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _generate() -> None:
        bg_db = SessionFactory()
        try:
            from app.routers.fixation import generate_fixation_package_for_client

            result = generate_fixation_package_for_client(db=bg_db, client_id=client_id)
            if result.get("success", False):
                logger.info(
                    "Background fixation package generated for client %s: %s files",
                    client_id,
                    len(result.get("files", [])),
                )
            else:
                logger.warning(
                    "Background fixation package generation failed for client %s: %s",
                    client_id,
                    result.get("message", "Unknown error"),
                )
        except Exception:
            logger.exception("fixation_bg_trigger_error")
        finally:
            bg_db.close()

    try:
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
    except Exception:
        logger.exception("fixation_bg_trigger_error")
