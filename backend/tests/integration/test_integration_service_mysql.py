import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Lock

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.integrations.jiandaoyun import (
    ExternalRejectedError,
    ExternalUncertainError,
    JianDaoYunConfig,
    JianDaoYunCreateResult,
)
from app.models.auth import User, UserSession
from app.models.catalog import CigaretteProduct
from app.models.finalization import ExportRecord, ScanItemSourceAllocation
from app.models.integration import IntegrationSnapshot
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem
from app.schemas.auth import AuthUser

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 9, 4, 4, 0, 0)
CONFIG = JianDaoYunConfig(
    create_url="https://example.test/create",
    app_id="test-app",
    entry_id="test-entry",
    api_key="test-key",
)


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def auth_user(model: User) -> AuthUser:
    return AuthUser(
        id=model.id,
        username=model.username,
        display_name=model.display_name,
        role=model.role,
        branch_code=model.branch_code,
        branch_name="凤台县局" if model.branch_code == "FENGTAI" else None,
    )


def prepare_completed_session() -> tuple[int, int, AuthUser, AuthUser, AuthUser]:
    engine = create_engine(database_url_for_test())
    with Session(engine) as session, session.begin():
        session.execute(delete(IntegrationSnapshot))
        session.execute(delete(ExportRecord))
        session.execute(delete(ScanItemSourceAllocation))
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(ScanSession))
        session.execute(delete(CigaretteProduct))
        session.execute(delete(User))
        admin = User(
            username="integration-admin",
            password_hash=hash_password("password"),
            display_name="系统管理员",
            role="ADMIN",
            branch_code=None,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        operator = User(
            username="integration-operator",
            password_hash=hash_password("password"),
            display_name="张三",
            role="OPERATOR",
            branch_code="FENGTAI",
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        other = User(
            username="integration-other",
            password_hash=hash_password("password"),
            display_name="李四",
            role="OPERATOR",
            branch_code="PANJI",
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        product = CigaretteProduct(
            carton_code="6900000080001",
            pack_code=None,
            brand="测试品牌",
            standard_name="测试卷烟",
            carton_retail_price=100,
            sticks_per_pack=20,
            packs_per_carton=10,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add_all([admin, operator, other, product])
        session.flush()
        batch = ScanSession(
            session_no="PD20260904-120000-8001",
            business_type="MARKET_INSPECTION",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="FENGTAI",
            operator_id=operator.id,
            status="COMPLETED",
            completed_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(batch)
        session.flush()
        item = ScanSessionItem(
            session_id=batch.id,
            product_id=product.id,
            carton_count=1,
            pack_count=0,
            manual_delta_sticks=0,
            total_sticks=200,
            product_snapshot={
                "product_id": product.id,
                "carton_code": product.carton_code,
                "pack_code": None,
                "brand": product.brand,
                "standard_name": product.standard_name,
                "carton_retail_price": "100.00",
                "sticks_per_pack": 20,
                "packs_per_carton": 10,
                "sticks_per_carton": 200,
            },
            updated_at=NOW,
        )
        session.add(item)
        session.flush()
        result = (
            batch.id,
            item.id,
            auth_user(operator),
            auth_user(admin),
            auth_user(other),
        )
    engine.dispose()
    return result


def test_first_import_succeeds_and_success_is_idempotent_and_immutable() -> None:
    from app.integrations.service import import_completed_session

    batch_id, item_id, operator, _, _ = prepare_completed_session()
    calls: list[dict[str, object]] = []

    def sender(_config, data):
        calls.append(data)
        return JianDaoYunCreateResult(data_id="external-id-1", created_at=None)

    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        first = import_completed_session(
            session,
            operator,
            batch_id,
            config=CONFIG,
            sender=sender,
            now=NOW,
        )
        item = session.get(ScanSessionItem, item_id)
        assert item is not None
        item.total_sticks = 400
        session.commit()
        repeated = import_completed_session(
            session,
            operator,
            batch_id,
            config=CONFIG,
            sender=sender,
            now=NOW + timedelta(minutes=1),
        )

        assert first.status == repeated.status == "SUCCEEDED"
        assert repeated.external_data_id == "external-id-1"
        assert repeated.attempt_count == 1
        assert len(calls) == 1
        assert first.payload_json == repeated.payload_json
        rows = first.payload_json["_widget_1788244617471"]["value"]
        assert rows[0]["_widget_1788247452468"]["value"] == 1
    engine.dispose()


def test_rejected_retry_reuses_original_snapshot() -> None:
    from app.integrations.service import import_completed_session

    batch_id, item_id, operator, _, _ = prepare_completed_session()
    attempts = 0

    def sender(_config, _data):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ExternalRejectedError("简道云明确拒绝请求：HTTP 422")
        return JianDaoYunCreateResult(data_id="external-id-2", created_at=None)

    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        with pytest.raises(ExternalRejectedError):
            import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW,
            )
        failed = session.scalar(select(IntegrationSnapshot))
        assert failed is not None
        original_hash = failed.payload_sha256
        item = session.get(ScanSessionItem, item_id)
        assert item is not None
        item.total_sticks = 400
        session.commit()

        succeeded = import_completed_session(
            session,
            operator,
            batch_id,
            config=CONFIG,
            sender=sender,
            now=NOW + timedelta(minutes=1),
        )
        assert succeeded.status == "SUCCEEDED"
        assert succeeded.attempt_count == 2
        assert succeeded.payload_sha256 == original_hash
        rows = succeeded.payload_json["_widget_1788244617471"]["value"]
        assert rows[0]["_widget_1788247452468"]["value"] == 1
    engine.dispose()


def test_uncertain_result_cannot_be_sent_again() -> None:
    from app.integrations.service import IntegrationUncertainError, import_completed_session

    batch_id, _, operator, _, _ = prepare_completed_session()
    attempts = 0

    def sender(_config, _data):
        nonlocal attempts
        attempts += 1
        raise ExternalUncertainError("访问简道云失败：ReadTimeout")

    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        with pytest.raises(ExternalUncertainError):
            import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW,
            )
        with pytest.raises(IntegrationUncertainError):
            import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW + timedelta(minutes=1),
            )
        assert attempts == 1
        snapshot = session.scalar(select(IntegrationSnapshot))
        assert snapshot is not None
        assert snapshot.status == "UNCERTAIN"
    engine.dispose()


def test_permissions_and_completed_state_are_enforced_before_sender() -> None:
    from app.integrations.service import import_completed_session
    from app.scanning.export_service import ExportSessionNotCompletedError
    from app.scanning.service import ScanSessionNotFoundError

    batch_id, _, operator, admin, other = prepare_completed_session()
    calls = 0

    def sender(_config, _data):
        nonlocal calls
        calls += 1
        return JianDaoYunCreateResult(data_id="external-id", created_at=None)

    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        with pytest.raises(ScanSessionNotFoundError):
            import_completed_session(
                session,
                other,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW,
            )
        batch = session.get(ScanSession, batch_id)
        assert batch is not None
        batch.status = "DRAFT"
        session.commit()
        with pytest.raises(ExportSessionNotCompletedError):
            import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW,
            )
        batch.status = "COMPLETED"
        session.commit()
        result = import_completed_session(
            session,
            admin,
            batch_id,
            config=CONFIG,
            sender=sender,
            now=NOW,
        )
        assert result.status == "SUCCEEDED"
        assert calls == 1
    engine.dispose()


def test_stale_pending_becomes_uncertain_without_sending() -> None:
    from app.integrations.service import IntegrationUncertainError, import_completed_session

    batch_id, _, operator, _, _ = prepare_completed_session()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session, session.begin():
        session.add(
            IntegrationSnapshot(
                session_id=batch_id,
                payload_json={"frozen": {"value": True}},
                payload_sha256="0" * 64,
                status="PENDING",
                external_data_id=None,
                attempt_count=1,
                last_error_code=None,
                last_error_message=None,
                created_by=operator.id,
                last_attempted_by=operator.id,
                created_at=NOW,
                updated_at=NOW,
                succeeded_at=None,
            )
        )

    calls = 0

    def sender(_config, _data):
        nonlocal calls
        calls += 1
        return JianDaoYunCreateResult(data_id="must-not-send", created_at=None)

    with Session(engine) as session:
        with pytest.raises(IntegrationUncertainError):
            import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW + timedelta(seconds=121),
            )
        snapshot = session.scalar(select(IntegrationSnapshot))
        assert snapshot is not None
        assert snapshot.status == "UNCERTAIN"
        assert snapshot.last_error_code == "PENDING_EXPIRED"
        assert calls == 0
    engine.dispose()


def test_concurrent_import_only_calls_sender_once() -> None:
    from app.integrations.service import IntegrationInProgressError, import_completed_session

    batch_id, _, operator, _, _ = prepare_completed_session()
    engine = create_engine(database_url_for_test())
    sender_entered = Event()
    release_sender = Event()
    count_lock = Lock()
    calls = 0

    def sender(_config, _data):
        nonlocal calls
        with count_lock:
            calls += 1
        sender_entered.set()
        assert release_sender.wait(timeout=10)
        return JianDaoYunCreateResult(data_id="external-concurrent", created_at=None)

    def first_import() -> str:
        with Session(engine) as session:
            return import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW,
            ).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(first_import)
        assert sender_entered.wait(timeout=10)
        with Session(engine) as session, pytest.raises(IntegrationInProgressError):
            import_completed_session(
                session,
                operator,
                batch_id,
                config=CONFIG,
                sender=sender,
                now=NOW + timedelta(seconds=1),
            )
        release_sender.set()
        assert first.result(timeout=10) == "SUCCEEDED"

    with Session(engine) as session:
        rows = list(session.scalars(select(IntegrationSnapshot)))
        assert len(rows) == 1
        assert rows[0].status == "SUCCEEDED"
        assert calls == 1
    engine.dispose()
