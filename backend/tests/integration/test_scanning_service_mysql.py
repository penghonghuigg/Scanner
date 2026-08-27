import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.catalog import CigaretteProduct
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem
from app.schemas.auth import AuthUser

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def auth_user(model: User) -> AuthUser:
    branch_names = {"FENGTAI": "凤台县局", "PANJI": "潘集分局"}
    return AuthUser(
        id=model.id,
        username=model.username,
        display_name=model.display_name,
        role=model.role,
        branch_code=model.branch_code,
        branch_name=branch_names.get(model.branch_code),
    )


def prepare_database() -> tuple[AuthUser, AuthUser]:
    initialize_database(database_url_for_test())
    engine = create_engine(database_url_for_test())
    now = datetime.now(UTC).replace(tzinfo=None)
    with Session(engine) as session, session.begin():
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(ScanSession))
        session.execute(delete(CigaretteProduct))
        session.execute(delete(User))
        admin = User(
            username="admin",
            password_hash=hash_password("password"),
            display_name="系统管理员",
            role="ADMIN",
            branch_code=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        operator = User(
            username="fengtai",
            password_hash=hash_password("password"),
            display_name="凤台人员",
            role="OPERATOR",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([admin, operator])
        session.flush()
        users = (auth_user(admin), auth_user(operator))
    engine.dispose()
    return users


def add_product(
    session: Session,
    *,
    carton_code: str,
    pack_code: str | None,
    name: str,
    sticks_per_pack: int = 20,
    packs_per_carton: int = 10,
    is_active: bool = True,
) -> CigaretteProduct:
    product = CigaretteProduct(
        carton_code=carton_code,
        pack_code=pack_code,
        brand="测试品牌",
        standard_name=name,
        carton_retail_price=Decimal("100.00"),
        sticks_per_pack=sticks_per_pack,
        packs_per_carton=packs_per_carton,
        is_active=is_active,
    )
    session.add(product)
    session.flush()
    return product


def test_scan_code_requires_exactly_thirteen_digits() -> None:
    from app.scanning.scan_service import BarcodeInvalidError, normalize_scan_code

    assert normalize_scan_code("6900000000101") == "6900000000101"
    for invalid_code in (
        "690000000101",
        "69000000000101",
        "69000000000000101",
        "69000000001A1",
    ):
        with pytest.raises(BarcodeInvalidError):
            normalize_scan_code(invalid_code)


def create_batch(session: Session, user: AuthUser) -> ScanSession:
    from app.scanning.service import create_scan_session

    return create_scan_session(
        session,
        user,
        {
            "business_type": "MARKET_INSPECTION",
            "branch_code": "FENGTAI",
        },
    )


def test_carton_and_pack_scans_merge_into_one_authoritative_item() -> None:
    from app.scanning.scan_service import scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000001",
            pack_code="6900000000002",
            name="测试卷烟一号",
        )
        session.commit()
        batch = create_batch(session, operator)

        first = scan_code(
            session, operator, batch.id, "00000000-0000-4000-8000-000000000001", product.carton_code
        )
        second = scan_code(
            session, operator, batch.id, "00000000-0000-4000-8000-000000000002", product.pack_code
        )
        third = scan_code(
            session, operator, batch.id, "00000000-0000-4000-8000-000000000003", product.carton_code
        )

        item = session.scalar(select(ScanSessionItem))
        assert item is not None
        assert (item.carton_count, item.pack_count, item.total_sticks) == (2, 1, 420)
        assert session.scalar(select(func.count(ScanSessionItem.id))) == 1
        assert session.scalar(select(func.count(ScanEvent.id))) == 3
        assert [first.event.unit_type, second.event.unit_type, third.event.unit_type] == [
            "CARTON",
            "PACK",
            "CARTON",
        ]
        assert first.event.product_snapshot == {
            "product_id": product.id,
            "carton_code": "6900000000001",
            "pack_code": "6900000000002",
            "brand": "测试品牌",
            "standard_name": "测试卷烟一号",
            "carton_retail_price": "100.00",
            "sticks_per_pack": 20,
            "packs_per_carton": 10,
            "sticks_per_carton": 200,
        }
    engine.dispose()


def test_unknown_disabled_and_ambiguous_codes_do_not_change_totals() -> None:
    from app.scanning.scan_service import scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        add_product(
            session,
            carton_code="6900000000011",
            pack_code="6900000000099",
            name="候选一",
        )
        add_product(
            session,
            carton_code="6900000000012",
            pack_code="6900000000099",
            name="候选二",
        )
        add_product(
            session,
            carton_code="6900000000013",
            pack_code="6900000000014",
            name="已停用品规",
            is_active=False,
        )
        session.commit()
        batch = create_batch(session, operator)

        unknown = scan_code(
            session, operator, batch.id, "00000000-0000-4000-8000-000000000011", "6900000000098"
        )
        disabled = scan_code(
            session, operator, batch.id, "00000000-0000-4000-8000-000000000012", "6900000000013"
        )
        ambiguous = scan_code(
            session, operator, batch.id, "00000000-0000-4000-8000-000000000013", "6900000000099"
        )

        assert unknown.event.result == "UNKNOWN"
        assert disabled.event.result == "UNKNOWN"
        assert ambiguous.event.result == "AMBIGUOUS"
        assert ambiguous.event.delta_sticks == 0
        assert {
            candidate["standard_name"] for candidate in ambiguous.event.candidate_snapshot or []
        } == {
            "候选一",
            "候选二",
        }
        assert session.scalar(select(func.count(ScanSessionItem.id))) == 0
    engine.dispose()


def test_scan_request_is_idempotent_and_conflicting_reuse_is_rejected() -> None:
    from app.scanning.scan_service import IdempotencyConflictError, scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    request_id = "00000000-0000-4000-8000-000000000021"
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000021",
            pack_code=None,
            name="幂等品规",
        )
        session.commit()
        batch = create_batch(session, operator)

        first = scan_code(session, operator, batch.id, request_id, product.carton_code)
        replay = scan_code(session, operator, batch.id, request_id, product.carton_code)

        assert replay.event.id == first.event.id
        assert replay.idempotent_replay is True
        assert session.scalar(select(func.count(ScanEvent.id))) == 1
        assert session.scalar(select(ScanSessionItem.total_sticks)) == 200
        with pytest.raises(IdempotencyConflictError):
            scan_code(session, operator, batch.id, request_id, "6900000000022")
    engine.dispose()


