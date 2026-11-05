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
from app.models.finalization import ExportRecord, ScanItemSourceAllocation
from app.models.integration import IntegrationSnapshot
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
        session.execute(delete(ExportRecord))
        session.execute(delete(ScanItemSourceAllocation))
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(IntegrationSnapshot))
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


def test_scan_code_accepts_six_to_sixty_four_digits() -> None:
    from app.scanning.scan_service import BarcodeInvalidError, normalize_scan_code

    assert normalize_scan_code("690001") == "690001"
    assert normalize_scan_code("6900000000101") == "6900000000101"
    assert normalize_scan_code("1" * 64) == "1" * 64
    for invalid_code in (
        "69000",
        "1" * 65,
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


def test_scan_state_returns_catalog_summary_and_latest_success() -> None:
    from app.scanning.scan_service import get_scan_state, scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        first = add_product(
            session,
            carton_code="6900000000061",
            pack_code="6900000000069",
            name="同名品规",
        )
        add_product(
            session,
            carton_code="6900000000062",
            pack_code="6900000000069",
            name="同名品规",
        )
        add_product(
            session,
            carton_code="6900000000063",
            pack_code=None,
            name="其他品规",
        )
        add_product(
            session,
            carton_code="6900000000064",
            pack_code="6900000000065",
            name="停用品规",
            is_active=False,
        )
        session.commit()
        batch = create_batch(session, operator)
        successful = scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000061",
            first.carton_code,
        )
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000062",
            "6999999999998",
        )
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000063",
            "6900000000069",
        )

        state = get_scan_state(session, operator, batch.id)

        assert state["catalog_summary"] == {
            "active_code_count": 4,
            "active_standard_product_count": 2,
        }
        assert state["latest_successful_event"]["id"] == successful.event.id
        assert state["latest_successful_event"]["raw_code"] == first.carton_code
        assert state["latest_successful_event"]["reason"] is None
    engine.dispose()


def test_adjust_carton_quantity_updates_manual_sticks_and_is_idempotent() -> None:
    from app.scanning.scan_service import (
        IdempotencyConflictError,
        NegativeQuantityError,
        QuantityAdjustmentInvalidError,
        ScanSessionItemNotFoundError,
        adjust_carton_quantity,
        scan_code,
    )

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000071",
            pack_code="6900000000072",
            name="人工调整品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        for request_id, code in (
            ("00000000-0000-4000-8000-000000000071", product.carton_code),
            ("00000000-0000-4000-8000-000000000072", product.carton_code),
            ("00000000-0000-4000-8000-000000000073", product.pack_code),
        ):
            scan_code(session, operator, batch.id, request_id, code)
        item = session.scalar(select(ScanSessionItem))
        assert item is not None

        increased = adjust_carton_quantity(
            session,
            operator,
            batch.id,
            product.id,
            "00000000-0000-4000-8000-000000000074",
            "DELTA",
            Decimal("0.1"),
        )
        session.refresh(item)
        assert (item.carton_count, item.pack_count) == (2, 1)
        assert (item.manual_delta_sticks, item.total_sticks) == (20, 440)
        assert increased.event.delta_sticks == 20
        assert increased.event.reason == (
            "人工调整条数：增加 0.1 条（1 包）；原因：现场核对修正"
        )

        set_result = adjust_carton_quantity(
            session,
            operator,
            batch.id,
            product.id,
            "00000000-0000-4000-8000-000000000075",
            "SET",
            Decimal("1.5"),
        )
        replay = adjust_carton_quantity(
            session,
            operator,
            batch.id,
            product.id,
            "00000000-0000-4000-8000-000000000075",
            "SET",
            Decimal("1.5"),
        )
        session.refresh(item)
        assert item.pack_count == 1
        assert (item.manual_delta_sticks, item.total_sticks) == (-120, 300)
        assert set_result.event.reason == (
            "人工调整条数：设为 1.5 条；原因：现场核对修正"
        )
        assert replay.event.id == set_result.event.id
        assert replay.idempotent_replay is True

        with pytest.raises(IdempotencyConflictError):
            adjust_carton_quantity(
                session,
                operator,
                batch.id,
                product.id,
                "00000000-0000-4000-8000-000000000075",
                "DELTA",
                Decimal("-0.1"),
            )
        with pytest.raises(QuantityAdjustmentInvalidError):
            adjust_carton_quantity(
                session,
                operator,
                batch.id,
                product.id,
                "00000000-0000-4000-8000-000000000076",
                "DELTA",
                0,
            )
        with pytest.raises(QuantityAdjustmentInvalidError):
            adjust_carton_quantity(
                session,
                operator,
                batch.id,
                product.id,
                "00000000-0000-4000-8000-000000000176",
                "SET",
                Decimal("0.15"),
            )
        adjust_carton_quantity(
            session,
            operator,
            batch.id,
            product.id,
            "00000000-0000-4000-8000-000000000077",
            "SET",
            0,
        )
        with pytest.raises(NegativeQuantityError):
            adjust_carton_quantity(
                session,
                operator,
                batch.id,
                product.id,
                "00000000-0000-4000-8000-000000000078",
                "DELTA",
                Decimal("-0.1"),
            )
        with pytest.raises(ScanSessionItemNotFoundError):
            adjust_carton_quantity(
                session,
                operator,
                batch.id,
                product.id + 999,
                "00000000-0000-4000-8000-000000000079",
                "SET",
                0,
            )
    engine.dispose()


