from app.core.config import Settings
from app.main import create_app


def test_openapi_exposes_the_same_user_and_registration_fields_as_the_frontend() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    schemas = app.openapi()["components"]["schemas"]
    assert set(schemas["AuthUser"]["properties"]) == {
        "id",
        "username",
        "display_name",
        "role",
        "branch_code",
        "branch_name",
    }
    assert set(schemas["CreateUserRequest"]["properties"]) == {
        "username",
        "display_name",
        "branch_code",
        "password",
        "password_confirmation",
    }


def test_openapi_exposes_the_catalog_contract_from_the_spec() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    schemas = app.openapi()["components"]["schemas"]
    assert set(schemas["ProductResponse"]["properties"]) == {
        "id",
        "carton_code",
        "pack_code",
        "brand",
        "standard_name",
        "carton_retail_price",
        "pack_retail_price",
        "sticks_per_pack",
        "packs_per_carton",
        "sticks_per_carton",
        "is_pack_ambiguous",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert set(schemas["CreateProductRequest"]["properties"]) == {
        "carton_code",
        "pack_code",
        "brand",
        "standard_name",
        "carton_retail_price",
        "sticks_per_pack",
        "packs_per_carton",
        "is_active",
    }


def test_openapi_exposes_the_stage_four_scan_session_contract() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]
    assert set(schemas["CreateScanSessionRequest"]["properties"]) == {
        "business_type",
        "filing_case_no",
        "location",
        "notes",
        "branch_code",
    }
    assert set(schemas["ScanSessionResponse"]["properties"]) == {
        "id",
        "session_no",
        "business_type",
        "business_type_name",
        "filing_case_no",
        "location",
        "notes",
        "branch_code",
        "branch_name",
        "operator_id",
        "operator_name",
        "status",
        "status_name",
        "completed_at",
        "product_count",
        "total_sticks",
        "display_label",
        "created_at",
        "updated_at",
    }
    assert "/api/v1/scan-sessions" in openapi["paths"]
    assert "/api/v1/scan-sessions/{session_id}" in openapi["paths"]


def test_openapi_exposes_the_stage_five_scanning_contract() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]
    assert set(schemas["ScanCodeRequest"]["properties"]) == {"request_id", "code"}
    assert schemas["ScanCodeRequest"]["properties"]["code"] == {
        "type": "string",
        "minLength": 13,
        "maxLength": 13,
        "pattern": "^\\d{13}$",
        "title": "Code",
    }
    assert set(schemas["ResolveAmbiguityRequest"]["properties"]) == {
        "request_id",
        "event_id",
        "product_id",
    }
    assert set(schemas["ProductSnapshotResponse"]["properties"]) == {
        "product_id",
        "carton_code",
        "pack_code",
        "brand",
        "standard_name",
        "carton_retail_price",
        "sticks_per_pack",
        "packs_per_carton",
        "sticks_per_carton",
    }
    assert set(schemas["ScanSessionItemResponse"]["properties"]) == {
        "id",
        "product_id",
        "carton_count",
        "pack_count",
        "manual_delta_sticks",
        "total_sticks",
        "product_snapshot",
        "updated_at",
    }
    assert set(schemas["ScanEventResponse"]["properties"]) == {
        "id",
        "request_id",
        "event_type",
        "result",
        "raw_code",
        "product_id",
        "unit_type",
        "delta_sticks",
        "source_event_id",
        "candidate_snapshot",
        "product_snapshot",
        "operator_id",
        "operator_name",
        "resolved",
        "created_at",
    }
    assert set(schemas["ScanSummaryResponse"]["properties"]) == {
        "product_count",
        "carton_count",
        "pack_count",
        "total_sticks",
        "unknown_count",
        "ambiguous_count",
    }
    assert set(schemas["ScanStateResponse"]["properties"]) == {
        "summary",
        "items",
        "recent_events",
        "pending_ambiguities",
    }
    assert set(schemas["ScanOperationResponse"]["properties"]) == {
        "event",
        "state",
        "idempotent_replay",
    }
    paths = openapi["paths"]
    assert "/api/v1/scan-sessions/{session_id}/scan" in paths
    assert "/api/v1/scan-sessions/{session_id}/resolve" in paths
    assert "/api/v1/scan-sessions/{session_id}/scan-state" in paths
