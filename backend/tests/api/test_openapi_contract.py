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
        "minLength": 6,
        "maxLength": 64,
        "pattern": "^\\d{6,64}$",
        "title": "Code",
    }
    assert set(schemas["ResolveAmbiguityRequest"]["properties"]) == {
        "request_id",
        "event_id",
        "product_id",
    }
    assert set(schemas["AdjustCartonQuantityRequest"]["properties"]) == {
        "request_id",
        "operation",
        "quantity",
        "reason_type",
        "reason_note",
    }
    quantity_schema = schemas["AdjustCartonQuantityRequest"]["properties"]["quantity"]
    assert any(
        option.get("multipleOf") == 0.1
        for option in quantity_schema.get("anyOf", [quantity_schema])
    )
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
        "reason",
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
        "catalog_summary",
        "latest_successful_event",
    }
    assert set(schemas["CatalogSummaryResponse"]["properties"]) == {
        "active_code_count",
        "active_standard_product_count",
    }
    assert set(schemas["ScanOperationResponse"]["properties"]) == {
        "event",
        "state",
        "idempotent_replay",
    }
    assert set(schemas["RemoveScanSessionItemRequest"]["properties"]) == {
        "request_id",
    }
    assert schemas["RemoveScanSessionItemRequest"]["additionalProperties"] is False
    assert set(schemas["ScanEventListPayload"]["properties"]) == {
        "items",
        "total",
        "page",
        "page_size",
    }
    paths = openapi["paths"]
    assert "/api/v1/scan-sessions/{session_id}/scan" in paths
    assert "/api/v1/scan-sessions/{session_id}/resolve" in paths
    assert "/api/v1/scan-sessions/{session_id}/scan-state" in paths
    assert (
        "/api/v1/scan-sessions/{session_id}/items/{product_id}/carton-quantity"
        in paths
    )
    assert "/api/v1/scan-sessions/{session_id}/items/{product_id}/remove" in paths
    assert "/api/v1/scan-sessions/{session_id}/events" in paths


def test_openapi_exposes_the_stage_six_and_seven_finalization_contract() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    openapi = app.openapi()
    paths = openapi["paths"]
    assert "/api/v1/regions" in paths
    assert "/api/v1/scan-sessions/{session_id}/source-allocations" in paths
    assert (
        "/api/v1/scan-sessions/{session_id}/items/{product_id}/source-allocations"
        in paths
    )
    assert "/api/v1/scan-sessions/{session_id}/complete" in paths
    assert "/api/v1/scan-sessions/{session_id}/export.xlsx" in paths

    schemas = openapi["components"]["schemas"]
    assert set(schemas["SourceAllocationInput"]["properties"]) == {
        "source_type",
        "province_name",
        "city_name",
        "pack_count",
    }
    assert set(schemas["ProductSourceAllocationState"]["properties"]) == {
        "product_id",
        "product_snapshot",
        "required_pack_count",
        "allocated_pack_count",
        "remaining_pack_count",
        "allocations",
    }
    assert set(schemas["CompleteScanSessionRequest"]["properties"]) == {
        "confirm_exceptions",
    }


def test_openapi_exposes_completed_result_correction_contract() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    openapi = app.openapi()
    paths = openapi["paths"]
    assert "/api/v1/product-options" in paths
    assert "/api/v1/scan-sessions/{session_id}/result-items" in paths
    assert (
        "/api/v1/scan-sessions/{session_id}/result-items/{product_id}" in paths
    )

    schemas = openapi["components"]["schemas"]
    assert set(schemas["ProductOptionResponse"]["properties"]) == {
        "id",
        "carton_code",
        "brand",
        "standard_name",
        "carton_retail_price",
        "sticks_per_pack",
        "packs_per_carton",
    }
    assert set(schemas["ResultItemCreateRequest"]["properties"]) == {
        "request_id",
        "product_id",
        "quantity_cartons",
        "source_allocations",
    }
    assert set(schemas["ResultItemReplaceRequest"]["properties"]) == {
        "request_id",
        "quantity_cartons",
        "source_allocations",
    }
    assert set(schemas["ResultItemOperationPayload"]["properties"]) == {
        "item",
        "source_state",
        "event",
        "idempotent_replay",
    }


def test_openapi_requires_an_adjustment_reason() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    adjustment = app.openapi()["components"]["schemas"]["AdjustCartonQuantityRequest"]
    assert set(adjustment["properties"]) == {
        "request_id",
        "operation",
        "quantity",
        "reason_type",
        "reason_note",
    }
    assert "reason_type" in adjustment["required"]


def test_openapi_exposes_stage_eight_integration_contract() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    openapi = app.openapi()
    paths = openapi["paths"]
    assert "/api/v1/scan-sessions/{session_id}/integration-snapshot" in paths
    assert "/api/v1/scan-sessions/{session_id}/jiandaoyun-import" in paths
    properties = openapi["components"]["schemas"]["IntegrationSnapshotResponse"][
        "properties"
    ]
    assert set(properties) == {
        "status",
        "external_data_id",
        "attempt_count",
        "last_error_code",
        "last_error_message",
        "created_at",
        "updated_at",
        "succeeded_at",
    }