def test_adjustment_records_other_reason_and_sets_the_final_pack_aligned_total() -> None:
    from app.scanning.scan_service import adjust_carton_quantity, scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000171",
            pack_code="6900000000172",
            name="带原因调整品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000171",
            product.carton_code,
        )
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000172",
            product.pack_code,
        )

        result = adjust_carton_quantity(
            session,
            operator,
            batch.id,
            product.id,
            "00000000-0000-4000-8000-000000000173",
            "SET",
            Decimal("1.5"),
            reason_type="OTHER",
            reason_note="包装破损复核",
        )
        item = session.scalar(select(ScanSessionItem))
        assert item is not None
        assert item.total_sticks == 300
        assert item.manual_delta_sticks == 80
        assert result.event.reason == (
            "人工调整条数：设为 1.5 条；原因：其他：包装破损复核"
        )
    engine.dispose()


def test_concurrent_carton_deltas_do_not_lose_counts() -> None:
    from app.scanning.scan_service import adjust_carton_quantity, scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test(), pool_size=6)
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000081",
            pack_code=None,
            name="并发调整品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000081",
            product.carton_code,
        )
        batch_id = batch.id
        product_id = product.id

    worker_count = 4
    barrier = Barrier(worker_count)

    def adjust_once(worker: int) -> int:
        with Session(engine) as worker_session:
            barrier.wait()
            result = adjust_carton_quantity(
                worker_session,
                operator,
                batch_id,
                product_id,
                f"00000000-0000-4000-8000-{worker:012d}",
                "DELTA",
                Decimal("0.1"),
            )
            return result.event.id

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        event_ids = list(executor.map(adjust_once, range(401, 401 + worker_count)))

    with Session(engine) as session:
        item = session.scalar(select(ScanSessionItem))
        assert item is not None
        assert (item.carton_count, item.manual_delta_sticks, item.total_sticks) == (
            1,
            80,
            280,
        )
        assert session.scalar(select(func.count(ScanEvent.id))) == 5
        assert len(set(event_ids)) == worker_count
    engine.dispose()


