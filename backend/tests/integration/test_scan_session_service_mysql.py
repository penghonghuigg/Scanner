import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
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


def auth_user(user_id: int, role: str, branch_code: str | None) -> AuthUser:
    branch_names = {"FENGTAI": "凤台县局", "PANJI": "潘集分局"}
    return AuthUser(
        id=user_id,
        username=f"user-{user_id}",
        display_name=f"人员{user_id}",
        role=role,
        branch_code=branch_code,
        branch_name=branch_names.get(branch_code),
    )


def prepare_users() -> dict[str, AuthUser]:
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
        session.execute(delete(User))
        models = [
            User(
                username="admin",
                password_hash=hash_password("password"),
                display_name="管理员",
                role="ADMIN",
                branch_code=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            User(
                username="fengtai",
                password_hash=hash_password("password"),
                display_name="凤台人员",
                role="OPERATOR",
                branch_code="FENGTAI",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            User(
                username="panji",
                password_hash=hash_password("password"),
                display_name="潘集人员",
                role="OPERATOR",
                branch_code="PANJI",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            User(
                username="viewer",
                password_hash=hash_password("password"),
                display_name="凤台查看员",
                role="VIEWER",
                branch_code="FENGTAI",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        ]
        session.add_all(models)
        session.flush()
        result = {
            "admin": auth_user(models[0].id, "ADMIN", None),
            "fengtai": auth_user(models[1].id, "OPERATOR", "FENGTAI"),
            "panji": auth_user(models[2].id, "OPERATOR", "PANJI"),
            "viewer": auth_user(models[3].id, "VIEWER", "FENGTAI"),
        }
    engine.dispose()
    return result


def payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "business_type": "MARKET_INSPECTION",
        "filing_case_no": "  ",
        "location": " 凤台县城区 ",
        "notes": " ",
        "branch_code": "PANJI",
    }
    values.update(overrides)
    return values


def test_operator_is_forced_to_own_branch_and_optional_text_is_cleaned() -> None:
    from app.scanning import service

    users = prepare_users()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        created = service.create_scan_session(
            session,
            users["fengtai"],
            payload(),
            now=datetime(2026, 8, 27, 8, 30),
            suffix_factory=lambda: 4821,
        )

        assert created.status == "DRAFT"
        assert created.branch_code == "FENGTAI"
        assert created.filing_case_no is None
        assert created.location == "凤台县城区"
        assert created.notes is None
        assert service.list_scan_sessions(session, users["fengtai"], {}, 1, 20).total == 1
        assert service.list_scan_sessions(session, users["panji"], {}, 1, 20).total == 0
    engine.dispose()


def test_admin_must_choose_valid_branch_and_viewer_cannot_create() -> None:
    from app.scanning import service

    users = prepare_users()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        with pytest.raises(service.BranchRequiredError):
            service.create_scan_session(session, users["admin"], payload(branch_code=None))
        with pytest.raises(service.BranchInvalidError):
            service.create_scan_session(session, users["admin"], payload(branch_code="UNKNOWN"))
        with pytest.raises(service.ScanSessionForbiddenError):
            service.create_scan_session(session, users["viewer"], payload())
    engine.dispose()


def test_cross_branch_detail_is_hidden_but_admin_can_read_it() -> None:
    from app.scanning import service

    users = prepare_users()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        created = service.create_scan_session(session, users["fengtai"], payload())
        assert service.get_scan_session(session, users["admin"], created.id).id == created.id
        with pytest.raises(service.ScanSessionNotFoundError):
            service.get_scan_session(session, users["panji"], created.id)
    engine.dispose()


def test_branch_users_cannot_see_admin_created_sessions_in_their_branch() -> None:
    from app.scanning import service

    users = prepare_users()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        admin_created = service.create_scan_session(
            session,
            users["admin"],
            payload(branch_code="FENGTAI"),
        )
        operator_created = service.create_scan_session(
            session,
            users["fengtai"],
            payload(),
        )

        admin_result = service.list_scan_sessions(session, users["admin"], {}, 1, 20)
        operator_result = service.list_scan_sessions(session, users["fengtai"], {}, 1, 20)
        viewer_result = service.list_scan_sessions(session, users["viewer"], {}, 1, 20)

        assert admin_result.total == 2
        assert {item.id for item in admin_result.items} == {
            admin_created.id,
            operator_created.id,
        }
        assert operator_result.total == 1
        assert [item.id for item in operator_result.items] == [operator_created.id]
        assert viewer_result.total == 1
        assert [item.id for item in viewer_result.items] == [operator_created.id]
        with pytest.raises(service.ScanSessionNotFoundError):
            service.get_scan_session(session, users["fengtai"], admin_created.id)
        with pytest.raises(service.ScanSessionNotFoundError):
            service.get_scan_session(session, users["viewer"], admin_created.id)
    engine.dispose()


def test_session_number_collision_is_retried() -> None:
    from app.scanning import service

    users = prepare_users()
    engine = create_engine(database_url_for_test())
    suffixes = iter((4821, 4822))
    with Session(engine) as session:
        first = service.create_scan_session(
            session,
            users["fengtai"],
            payload(),
            now=datetime(2026, 8, 27, 8, 30, 45),
            suffix_factory=lambda: 4821,
        )
        second = service.create_scan_session(
            session,
            users["fengtai"],
            payload(),
            now=datetime(2026, 8, 27, 8, 30, 45),
            suffix_factory=lambda: next(suffixes),
        )

        assert first.session_no == "PD20260827-163045-4821"
        assert second.session_no == "PD20260827-163045-4822"
    engine.dispose()


def test_three_session_number_collisions_fail_cleanly() -> None:
    from app.scanning import service

    users = prepare_users()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        service.create_scan_session(
            session,
            users["fengtai"],
            payload(),
            now=datetime(2026, 8, 27, 8, 30, 45),
            suffix_factory=lambda: 4821,
        )
        with pytest.raises(service.ScanSessionCreateFailedError):
            service.create_scan_session(
                session,
                users["fengtai"],
                payload(),
                now=datetime(2026, 8, 27, 8, 30, 45),
                suffix_factory=lambda: 4821,
            )
    engine.dispose()
