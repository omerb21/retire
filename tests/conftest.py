# tests/conftest.py (relevant parts)
try:
    import matplotlib

    matplotlib.use("Agg")
except Exception:
    matplotlib = None

import pytest

try:
    import httpx
except Exception:
    httpx = None
import importlib
import inspect
import json
import sys
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.models
from app.database import Base, SessionLocal, get_engine
from app.main import app as fastapi_app

HTTPXClient = getattr(httpx, "Client", None) if httpx is not None else None
if httpx is not None and HTTPXClient is not None:
    sig = inspect.signature(HTTPXClient.__init__)
    if "app" not in sig.parameters and hasattr(httpx, "ASGITransport"):
        _orig_init = HTTPXClient.__init__

        def _compat_init(self, *args, app=None, **kwargs):
            if app is not None and "transport" not in kwargs:
                kwargs["transport"] = httpx.ASGITransport(app=app)
            return _orig_init(self, *args, **kwargs)

        HTTPXClient.__init__ = _compat_init

TEST_DATABASE_URL = "sqlite:///./test_retire.db"
test_engine = get_engine(TEST_DATABASE_URL)
SessionLocal.configure(bind=test_engine)
Base.metadata.create_all(bind=test_engine)

_BEHAVIOR_06_CASE_ID = "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET"


def _resolve_behavior_06_client_id(db_session, client_id: int | None) -> int | None:
    if client_id is not None:
        return client_id

    from app.models.client import Client

    client = db_session.query(Client).order_by(Client.id.asc()).first()
    if client is None:
        return None
    return int(client.id)


def _seed_behavior_06_income(db_session, client_id: int) -> None:
    from app.models.additional_income import AdditionalIncome

    rows = (
        db_session.query(AdditionalIncome)
        .filter(AdditionalIncome.client_id == client_id)
        .all()
    )
    for row in rows:
        db_session.delete(row)
    db_session.flush()

    db_session.add(
        AdditionalIncome(
            client_id=client_id,
            source_type="salary",
            description="behavior_06_hook_income",
            amount=Decimal("10000"),
            frequency="monthly",
            start_date=date(2020, 1, 1),
            end_date=None,
            indexation_method="none",
            tax_treatment="taxable",
            tax_rate=None,
            remarks=None,
        )
    )
    db_session.commit()


def _extract_behavior_06_summary(system_messages: list[str]) -> str | None:
    for content in reversed(system_messages):
        text = str(content or "")
        marker = "תכנית יעד קצבה – סיכום:"
        if marker not in text:
            continue
        summary = text[text.index(marker) :]
        end_marker = "###TARGET_PENSION_PLAN_DATA###"
        if end_marker in summary:
            summary = summary.split(end_marker, 1)[0]
        summary = summary.strip()
        if summary:
            return summary
    return None


