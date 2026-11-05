CREATE TABLE IF NOT EXISTS scan_item_source_allocations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_item_id BIGINT UNSIGNED NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    province_name VARCHAR(50) NULL,
    city_name VARCHAR(80) NULL,
    pack_count INT UNSIGNED NOT NULL,
    quantity_sticks INT UNSIGNED NOT NULL,
    source_key VARCHAR(200) NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    updated_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT uq_scan_item_source_allocations_item_key
        UNIQUE (session_item_id, source_key),
    CONSTRAINT ck_scan_item_source_allocations_type
        CHECK (source_type IN (
            'OUTSIDE_PROVINCE', 'UNKNOWN', 'LOCAL_HUAINAN', 'ANHUI_OTHER_CITY'
        )),
    CONSTRAINT ck_scan_item_source_allocations_quantity
        CHECK (pack_count > 0 AND quantity_sticks > 0),
    CONSTRAINT fk_scan_item_source_allocations_item
        FOREIGN KEY (session_item_id) REFERENCES scan_session_items(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_scan_item_source_allocations_created_by
        FOREIGN KEY (created_by) REFERENCES users(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_scan_item_source_allocations_updated_by
        FOREIGN KEY (updated_by) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_scan_item_source_allocations_item (session_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS export_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id BIGINT UNSIGNED NOT NULL,
    filename VARCHAR(180) NOT NULL,
    file_size BIGINT UNSIGNED NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    template_version VARCHAR(20) NOT NULL,
    generated_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_export_records_session
        FOREIGN KEY (session_id) REFERENCES scan_sessions(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_export_records_generated_by
        FOREIGN KEY (generated_by) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_export_records_session_created (session_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
