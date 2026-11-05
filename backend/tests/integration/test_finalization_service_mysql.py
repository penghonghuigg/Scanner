import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

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


def current_user(model: User) -> AuthUser:
    return AuthUser(
        id=model.id,
        username=model.username,
        display_name=model.display_name,
        role=model.role,
        branch_code=model.branch_code,
        branch_name="凤台县局" if model.branch_code == "FENGTAI" else None,
    )


def prepare_source_item() -> tuple[int, int, AuthUser, AuthUser]:
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
        operator = User(
            username="source-operator",
            password_hash=hash_password("password"),
            display_name="来源操作员",
            role="OPERATOR",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        viewer = User(
            username="source-viewer",
            password_hash=hash_password("password"),
            display_name="来源查看员",
            role="VIEWER",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        product = CigaretteProduct(
            carton_code="6900000060701",
            pack_code="6900000060702",
            brand="测试品牌",
            standard_name="来源测试卷烟",
            carton_retail_price=100,
            sticks_per_pack=20,
            packs_per_carton=10,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([operator, viewer, product])
        session.flush()
        batch = ScanSession(
            session_no="PD20260902-150000-6070",
            business_type="MARKET_INSPECTION",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="FENGTAI",
            operator_id=operator.id,
            status="DRAFT",
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(batch)
        session.flush()
        item = ScanSessionItem(
            session_id=batch.id,
            product_id=product.id,
            carton_count=1,
            pack_count=8,
            manual_delta_sticks=0,
            total_sticks=360,
            product_snapshot={
                "product_id": product.id,
                "carton_code": product.carton_code,
                "pack_code": product.pack_code,
                "brand": product.brand,
                "standard_name": product.standard_name,
                "carton_retail_price": "100.00",
                "sticks_per_pack": 20,
                "packs_per_carton": 10,
                "sticks_per_carton": 200,
            },
            updated_at=now,
        )
        session.add(item)
        session.flush()
        result = (batch.id, product.id, current_user(operator), current_user(viewer))
    engine.dispose()
    return result


def test_replace_source_allocations_merges_and_persists_authoritative_rows() -> None:
    from app.scanning.source_service import list_source_allocations, replace_source_allocations

    batch_id, product_id, operator, _ = prepare_source_item()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        state = replace_source_allocations(
            session,
            operator,
            batch_id,
            product_id,
            [
                {
                    "source_type": "OUTSIDE_PROVINCE",
                    "province_name": "天津市",
                    "city_name": "天津市",
                    "pack_count": 10,
                },
                {
                    "source_type": "OUTSIDE_PROVINCE",
                    "province_name": "天津市",
                    "city_name": "天津市",
                    "pack_count": 5,
                },
                {
                    "source_type": "UNKNOWN",
                    "province_name": None,
                    "city_name": None,
                    "pack_count": 3,
                },
            ],
        )
        assert state["required_pack_count"] == 18
        assert state["allocated_pack_count"] == 18
        assert state["remaining_pack_count"] == 0
        assert [row["pack_count"] for row in state["allocations"]] == [15, 3]
        assert session.scalar(select(func.count(ScanItemSourceAllocation.id))) == 2

    with Session(engine) as restarted_session:
        states = list_source_allocations(restarted_session, operator, batch_id)
        assert len(states) == 1
        assert states[0]["allocations"][0]["province_name"] == "天津市"
        assert states[0]["allocations"][1]["source_type"] == "UNKNOWN"
    engine.dispose()


def test_replace_source_allocations_rejects_mismatch_without_overwriting_existing() -> None:
    from app.scanning.source_service import (
        SourceQuantityMismatchError,
        replace_source_allocations,
    )

    batch_id, product_id, operator, _ = prepare_source_item()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        replace_source_allocations(
            session,
            operator,
            batch_id,
            product_id,
            [{"source_type": "UNKNOWN", "pack_count": 18}],
        )
        with pytest.raises(SourceQuantityMismatchError):
            replace_source_allocations(
                session,
                operator,
                batch_id,
                product_id,
                [{"source_type": "UNKNOWN", "pack_count": 17}],
            )
        assert session.scalar(select(ScanItemSourceAllocation.pack_count)) == 18
    engine.dispose()


def test_viewer_cannot_replace_sources_but_operator_can_correct_completed_result() -> None:
    from app.scanning.service import ScanSessionForbiddenError
    from app.scanning.source_service import replace_source_allocations

    batch_id, product_id, operator, viewer = prepare_source_item()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        with pytest.raises(ScanSessionForbiddenError):
            replace_source_allocations(
                session,
                viewer,
                batch_id,
                product_id,
                [{"source_type": "UNKNOWN", "pack_count": 18}],
            )
        batch = session.get(ScanSession, batch_id)
        assert batch is not None
        batch.status = "COMPLETED"
        session.commit()
        state = replace_source_allocations(
            session,
            operator,
            batch_id,
            product_id,
            [{"source_type": "UNKNOWN", "pack_count": 18}],
        )
        assert state["allocated_pack_count"] == 18
    engine.dispose()


def test_concurrent_completed_result_additions_do_not_lose_quantity() -> None:
    from app.scanning.result_service import add_result_item
    from app.scanning.source_service import replace_source_allocations

    batch_id, product_id, operator, _ = prepare_source_item()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        replace_source_allocations(
            session,
            operator,
            batch_id,
            product_id,
            [{"source_type": "UNKNOWN", "pack_count": 18}],
        )
        batch = session.get(ScanSession, batch_id)
        assert batch is not None
        batch.status = "COMPLETED"
        batch.completed_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()

    def add_one_pack(request_id: str) -> None:
        with Session(engine) as worker_session:
            add_result_item(
                worker_session,
                operator,
                batch_id,
                request_id=request_id,
                product_id=product_id,
                quantity_cartons=Decimal("0.1"),
                allocations=[{"source_type": "UNKNOWN", "pack_count": 1}],
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                add_one_pack,
                f"00000000-0000-4000-8000-00000000630{index}",
            )
            for index in (1, 2)
        ]
        for future in futures:
            future.result(timeout=10)

    with Session(engine) as restarted_session:
        item = restarted_session.scalar(
            select(ScanSessionItem).where(
                ScanSessionItem.session_id == batch_id,
                ScanSessionItem.product_id == product_id,
            )
        )
        assert item is not None
        assert item.total_sticks == 400
        assert restarted_session.scalar(
            select(func.sum(ScanItemSourceAllocation.pack_count)).where(
                ScanItemSourceAllocation.session_item_id == item.id
            )
        ) == 20
    engine.dispose()


def add_unresolved_exceptions(
    session: Session,
    *,
    batch_id: int,
    operator_id: int,
    product_id: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add_all(
        [
            ScanEvent(
                request_id="00000000-0000-4000-8000-000000006101",
                session_id=batch_id,
                event_type="SCAN",
                result="UNKNOWN",
                raw_code="6999999999991",
                product_id=None,
                unit_type=None,
                delta_sticks=0,
                source_event_id=None,
                reason=None,
                candidate_snapshot=None,
                product_snapshot=None,
                operator_id=operator_id,
                created_at=now,
            ),
            ScanEvent(
                request_id="00000000-0000-4000-8000-000000006102",
                session_id=batch_id,
                event_type="SCAN",
                result="AMBIGUOUS",
                raw_code="6999999999992",
                product_id=None,
                unit_type="PACK",
                delta_sticks=0,
                source_event_id=None,
                reason=None,
                candidate_snapshot=[{"product_id": product_id}],
                product_snapshot=None,
                operator_id=operator_id,
                created_at=now,
            ),
        ]
    )
    session.commit()


def test_complete_requires_a_full_source_allocation() -> None:
    from app.scanning.completion_service import (
        SourceAllocationRequiredError,
        complete_scan_session,
    )

    batch_id, _, operator, _ = prepare_source_item()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        with pytest.raises(SourceAllocationRequiredError):
            complete_scan_session(
                session,
                operator,
                batch_id,
                confirm_exceptions=False,
            )
        batch = session.get(ScanSession, batch_id)
        assert batch is not None
        assert batch.status == "DRAFT"
        assert batch.completed_at is None
    engine.dispose()


def test_complete_allows_confirmed_unknown_and_unresolved_ambiguity_and_is_repeatable() -> None:
    from app.scanning.completion_service import (
        ExceptionConfirmationRequiredError,
        complete_scan_session,
    )
    from app.scanning.source_service import replace_source_allocations

    batch_id, product_id, operator, _ = prepare_source_item()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        replace_source_allocations(
            session,
            operator,
            batch_id,
            product_id,
            [
                {
                    "source_type": "OUTSIDE_PROVINCE",
                    "province_name": "天津市",
                    "city_name": "天津市",
                    "pack_count": 15,
                },
                {"source_type": "UNKNOWN", "pack_count": 3},
            ],
        )
        add_unresolved_exceptions(
            session,
            batch_id=batch_id,
            operator_id=operator.id,
            product_id=product_id,
        )
        with pytest.raises(ExceptionConfirmationRequiredError):
            complete_scan_session(
                session,
                operator,
                batch_id,
                confirm_exceptions=False,
            )

        completed = complete_scan_session(
            session,
            operator,
            batch_id,
            confirm_exceptions=True,
        )
        repeated = complete_scan_session(
            session,
            operator,
            batch_id,
            confirm_exceptions=True,
        )

        assert completed.scan_session.status == "COMPLETED"
        assert completed.scan_session.completed_at is not None
        assert completed.unknown_count == 1
        assert completed.unresolved_ambiguity_count == 1
        assert completed.source_product_count == 1
        assert completed.source_allocated_product_count == 1
        assert repeated.scan_session.completed_at == completed.scan_session.completed_at
    engine.dispose()