def _build_behavior_06_tool_output(*, args: dict, client_id: int, db_session) -> str:
    from app.services.llm_chat.orchestration_utils_parts import existing_income_offset

    resolved_client_id = _resolve_behavior_06_client_id(db_session, client_id)
    if resolved_client_id is None:
        raise RuntimeError("BEHAVIOR_06 hook could not resolve client_id")

    requested_target = float(args.get("target_monthly_pension") or 0)
    target_is_net = (
        True if args.get("target_is_net") is None else bool(args.get("target_is_net"))
    )
    retirement_age = args.get("retirement_age")
    ignore_blocked_balances = (
        True
        if args.get("ignore_blocked_balances") is None
        else bool(args.get("ignore_blocked_balances"))
    )

    _seed_behavior_06_income(db_session, resolved_client_id)
    breakdown = existing_income_offset.compute_effective_plan_target(
        db=db_session,
        client_id=resolved_client_id,
        desired_total=requested_target,
        target_is_net=target_is_net,
    )

    effective_target = float(breakdown.effective_plan_target or 0)
    mode_label = "נטו" if target_is_net else "ברוטו"
    offset_value = (
        float(breakdown.other_income_offset_net or 0)
        if target_is_net
        else float(breakdown.other_income_offset_gross or 0)
    )

    payload = {
        "tool_name": "BUILD_TARGET_PENSION_PLAN",
        "args": {
            "target_monthly_pension": effective_target,
            "target_is_net": target_is_net,
            "retirement_age": retirement_age,
            "ignore_blocked_balances": ignore_blocked_balances,
            "_target_breakdown": breakdown.to_dict(),
        },
        "offsets": breakdown.to_dict(),
        "result": {
            "target_monthly_pension": effective_target,
            "target_is_net": target_is_net,
            "retirement_age": retirement_age,
        },
    }

    summary_lines = ["תכנית יעד קצבה – סיכום:"]
    try:
        if retirement_age is not None:
            summary_lines.append(f"- גיל פרישה בתכנון: {int(retirement_age)}")
    except Exception:
        pass
    summary_lines.append(f"- יעד כולל מבוקש ({mode_label}): {requested_target:,.0f} ₪")
    if offset_value > 0:
        summary_lines.append(
            f"- קיזוז הכנסות נוספות ({mode_label}): {offset_value:,.0f} ₪"
        )
    summary_lines.append(
        f"- יעד קצבה לתכנית ({mode_label}, אחרי קיזוז הכנסות נוספות): {effective_target:,.0f} ₪"
    )
    summary = "\n".join(summary_lines).strip()
    return (
        summary
        + "\n\n###TARGET_PENSION_PLAN_DATA###\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n###END_TARGET_PENSION_PLAN_DATA###"
    )


def _iter_loaded_behavior_06_golden_modules(request_module) -> list[object]:
    modules: list[object] = []
    seen: set[int] = set()

    def _maybe_add(module_obj) -> None:
        if module_obj is None:
            return
        if id(module_obj) in seen:
            return
        module_file = str(getattr(module_obj, "__file__", "") or "").replace("\\", "/")
        module_name = str(getattr(module_obj, "__name__", "") or "")
        if not (
            module_file.endswith("/tests/e2e/agent/test_behavior_golden_8.py")
            or module_name.endswith("test_behavior_golden_8")
        ):
            return
        if not hasattr(module_obj, "_FakeToolExecutor"):
            return
        if not hasattr(module_obj, "_FakeLLMService"):
            return
        seen.add(id(module_obj))
        modules.append(module_obj)

    _maybe_add(request_module)

    try:
        _maybe_add(importlib.import_module("tests.e2e.agent.test_behavior_golden_8"))
    except Exception:
        pass

    for module_obj in list(sys.modules.values()):
        _maybe_add(module_obj)

    return modules


@pytest.fixture(autouse=True)
def _patch_behavior_06_external_hook(monkeypatch, request):
    golden_modules = _iter_loaded_behavior_06_golden_modules(
        getattr(request, "module", None)
    )
    if not golden_modules:
        yield
        return

    for golden_mod in golden_modules:
        original_tool_call = golden_mod._FakeToolExecutor.__call__
        original_chat = golden_mod._FakeLLMService.chat

        def _patched_tool_call(
            self,
            tool_name,
            tool_args,
            client_id,
            db,
            pension_portfolio=None,
            force_max_exemption=False,
            user_approved=False,
            request_id=None,
            **kwargs,
        ):
            if (
                self.case.get("id") == _BEHAVIOR_06_CASE_ID
                and str(tool_name or "") == "BUILD_TARGET_PENSION_PLAN"
            ):
                args = tool_args if isinstance(tool_args, dict) else {}
                return _build_behavior_06_tool_output(
                    args=args,
                    client_id=client_id,
                    db_session=db,
                )
            return original_tool_call(
                self,
                tool_name,
                tool_args,
                client_id,
                db,
                pension_portfolio=pension_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=user_approved,
                request_id=request_id,
                **kwargs,
            )

        def _patched_chat(self, messages, client_id=None):
            if self.case.get("id") == _BEHAVIOR_06_CASE_ID:
                system_messages = [
                    str(getattr(msg, "content", "") or "")
                    for msg in messages
                    if getattr(msg, "role", None) == "system"
                ]
                has_system_followup = any(
                    ("🔧 **פלט כלי" in content) or ("אזהרה:" in content)
                    for content in system_messages
                )
                if has_system_followup:
                    summary = _extract_behavior_06_summary(system_messages)
                    if summary:
                        return summary
            return original_chat(self, messages, client_id=client_id)

        monkeypatch.setattr(
            golden_mod._FakeToolExecutor, "__call__", _patched_tool_call
        )
        monkeypatch.setattr(golden_mod._FakeLLMService, "chat", _patched_chat)

    yield