def test_scan_event_page_returns_ten_rows_in_descending_order() -> None:
    from app.scanning.scan_service import (
        adjust_carton_quantity,
        list_scan_events,
        scan_code,
    )

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000091",
            pack_code=None,
            name="流水分页品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        for index in range(21):
            scan_code(
                session,
                operator,
                batch.id,
                f"00000000-0000-4000-8000-{500 + index:012d}",
                f"6999999{index:06d}",
            )
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000521",
            product.carton_code,
        )
        adjust_carton_quantity(
            session,
            operator,
            batch.id,
            product.id,
            "00000000-0000-4000-8000-000000000522",
            "DELTA",
            Decimal("0.1"),
        )

        page_one = list_scan_events(session, operator, batch.id, page=1, page_size=10)
        page_three = list_scan_events(session, operator, batch.id, page=3, page_size=10)

        assert (page_one.total, len(page_one.items)) == (23, 10)
        assert len(page_three.items) == 3
        assert page_one.items[0]["event_type"] == "ADJUST"
        assert page_one.items[0]["reason"] == (
            "人工调整条数：增加 0.1 条（1 包）；原因：现场核对修正"
        )
        assert page_one.items[0]["created_at"] >= page_one.items[-1]["created_at"]
    engine.dispose()


def test_remove_session_item_preserves_audit_replays_and_allows_rescan() -> None:
    from app.scanning.scan_service import (
        IdempotencyConflictError,
        ScanSessionItemNotFoundError,
        remove_session_item,
        scan_code,
    )

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000111",
            pack_code="6900000000112",
            name="删除后重扫品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000811",
            product.carton_code,
        )
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000812",
            product.pack_code,
        )

        request_id = "00000000-0000-4000-8000-000000000813"
        removed = remove_session_item(
            session,
            operator,
            batch.id,
            product.id,
            request_id,
        )

        assert session.scalar(select(ScanSessionItem)) is None
        assert removed.idempotent_replay is False
        assert removed.event.event_type == "ADJUST"
        assert removed.event.result == "SUCCESS"
        assert removed.event.unit_type == "STICK"
        assert removed.event.delta_sticks == -220
        assert removed.event.reason == "删除品规统计：数量归零并隐藏"
        assert removed.event.product_snapshot["standard_name"] == "删除后重扫品规"
        assert session.scalar(select(func.count(ScanEvent.id))) == 3

        replay = remove_session_item(
            session,
            operator,
            batch.id,
            product.id,
            request_id,
        )
        assert replay.idempotent_replay is True
        assert replay.event.id == removed.event.id
        assert session.scalar(select(func.count(ScanEvent.id))) == 3

        with pytest.raises(ScanSessionItemNotFoundError):
            remove_session_item(
                session,
                operator,
                batch.id,
                product.id,
                "00000000-0000-4000-8000-000000000814",
            )
        with pytest.raises(IdempotencyConflictError):
            remove_session_item(
                session,
                operator,
                batch.id,
                product.id + 1,
                request_id,
            )

        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000815",
            product.carton_code,
        )
        recreated = session.scalar(select(ScanSessionItem))
        assert recreated is not None
        assert (recreated.carton_count, recreated.pack_count, recreated.total_sticks) == (
            1,
            0,
            200,
        )
    engine.dispose()


def test_concurrent_remove_with_same_request_only_appends_one_event() -> None:
    from app.scanning.scan_service import remove_session_item, scan_code

    _, operator = prepare_database()
    engine = create_engine(database_url_for_test(), pool_size=4)
    with Session(engine) as session:
        product = add_product(
            session,
            carton_code="6900000000121",
            pack_code=None,
            name="并发删除品规",
        )
        session.commit()
        batch = create_batch(session, operator)
        scan_code(
            session,
            operator,
            batch.id,
            "00000000-0000-4000-8000-000000000821",
            product.carton_code,
        )
        batch_id = batch.id
        product_id = product.id

    barrier = Barrier(2)
    request_id = "00000000-0000-4000-8000-000000000822"

    def remove_once() -> tuple[int, bool]:
        with Session(engine) as worker_session:
            barrier.wait()
            result = remove_session_item(
                worker_session,
                operator,
                batch_id,
                product_id,
                request_id,
            )
            return result.event.id, result.idempotent_replay

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: remove_once(), range(2)))

    with Session(engine) as session:
        assert session.scalar(select(ScanSessionItem)) is None
        assert session.scalar(select(func.count(ScanEvent.id))) == 2
        assert len({event_id for event_id, _ in results}) == 1
        assert sorted(replayed for _, replayed in results) == [False, True]
    engine.dispose()