def test_ambiguity_resolution_appends_once_and_uses_original_candidate_snapshot() -> None:
    from app.scanning.scan_service import (
        AmbiguityAlreadyResolvedError,
        AmbiguityCandidateInvalidError,
        resolve_ambiguity,
        scan_code,
    )

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        selected = add_product(
            session,
            carton_code="6900000000031",
            pack_code="6900000000039",
            name="歧义候选一",
        )
        add_product(
            session,
            carton_code="6900000000032",
            pack_code="6900000000039",
            name="歧义候选二",
        )
        outsider = add_product(
            session,
            carton_code="6900000000033",
            pack_code=None,
            name="非候选品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        ambiguous = scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000031",
            "6900000000039",
        )

        with pytest.raises(AmbiguityCandidateInvalidError):
            resolve_ambiguity(
                session,
                operator,
                batch.id,
                "00000000-0000-4000-8000-000000000032",
                ambiguous.event.id,
                outsider.id,
            )

        resolved = resolve_ambiguity(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000033",
            ambiguous.event.id,
            selected.id,
        )
        replay = resolve_ambiguity(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000033",
            ambiguous.event.id,
            selected.id,
        )

        assert resolved.event.event_type == "RESOLVE"
        assert resolved.event.result == "SUCCESS"
        assert resolved.event.unit_type == "PACK"
        assert resolved.event.source_event_id == ambiguous.event.id
        assert resolved.event.product_snapshot is not None
        assert resolved.event.product_snapshot["standard_name"] == "歧义候选一"
        assert replay.event.id == resolved.event.id
        assert replay.idempotent_replay is True
        item = session.scalar(select(ScanSessionItem))
        assert item is not None
        assert (item.carton_count, item.pack_count, item.total_sticks) == (0, 1, 20)
        original = session.get(ScanEvent, ambiguous.event.id)
        assert original is not None
        assert original.result == "AMBIGUOUS"

        with pytest.raises(AmbiguityAlreadyResolvedError):
            resolve_ambiguity(
                session,
                operator,
                batch.id,
                "00000000-0000-4000-8000-000000000034",
                ambiguous.event.id,
                selected.id,
            )
    engine.dispose()


def test_concurrent_scans_on_one_batch_do_not_lose_counts() -> None:
    from app.scanning.scan_service import scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test(), pool_size=6)
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000041",
            pack_code=None,
            name="并发品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        batch_id = batch.id
        carton_code = product.carton_code

    worker_count = 4
    barrier = Barrier(worker_count)

    def scan_once(worker: int) -> int:
        with Session(engine) as worker_session:
            barrier.wait()
            result = scan_code(
                worker_session,
                operator,
                batch_id,
                f"00000000-0000-4000-8000-{worker:012d}",
                carton_code,
            )
            return result.event.id

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        event_ids = list(executor.map(scan_once, range(101, 101 + worker_count)))

    with Session(engine) as session:
        item = session.scalar(select(ScanSessionItem))
        assert item is not None
        assert (item.carton_count, item.pack_count, item.total_sticks) == (4, 0, 800)
        assert session.scalar(select(func.count(ScanEvent.id))) == worker_count
        assert len(set(event_ids)) == worker_count
    engine.dispose()


def test_scan_state_returns_authoritative_totals_recent_events_and_pending_items() -> None:
    from app.scanning.scan_service import get_scan_state, resolve_ambiguity, scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        unique = add_product(
            session,
            carton_code="6900000000051",
            pack_code=None,
            name="状态品规",
        )
        selected = add_product(
            session,
            carton_code="6900000000052",
            pack_code="6900000000059",
            name="状态候选一",
        )
        add_product(
            session,
            carton_code="6900000000053",
            pack_code="6900000000059",
            name="状态候选二",
        )
        session.commit()
        batch = create_batch(session, operator)
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000051",
            unique.carton_code,
        )
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000052",
            "6900000000058",
        )
        ambiguity = scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000053",
            "6900000000059",
        )

        pending = get_scan_state(session, operator, batch.id)
        assert pending["summary"] == {
            "product_count": 1,
            "carton_count": 1,
            "pack_count": 0,
            "total_sticks": 200,
            "unknown_count": 1,
            "ambiguous_count": 1,
        }
        assert [event["id"] for event in pending["pending_ambiguities"]] == [ambiguity.event.id]

        resolve_ambiguity(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000054",
            ambiguity.event.id,
            selected.id,
        )
        state = get_scan_state(session, operator, batch.id)

        assert state["summary"] == {
            "product_count": 2,
            "carton_count": 1,
            "pack_count": 1,
            "total_sticks": 220,
            "unknown_count": 1,
            "ambiguous_count": 0,
        }
        assert len(state["items"]) == 2
        assert len(state["recent_events"]) == 4
        assert state["recent_events"][0]["event_type"] == "RESOLVE"
        assert state["recent_events"][0]["operator_name"] == "凤台人员"
        assert state["pending_ambiguities"] == []
    engine.dispose()