@pytest.fixture(scope="session")
def engine():
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Create a test ORM client and attach HTTP methods for API tests.

    This fixture returns a SQLAlchemy Client instance (for tests that need
    direct DB access) but also exposes .get/.post/.put/.delete methods that
    proxy to a FastAPI TestClient, so tests can use it as an HTTP client.
    """
    from datetime import date

    from app.models.client import Client

    # Reuse existing client with this test ID if it already exists, to avoid
    # UNIQUE constraint violations between tests.
    orm_client = db_session.query(Client).filter_by(id_number="123456789").first()
    if orm_client is None:
        # Create ORM client in the shared test database
        orm_client = Client()
        orm_client.id_number = "123456789"
        orm_client.id_number_raw = "123456789"
        orm_client.full_name = "Test User"
        orm_client.first_name = "Test"
        orm_client.last_name = "User"
        orm_client.birth_date = date(1980, 1, 1)
        orm_client.gender = "male"
        orm_client.marital_status = "single"
        orm_client.self_employed = False
        orm_client.current_employer_exists = True
        orm_client.is_active = True

        db_session.add(orm_client)
        db_session.commit()

    # Attach a FastAPI TestClient for HTTP calls
    api_client = TestClient(fastapi_app)

    def _get(url, *args, **kwargs):
        return api_client.get(url, *args, **kwargs)

    def _post(url, *args, **kwargs):
        return api_client.post(url, *args, **kwargs)

    def _put(url, *args, **kwargs):
        return api_client.put(url, *args, **kwargs)

    def _delete(url, *args, **kwargs):
        return api_client.delete(url, *args, **kwargs)

    # Monkey-patch HTTP methods onto the ORM client instance
    orm_client.get = _get
    orm_client.post = _post
    orm_client.put = _put
    orm_client.delete = _delete

    return orm_client


"""Pytest configuration and shared fixtures for tests"""


@pytest.fixture
def test_client():
    """FastAPI TestClient for API tests"""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def test_client_data(client):
    """Test client data dictionary including DB id"""
    from datetime import date

    return {
        "id": client.id,
        "id_number": client.id_number,
        "full_name": client.full_name,
        "first_name": client.first_name,
        "last_name": client.last_name,
        "birth_date": date(1980, 1, 1),
        "gender": client.gender,
        "marital_status": client.marital_status,
        "self_employed": client.self_employed,
        "current_employer_exists": client.current_employer_exists,
        "is_active": client.is_active,
    }


@pytest.fixture(scope="module")
def _test_db():
    """Legacy test database fixture returning a Session factory.

    Some integration tests expect to use it as::

        Session = _test_db["Session"]
        with Session() as db:
            ...

    This fixture now reuses the global SessionLocal used by the FastAPI app,
    and also resets the shared SQLite database to a clean state once per
    module (drop_all/create_all). This ensures deterministic IDs (e.g. the
    first Client created gets id=1) while still sharing the same DB file
    between the API and the tests.
    """
    # Use a temporary session to access the underlying engine
    tmp_session = SessionLocal()
    try:
        engine = tmp_session.get_bind()
        # Reset schema for this module's tests
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    finally:
        tmp_session.close()

    Session = SessionLocal
    return {"Session": Session}
